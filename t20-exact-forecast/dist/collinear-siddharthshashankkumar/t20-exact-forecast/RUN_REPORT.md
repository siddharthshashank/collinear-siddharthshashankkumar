# Run report

**t20-exact-forecast · Siddharth Shashank Kumar · September 2026**

This report separates three things: what the task checks, what the recorded trials show, and what remains uncertain. The canonical requirements are the supplied [assignment sections 4–9](ASSIGNMENT_BRIEF.md). They require GPT-5.5-high or Claude Opus 4.7 evidence; the other model trials below are supplementary.

The evaluated prompt, engine, data, oracle and verifier are preserved. Reviewer documentation and packaging have been revised. Fresh validation is recorded separately in [VALIDATION.md](VALIDATION.md).

## 1. Result at a glance

The original oracle passed every reward component at **1.0**, and the no-op starter scored **0.0 overall**. All ten archived submissions from the required models missed the forecasting rule: five Opus 4.7 and five GPT-5.5 submissions, using their native harnesses with high reasoning effort.

Two qualifications belong beside that result. GPT-5.5 run 6 is near enough to the threshold that uncertainty in the reference affects the interpretation. Run 8 hit an account limit after producing its program; excluding it leaves GPT-5.5 at 0/4. Neither qualification changes the clear failures in the other trials.

For a representative failure, inspect **GPT-5.5 run 2**:

| Evidence | File |
|---|---|
| Harness, model and high-effort setting | [Trial configuration](jobs/2026-09-23__20-04-36/t20-exact-forecast__MteQG7J/config.json) |
| Overall 0.0; constraints and artifact quality 1.0 | [Reward](jobs/2026-09-23__20-04-36/t20-exact-forecast__MteQG7J/verifier/reward.json) |
| Total ratio 1.575; held-out ratio 1.613 | [Per-world results](jobs/2026-09-23__20-04-36/t20-exact-forecast__MteQG7J/verifier/details.json) |
| Submitted implementation | [forecast.py](jobs/2026-09-23__20-04-36/t20-exact-forecast__MteQG7J/artifacts/app/solution/forecast.py) |
| What the agent inspected and checked | [Codex transcript](jobs/2026-09-23__20-04-36/t20-exact-forecast__MteQG7J/agent/codex.txt) |

This submission ran, respected the measured constraints and produced valid probabilities. It failed the central forecasting requirement by a substantial margin. Section 7 explains the diagnosis.

## 2. The rule behind every verdict

Each of eight worlds has 24 fixtures. For stored home-win probability `p` and submitted probability `q`:

```text
q      = clip(q, 0.002, 0.998)
regret = p * ln(p / q) + (1 - p) * ln((1 - p) / (1 - q))
```

The verifier averages regret over each world's fixtures, then sums the world averages. A submission must have at most **1.10 times** the reference sum on all eight worlds and separately on the seven held-out worlds. The absolute tolerance is zero.

| Reward field | Meaning |
|---|---|
| `functional_correctness` | All-eight-world rule passed |
| `robustness` | Held-out-seven rule passed |
| `constraint_satisfaction` | Mean of three checks: original engine files unchanged, visible-world output repeated within `1e-12`, every initial world run under 720 seconds |
| `artifact_quality` | Fraction of worlds with a readable, complete, finite forecast in [0, 1] |
| `overall` | Functional correctness × (0.5 × robustness + 0.25 × constraints + 0.25 × artifact quality) |

Only **overall = 1.0** counts as solved. A missing or failed submission can still receive partial component credit; it cannot satisfy the full success rule.

The rule in `harbor/bar.json` was committed before the first pilot, job `2026-09-23__19-48-37`. The original commit is titled “Harbor metadata, pass bar, lock file, instruction”. The documentation revision does not change it.

### What “exact” means here

The grader evaluates expected loss against **stored probability estimates**, not a newly sampled match outcome. Those estimates come from 100,000 simulated matches per batting order. Scoring is repeatable, but the underlying probabilities are Monte Carlo estimates.

The reference forecast is also simulated, at 4,000 copies per batting order. Development resimulations in `bar.log` imply about **1.14%** relative variation in pooled reference regret. That makes ratios around 1.08–1.12 a useful caution band around the 1.10 threshold, not a formal confidence interval for each trial.

GPT-5.5 run 6 at 1.109 and supplementary Fable run F2 at 1.104 fall in that band. Their fixed-rule verdicts remain recorded as failures; neither is strong evidence of a clear statistical separation from the pass threshold. The submission's target-model failure claim does not depend on them.

## 3. Environment and reproducibility boundaries

| Item | Recorded configuration |
|---|---|
| Harness | Harbor 0.23.0, schema 1.4, local Docker |
| Original host | macOS on Apple silicon, Docker Desktop |
| Images | Python 3.12 slim, identical base digest in agent and verifier Dockerfiles |
| Base digest | `sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea` |
| Primary packages | NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1 |
| Resources | 2 CPUs, 4,096 MB memory, 10,240 MB storage requested |
| Build budget | 900 seconds |
| Session budgets | Agent: 10,800 seconds; verifier: 10,800 seconds |
| Program budget | 720 seconds per world |
| Model configuration | Native Codex or Claude Code harness; `reasoning_effort=high` in trial configs |
| Network | Agent environment explicitly public for harness installation and API access; verifier network mode omitted, so no network isolation is claimed |
| Program network rule | Handbook prohibits network use; the forecasting task needs no external data |

The base image and three direct dependencies are pinned. Transitive Python dependencies are not fully locked or hash-pinned, and model harness installations may change between reruns. These are limits on byte-for-byte reproducibility. The committed data avoid having to regenerate the original calibration to run the task.

The verifier makes no intended network calls. That is distinct from preventing submitted code from doing so. The original report attributed the omitted isolation setting to Docker Desktop compatibility; this revision does not treat that historical explanation as a verified platform-wide limitation.

Original jobs used the author's subscriptions. Provider access is required to repeat model trials. Oracle and no-op checks need Docker but no model credentials. Harbor's optional `check` command is an LLM-based review and does require model access.

## 4. Positive and negative controls

| Run | Job record | Overall | Functional | Robustness | Constraints | Artifact |
|---|---|---:|---:|---:|---:|---:|
| Oracle | [2026-09-23__19-38-27](jobs/2026-09-23__19-38-27/) | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| No-op starter | [2026-09-23__19-33-46](jobs/2026-09-23__19-33-46/) | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 |

The oracle installs the reference as a submission through the same interface used by agents. Its total regret ratio is 1.000. The no-op starter predicts 0.5 everywhere and scores 1.891 times reference regret.

The earlier oracle attempt, [2026-09-23__19-33-12](jobs/2026-09-23__19-33-12/), failed because of a shell assignment error in `solve.sh`. The solution was never installed, so the starter was graded. That is a packaging failure, not a model result, and it remains in the record.

Harbor's historical task check, [2026-09-24__12-21-19](jobs/2026-09-24__12-21-19/), passed 11 review criteria. It is a language-model review of the task package, not the task's reward mechanism, not a trajectory judge, and not a deterministic security test.

The comparison methods also miss the 1.10 limit: last season only 1.50, no shrinkage 1.59, coin flip 1.89, team ratings 3.23 and raw head-to-head 4.01. These ratios are derived from `task_data/private/*/reference.json`. The last-season baseline has a validation defect noted in Section 13, so it should not carry the argument on its own.

Fresh oracle and no-op results are separate from these original gates; see [VALIDATION.md](VALIDATION.md).

## 5. Required-model trials

All trials below follow the committed rule, using the same task and high reasoning effort.

| Run | Model | Job | Total / reference | Held-out / reference | Nearest comparison | Session |
|---|---|---|---:|---:|---|---|
| 1 | Opus 4.7 | [2026-09-23__19-48-37](jobs/2026-09-23__19-48-37/) | 1.533 | 1.492 | No shrinkage, 6/8 worlds | 16 min |
| 2 | GPT-5.5 | [2026-09-23__20-04-36](jobs/2026-09-23__20-04-36/) | 1.575 | 1.613 | No shrinkage, 7/8 | 25 min |
| 3 | Opus 4.7 | [2026-09-23__20-29-40](jobs/2026-09-23__20-29-40/) | 1.573 | 1.537 | No shrinkage, 8/8 | 25 min |
| 4 | GPT-5.5 | [2026-09-23__20-54-41](jobs/2026-09-23__20-54-41/) | 1.545 | 1.543 | No shrinkage 5; last season 2 | 19 min |
| 5 | Opus 4.7 | [2026-09-23__21-13-35](jobs/2026-09-23__21-13-35/) | 1.396 | 1.376 | No shrinkage, 8/8 | 21 min |
| 6 | GPT-5.5 | [2026-09-23__21-34-46](jobs/2026-09-23__21-34-46/) | 1.109 | 1.117 | Reference, 7/8 | 20 min; borderline |
| 7 | Opus 4.7 | [2026-09-23__23-47-55](jobs/2026-09-23__23-47-55/) | 1.364 | 1.345 | No shrinkage, 8/8 | 22 min |
| 8 | GPT-5.5 | [2026-09-24__00-10-13](jobs/2026-09-24__00-10-13/) | 1.362 | 1.341 | No shrinkage, 8/8 | 13 min; account limit after program written |
| 9 | Opus 4.7 | [2026-09-24__00-23-00](jobs/2026-09-24__00-23-00/) | 1.703 | 1.661 | No shrinkage, 8/8 | 23 min |
| 10 | GPT-5.5 | [2026-09-24__00-45-36](jobs/2026-09-24__00-45-36/) | 1.409 | 1.398 | No shrinkage, 8/8 | 26 min |

All ten received 1.0 for artifact quality and constraints. Their overall failures came from forecast regret. Opus passed 0/5; GPT-5.5 passed 0/5 graded submissions, or 0/4 with run 8 excluded. These are observed counts, not estimates that either model always fails.

“Nearest comparison” is a diagnostic resemblance measured from forecasts. It is not, by itself, proof of why a program failed.

## 6. Supplementary trials and exclusions

These trials are useful solvability evidence but are not required by the canonical brief.

| Run | Model | Job | Total / reference | Held-out / reference | Session | Recorded verdict |
|---|---|---|---:|---:|---|---|
| F1 | Fable 5.1 | [2026-09-24__15-33-25](jobs/2026-09-24__15-33-25/) | 1.027 | 1.015 | 2 h 02 | Pass |
| F2 | Fable 5.1 | [2026-09-24__20-28-49](jobs/2026-09-24__20-28-49/) | 1.104 | 1.093 | 2 h 37 | Fail on all-world rule; borderline |
| F3 | Fable 5.1 | [2026-09-24__23-50-11](jobs/2026-09-24__23-50-11/) | 1.008 | 0.989 | 1 h 44 | Pass |
| A1 | GPT-6-astra | [2026-09-24__19-42-59](jobs/2026-09-24__19-42-59/) | 1.054 | 1.047 | 46 min | Pass |
| A2 | GPT-6-astra | [2026-09-24__23-05-34](jobs/2026-09-24__23-05-34/) | 1.072 | 1.061 | 45 min | Pass |

The passing programs estimated prior scales from data and used checks intended to challenge their estimates. Fable passed 2/3 and GPT-6-astra 2/2 completed trials. These small samples support solvability; they do not establish a broad comparison between model generations.

Four jobs are excluded from substantive pass-rate claims:

| Job | Model | Reason |
|---|---|---|
| [2026-09-24__17-35-36](jobs/2026-09-24__17-35-36/) | GPT-6-astra | Account limit before a solution existed; verifier graded the starter |
| [2026-09-25__01-34-12](jobs/2026-09-25__01-34-12/) | GPT-6-astra | Operator stopped the run during verification after a program was written |
| [2026-09-25__01-51-10](jobs/2026-09-25__01-51-10/) | Fable 5.1 | Stopped at the beginning |
| [2026-09-24__19-41-42](jobs/2026-09-24__19-41-42/) | Fable 5.1 | Cancelled after 72 seconds when the loop was restarted |

There are **19 original model jobs: 15 included graded submissions, one excluded starter-only grade, and three jobs without a completed grade**. The original oracle attempts, no-op gate and task check are separate. New validation jobs are stored outside this historical series.

## 7. Failure analysis

The strongest diagnosis combines reading the programs with an intervention. The first six programs used the documented match mechanism but set prior scales that allowed too much variation in player estimates. The historical analysis places their shrinkage penalties roughly 3–44 times below the relevant quality penalty.

Four of the six checked execution, determinism or output shape. Run 5 also checked symmetry and range. Run 3 generated its own validation leagues, but used the same loose priors that its estimator assumed. That check supported the assumption instead of testing whether the supplied history justified it.

The interventions changed one setting at a time and reran each program on **held-out world c**. The original forecasts reproduced the archived world scores before edits were applied.

| Program | As submitted / reference | Intervention | After / reference |
|---|---:|---|---:|
| Opus run 1 | 2.70 | Common ridge 1 → 25 | 1.36 |
| GPT-5.5 run 2 | 2.55 | Prior standard deviations × 0.33 | 1.57 |
| Opus run 3 | 2.17 | Ridge penalties × 12 | 1.64 |
| GPT-5.5 run 4 | 2.29 | Ridge penalties × 12 | 1.60 |
| Opus run 5 | 2.10 | Quality ridges set to generating-scale values | 1.27 |
| GPT-5.5 run 6 | 1.42 | Remove output hedge | 1.67 |
| GPT-5.5 run 6 | 1.42 | Deepen output hedge to 0.75 | 1.13 |
| GPT-5.5 run 6 | 1.42 | Prior standard deviations × 0.5; keep hedge | 0.91 |

Evidence: [ablations.log](ablations.log), `dev/ablate_pilots.py`, and the submitted programs in the jobs above. The reviewer repeated these interventions independently, as recorded in Section 13.

The results support **overconfident estimation combined with ineffective validation** as a failure mode in those six programs. They do not establish that one edit would pass the whole task, and they are not new model trials. Runs 7–10 have resemblance evidence but no equivalent intervention here.

## 8. Reproduction commands

### From a source checkout

Start at the Git repository root:

```sh
cd t20-exact-forecast
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
harbor view ./jobs
```

Run either target model to satisfy the brief's model choice; both are shown for reproducibility. Credentials must be configured through the chosen harness/provider. No live target-model trial was added by the documentation revision; the original evidence is included unchanged.

### From the submission zip

Extract it, enter `collinear-siddharthshashankkumar/`, then:

```sh
harbor run -p ./t20-exact-forecast -a oracle
harbor run -p ./t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
harbor run -p ./t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
harbor view ./jobs
```

The extracted task's `jobs/` directory contains the original evidence; new runs above create a sibling `jobs/` directory. Use `harbor view ./t20-exact-forecast/jobs` to inspect the archived series.

### Rebuild reviewer artifacts and audit evidence

From `t20-exact-forecast/` in the source checkout:

```sh
make venv PYTHON=python3.12
make package
make audit
make submission
.venv/bin/python dev/ablate_pilots.py heldout_c
```

The ablation script reads archived programs directly from `jobs/`; no external program folder is needed. The optional command below runs Harbor's model-based task review and may incur provider charges:

```sh
harbor check ./dist/collinear-siddharthshashankkumar/t20-exact-forecast
```

The committed worlds are sufficient for normal reproduction. `make data` can regenerate synthetic data, but its cache checks only some parameters; it is not proof of a clean rebuild after source changes. Recreating the calibration additionally requires the untracked original Cricsheet archive, whose download hash was not recorded.

## 9. Realism, economic value and long-horizon difficulty

The useful output is a repeatable forecasting program: an analytics team can give it a fresh league folder and obtain probabilities for new fixtures. The work resembles the estimation and validation needed by sports analytics teams, while avoiding claims that this simplified simulator predicts real matches.

The agent must connect data inspection, estimation, simulation, validation and packaging. A bad uncertainty assumption can survive all the engineering steps and still produce a poor forecast. That dependency between steps creates the long-horizon difficulty.

Data generation and reference calculations are done once. Grading reuses the stored inputs, making repeated trials practical. The oracle is fast, but candidate compute and model-session costs vary; no financial return or production performance has been measured.

## 10. Verifier design and failure interpretation

The agent sees public history, code and documentation. The separate verifier image contains all eight worlds, the stored probabilities, reference regrets, comparison forecasts and the grading rule. It copies the submitted solution, checks original engine files against their hashes, then runs the program next to a pristine engine.

Inside the intended image, the grader runs as root and launches candidate code as `runner`; `/tests` is unreadable to that user. Each initial world run has a 720-second timeout. The visible world is run again for repeatability. Valid forecasts are scored programmatically. No LLM decides the reward or judges the trajectory.

`tests/test.sh` writes a zero reward if the grader fails to produce one. The grader also records exceptions in `details.json`. **Always inspect the error information before interpreting a zero as model failure.** A zero fallback prevents an accidental pass but does not distinguish infrastructure failure by itself.

The baseline and comparison results show that several plausible shortcuts fail. They do not prove that every shallow or adversarial strategy is rejected. In particular:

- The verifier's network isolation is not explicitly configured.
- Privilege separation relies on the intended root-run image; a non-root local invocation does not provide the same boundary.
- Timeout handling does not explicitly clean up a whole descendant process group.
- The runtime component can credit a missing or quickly failing program as “in time”; functional and artifact checks still prevent a full pass.
- Repeatability compares probability arrays in row order on the visible world, rather than aligning fixture IDs across all worlds.
- Extra output rows can be ignored after reindexing, and added engine files are not rejected by the original-file hash check.

These are disclosed weaknesses of the frozen verifier, not claims that the documented target-model failures exploited them.

## 11. Fairness audit

| Question | Assessment |
|---|---|
| Are the task contract and scoring rule available? | The prompt and handbook state the schemas, formula, tolerances, runtime, determinism and engine constraints. The wording overstates probability exactness and understates the reference's design advantage. |
| Can the task be solved through the agent's interface? | Yes: the oracle and four supplementary submissions pass. This supports solvability, not equal information at design time. |
| Does the reference have an advantage? | Yes. It reads public inputs at runtime, but its base prior scales were chosen with knowledge of the generating spreads. The size of that advantage is not directly measured. |
| Do near-threshold failures count as strong evidence? | No. The fixed-rule verdict is retained, but the two borderline failures are flagged. Clear failures elsewhere satisfy the target-model evidence requirement. |
| Were infrastructure failures separated? | The first oracle error and four excluded model jobs are listed separately. GPT run 8 is counted with an interruption flag and an exclusion sensitivity count. |
| Was the rule adjusted after model trials? | No scoring or runtime change is made in this documentation revision; the historical pre-pilot rule remains. |
| Does AI-assisted design introduce possible bias? | Possibly. Cross-family passes and same-family failures provide context, but do not rule out design bias. Assistance is disclosed. |
| Is a human completion time measured? | No. Metadata contains an estimate; no human baseline was run. |

## 12. Evidence integrity and open work

The original `jobs/` tree contains 23 job directories: nineteen model jobs, two oracle attempts, one no-op gate and one task check. Sixteen model jobs have verifier output, including the excluded starter-only run; three ended without a completed grade.

A historical Harbor redaction replaced the literal token `true` with `[REDACTED]` in some records. That makes some archived JSON invalid and changes `store_true` in two programs. The audit and ablation tools restore that known literal in memory and leave raw evidence untouched. This restoration is documented; it is not permission to infer unknown redacted values.

The current audit checks trial configurations, reward fields, rounded regret summaries and artifact presence. It does not rerun every model or establish the complete correctness of every archived transcript. Fresh control runs and verifier-contract checks are recorded in [VALIDATION.md](VALIDATION.md).

Open work includes an independent-stream truth audit, a reference with learned prior scales, interventions on more worlds and programs, investigation of the visible-world performance pattern, a human baseline, and verifier hardening.

## 13. Independent review

The repository records a review by Rutvikk Kharod on 26 September 2026 at revision `9da6375`. The existing review account says he recomputed graded verdicts and pooled reference variation, checked the freeze, and repeated the eight interventions on Windows with the pinned libraries. Those review claims are retained as historical evidence; the new checks in this revision are identified separately.

| Finding | Original response and current status |
|---|---|
| Drawing attribution | Six architecture drawings attributed to Rutvikk Kharod, used with permission |
| Near-threshold uncertainty | Disclosed beside result claims; borderline misses are not presented as clear separation |
| Reference advantage | Designer-informed prior scales disclosed; advantage remains unmeasured |
| Layout, linter count and missing cancelled job | Repository/zip distinction clarified, 11 review checks reported, fourth exclusion listed |
| Windows line endings | Existing `.gitattributes` pins relevant files to LF |
| Ablation reproduction | Script now reads programs from committed jobs and copies the engine |
| Partial package acceptance | Packaging revision checks all required worlds and inputs before replacing the assembled task |
| Last-season comparison | Validation uses zero-weight seasons and selects the weakest scale; baseline limitation retained |
| `History.played` | Documented field remains empty; raw historical line-ups are in `lineups.csv` |
| Verifier isolation and timeout weaknesses | Still present in the evaluated runtime; disclosed in Section 10 |
| Data cache ignores some inputs | Still present; fresh regeneration after source changes must be deliberate |
| Calibration counting issues | Wicket/dismissal and no-result treatment affect realism; no recalibration is included |
| Missing development tests | This revision adds focused verifier-contract and submission-evidence checks; it is not a full simulator test suite |

Fixes that alter the task or verdicts need a newly evaluated version. The documentation revision preserves the existing experiment and makes its strengths and limitations easier to inspect.
