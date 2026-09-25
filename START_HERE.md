# Start here

Submission for the Collinear AI take-home, by Siddharth Shashank Kumar. Repository: github.com/siddharthshashank/collinear-siddharthshashankkumar

The primary deliverable is `DESIGN_DOCUMENT.md`. The one Harbor task directory is `task/collinear-siddharthshashankkumar/t20-exact-forecast/`.

| The brief asks for | Where it is |
|---|---|
| A clear design document | `DESIGN_DOCUMENT.md`; extended version with all drawings in `docs/DESIGN.pdf` |
| Exactly one net-new task directory, stable slug | `task/collinear-siddharthshashankkumar/t20-exact-forecast/` |
| `instruction.md` | in the task directory |
| `task.toml` | in the task directory |
| `environment/Dockerfile`, pinned | in the task directory; base image pinned by digest, libraries by version |
| `tests/test.sh` writing `/logs/verifier/reward.json` | in the task directory |
| Grader files | `tests/grader.py` in the task directory |
| `solution/solve.sh`, an oracle that passes | in the task directory; job `2026-09-23__19-38-27` scores 1.000 |
| Seed files | the visible league, the engine and the handbook under `environment/app/`; all eight worlds and the private truth under `tests/` |
| `README.md` or `RUN_REPORT.md` in the task | `RUN_REPORT.md`, also at the top level |
| Task idea, fairness, economic viability, model runs, verifier design, limitations, commands | `RUN_REPORT.md` Sections 1 to 12; `DESIGN_DOCUMENT.md` Sections 9 to 13 |
| Oracle result, model results, failure analysis | `RUN_REPORT.md` Sections 4 to 7; every job under `evidence/jobs/` |
| External sources and licences | `PROVENANCE.md` |
| Not copied from an existing benchmark | `PROVENANCE.md`, "What is new" |
| Architecture diagrams | `figures/`, placed in the design document |
| Focused experiments | the bar analysis (`source/bar.log`), the ladder (`source/results/`), the ablations (`source/ablations.log`) |

`source/` holds the code that builds the task directory (`make data`, `make package`); `source/harbor/` and `source/task_src/` are the templates the packager copies, not a second task. `evidence/jobs/` holds every Harbor job: the two gates, the linter, and the eighteen model jobs, with agent session directories excluded. Decisions and their alternatives are in `DECISIONS.md`; file-by-file notes in `NOTES.md`.
