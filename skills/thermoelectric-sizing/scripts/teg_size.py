#!/usr/bin/env python3
"""Size a thermoelectric generator (TEG) or Peltier cooler (TEC) build with tegkit.

Generator mode accounts for the heat exchangers the modules share: adding
modules lowers the temperature difference each one sees, so the script
iterates until the array size and the module temperature difference agree.

Examples
--------
    # How many TG12-4 modules for 20 W at 12 V between 150 C coolant and 30 C water?
    python teg_size.py generate --preset TG12-4 --t-hot 150 --t-cold 30 \
        --r-hot 0.05 --r-cold 0.08 --power 20 --voltage 12

    # Peltier: pump 30 W out of a box held at 5 C, hot side at 35 C
    python teg_size.py cool --preset TEC1-12706 --t-hot 35 --t-cold 5 --heat-load 30

Temperatures are in degrees C. Thermal resistances are in K/W for the whole
heat exchanger (all modules together), including interface material.
Add --json for machine-readable output.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

try:
    import tegkit
    from tegkit import TEGArray, TEGModule, c_to_k, presets
    from tegkit import peltier
except ImportError:  # pragma: no cover
    sys.exit("tegkit is not installed. Run: pip install tegkit")


# --------------------------------------------------------------------------- #
# Building the module
# --------------------------------------------------------------------------- #
def build_module(a: argparse.Namespace) -> TEGModule:
    if a.preset:
        try:
            return presets.get(a.preset)
        except KeyError:
            sys.exit(f"Unknown preset {a.preset!r}. Available: {', '.join(presets.names())}")
    if a.tec:
        i_max, v_max, dt_max, th_c = a.tec
        return TEGModule.from_tec_datasheet(i_max, v_max, dt_max, c_to_k(th_c), name="custom TEC")
    if a.datasheet:
        p, v, dt, k = a.datasheet
        return TEGModule.from_datasheet(p, v, dt, k, name="custom TEG")
    if a.params:
        s, r, k = a.params
        return TEGModule(s, r, k, name="custom")
    sys.exit("Describe the module with --preset, --tec, --datasheet or --params.")


def rated_current(a: argparse.Namespace) -> float | None:
    """Datasheet Imax (A) when known; the model alone can overshoot it."""
    if a.tec:
        return a.tec[0]
    if a.preset:
        return presets.info(a.preset).datasheet.get("Imax_A")
    return None


def module_info(m: TEGModule) -> dict:
    return {
        "name": m.name or "custom",
        "seebeck_V_per_K": m.seebeck,
        "resistance_ohm": m.resistance,
        "thermal_conductance_W_per_K": m.thermal_conductance,
        "Z_per_K": m.figure_of_merit(),
    }


# --------------------------------------------------------------------------- #
# Generator sizing
# --------------------------------------------------------------------------- #
def module_dt(m: TEGModule, n: int, source_dt: float, r_hot: float, r_cold: float) -> float:
    """Temperature difference across each module when n modules share the
    same hot and cold exchangers (thermally in parallel)."""
    r_stack = 1.0 / (n * m.thermal_conductance)
    return source_dt * r_stack / (r_stack + r_hot + r_cold)


def generate(a: argparse.Namespace) -> dict:
    m = build_module(a)
    th, tc = c_to_k(a.t_hot), c_to_k(a.t_cold)
    source_dt = th - tc
    if source_dt <= 0:
        sys.exit("--t-hot must be above --t-cold")

    r_ext = a.r_hot + a.r_cold
    # Thermal matching: total power N * P(dT(N)) peaks when the module stack's
    # thermal resistance equals the external resistance.
    n_best = None
    if r_ext > 0:
        n_best = max(1, round(1.0 / (m.thermal_conductance * r_ext)))

    def total_power(n: int) -> float:
        return n * m.max_power(module_dt(m, n, source_dt, a.r_hot, a.r_cold))

    p_ceiling = total_power(n_best) if n_best else math.inf

    # Iterate: array size depends on dT, dT depends on array size.
    n, arr, dt = 1, None, source_dt
    for _ in range(200):
        dt = module_dt(m, n, source_dt, a.r_hot, a.r_cold)
        arr = tegkit.suggest_array(m, dt, a.power, a.voltage or m.open_circuit_voltage(dt) / 2)
        if arr.count == n:
            break
        if n_best and arr.count > n_best and total_power(arr.count) < a.power:
            arr = None
            break
        n = arr.count
    else:
        arr = None

    out = {
        "mode": "generate",
        "module": module_info(m),
        "inputs": {
            "t_hot_C": a.t_hot, "t_cold_C": a.t_cold, "source_dT_K": source_dt,
            "r_hot_K_per_W": a.r_hot, "r_cold_K_per_W": a.r_cold,
            "target_power_W": a.power, "target_voltage_V": a.voltage,
        },
        "single_module_no_heat_sinks": {
            "max_power_W": m.max_power(source_dt),
            "max_efficiency": m.max_efficiency(th, tc),
            "zt": m.zt(th, tc),
        },
        "thermal_matching": {
            "best_module_count": n_best,
            "power_ceiling_W": None if math.isinf(p_ceiling) else p_ceiling,
        },
    }

    if arr is None:
        out["result"] = None
        out["verdict"] = (
            "Target not reachable with these heat exchangers. Adding modules stops helping "
            f"around {n_best} modules (about {p_ceiling:.1f} W). Improve the heat exchangers "
            "(lower --r-hot/--r-cold), raise the temperature difference, or pick a module "
            "with a higher figure of merit Z."
        )
        return out

    eq = arr.as_module()
    t_face_hot = th - dt * a.r_hot / (1.0 / (arr.count * m.thermal_conductance))
    t_face_cold = t_face_hot - dt
    out["result"] = {
        "series": arr.series,
        "parallel": arr.parallel,
        "modules": arr.count,
        "module_dT_K": dt,
        "share_of_source_dT": dt / source_dt,
        "open_circuit_voltage_V": arr.open_circuit_voltage(dt),
        "matched_load_ohm": arr.matched_load(),
        "matched_voltage_V": arr.open_circuit_voltage(dt) / 2,
        "max_power_W": arr.max_power(dt),
        "heat_through_modules_W": eq.thermal_conductance * dt,
        "efficiency_at_matched_load": eq.efficiency(t_face_hot, t_face_cold, eq.resistance),
        "best_efficiency_load_ohm": eq.optimal_efficiency_load(t_face_hot, t_face_cold),
    }
    out["verdict"] = "OK"
    if dt / source_dt < 0.5:
        out["warning"] = (
            "Less than half the available temperature difference reaches the modules. "
            "The heat exchangers, not the modules, are limiting this design."
        )
    return out


# --------------------------------------------------------------------------- #
# Peltier sizing
# --------------------------------------------------------------------------- #
def cool(a: argparse.Namespace) -> dict:
    m = build_module(a)
    th, tc = c_to_k(a.t_hot), c_to_k(a.t_cold)
    if tc >= th:
        sys.exit("For cooling, --t-cold must be below --t-hot (face temperatures).")
    dt_max = peltier.max_delta_t_at_hot(m, th)
    out = {
        "mode": "cool",
        "module": module_info(m),
        "inputs": {"t_hot_C": a.t_hot, "t_cold_C": a.t_cold, "heat_load_W": a.heat_load},
        "max_dT_at_this_hot_side_K": dt_max,
    }
    if th - tc >= dt_max:
        out["result"] = None
        out["verdict"] = (
            f"Impossible: this module can hold at most {dt_max:.1f} K across itself with the "
            "hot side at this temperature. Use a better hot-side heat sink or stage modules."
        )
        return out

    i_cop = peltier.optimal_cop_current(m, th, tc)
    q_cop = peltier.cooling_power(m, i_cop, th, tc)
    i_max = peltier.max_cooling_current(m, tc)
    rated = rated_current(a)
    capped = rated is not None and i_max > rated
    if capped:
        i_max = rated
    q_max = peltier.cooling_power(m, i_max, th, tc)
    if rated is not None and i_cop > rated:
        i_cop = rated
        q_cop = peltier.cooling_power(m, i_cop, th, tc)

    def plan(current: float, q_each: float) -> dict | None:
        if q_each <= 0:
            return None
        n = math.ceil(a.heat_load / q_each - 1e-12)
        p_in = n * peltier.input_power(m, current, th, tc)
        return {
            "modules": n,
            "current_per_module_A": current,
            "cooling_per_module_W": q_each,
            "total_input_power_W": p_in,
            "heat_to_reject_on_hot_side_W": a.heat_load + p_in,
            "cop": a.heat_load / p_in if p_in > 0 else None,
        }

    out["result"] = {
        "efficient (best COP)": plan(i_cop, q_cop),
        "compact (max cooling)": plan(i_max, q_max),
    }
    out["verdict"] = "OK"
    if capped:
        out["current_limit"] = (
            f"Max-cooling current capped at the datasheet Imax of {rated:g} A "
            "(the model alone would ask for more)."
        )
    out["note"] = (
        "The hot-side heat sink must reject heat_to_reject_on_hot_side_W while staying at "
        "t_hot. If it can't, the hot side warms up and the plan no longer holds."
    )
    return out


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    return v


def print_report(d: dict, indent: int = 0) -> None:
    pad = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{pad}{k}:")
            print_report(v, indent + 1)
        elif v is not None:
            print(f"{pad}{k}: {_fmt(v)}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)

    def module_args(sp):
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--preset", help=f"one of: {', '.join(presets.names())}")
        g.add_argument("--tec", nargs=4, type=float, metavar=("IMAX", "VMAX", "DTMAX", "TH_C"),
                       help="Peltier datasheet: Imax A, Vmax V, dTmax K, hot side C")
        g.add_argument("--datasheet", nargs=4, type=float, metavar=("P", "V", "DT", "K"),
                       help="TEG datasheet matched-load point: power W, voltage V, dT K, conductance W/K")
        g.add_argument("--params", nargs=3, type=float, metavar=("S", "R", "K"),
                       help="Seebeck V/K, resistance ohm, thermal conductance W/K")
        sp.add_argument("--t-hot", type=float, required=True, help="hot side, C")
        sp.add_argument("--t-cold", type=float, required=True, help="cold side, C")
        sp.add_argument("--json", action="store_true", help="print JSON")

    g = sub.add_parser("generate", help="size a generator")
    module_args(g)
    g.add_argument("--r-hot", type=float, default=0.0, help="hot exchanger + interface, K/W (whole array)")
    g.add_argument("--r-cold", type=float, default=0.0, help="cold exchanger + interface, K/W (whole array)")
    g.add_argument("--power", type=float, required=True, help="target electrical power, W")
    g.add_argument("--voltage", type=float, default=0.0, help="target matched-load voltage, V")

    c = sub.add_parser("cool", help="size a Peltier cooler")
    module_args(c)
    c.add_argument("--heat-load", type=float, required=True, help="heat to pump from the cold side, W")

    a = p.parse_args(argv)
    try:
        result = generate(a) if a.mode == "generate" else cool(a)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
