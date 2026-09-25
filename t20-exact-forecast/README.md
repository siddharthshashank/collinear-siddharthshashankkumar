# t20-exact-forecast

A Harbor task in which an AI agent forecasts match win probabilities for a simulated Twenty20 cricket league and is graded against the exact truth. The agent receives three seasons of ball-by-ball history, the match engine with its hidden values stripped out, and next season's fixtures with their line-ups. It must deliver a program that outputs the home side's win probability for every fixture. Because the league is generated, the true probability of every fixture is known, and a forecast is scored by its expected log loss against that truth. No match result enters the grade, so a forecast cannot be lucky or unlucky, only close or far.

The simulator is calibrated to 295,557 real deliveries from the Cricsheet IPL archive and contains only effects that repeat in independent halves of that archive. Every player, team and venue is invented, and only aggregate constants ship. The pass rule, regret summed over eight worlds at most 1.10 times a reference forecaster built from ordinary regularised statistics, was chosen on worlds that are never graded and committed before any model ran.

## Results

| Model, native harness, high reasoning effort | Runs | Passed | Total regret, times the reference |
|---|---|---|---|
| Claude Opus 4.7 (Claude Code) | 5 | 0 | 1.36 to 1.70 |
| GPT-5.5 (Codex) | 5 | 0 | 1.11 to 1.58 |
| Claude Fable 5.1 (Claude Code) | 1 so far | 1 | 1.027 |
| GPT-6-astra (Codex) | first run cut short by an account usage limit; reruns in progress | | |

Every run produced a valid, deterministic forecast inside its constraints, so every verdict is about forecast quality. Reading the ten failed programs found the same cause in each: prior scales set three to forty-four times too weak, with no check that could see it. Changing that one constant moved each program most of the way to the reference, and made the near miss beat it (`ablations.log`). The passing Fable program learned its prior scales from the data by marginal likelihood and validated on synthetic leagues it built with the shipped engine, checked against the handbook's own yardstick. The oracle, the reference forecaster installed as a solution, passes at exactly 1.000 times its stored regret; the do-nothing starter scores 0. Harbor's task linter passes 22 of 22 checks.

## Where to read

| File | What it is |
|---|---|
| `docs/DESIGN.pdf` | The design document, as a paper: the idea, the alternatives, the pipeline part by part, the pass rule and its derivation, the pilots, the ablations, decisions, assumptions, trade-offs, validation, limitations. |
| `RUN_REPORT.md` | Environment, versions, commands, gate results, every pilot with its job id, the ablations. |
| `DECISIONS.md` | Twenty-eight decisions, each with context, options, choice, consequences and status. |
| `NOTES.md` | A study of every file in the pipeline, written while retyping it from scratch and checking each against known numbers. |
| `docs/ARCHITECTURE.md` | Mermaid diagrams of the system and of grading one submission. |
| `figures/` | The seven drawings used in the design document; `figures/src/pilot_results.py` redraws the pilot figure from the job records. |
| `jobs/` | Harbor job records: two gates, the linter, every pilot. Agent session directories are excluded. |

## Layout

    dev/            calibration from the archive (parse, explore, fit, build), validation, the ladder, the bar analysis, the task-data build, the ablations
    league/         the constants, the engine, the world generator and truth engine, the public file reader and writer
    forecasters/    the reference ladder: coin flip, team ratings, unshrunk, last season only, head-to-head, reference
    scoring/        the exact scorer
    task_data/      the eight worlds: public league folders, and the private truth, reference numbers and tier forecasts
    task_src/       what the agent sees: the handbook template and the starter program
    harbor/         task.toml, bar.json, the two Dockerfiles, the verifier, the oracle
    package_task.py assembles dist/collinear-siddharthshashankkumar/t20-exact-forecast/, the one directory Harbor runs
    dist/           the packaged task

## Reproducing

    make venv                      # .venv with numpy 2.4.4, pandas 3.0.2, scipy 1.17.1
    make data                      # eight worlds, truth at 100,000 copies per batting order, reference regret, careless tiers (about 25 minutes)
    make package                   # the Harbor task directory
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle     # expect 1.000 on every key
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop        # expect 0.000 overall, 1.000 artifact and constraints
    harbor check dist/collinear-siddharthshashankkumar/t20-exact-forecast
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high

Rebuilding the calibration itself needs the Cricsheet IPL archive under `data/raw/ipl/`, which is not tracked; `dev/parse_archive.py` through `dev/build_calibration.py` regenerate `league/calibration.json` from it. The world generator is deterministic given the constants, and the packaged task rebuilds byte for byte from a fresh clone.

The design document builds from `docs/design_source/content.py` in two forms: `build_doc.py` for the ReportLab version, `build_tex.py` then `latexmk -pdf` for the paper. Both read the drawings from `figures/`.

## The task, from the agent's side

The agent's container holds the visible league, the engine as code with public constants, the handbook and a starter that says 0.5 everywhere. The handbook states the scoring formula, the clip, the tolerance, the eight-world rule, the time limit, the determinism rule, every file's columns, the ball model in words, and the structure of everything hidden, including that there is no effect for one specific batter against one specific bowler. It withholds every magnitude. Unknown quantities are allowed; unknown rules are not.

## Provenance

Calibration constants derived from data sourced from Cricsheet (cricsheet.org), maintained by Stephen Rushe, licensed under the Open Data Commons Attribution License 1.0. Aggregates only; no Cricsheet row is shipped. Task, verifier, documents and records by Siddharth Shashank Kumar, September 2026.
