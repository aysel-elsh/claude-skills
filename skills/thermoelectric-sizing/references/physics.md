# Thermoelectric physics and tegkit reference

Read this when the sizing script doesn't cover the question, or to explain a result.

## Model

Constant-property, lumped model. One module is described by three numbers:

| Symbol | Meaning | Unit |
|---|---|---|
| S | Seebeck coefficient of the whole module | V/K |
| R | Internal electrical resistance | Ω |
| K | Thermal conductance | W/K |

Figure of merit: Z = S² / (R·K), and ZT uses the mean temperature T = (Th + Tc)/2 in kelvin.
Commercial Bi2Te3 modules have ZT of roughly 0.4–1 in this whole-module sense.

## Generator (TEG)

With temperature difference ΔT across the module faces and load resistance RL:

- Open-circuit voltage: Voc = S·ΔT
- Current: I = Voc / (R + RL)
- Power: P = I²·RL. The maximum is Voc² / (4R), at RL = R (matched load), where the load
  voltage is Voc/2.
- Hot-side heat: Qh = S·I·Th + K·ΔT − I²R/2
- Best possible efficiency:
  ηmax = (ΔT/Th) · (√(1+ZT) − 1) / (√(1+ZT) + Tc/Th), at RL = R·√(1+ZT)

### Heat exchangers and the power ceiling

The modules sit in series with the hot-side and cold-side thermal resistances
(Rhot, Rcold in K/W, including interface material). For N identical modules sharing the
same exchangers:

    ΔT_module = ΔT_source · (1/(N·K)) / (1/(N·K) + Rhot + Rcold)

Total power N·Voc²/(4R) peaks at **thermal matching**, when the stack's thermal resistance
equals the external one: N·K = 1/(Rhot + Rcold). There, half the source ΔT reaches the
modules and

    P_ceiling = Z · ΔT_source² / (16 · (Rhot + Rcold))

So past a point, only better heat exchangers, a bigger ΔT or a higher-Z module raise power.

This estimate ignores Peltier and Joule heat inside the modules (the open-circuit
approximation). Under load the real ΔT is a few percent lower.

### Series and parallel

N_s in series × N_p strings: Voc and resistance scale with N_s, resistance divides by N_p,
and matched power scales with N_s·N_p. Modules in series set the voltage. Parallel strings
add power without raising voltage.

## Cooler (Peltier / TEC)

With current I, hot face Th and cold face Tc:

- Heat pumped from the cold side: Qc = S·I·Tc − I²R/2 − K·ΔT
- Electrical input: P = S·I·ΔT + I²R
- COP = Qc / P
- Current for maximum cooling: I = S·Tc / R. Never exceed the datasheet Imax.
- Maximum ΔT (at Qc = 0, hot side fixed): solve Z·Tc²/2 = Th − Tc for Tc
- Heat the hot-side sink must reject: Qh = Qc + P

Converting a Peltier datasheet (Imax, Vmax, ΔTmax at hot side Th):

    S = Vmax / Th
    R = (Vmax / Imax) · (Th − ΔTmax) / Th
    K = Imax · Vmax · (Th − ΔTmax) / (2 · Th · ΔTmax)

Known bias: this reproduces ΔTmax exactly, but gives Qmax about 15–20% high and R about 10%
low, because it ignores contact resistance and Thomson heat.

## Rough heat-exchanger values

Starting points only. Use the heat-sink datasheet, or a measurement, when you can. Values are
for the whole exchanger, including thermal paste.

| Exchanger | Thermal resistance |
|---|---|
| Liquid cold plate / water block | ~0.02–0.1 K/W |
| Large finned heat sink with a fan | ~0.1–0.5 K/W |
| Finned heat sink, natural convection | ~0.5–3 K/W |
| Thermal paste layer, one 40 mm module | ~0.02–0.1 K/W |

## tegkit API

```python
from tegkit import TEGModule, TEGArray, c_to_k, presets, peltier
from tegkit import iv_curve, max_power_point, suggest_array, modules_for_power
from tegkit import required_cold_side_resistance

m = presets.get("TG12-4")                       # or TEGModule(S, R, K)
m = TEGModule.from_tec_datasheet(6.4, 14.4, 66, c_to_k(25))
m = TEGModule.from_datasheet(matched_power, matched_voltage, delta_t, thermal_conductance)
m = TEGModule.from_measurements(voc, isc, delta_t, thermal_conductance)

m.max_power(dt); m.power(dt, r_load); m.open_circuit_voltage(dt)
m.max_efficiency(th_k, tc_k); m.optimal_efficiency_load(th_k, tc_k); m.zt(th_k, tc_k)
m.module_delta_t(source_dt, hot_side_resistance, cold_side_resistance)   # single module

arr = TEGArray(m, series=4, parallel=2); arr.max_power(dt); arr.matched_load()
iv_curve(arr, dt, points=21); max_power_point(arr, dt)
required_cold_side_resistance(m, source_dt, target_module_dt, hot_side_resistance)

peltier.cooling_power(m, i, th_k, tc_k); peltier.cop(m, i, th_k, tc_k)
peltier.optimal_cop_current(m, th_k, tc_k); peltier.max_delta_t_at_hot(m, th_k)
presets.names(); presets.info("TG12-4").source
```

Temperatures in tegkit functions are in kelvin. Use `c_to_k()`.
Source and issues: https://github.com/aysel-elsh/tegkit
