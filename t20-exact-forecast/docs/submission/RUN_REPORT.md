# Run report and evidence boundaries

**Task:** `collinear-siddharthshashankkumar/t20-exact-forecast`  
**Document purpose:** supporting evidence for the [design document](DESIGN_DOCUMENT.md).  
**Evidence:** the job records under `jobs/`, the logs, the git history and the code in this repository.

## 1. What the results establish

The corrected oracle passed every reward component. All ten older-model submissions failed the fixed forecast-quality rule: Claude Opus 4.7 passed 0 of 5, and GPT-5.5 passed 0 of 5. Claude Fable 5.1 passed 2 of 3 completed runs and GPT-6-astra 2 of 2. One completed Fable forecast failed narrowly, at 1.104 times the reference across all worlds, while passing the held-out group at 1.093.

These findings support a functioning, discriminating forecasting task. They do **not** support a claim that the newest pair consistently fails. They also do not isolate model generation, vendor, or any individual design feature as the cause of different outcomes. There are few trials, and the evidence available for inspection differs across rounds.

The assignment materials name different target pairs in different places. This report therefore identifies every model explicitly. Against the older pair, it records repeated failures; against the newer pair, it records four passes and one near-threshold failure among five completed runs. That distinction should remain visible when judging the assignment's target-model objective.

## 2. Rule used for every reported verdict

Each program forecasts the home team's win probability for 24 fixtures in each of eight synthetic worlds. One world is visible during development; seven are held out. Regret measures the distance from the stored simulator-derived probabilities using expected logarithmic loss, with submitted probabilities clipped to `[0.002, 0.998]` for scoring.

For a group of worlds, the reported ratio is:

```text
sum of the submission's world regrets
------------------------------------
sum of the reference's world regrets
```

The program must achieve a ratio at most **1.10**, first across all eight worlds and again across the seven held-out worlds. This is a ratio of sums, not an average of the ratios for individual worlds. The grader applies the rule to unrounded quantities; tables show rounded results.

The rule file records relative tolerance `0.10` and absolute tolerance `0`. It was committed before the first model pilot: the commit "Harbor metadata, pass bar, lock file, instruction" precedes job `2026-09-23__19-48-37` in the git log, and it has not changed through both generations of trials.

The reward fields separate causes:

| Field | Meaning |
|---|---|
| `functional_correctness` | The all-world ratio is within the bar |
| `robustness` | The held-out ratio is within the bar |
| `artifact_quality` | Share of worlds with complete, finite probabilities in `[0, 1]` |
| `constraint_satisfaction` | Mean of engine integrity, visible-world repeatability, and execution-time checks |
| `overall` | `functional_correctness × (0.50 × robustness + 0.25 × constraint_satisfaction + 0.25 × artifact_quality)` |

Only full reward counts as solved. The grader also records the nearest reference-ladder forecast by root-mean-square distance. That diagnostic does not affect the grade and does not, by itself, prove a failure's cause.

## 3. Controls before the model trials

| Control | Job directory | Outcome and interpretation |
|---|---|---|
| First oracle attempt | `2026-09-23__19-33-12` | Installation failed with exit code 127 and `HERE: command not found`; the starter remained and received zero overall |
| Do-nothing starter | `2026-09-23__19-33-46` | Zero overall; artifact and constraint scores were 1.0; regret ratios 1.891 overall and 1.828 held out |
| Corrected oracle | `2026-09-23__19-38-27` | Every reward component was 1.0; both regret ratios were exactly 1.000 |

The first attempt is an author-side packaging defect, not evidence of a model failure. The corrected oracle installs the reference forecaster and computes forecasts through the public runtime interface. It does not copy stored answer probabilities.

This is a concrete solvability witness under that interface. It does not remove the reference's design-time advantage: its starting prior scales were informed by the generator's population scales. The tolerance and subsequent successful independent agents are relevant evidence, but the advantage remains a limitation of this version.

Harbor's linter, `harbor check`, passed all 22 checks under job `2026-09-24__12-21-19`; the report is in that job's folder.

## 4. Ten older-model trials

All sessions used the native harnesses at high reasoning effort: Claude Code for Opus 4.7 and Codex for GPT-5.5. Each had a three-hour agent budget.

| Run | Model | All worlds | Held out | Nearest ladder forecast | Session |
|---|---|---:|---:|---|---:|
| 1 | Opus 4.7 | 1.533 | 1.492 | No shrinkage on 6 of 8 worlds | 16 min |
| 2 | GPT-5.5 | 1.575 | 1.613 | No shrinkage on 7 of 8 | 25 min |
| 3 | Opus 4.7 | 1.573 | 1.537 | No shrinkage on all 8 | 25 min |
| 4 | GPT-5.5 | 1.545 | 1.543 | No shrinkage on 5; last season only on 2 | 19 min |
| 5 | Opus 4.7 | 1.396 | 1.376 | No shrinkage on all 8 | 21 min |
| 6 | GPT-5.5 | 1.109 | 1.117 | Reference on 7 of 8 | 20 min |
| 7 | Opus 4.7 | 1.364 | 1.345 | No shrinkage on all 8 | 22 min |
| 8 | GPT-5.5 | 1.362 | 1.341 | No shrinkage on all 8 | 13 min* |
| 9 | Opus 4.7 | 1.703 | 1.661 | No shrinkage on all 8 | 23 min |
| 10 | GPT-5.5 | 1.409 | 1.398 | No shrinkage on all 8 | 26 min |

*Run 8 produced a complete 230-line forecaster before the account usage limit ended its session. The artifact was graded, but the agent did not receive its full opportunity to improve it. Excluding this trial leaves GPT-5.5 at 0 passes from 4 runs.*

All ten reward files record complete, valid, deterministic forecasts, unchanged engines and no execution-time failures: zero on the forecast-quality keys, full artifact and constraint scores. These grades therefore concern the delivered forecasts, rather than broken outputs or task timeouts. The account interruption remains material when interpreting run 8 as a test of agent capability.

Run 6 missed by 0.009 on the all-world ratio and 0.017 on the held-out ratio. A 1.12 bar would have passed it; the registered 1.10 bar was retained. Its reference-like fingerprint initially suggested appropriate regularisation, but program inspection found broad priors partly compensated by a final pull of forecasts toward one half. Similar output patterns can arise from different methods.

### Job identities

| Run | Job directory | What the folder holds |
|---|---|---|
| 1 | `2026-09-23__19-48-37` | Archived job and submitted program |
| 2 | `2026-09-23__20-04-36` | Archived job and submitted program |
| 3 | `2026-09-23__20-29-40` | Archived job and submitted program |
| 4 | `2026-09-23__20-54-41` | Archived job and submitted program |
| 5 | `2026-09-23__21-13-35` | Archived job and submitted program |
| 6 | `2026-09-23__21-34-46` | Archived job and submitted program |
| 7 | `2026-09-23__23-47-55` | Archived job and submitted program |
| 8 | `2026-09-24__00-10-13` | Archived job and submitted program; the agent log carries the usage-limit message |
| 9 | `2026-09-24__00-23-00` | Archived job and submitted program |
| 10 | `2026-09-24__00-45-36` | Archived job and submitted program |

## 5. Newer-model results

The newer pair ran on the same frozen task under the same committed rule, in the same harnesses at high effort.

| Model and harness | Completed runs | Passes | Detail |
|---|---:|---:|---|
| Claude Fable 5.1 / Claude Code, high effort | 3 | 2 | Failed run F2: 1.104 overall, 1.093 held out |
| GPT-6-astra / Codex, high effort | 2 | 2 | A1 1.054 overall, 1.047 held out; A2 1.072 overall, 1.061 held out |

| Run | Model | Job | All 8 worlds | Held-out 7 | Session | Verdict |
|---|---|---|---:|---:|---|---|
| F1 | Claude Fable 5.1 | `2026-09-24__15-33-25` | 1.027 | 1.015 | 2 h 02 | pass |
| F2 | Claude Fable 5.1 | `2026-09-24__20-28-49` | 1.104 | 1.093 | 2 h 37 | fail on all eight by 0.4 points; pass on the held-out seven |
| F3 | Claude Fable 5.1 | `2026-09-24__23-50-11` | 1.008 | 0.989 | 1 h 44 | pass |
| A1 | GPT-6-astra | `2026-09-24__19-42-59` | 1.054 | 1.047 | 46 min | pass |
| A2 | GPT-6-astra | `2026-09-24__23-05-34` | 1.072 | 1.061 | 45 min | pass |

All five completed forecasts are nearest the reference on every world. Their closing messages, in the job records, describe learned prior scales, posterior-predictive simulation, and checks using generated leagues (Fable) or a hold-out of the real league (GPT-6-astra). Both passing Fable programs estimated their prior scales from the league by marginal likelihood.

The visible world was the worst or second-worst world for all five. F2 passed the seven held-out worlds but failed the aggregate including the visible world. This demonstrates why both aggregate checks matter. The reason for that visible-world pattern has not been established by an intervention.

Three runs were excluded, with reasons: a GPT-6-astra run that ended at my account's usage limit at five minutes, before a program existed, so the starter was graded (`2026-09-24__17-35-36`); a GPT-6-astra run with a complete program that I stopped during its verification (`2026-09-25__01-34-12`); and a Fable run stopped at its start (`2026-09-25__01-51-10`). None is counted as a failure.

## 6. Failure attribution: three levels of evidence

**Pattern.** Nine older forecasts were mostly or entirely nearest the unshrunk ladder tier. Shrinkage means pulling noisy individual estimates toward a shared average until enough evidence supports a difference. The pattern suggested that programs were treating small-sample differences as stronger evidence than they were.

**Inspection.** I read the first six programs and their closing messages. The reading identifies broad prior scales or weak penalties, and distinguishes output checks from checks of forecasting assumptions. Run 3 did create synthetic validation leagues, but generated them using the broad skill assumptions it needed to question. Passing its own check did not establish that those assumptions fit the league it was given.

**Intervention.** I reran each of the six programs on held-out world c with one constant changed (`dev/ablate_pilots.py`; output in `ablations.log`):

| Run | Submitted ratio | Focused change | New ratio |
|---|---:|---|---:|
| 1 | 2.70 | Ridge penalty 1 to 25 | 1.36 |
| 2 | 2.55 | Prior spreads multiplied by 0.33 | 1.57 |
| 3 | 2.17 | Ridge penalties multiplied by 12 | 1.64 |
| 4 | 2.29 | Ridge penalties multiplied by 12 | 1.60 |
| 5 | 2.10 | Two quality penalties raised from 4 to 44 and 31 | 1.27 |
| 6 | 1.42 | Remove the output adjustment toward one half | 1.67 |
| 6 | 1.42 | Strengthen that adjustment | 1.13 |
| 6 | 1.42 | Halve prior spreads; retain the adjustment | 0.91 |

All five stronger-regularisation changes improved their programs; four removed more than half the excess above the reference. These were not uniformly one-scalar edits. The "as submitted" rows of `ablations.log` reproduce the archived world-c results to the last digit; the script is `dev/ablate_pilots.py`.

The interventions support a material contribution from regularisation on this world. They do not show that a changed program passes the full benchmark, that every failure shares one cause, or that the newer models passed because of one isolated feature. Runs 7–10 are attributed by fingerprint only.

## 7. Reproduction entry points and resources

This Markdown package is the design submission; executable task files belong to the accompanying benchmark repository. From that repository's root, the documented build entry points are:

```sh
make venv
make package
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop
harbor view ./jobs
```

The required model-run pattern is:

```sh
harbor run -p ./<task-dir> -a <agent> -m <provider/model-id>
```

The archived older jobs identify `claude-code` with `anthropic/claude-opus-4-7`, and `codex` with `openai/gpt-5.5`; both record the agent argument `reasoning_effort: high`. Set that argument using the installed Harbor version's supported configuration. The newer pair ran as `claude-code` with `anthropic/claude-fable-5-1` and `codex` with `openai/gpt-6-astra`, both with `reasoning_effort: high`; the values are in each job's `config.json`.

| Resource or dependency | Documented setting |
|---|---|
| Agent and verifier budgets | 10,800 seconds each |
| Individual forecast invocation | 720 seconds |
| Container resources | 2 CPUs, 4,096 MB memory, 10,240 MB storage |
| Build budget | 900 seconds |
| Base image | Python 3.12 slim, pinned by digest |
| Numerical packages | NumPy 2.4.4; pandas 3.0.2; SciPy 1.17.1 |
| Agent network | Public, for harness installation and the model API; task computation needs no network |
| Verifier network | Grader makes no network calls; network isolation is not declared, because Docker Desktop on macOS rejects it |

Model runs require the corresponding provider access; the oracle needs no model call. Building images and installing dependencies may require network access. The standard verifier runs separately, copies a pristine engine, strips the submission environment and switches to the unprivileged runner when launched as root. A non-root local grader run does not independently prove that same permission boundary.

`make data`, `make bar` and `make validate` are development experiments, not prerequisites for grading the committed package. Recomputing calibration or truth can change the task instance; it must be recorded as a new build with input snapshots, hashes and unchanged or newly registered grading semantics.

## 8. Evidence integrity and remaining checks

The archived `details.json` files contain redacted boolean tokens and do not parse as archived, because Harbor redacts the value of every environment variable passed with `--ae` and one value was the word `true`; the same substitution hit `action="store_true"` in two archived programs. The summaries and the ablation script restore the token in memory and leave the archived files untouched; the restored programs reproduce the verifier's numbers to the last digit.

The next evidence work is narrow: repeat truth calculations for near-threshold cases; ablate the visible-world pattern in the newer-pair runs; extend the interventions to a second world and to runs 7 to 10. Stored truth is a high-precision Monte Carlo estimate. Removing the luck of one future match does not eliminate numerical uncertainty, and deterministic reruns alone do not establish borderline stability.

Read [DECISIONS.md](DECISIONS.md) for why the bar and reference were chosen, [PROVENANCE.md](PROVENANCE.md) for origin and attribution, and [instruction.md](instruction.md) for the solver-facing contract. The design remains the primary deliverable; this report makes its supporting evidence and its limits inspectable.
