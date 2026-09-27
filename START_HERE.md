# Start here

Submission for the Collinear AI take-home, by Siddharth Shashank Kumar. This file maps the brief's checklist to this repository's layout. Everything is under `t20-exact-forecast/`; the paths below are relative to that folder.

The primary deliverable is `DESIGN_DOCUMENT.md`. The one Harbor task directory is `dist/collinear-siddharthshashankkumar/t20-exact-forecast/`.

| The brief asks for | Where it is |
|---|---|
| A clear design document | `DESIGN_DOCUMENT.md`; extended version with the drawings in `docs/DESIGN.pdf` |
| Exactly one net-new task directory, stable slug | `dist/collinear-siddharthshashankkumar/t20-exact-forecast/`, built by `package_task.py` from `harbor/`, `task_src/`, `league/`, `forecasters/` and `task_data/`; `harbor/` holds the templates the packager copies and is not a second task |
| `instruction.md` | `dist/collinear-siddharthshashankkumar/t20-exact-forecast/instruction.md` |
| `task.toml` with metadata, timeouts, resources, network policy, authorship, category | `dist/collinear-siddharthshashankkumar/t20-exact-forecast/task.toml` |
| `environment/Dockerfile`, pinned | `dist/collinear-siddharthshashankkumar/t20-exact-forecast/environment/Dockerfile`; base image by digest, libraries by version |
| `tests/test.sh` writing `/logs/verifier/reward.json` | `dist/collinear-siddharthshashankkumar/t20-exact-forecast/tests/test.sh` |
| Grader files | `dist/collinear-siddharthshashankkumar/t20-exact-forecast/tests/grader.py` |
| `solution/solve.sh`, an oracle that passes | `dist/collinear-siddharthshashankkumar/t20-exact-forecast/solution/solve.sh`; job `jobs/2026-09-23__19-38-27` scores 1.000 |
| Seed files | the visible league, the engine and the handbook under `environment/app/` in the task directory; all eight worlds and the private truth under its `tests/` |
| `README.md` or `RUN_REPORT.md` for the task | `RUN_REPORT.md` at this level (the submission zip also carries a copy inside the task directory) |
| Task idea, fairness, economic viability, model runs, verifier design, limitations, commands | `RUN_REPORT.md`, Sections 1 to 13; `DESIGN_DOCUMENT.md`, Sections 9 to 14 |
| Oracle result, model results, failure analysis | `RUN_REPORT.md`, Sections 4 to 7; every job under `jobs/` |
| External sources and licences | `PROVENANCE.md` |
| Not copied from an existing benchmark | `PROVENANCE.md`, "What is new" |
| Architecture diagrams | `figures/`, placed in the design document; six are by Rutvikk Kharod, used with permission (see `PROVENANCE.md`) |
| Focused experiments | the bar analysis (`bar.log`), the ladder (`results/ladder_v2.jsonl`), the ablations (`ablations.log`, `dev/ablate_pilots.py`) |
| Independent review | `RUN_REPORT.md`, Section 13 |

`jobs/` holds every Harbor job: the two gates, the linter, and the nineteen model jobs (sixteen graded, three stopped), with agent session directories excluded. Decisions and their alternatives are in `DECISIONS.md`; file-by-file notes in `NOTES.md`; the full-length working notes in `docs/NOTES_FULL.md`.
