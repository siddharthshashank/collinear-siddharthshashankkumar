# Run report

`t20-exact-forecast`. What was run, on what, what came out, and how to run it again. Every number here is in a job folder under `jobs/`, in `ablations.log`, or in the git history.

---

## 1. The short version

The task passed its own two gates and Harbor's linter. The two models the brief's goal line names, Claude Opus 4.7 and GPT-5.5, failed it in all ten runs. The next generation, Claude Fable 5.1 and GPT-6-astra, passed four of five completed runs, with one narrow Fable miss that passed the held-out rule and failed the all-worlds rule by 0.4 points. The pass rule was committed before any of the eighteen model jobs and has not changed.

---

## 2. The rule every verdict was graded by

For each of 24 fixtures in each of eight worlds, the program's home-win probability `q` is compared with the stored true probability `p`:

```text
q      = clip(q, 0.002, 0.998)
regret = p * ln(p / q) + (1 - p) * ln((1 - p) / (1 - q))
```

Regret is averaged over the fixtures of each world. The program passes the forecasting rule when the sum of its eight world regrets is at most 1.10 times the sum of the reference forecaster's, and the same holds for the seven held-out worlds on their own. The reward has four keys:

| Key | Meaning |
|---|---|
| `functional_correctness` | The all-eight-worlds rule passed |
| `robustness` | The held-out-seven rule passed |
| `constraint_satisfaction` | Mean of three checks: engine unchanged (hash), identical output on a second run, every world inside 720 seconds |
| `artifact_quality` | Share of worlds with a complete, finite forecast between 0 and 1 for every fixture |
| `overall` | `functional_correctness × (0.5 × robustness + 0.25 × constraint_satisfaction + 0.25 × artifact_quality)` |

Only `overall = 1.0` counts as solved. The rule file is `harbor/bar.json` (relative tolerance 0.10, absolute tolerance 0, clip 0.002). It was committed before the first pilot: the commit "Harbor metadata, pass bar, lock file, instruction" precedes job `2026-09-23__19-48-37` in the git log.

---

## 3. Environment

| Item | Value |
|---|---|
| Harness | Harbor 0.23.0, task schema 1.4, local Docker |
| Host | macOS on Apple silicon, Docker Desktop |
| Base image | `python:3.12-slim`, pinned by digest, for both the agent and the verifier |
| Libraries | numpy 2.4.4, pandas 3.0.2, scipy 1.17.1, pinned in both lock files |
| Container resources | 2 CPUs, 4,096 MB memory, 10,240 MB storage; build budget 900 s |
| Budgets | Agent session 3 hours; verifier 3 hours; 720 seconds per world for the submitted program |
| Agents | Claude Code 2.1.274 with `anthropic/claude-opus-4-7` and `anthropic/claude-fable-5-1`; Codex CLI with `openai/gpt-5.5` and `openai/gpt-6-astra`; all with `reasoning_effort: high`; the values are in each job's `config.json` |
| Credentials | My own subscriptions; no token appears in any job record; agent session directories are excluded from the repository |
| Network | The agent's container has network for the model API; the forecasting program needs none; the verifier makes no network calls, though its no-network mode is not declared because Docker Desktop on macOS rejects it |

---

## 4. The gates

| Run | Job | Overall | Functional | Robustness | Constraints | Artifact |
|---|---|---:|---:|---:|---:|---:|
| Oracle: the reference forecaster installed as the solution | `2026-09-23__19-38-27` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Do nothing: the starter that says 0.5 everywhere | `2026-09-23__19-33-46` | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 |

The first oracle attempt, `2026-09-23__19-33-12`, scored 0.000 because `solve.sh` had spaces around a shell assignment, so the oracle was never installed and the verifier graded the starter. That is a packaging error on my side, fixed and rerun; it is kept in the record so that an infrastructure error is never mistaken for a model result. The oracle passes at exactly 1.000 times the stored reference regret, which is what "solvable from the agent's files" means here.

Harbor's task linter, `harbor check`, passed all 22 checks, job `2026-09-24__12-21-19`. It noted one typo in a comment in the engine, left as is because changing the engine after the pilots would change the task.

On the eight graded worlds, the careless methods on the ladder total 1.50 (last season only), 1.58 (no shrinkage), 1.89 (coin flip), 3.23 (team ratings) and 4.00 (raw head-to-head) times the reference's regret, against the bar of 1.10.

---

## 5. The pair named in the brief's goal line

All runs after the rule was committed, alternating between the two models.

| Run | Model | Job | Total regret, times the reference | Held-out only | Most resembles | Session |
|---|---|---|---:|---:|---|---|
| 1 | Claude Opus 4.7 | `2026-09-23__19-48-37` | 1.533 | 1.492 | no shrinkage, 6 of 8 worlds | 16 min |
| 2 | GPT-5.5 | `2026-09-23__20-04-36` | 1.575 | 1.613 | no shrinkage, 7 of 8 | 25 min |
| 3 | Claude Opus 4.7 | `2026-09-23__20-29-40` | 1.573 | 1.537 | no shrinkage, all 8 | 25 min |
| 4 | GPT-5.5 | `2026-09-23__20-54-41` | 1.545 | 1.543 | no shrinkage 5, last season only 2 | 19 min |
| 5 | Claude Opus 4.7 | `2026-09-23__21-13-35` | 1.396 | 1.376 | no shrinkage, all 8 | 21 min |
| 6 | GPT-5.5 | `2026-09-23__21-34-46` | 1.109 | 1.117 | the reference, 7 of 8 | 20 min |
| 7 | Claude Opus 4.7 | `2026-09-23__23-47-55` | 1.364 | 1.345 | no shrinkage, all 8 | 22 min |
| 8 | GPT-5.5 | `2026-09-24__00-10-13` | 1.362 | 1.341 | no shrinkage, all 8 | 13 min; session cut short by my account's usage limit after the program was written |
| 9 | Claude Opus 4.7 | `2026-09-24__00-23-00` | 1.703 | 1.661 | no shrinkage, all 8 | 23 min |
| 10 | GPT-5.5 | `2026-09-24__00-45-36` | 1.409 | 1.398 | no shrinkage, all 8 | 26 min |

Opus 4.7 0 of 5. GPT-5.5 0 of 5, or 0 of 4 excluding run 8; I count it and flag it because its program was complete and graded. Every run produced a complete, valid, deterministic forecast, left the engine untouched and finished well inside its limits, so every failure is about forecast quality. Run 6 missed by 0.9 points on all eight worlds and 1.7 on the held-out seven; a 1.12 bar would have passed it, and the 1.10 bar stands.

---

## 6. The pair named in the brief's opening section

Same task, same rule, same harnesses, high effort.

| Run | Model | Job | Total regret, times the reference | Held-out only | Session | Verdict |
|---|---|---|---:|---:|---|---|
| F1 | Claude Fable 5.1 | `2026-09-24__15-33-25` | 1.027 | 1.015 | 2 h 02 | pass |
| F2 | Claude Fable 5.1 | `2026-09-24__20-28-49` | 1.104 | 1.093 | 2 h 37 | fail on all eight by 0.4 points; pass on the held-out seven |
| F3 | Claude Fable 5.1 | `2026-09-24__23-50-11` | 1.008 | 0.989 | 1 h 44 | pass |
| A1 | GPT-6-astra | `2026-09-24__19-42-59` | 1.054 | 1.047 | 46 min | pass |
| A2 | GPT-6-astra | `2026-09-24__23-05-34` | 1.072 | 1.061 | 45 min | pass |

Excluded, with their records kept:

| Job | Model | Why excluded |
|---|---|---|
| `2026-09-24__17-35-36` | GPT-6-astra | My account's usage limit at 5 minutes, before a program existed; the starter was graded |
| `2026-09-25__01-34-12` | GPT-6-astra | Program complete; I stopped the loop during its verification |
| `2026-09-25__01-51-10` | Claude Fable 5.1 | Stopped at its start |

Fable 5.1 2 of 3 completed runs, GPT-6-astra 2 of 2. All five forecasts most resemble the reference on every world. Their closing messages, in the agent logs, describe prior scales estimated from the league by marginal likelihood, simulation that averages over the uncertainty in the estimates, and validation against leagues they generated from the handbook's description (Fable) or a held-out slice of the real league (GPT-6-astra). In all five the visible world was the worst or second-worst world; F2's miss is entirely the visible world, 1.191 there against 1.093 elsewhere.

---

## 7. Why the older pair failed: reading and intervention

**Reading.** I read the six first-round programs and each session's closing message. All six fit the documented model correctly. All six set the prior scale on player quality, the number that controls how much a short history is trusted, between 3 and 44 times too weak (the true value is a ridge of about 44; they used 1.0, a prior sd of 0.75, 1.0, 1.2, 4, and a prior sd of about 0.45). Four checked only runtime, determinism and output shape. Run 5 checked symmetry and range. Run 3 generated synthetic leagues and scored itself well inside the bar, but generated them with the same too-loose priors as its estimator, so the check confirmed its assumption rather than testing it. Run 6, the near miss, multiplied every output's logit by 0.90, a hedge that partly compensated for its loose priors.

**Intervention.** I reran each of the six programs on held-out world c with one constant changed (`dev/ablate_pilots.py`; output in `ablations.log`). The "as submitted" rows reproduce the verifier's own numbers for that world to the last digit.

| Program | As submitted | The one change | After |
|---|---:|---|---:|
| Run 1, Opus | 2.70 | ridge 1.0 on everything raised to 25 | 1.36 |
| Run 2, GPT-5.5 | 2.55 | every prior sd multiplied by 0.33 | 1.57 |
| Run 3, Opus | 2.17 | every ridge multiplied by 12 | 1.64 |
| Run 4, GPT-5.5 | 2.29 | every ridge multiplied by 12 | 1.60 |
| Run 5, Opus | 2.10 | the two quality ridges raised to the true values | 1.27 |
| Run 6, GPT-5.5 | 1.42 | hedge removed | 1.67 |
| Run 6, GPT-5.5 | 1.42 | hedge deepened to 0.75 | 1.13 |
| Run 6, GPT-5.5 | 1.42 | every prior sd halved, hedge kept | 0.91 |

Every change moved the regret the way the reading predicted. Four of the five programs cut their excess above the reference by more than half; run 3 cut it by 45 percent. Run 6 got worse without its hedge, better with a deeper one, and better than the reference with its priors corrected, so the near miss was a hedged wrong answer. None of this shows that one edit would make a program pass on all eight worlds; it is one world and one constant each. Runs 7 to 10 are attributed by resemblance only.

---

## 8. Reproducing it

From the repository root:

```sh
make venv                      # .venv with the three pinned libraries
make data                      # eight worlds, truth at 100,000 copies per batting order, reference regrets, ladder tiers (about 25 minutes)
make package                   # dist/collinear-siddharthshashankkumar/t20-exact-forecast/
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop
harbor check dist/collinear-siddharthshashankkumar/t20-exact-forecast
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-fable-5-1 --ak reasoning_effort=high
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-6-astra --ak reasoning_effort=high
harbor view ./jobs
.venv/bin/python dev/ablate_pilots.py heldout_c <folder of archived programs>
```

Model runs need the corresponding provider access; the oracle, the control and the linter need none. `make data` regenerates the worlds deterministically from the committed constants; the packaged task rebuilds byte for byte from a fresh clone. Rebuilding the calibration itself needs the Cricsheet IPL archive under `data/raw/ipl/`, which is not tracked; the scripts in `dev/` regenerate `league/calibration.json` from it, and did so to within 0.0007 of an earlier build.

---

## 9. Why this is a real task, and worth money

The job the agent is asked to do is the job of a quantitative analyst at a sportsbook, a fantasy platform or a broadcaster's analytics desk: turn a ball-by-ball archive into calibrated match probabilities for the coming fixtures, delivered as a program that runs again every season on new data. Those desks exist, they pay for this work, and the mistake the task catches, treating a short history as a settled fact, is the mistake that costs them. The same skill, with the same failure mode, is what a forecaster does with conversion rates, equipment failures, disease counts or demand: decide how much of a small sample to believe. The cricket is the setting; the capability is general.

The task is economically viable to run as a benchmark too. The world builds in 25 minutes once, the truth is stored so grading is deterministic and cheap, a full verification of eight worlds takes under five minutes, and the agent's session is the only cost that scales with the number of runs.

## 10. Verifier design

The verifier is a separate container that the agent never sees. It holds the eight worlds, the stored truth, the reference's regrets, the ladder's forecasts and the rule. It copies the agent's `solution/` and hashes the agent's `engine/` against a pristine copy, then runs the program once on each world, and a second time on the visible world, as an unprivileged user beside the pristine engine, with the private files unreadable and a 720-second limit per world. It scores each forecast by clipped logarithmic regret against the truth, applies the pooled rule on all eight worlds and again on the seven held out, and writes `/logs/verifier/reward.json` with four keys plus per-world details, including which ladder rung each forecast most resembles. `tests/test.sh` is the entrypoint; it runs `grader.py` and, if the grader itself fails, writes a zero reward rather than nothing, so an infrastructure failure never looks like a pass.

A shallow solution cannot pass it. The starter scores zero. Team ratings, last season only, unshrunk player estimates and head-to-head tables are all on the ladder and all sit at 1.50 times the reference or worse; the bar is 1.10. Copying the visible world's answers is impossible because the truth never enters the agent's container, and tuning to the visible world is caught by the held-out rule.

## 11. Fairness audit

| Question | Answer |
|---|---|
| Is everything the grader checks stated to the agent? | Yes: the score, the clip, the tolerance, both applications of the rule, the time limit, the determinism check and the engine check are in the handbook, whose numbers are filled from `bar.json` at packaging |
| Can the reference see anything the agent cannot? | At run time, no: it is fitted from the same seven files through the same reader. Its prior scales were set by me knowing the true spreads; this advantage is stated and measured (Section 7) |
| Is the task solvable through the agent's interface? | Yes: the oracle installs the reference forecaster as a submission and scores 1.000 on every key |
| Did any run fail for an infrastructure reason? | No: every graded run produced a valid, deterministic forecast inside its limits; the one packaging error in the record is the first oracle attempt, kept and labelled |
| Were the models run as intended? | Native harnesses, high reasoning effort, three-hour sessions, the same frozen task for all four models |
| Was the rule fixed before the runs? | Yes: `bar.json` was committed before the first pilot job and has not changed |
| Could the task favour one model family? | It was designed with an assistant of Fable's family; the same family's previous model failed five times on the same handbook, and a model from another lab passed, so the passes are not family affinity |
| What is the task not fair about? | Nothing known. Its known limitation is on the other side: as calibrated, it does not fail the newest generation |

## 12. Evidence integrity

Every graded job under `jobs/` holds its reward, per-world details, agent log, config and the submitted program; the two jobs I stopped (`2026-09-25__01-34-12`, which has its complete program, and `2026-09-25__01-51-10`) hold their agent logs and config only. Harbor redacts the value of every environment variable passed on the command line, and one such value was the word `true`, so every literal `true` in the archived files reads `[REDACTED]`; that breaks `details.json` parsing and `action="store_true"` in two archived programs. The summaries and the ablation script restore the token in memory and leave the archived files untouched; the restored programs reproduce the verifier's numbers to the last digit.

Still open: repeating the truth calculations with independent random streams to confirm that borderline verdicts are stable; extending the interventions to a second world and to runs 7 to 10; and investigating why the newer pair does worst on the visible world.
