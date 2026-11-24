"""Checks the sizing script against hand-calculated values."""

import importlib.util
import json
import math
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/thermoelectric-sizing/scripts/teg_size.py"
spec = importlib.util.spec_from_file_location("teg_size", SCRIPT)
teg_size = importlib.util.module_from_spec(spec)
spec.loader.exec_module(teg_size)


def run(capsys, *args):
    assert teg_size.main([*args, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def test_no_heat_sinks_matches_hand_calc(capsys):
    # TG12-4: S = 0.0525 V/K, R = 5.526 ohm. Per module at 120 K: (0.0525*120)^2 / (4*5.526) = 1.80 W
    out = run(capsys, "generate", "--preset", "TG12-4", "--t-hot", "150", "--t-cold", "30", "--power", "5")
    r = out["result"]
    assert r["modules"] == 3
    assert r["module_dT_K"] == pytest.approx(120)
    assert r["max_power_W"] == pytest.approx(3 * 0.0525**2 * 120**2 / (4 * 5.526), rel=1e-3)


def test_power_ceiling_formula(capsys):
    # P_ceiling = Z * dT^2 / (16 * R_ext)
    out = run(capsys, "generate", "--preset", "TG12-4", "--t-hot", "150", "--t-cold", "30",
              "--r-hot", "0.05", "--r-cold", "0.08", "--power", "20", "--voltage", "12")
    assert out["result"] is None
    z = out["module"]["Z_per_K"]
    expected = z * 120**2 / (16 * 0.13)
    assert out["thermal_matching"]["power_ceiling_W"] == pytest.approx(expected, rel=0.05)


def test_layout_meets_targets(capsys):
    out = run(capsys, "generate", "--preset", "TG12-4", "--t-hot", "180", "--t-cold", "30",
              "--r-hot", "0.05", "--r-cold", "0.15", "--power", "5", "--voltage", "6")
    r = out["result"]
    assert r["max_power_W"] >= 5
    assert r["matched_voltage_V"] >= 6
    assert r["modules"] == r["series"] * r["parallel"]
    # dT is consistent with the module count on shared exchangers
    k = out["module"]["thermal_conductance_W_per_K"]
    r_stack = 1 / (r["modules"] * k)
    assert r["module_dT_K"] == pytest.approx(150 * r_stack / (r_stack + 0.2))


def test_peltier_respects_rated_current(capsys):
    out = run(capsys, "cool", "--preset", "TEC1-12706", "--t-hot", "35", "--t-cold", "5", "--heat-load", "30")
    for plan in out["result"].values():
        assert plan["current_per_module_A"] <= 6.4 + 1e-9
        assert plan["modules"] * plan["cooling_per_module_W"] >= 30
        assert plan["heat_to_reject_on_hot_side_W"] == pytest.approx(30 + plan["total_input_power_W"])


def test_peltier_impossible_delta_t(capsys):
    out = run(capsys, "cool", "--preset", "TEC1-12706", "--t-hot", "35", "--t-cold", "-60", "--heat-load", "30")
    assert out["result"] is None
    assert out["verdict"].startswith("Impossible")


def test_custom_tec_matches_preset(capsys):
    a = run(capsys, "cool", "--preset", "TEC1-12706", "--t-hot", "35", "--t-cold", "10", "--heat-load", "20")
    b = run(capsys, "cool", "--tec", "6.4", "14.4", "66", "25", "--t-hot", "35", "--t-cold", "10", "--heat-load", "20")
    assert math.isclose(a["module"]["seebeck_V_per_K"], b["module"]["seebeck_V_per_K"], rel_tol=1e-9)
