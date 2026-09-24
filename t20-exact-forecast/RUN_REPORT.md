# Run report. t20-exact-forecast

## What this is

The t20-exact-forecast task, built and typed by me with a check against known numbers after every file (`NOTES.md`), packaged as `dist/collinear-siddharthshashankkumar/t20-exact-forecast/`, run through Harbor's gates, and piloted ten times, five per model.

## Environment

| Item | Value |
|---|---|
| Harness | Harbor 0.23.0, task schema 1.4, local Docker |
| Host | macOS on Apple silicon, Docker Desktop |
| Base image | `python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea` |
| Libraries | numpy 2.4.4, pandas 3.0.2, scipy 1.17.1 |
| Agents | Claude Code CLI 2.1.274 with `anthropic/claude-opus-4-7`; Codex CLI with `openai/gpt-5.5`; both at high reasoning effort |
| Credentials | My own subscriptions. No token appears in any job record; agent session directories are excluded from the repository. |
| Budgets | Agent 3 hours, verifier 3 hours, 12 minutes per world for the submitted program |

## Commands

    make venv
    make data              # eight worlds, truth at 100,000 copies per batting order, reference regret, careless tiers (about 25 minutes)
    make package
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
    harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
    harbor view ./jobs
    python dev/ablate_pilots.py heldout_c <folder with the archived programs>

## Gates

| Run | Job | Overall | Functional | Robustness | Constraints | Artifact |
|---|---|---|---|---|---|---|
| Oracle (the reference forecaster) | 2026-09-23__19-38-27 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Do nothing (the starter says 0.5 everywhere) | 2026-09-23__19-33-46 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 |

The first oracle run (job 2026-09-23__19-33-12) scored 0.000 because `solve.sh` had spaces around a shell assignment and never installed the oracle, so the verifier graded the starter. Fixed, repackaged, rerun. Only `solve.sh` changed between the packages, which the do-nothing run does not use.

On the eight graded worlds, total regret as a multiple of the reference's: last season only 1.50, no shrinkage 1.58, coin flip 1.89, team ratings 3.23, raw head-to-head 4.00. The bar is 1.10.

## Pilots

| Trial | Model | Job | Verdict | Total regret, times the reference | Held-out only | Wall time |
|---|---|---|---|---|---|---|
| 1 | Claude Opus 4.7 | 2026-09-23__19-48-37 | Failed | 1.533 | 1.492 | 16 min |
| 1 | GPT-5.5 | 2026-09-23__20-04-36 | Failed | 1.575 | 1.613 | 25 min |
| 2 | Claude Opus 4.7 | 2026-09-23__20-29-40 | Failed | 1.573 | 1.537 | 25 min |
| 2 | GPT-5.5 | 2026-09-23__20-54-41 | Failed | 1.545 | 1.543 | 19 min |
| 3 | Claude Opus 4.7 | 2026-09-23__21-13-35 | Failed | 1.396 | 1.376 | 21 min |
| 3 | GPT-5.5 | 2026-09-23__21-34-46 | Failed | 1.109 | 1.117 | 20 min |
| 4 | Claude Opus 4.7 | 2026-09-23__23-47-55 | Failed | 1.364 | 1.345 | 22 min |
| 4 | GPT-5.5 | 2026-09-24__00-10-13 | Failed; session cut short by my account's usage limit after the program was written | 1.362 | 1.341 | 13 min |
| 5 | Claude Opus 4.7 | 2026-09-24__00-23-00 | Failed | 1.703 | 1.661 | 23 min |
| 5 | GPT-5.5 | 2026-09-24__00-45-36 | Failed | 1.409 | 1.398 | 26 min |

Opus 4.7 0 of 5, GPT-5.5 0 of 5. No run came near a time limit; every run produced a complete, valid, deterministic forecast and left the engine untouched, so every verdict is about forecast quality. The verifier found nine of the ten forecasts closest to the unshrunk tier. Run 8 delivered a 230-line program and was then ended by my account's usage limit; the delivered program was graded, and the run is counted and flagged. Excluding it leaves GPT-5.5 at 0 of 4.

## Ablations

The six first-round programs were read and each rerun on held-out world c with one constant changed (`dev/ablate_pilots.py`, output in `ablations.log`). Regret as a multiple of the reference's: trial 1 from 2.70 to 1.36 (its single ridge raised from 1.0 to 25); trial 2 from 2.55 to 1.57 (every prior sd times 0.33); trial 3 from 2.17 to 1.64 (every ridge times 12); trial 4 from 2.29 to 1.60 (every ridge times 12); trial 5 from 2.10 to 1.27 (its two quality ridges raised to the true values); trial 6, the near miss, from 1.42 to 1.67 with its output hedge removed, to 1.13 with the hedge deepened, and to 0.91 with its priors halved and the hedge kept. The "as submitted" rows reproduce the verifier's column for that world to the last digit. Harbor redacts the env value `true` in job artifacts, so archived programs and `details.json` files need `[REDACTED]` restored to `true` before they run or parse; the script and the summaries do that.

## Fairness, provenance, limitations

Everything the grader checks is stated in the handbook; the reference uses only the agent's files and engine; the rule was committed before any pilot; the oracle passes at exactly 1.000 times the stored reference. The constants were reproduced from the raw Cricsheet archive by the scripts in `dev/` and match an earlier build of the same pipeline to within 0.0007; only aggregates ship. Limitations are in the design document, section 8.
