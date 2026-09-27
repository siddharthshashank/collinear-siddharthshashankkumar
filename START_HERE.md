# Start here

This is Siddharth Shashank Kumar's Collinear take-home submission. The task asks an agent to turn a noisy cricket history into useful match probabilities. It tests statistical judgment, implementation, and validation across several dependent steps.

**Submit the zip produced by `make submission`.** It has one task directory at `collinear-siddharthshashankkumar/t20-exact-forecast/`. The full repository retains development code and historical records for review; passing the repository root to Harbor would select the wrong directory.

## A short review route

Start with [DECISIONS.md](t20-exact-forecast/DECISIONS.md) for how I chose and revised the approach, [ASSUMPTIONS.md](t20-exact-forecast/ASSUMPTIONS.md) for uncertainty and ambiguity, and [NOTES.md](t20-exact-forecast/NOTES.md) for how I checked the implementation. Then read the [overview](t20-exact-forecast/README.md) and [run report](t20-exact-forecast/RUN_REPORT.md). For a concrete failure, start with GPT-5.5 run 2: its program met the format, timing, engine-integrity and determinism checks, but incurred **1.575×** the reference's total regret against a **1.10×** limit. The report links its config, reward, per-world results, submitted code and transcript.

The [design document](t20-exact-forecast/DESIGN_DOCUMENT.md) explains why the task is useful and where its conclusions stop. The [validation record](t20-exact-forecast/VALIDATION.md) separates checks performed for this documentation revision from the historical model trials.

## Canonical brief → submitted artifact

Paths in the second column are relative to the packaged task directory.

| Requirement | Artifact or evidence |
|---|---|
| Exactly one net-new Harbor task | One `task.toml` in the submission zip; stable slug `collinear-siddharthshashankkumar/t20-exact-forecast` |
| Clear prompt, files, constraints and deliverable | `instruction.md`; detailed contract in `environment/app/docs/handbook.md` |
| Metadata, author, category, timeouts, resources and network policy | `task.toml`; network-enforcement limitation explained in `RUN_REPORT.md` |
| Pinned container environment | `environment/Dockerfile`, `tests/Dockerfile`, and their `requirements.lock` files; transitive dependency limitation disclosed |
| Verifier entrypoint and machine-readable reward | `tests/test.sh` → `/logs/verifier/reward.json`; five named reward fields |
| Functional grading logic and fixtures | `tests/grader.py`, `tests/leagues/`, `tests/private/`, `tests/pristine/` |
| Executable passing oracle | `solution/solve.sh`; original passing job and fresh validation evidence in the report |
| Seed files | Public engine, starter, seven CSVs and handbook under `environment/app/` |
| Candidate reasoning, assumptions and iteration | `DECISIONS.md`, `ASSUMPTIONS.md`, `NOTES.md`; choices tied to evidence rather than a reconstructed diary |
| Explanation, realism, fairness, limitations and reproduction | `README.md`, `DESIGN_DOCUMENT.md`, `RUN_REPORT.md` |
| Model-name ambiguity | `ASSIGNMENT_BRIEF.md` preserves the full wording; the decision record explains the interpretation and the unmet stricter reading |
| Requested model failure, native harness, high effort | Five archived Opus 4.7 trials and five GPT-5.5 trials; commands and caveats in `RUN_REPORT.md` |
| Substantive failure analysis | Program inspection and one-constant interventions for six programs on one world; remaining four diagnoses are tentative |
| Net-new work, sources and licenses | `PROVENANCE.md`; no existing benchmark task or public issue was ported |
| Validation and inspectable evidence | `VALIDATION.md`, `validation/`, and original `jobs/` records |

The canonical rubric assigns 20 points each to reproducibility, fairness and verifier quality; 15 each to long-horizon difficulty and target-model failure; and 10 to originality and realism. This mapping locates the evidence; it does not award the submission a score or erase the limitations in the report.

The task inputs, grading rule and runnable files are preserved from the evaluated version. Reviewer documents and packaging have been updated. The earlier PDF and working notes remain historical material; use the current Markdown report when their wording differs.
