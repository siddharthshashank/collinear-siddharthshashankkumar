# Start here

This is Siddharth Shashank Kumar's Collinear take-home submission. The task asks an agent to turn a noisy cricket history into useful match probabilities. It tests statistical judgment, implementation, and validation across several dependent steps.

**Submit the zip produced by `make submission`.** It has one task directory at `collinear-siddharthshashankkumar/t20-exact-forecast/`. The full repository retains development code and historical records for review; passing the repository root to Harbor would select the wrong directory.

## Review in three steps

1. [Overview](t20-exact-forecast/README.md): understand the task and run it.
2. [Decisions](t20-exact-forecast/DECISIONS.md): inspect my reasoning, alternatives and changes of mind.
3. Evidence: use [the run report](t20-exact-forecast/RUN_REPORT.md) for historical trials and failure analysis, [replication](t20-exact-forecast/REPLICATION_REPORT.md) for the predeclared current-version batch, and [validation](t20-exact-forecast/VALIDATION.md) for controls and verifier checks.

[Assumptions](t20-exact-forecast/ASSUMPTIONS.md), [engineering notes](t20-exact-forecast/NOTES.md) and the [design document](t20-exact-forecast/DESIGN_DOCUMENT.md) provide supporting detail. For a concrete historical failure, start with GPT-5.5 run 2: its artifact met the original validity and constraint checks but incurred **1.575×** reference regret against a **1.10×** limit. Its genuine 90-match backtest did not establish the forecast quality the task required.

The package is now **v0.1.1**. The current oracle passes; the first v0.1.1 GPT-5.5-high attempt fails forecast quality at **1.230×** total / **1.246×** held-out reference regret, while satisfying the artifact and constraint checks. That attempt is separate from the later predeclared replication batch. Original model jobs belong to **v0.1.0**; fresh controls, the archived-program replay and new model attempts are identified separately. A replay tests the old artifact under the new verifier; it is not a new model attempt.

The fixed replication batch is complete: **GPT-5.5 1/2 passes, Opus 4.7 0/2, GPT-6-astra 2/2 and Fable 5.1 2/2**, all at high effort through native harnesses. All eight sessions finished normally without retries. The three misses are forecasting failures with valid artifacts and satisfied constraints. The report makes the passing GPT-5.5 result and the absence of a clean newer-pair failure explicit.

## Canonical brief → submitted artifact

Paths in the second column are relative to the packaged task directory.

| Requirement | Artifact or evidence |
|---|---|
| Exactly one net-new Harbor task | One `task.toml` in the submission zip; stable slug `collinear-siddharthshashankkumar/t20-exact-forecast` |
| Clear prompt, files, constraints and deliverable | `instruction.md`; detailed contract in `environment/app/docs/handbook.md` |
| Metadata, author, category, timeouts, resources and network policy | `task.toml`; verifier network isolation in `tests/docker-compose.yaml` |
| Pinned container environment | Digest-pinned Dockerfiles and hash-locked Python dependencies; current build evidence in `VALIDATION.md` |
| Verifier entrypoint and machine-readable reward | `tests/test.sh` → `/logs/verifier/reward.json`; five named reward fields |
| Functional grading logic and fixtures | `tests/grader.py`, `tests/leagues/`, `tests/private/`, `tests/pristine/` |
| Executable passing oracle | `solution/solve.sh`; historical result and current control status recorded separately in `VALIDATION.md` |
| Seed files | Public engine, starter, seven CSVs and handbook under `environment/app/` |
| Candidate reasoning, assumptions and iteration | `DECISIONS.md`, `ASSUMPTIONS.md`, `NOTES.md`; choices tied to evidence rather than a reconstructed diary |
| Explanation, realism, fairness, limitations and reproduction | `README.md`, `DESIGN_DOCUMENT.md`, `RUN_REPORT.md` |
| Model-name ambiguity | `ASSIGNMENT_BRIEF.md` preserves the full wording; the decision record explains the interpretation, and `REPLICATION_REPORT.md` covers both named pairs |
| Requested model failure, native harness, high effort | Original v0.1.0 trials in `RUN_REPORT.md`; the earlier v0.1.1 attempt in `VALIDATION.md`; the separate predeclared batch in `REPLICATION_REPORT.md` |
| Fixed replication plan and complete attempt accounting | `REPLICATION_REPORT.md`, with declared slots, stopping rule, recorded outcomes and operational retries under `validation/replication-20260927/` |
| Substantive failure analysis | Program inspection and one-constant interventions for six programs on one world; remaining four diagnoses are tentative |
| Net-new work, sources and licenses | `PROVENANCE.md`; no existing benchmark task or public issue was ported |
| Validation and inspectable evidence | `VALIDATION.md`, `validation/`, and original `jobs/` records |

The canonical rubric assigns 20 points each to reproducibility, fairness and verifier quality; 15 each to long-horizon difficulty and target-model failure; and 10 to originality and realism. This mapping locates the evidence; it does not award the submission a score or erase the limitations in the report.

The revised package contains 119 runtime files: 109 unchanged from the historical baseline, nine revised and one added. The data, engine, oracle and scoring inputs retain their original hashes. Changes to the verifier, environment and agent-facing disclosures are listed in `validation/runtime-revision.json`. The earlier PDF and working notes remain historical material; use the current Markdown report when their wording differs.
