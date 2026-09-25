# t20-exact-forecast

A Harbor task in which an AI agent forecasts match win probabilities for a simulated Twenty20 cricket league and is graded against the exact truth.

Status: complete and frozen. Task, verifier, oracle, gates, linter, eighteen model jobs and the documents, as of 25 September 2026. No changes to the task after the first pilot.

![The whole system: calibration from real data, the synthetic world, task build and packaging, the Harbor runtime, and the evidence](figures/system_overview.png)

## What it is

The agent gets three seasons of ball-by-ball history from a made-up league, the engine that plays the matches, and next season's fixtures with their line-ups. It must write a program that says how likely the home side is to win each fixture. Because the league is generated, the true probability of every fixture is known, so a forecast is graded on how far it is from the truth, not on whether one match happened to go one way. The league was calibrated to 295,557 real IPL deliveries so it behaves like cricket, but every player, team and ground is invented, so nothing the agent knows about real cricket helps it.

The hard part is not writing the code. It is deciding how much of a player's short history to believe, and building a check that could tell you if you have got that wrong. The pass mark was fixed and committed before any model tried the task.

## Results

| Model, native harness, high reasoning effort | Completed runs | Passed | Total regret, times the reference |
|---|---:|---:|---|
| Claude Opus 4.7 (Claude Code) | 5 | 0 | 1.36 to 1.70 |
| GPT-5.5 (Codex) | 5 | 0 | 1.11 to 1.58 |
| Claude Fable 5.1 (Claude Code) | 3 | 2 | 1.008 and 1.027; the miss at 1.104 passed on the seven held-out worlds |
| GPT-6-astra (Codex) | 2 | 2 | 1.054 and 1.072 |

The pass bar is 1.10 times a reference forecaster built from ordinary statistics. The pair the brief's goal line names failed ten times out of ten, all for the same reason: they took players' short histories at face value and had no check that could see it; changing that one number in each program moved it most of the way to the reference. The next generation passed four of five completed runs by doing exactly what the failures skipped. So the bar sits between the two generations. Three further runs were cut short for account or operator reasons and are recorded as excluded, not as failures. Every number in this table is in a job folder under `jobs/`; the ids are in RUN_REPORT.md, and every claim in DESIGN_DOCUMENT.md carries a pointer to its evidence.

## Where to read

| File | What it is |
|---|---|
| [DESIGN_DOCUMENT.md](DESIGN_DOCUMENT.md) | The design in plain English: what the task measures, why cricket, why a simulated league, how it is built, how it is graded, how cheating is prevented, what the models did, and what it all means. Start here. |
| [DECISIONS.md](DECISIONS.md) | Twenty-four decisions that could have gone another way, each with the alternative, the cost and whether it stands. |
| [RUN_REPORT.md](RUN_REPORT.md) | Environment, the rule, every run with its job identity, the exclusions, the ablations, and the commands to repeat it all. |
| [PROVENANCE.md](PROVENANCE.md) | What is new, what is borrowed, the data licence, and the use of AI assistance. |
| [NOTES.md](NOTES.md) | Notes on every file in the pipeline: what it does, how it works, what it was checked against, and what the checks caught. The full-length working notes are in `docs/NOTES_FULL.md`. |
| `docs/DESIGN.pdf` | The extended version of the design document, with derivations and all seven drawings. |
| `figures/` | The drawings used in the documents. |
| `jobs/` | Every Harbor job: the two gates, the linter, the sixteen graded model jobs with rewards, per-world details, agent logs and submitted programs, and the two jobs I stopped, with their agent logs. |

## Layout

    dev/            calibration from the archive, validation, the ladder, the bar analysis, the task-data build, the ablations
    league/         the constants, the engine, the world generator and truth engine, the public file reader and writer
    forecasters/    the reference ladder: coin flip, team ratings, unshrunk, last season only, head-to-head, reference
    scoring/        the exact scorer
    task_data/      the eight worlds: public league folders, and the private truth, reference numbers and ladder forecasts
    task_src/       what the agent sees: the handbook template and the starter program
    harbor/         task.toml, bar.json, the two Dockerfiles, the verifier, the oracle
    package_task.py assembles dist/collinear-siddharthshashankkumar/t20-exact-forecast/, the one directory Harbor runs
    dist/           the packaged task

## Running it

    make venv
    make data                      # eight worlds and their truths, about 25 minutes
    make package
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle     # expect 1.000
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop        # expect 0.000
    harbor check dist/collinear-siddharthshashankkumar/t20-exact-forecast              # 22 of 22
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high

Rebuilding the calibration itself needs the Cricsheet IPL archive under `data/raw/ipl/`, which is not tracked. Everything else rebuilds from a fresh clone.

## Provenance

Calibration constants derived from data sourced from Cricsheet (cricsheet.org), maintained by Stephen Rushe, under the Open Data Commons Attribution License 1.0. Aggregates only; no Cricsheet row is shipped. Task, verifier, documents and records by Siddharth Shashank Kumar, September 2026, built with AI assistance as described in PROVENANCE.md.
