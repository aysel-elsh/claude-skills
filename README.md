# claude-skills

Engineering skills for Claude, built on the open [Agent Skills](https://agentskills.io) format.

| Skill | What it does |
|---|---|
| [thermoelectric-sizing](skills/thermoelectric-sizing) | Sizes thermoelectric generators (TEGs) and Peltier coolers from real datasheets: how many modules, series/parallel layout, power, efficiency, COP, and whether your heat sinks are the real limit. |

## thermoelectric-sizing

Ask Claude things like:

- "Could TEG modules on my wood stove charge a phone?"
- "How many TEC1-12706 Peltiers do I need to pull 30 W out of a cooler box?"
- "I have 150 °C exhaust and 30 °C water. What's the most power I can get, and what's limiting it?"

Claude gathers the temperatures, module and heat-sink details, runs
[`scripts/teg_size.py`](skills/thermoelectric-sizing/scripts/teg_size.py), and explains the result.

What makes it different from a back-of-envelope calculation: it accounts for the heat
exchangers the modules share. Each module added to the same heat sink lowers the
temperature difference every module sees, so there's a ceiling on power that more modules
can't break. The skill finds that ceiling and tells you when better heat sinks will help
more than more modules.

It uses [tegkit](https://github.com/aysel-elsh/tegkit) (`pip install tegkit`), a small
open-source Python library with presets built from public manufacturer datasheets.

You can also run the script on its own:

```bash
pip install tegkit
python skills/thermoelectric-sizing/scripts/teg_size.py generate --preset TG12-4 \
    --t-hot 180 --t-cold 30 --r-hot 0.05 --r-cold 0.15 --power 5 --voltage 6
```

## Install

**Claude Code**

```
/plugin marketplace add aysel-elsh/claude-skills
/plugin install thermoelectric-sizing@aysel-elsh-skills
```

**Claude.ai**: zip the [`skills/thermoelectric-sizing`](skills/thermoelectric-sizing) folder
and upload it as a custom skill. See
[Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude).
Code execution needs to be on so Claude can run the script.

**Claude API**: upload the folder as a custom skill. See the
[Skills API quickstart](https://docs.claude.com/en/api/skills-guide#creating-a-skill).

## Limits

The underlying model is the standard constant-property thermoelectric model. It's meant for
sizing and feasibility checks, not final design. Expect real results within roughly ±20%,
and check module temperature ratings on the datasheet.

## Tests

```bash
pip install tegkit pytest
pytest
```

## License

MIT. Made by [Aysel Elshenawy](https://aysel-elshenawy.vercel.app), EE student at FAU.
Developed with AI assistance (Claude).
