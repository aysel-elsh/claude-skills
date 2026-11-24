---
name: thermoelectric-sizing
description: Size thermoelectric generators (TEGs) and Peltier coolers (TECs) from real datasheets - how many modules, series/parallel layout, power, voltage, efficiency, COP and heat-sink requirements. Use when someone asks how much power a TEG or Peltier module will give, how many modules they need, whether a waste-heat or Peltier cooling idea is feasible, or what heat sink a thermoelectric build needs.
---

# Thermoelectric sizing

Answers "how many modules, wired how, and will it actually work?" for thermoelectric
generators and Peltier coolers, using the open-source `tegkit` library and the bundled
`scripts/teg_size.py`.

The most common mistake in thermoelectric projects is assuming the modules see the full
temperature difference. They don't: the heat exchangers on both sides eat part of it, and
every module added to the same heat sink makes it worse. Always account for this.

## Setup

```bash
pip install tegkit
```

## Workflow

### 1. Get the inputs

Ask only for what's missing. Make reasonable assumptions for the rest and state them.

| Input | Notes |
|---|---|
| Mode | Generating power (TEG) or cooling (Peltier/TEC)? |
| Module | A preset name, or datasheet numbers (see below). If unknown, suggest a preset. |
| Hot and cold temperatures (°C) | Generator: the heat source and the coolant/ambient. Cooler: the hot face and the cold face to hold. |
| Heat exchangers (K/W) | Generator only. Total thermal resistance of the hot-side and cold-side exchangers, including thermal paste, for the whole array. If unknown, use the ranges in `references/physics.md` and say so. |
| Target | Generator: power (W), and voltage (V) if a converter or battery needs one. Cooler: heat load to pump (W). |

**Module options** (`--preset`, `--tec`, `--datasheet`, `--params`):
- Presets built from public datasheets: `TEC1-12706`, `TEC-40-36-127`, `TEC-30-36-71`
  (Peltier coolers), `TG12-4`, `TEG2-126LDT` (generators).
- Any Peltier datasheet: `--tec IMAX VMAX DTMAX TH_C`.
- A TEG datasheet's matched-load point: `--datasheet POWER_W VOLTAGE_V DT_K CONDUCTANCE_W_PER_K`.
- Raw parameters: `--params SEEBECK_V_PER_K RESISTANCE_OHM CONDUCTANCE_W_PER_K`.

Cheap "TEC1-127xx" Peltier modules are often used as generators. That works, but they're
built for cooling, so expect less power than a purpose-made TEG module.

### 2. Run the sizing script

```bash
# Generator
python scripts/teg_size.py generate --preset TG12-4 --t-hot 150 --t-cold 30 \
    --r-hot 0.05 --r-cold 0.08 --power 20 --voltage 12

# Peltier cooler
python scripts/teg_size.py cool --preset TEC1-12706 --t-hot 35 --t-cold 5 --heat-load 30
```

Add `--json` to get structured output when you need to compute further.

For anything the script doesn't cover (I-V curves, a fixed load resistance, custom arrays),
use tegkit directly. See `references/physics.md` for the API and equations.

### 3. Read the result

**Generator mode**
- `verdict` not OK: the target can't be reached with those heat exchangers. Adding modules
  stops helping at `thermal_matching.best_module_count`, and `power_ceiling_W` is the most
  this setup can ever produce. Say this clearly. It's the most useful thing you can tell them.
- `share_of_source_dT` below 0.5: the heat exchangers are the bottleneck, not the modules.
  Better heat sinks will help more than more modules.
- `matched_load_ohm`: the load for maximum power. `best_efficiency_load_ohm` is slightly
  higher and gives a bit less power but better efficiency.
- `heat_through_modules_W`: the heat the hot side must supply. Efficiency is a few percent
  at best, so almost all of it has to leave through the cold side.

**Cooler mode**
- Two plans are given: `efficient (best COP)` uses more modules at a lower current;
  `compact (max cooling)` uses fewer modules at full current and far more input power.
  Recommend the efficient plan unless space or cost rules it out.
- `heat_to_reject_on_hot_side_W` is the heat load plus all the electrical input. The hot-side
  heat sink must handle it while staying at `t_hot`. This is where most Peltier builds fail.
- `Impossible` means the temperature difference exceeds what the module can hold. The
  options are a better hot-side heat sink, a lower target, or stacked (cascaded) modules.

### 4. Answer

Lead with the answer: module count, layout (for example "4 in series × 4 in parallel"),
expected power or cooling, and the main limitation. Then list the assumptions you made, and
the caveats below. Keep the numbers to 2–3 significant figures. The model doesn't support more.

## Caveats to state

- This is the standard constant-property model (properties don't change with temperature).
  It's good for sizing and feasibility, not for final design. Expect real results within
  roughly ±20%, usually on the low side.
- For Peltier presets, the model overestimates maximum cooling by about 15–20% and
  underestimates resistance by about 10% compared with datasheets. Leave margin.
- Heat-exchanger resistance is usually the biggest uncertainty. If it was assumed, say so,
  and suggest measuring it or taking it from the heat-sink datasheet.
- A generator's output depends on the load. A DC-DC converter with maximum power point
  tracking (MPPT) keeps it near the matched load.
- Never exceed the module's rated maximum hot-side temperature from its datasheet. Standard
  Peltier modules are usually rated much lower than purpose-built TEG modules.

## Example

User: "Could thermoelectric modules on my wood stove (about 180 °C on top) charge a phone at
5 W? I'd put a fan-cooled heat sink on the cold side."

1. Pick a generator module (`--preset TG12-4`). Assume a flat aluminium hot plate
   (`--r-hot 0.05`) and a fan-cooled heat sink (`--r-cold 0.15`), and say these are assumptions.
2. Run `generate` with `--t-hot 180 --t-cold 30 --power 5 --voltage 6`. Use 6 V so a 5 V USB
   regulator has headroom.
3. The result is 6 modules, 3 in series × 2 in parallel, about 7 W at matched load. Only
   about 65% of the 150 K difference reaches the modules, and the setup tops out near 8 W
   however many modules are added. So: yes, with margin, and a bigger heat sink is the
   upgrade that matters most.
