# Run report

**t20-exact-forecast · Siddharth Shashank Kumar · September 2026**

This report separates three things: what the task checks, what the recorded trials show, and what remains uncertain. The [full assignment](ASSIGNMENT_BRIEF.md) names GPT-5.5-high / Opus 4.7 in the goal and explicit run requirement, but GPT-6-astra-high / Fable 5.1 in the target-outcome paragraph. I treat the repeated goal/run requirement as primary and report the other pair separately. That is an interpretation; this version does not establish a clean failure under the stricter newer-pair reading. [DECISIONS.md](DECISIONS.md) and [ASSUMPTIONS.md](ASSUMPTIONS.md) explain the approach and remaining uncertainty.

The current submission is **v0.1.1**. It hardens the verifier, clarifies the agent-facing contract, and locks the existing dependency versions. The engine, data, oracle, reference regrets and scoring rule are unchanged. The original **v0.1.0** evaluation and review are labeled separately below. Current controls and the artifact replay are recorded in [VALIDATION.md](VALIDATION.md). Section 5 separates the first fresh model attempt from the later fixed eight-trial batch in [REPLICATION_REPORT.md](REPLICATION_REPORT.md).

## 1. Result at a glance

**Current v0.1.1 controls and first model trial:** the oracle passes all five components, no-op fails overall, and the first fresh GPT-5.5-high attempt fails forecast quality with **1.230×** total and **1.246×** held-out regret. Its constraints and artifact scores are **1.0**, with no infrastructure exception. [Current trial analysis](#fresh-v011-trial) and [validation records](VALIDATION.md) document this separate result. The later [replication batch](REPLICATION_REPORT.md) adds two fresh attempts per model; both Astra and both Fable submissions pass the current task.

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

The rule in `harbor/bar.json` is present in commit `99b2d9f` (23 September, 18:59 CDT), before the first archived model job, `2026-09-23__19-48-37`. The older development notes describe a separate prototype and an earlier September 19 freeze/pilot sequence in another repository. This checkout establishes the ordering for the shipped evaluation series; it does not independently verify the earlier sequence.

### What “exact” means here

The grader evaluates expected loss against **stored probability estimates**, not a newly sampled match outcome. Those estimates come from 100,000 simulated matches per batting order. Scoring is repeatable, but the underlying probabilities are Monte Carlo estimates.

The reference forecast is also simulated, at 4,000 copies per batting order. The previously reported **1.14%** pooled variability is an independence approximation, not a directly measured pooled standard deviation. It is reconstructed as `sqrt(sum((r_i * s_i)^2)) / sum(r_i)` from rounded per-world reference regrets `r_i` and relative standard deviations `s_i` in `bar.log`. That calculation omits cross-world covariance. The code reuses simulation seeds and fixture IDs across worlds, and the raw repeat vectors were not retained, so their covariance cannot be recovered from this log.

The earlier 1.08–1.12 caution range should therefore not be treated as an established uncertainty interval. GPT-5.5 run 6 at 1.109 and supplementary Fable run F2 at 1.104 are small fixed-rule misses; without a direct uncertainty analysis, neither supports a clean separation from the 1.10 threshold. The failure claim rests on the much larger misses elsewhere. A stronger audit would retain the full repeat matrix and measure pooled variation directly under explicit simulation streams.

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
| Network, v0.1.1 | Agent environment public for harness setup/API access; verifier Docker Compose service uses `network_mode: none` |
| Program network rule | Handbook prohibits network use; the forecasting task needs no external data |

The Python base image is pinned by digest. In v0.1.1, all five packages in the Linux numerical dependency closure are version- and hash-locked: NumPy, pandas, SciPy, python-dateutil 2.9.0.post0 and six 1.17.0. These match the previously used versions. Native model-harness installers are still separate provider tooling; their versions are recorded in each trial rather than presented as immutable task dependencies.

The original verifier omitted a network policy. For v0.1.1, Docker Compose disables the verifier container's network directly. Harbor 0.23's nftables capability probe returns false on the tested Docker Desktop kernel, so the Harbor baseline remains explicitly public with a metadata explanation; the service's actual network is `none`. [Container inspection evidence](validation/network-isolation.json) confirms the configuration of inspected Harbor verifier containers, including the fresh model trial. This is a tested host-specific workaround, not a claim that all Docker Desktop installations lack Harbor network-policy support. See Harbor's [network policy](https://docs.harborframework.com/core-concepts/tasks/network-policies) and [separate verifier](https://docs.harborframework.com/core-concepts/tasks/separate-verifier) documentation for the distinction between environment configuration and phase policy.

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

These are the original v0.1.0 trials under the committed rule, with high reasoning effort recorded in their native-harness configurations. They are historical model attempts, not fresh v0.1.1 trials.

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

### Fresh v0.1.1 trial

The revised runtime was committed before a new GPT-5.5-high attempt through the native Codex harness. It completed on 27 September in **32 minutes 4 seconds** and received **overall 0.0**: total regret **1.230×** and held-out regret **1.246×**, against the unchanged **1.10×** limit. Constraint satisfaction and artifact quality were both **1.0**. There was no infrastructure exception; all eight initial world runs finished in **75–87 seconds**, well within the 720-second limit. The [reward](validation/jobs/revision-gpt55-high/t20-exact-forecast__7VMTU5v/verifier/reward.json), [per-world details](validation/jobs/revision-gpt55-high/t20-exact-forecast__7VMTU5v/verifier/details.json) and [trial result](validation/jobs/revision-gpt55-high/t20-exact-forecast__7VMTU5v/result.json) preserve the evidence. This is a new model attempt, separate from both the historical series and the replay of run 2.

This agent fitted a regularized ball-level likelihood and used the public simulator for fixture probabilities. It predicted 90 later matches in each of two forward season splits. The initial outcome log losses were **0.684862** and **0.680139**, compared with **0.693147** for a coin flip. It then added match-day effects, tested role/style baselines, and removed those baselines after slightly worse sampled validation. The final visible-world execution took **73.443 seconds** in its own check. It verified the 24 fixture IDs, finite in-range probabilities, syntax and ordinary-file deliverable.

Those are meaningful checks. They do not directly establish performance against stored probability estimates or the stronger reference on unseen leagues. The delivered program retains fixed prior scales, recency weighting and future-effect assumptions; the transcript shows no prior-scale search or uncertainty analysis. These are possible sources of error, not a demonstrated causal diagnosis of this new artifact. No intervention on it has been run. Its final response claims implementation and interface verification, not that it passed a hidden verifier.

Evidence: [transcript](validation/jobs/revision-gpt55-high/t20-exact-forecast__7VMTU5v/agent/codex.txt), lines 45, 51, 54, 63–64, 71, 76, 86 and 96–97; [delivered program](validation/jobs/revision-gpt55-high/t20-exact-forecast__7VMTU5v/artifacts/app/solution/forecast.py), especially the prior settings, optimization and simulation sections. The small outcome-loss differences are observations from two noisy historical splits; they are not significance claims.

### Fixed eight-trial replication batch

A separate, predeclared batch adds two new high-effort attempts per model on the current task: GPT-5.5 and GPT-6-astra through Codex, and Opus 4.7 and Fable 5.1 through Claude Code. All eight completed normally without retries. Passes were **GPT-5.5 1/2, Opus 4.7 0/2, GPT-6-astra 2/2 and Fable 5.1 2/2**. The three failures missed both forecast gates while receiving full artifact and constraint scores. Its [protocol, individual results and analysis](REPLICATION_REPORT.md) retain every slot, including the passing GPT-5.5 program. The earlier v0.1.1 GPT-5.5 trial above remains outside that batch. The v0.1.0 tables below also remain separate.

## 6. Supplementary trials and exclusions

These trials address the newer pair named in the brief's target-outcome paragraph. They are reported separately from the repeated goal/run requirement. Their passes and one borderline miss do not establish a clean newer-pair failure.

| Run | Model | Job | Total / reference | Held-out / reference | Session | Recorded verdict |
|---|---|---|---:|---:|---|---|
| F1 | Fable 5.1 | [2026-09-24__15-33-25](jobs/2026-09-24__15-33-25/) | 1.027 | 1.015 | 2 h 02 | Pass |
| F2 | Fable 5.1 | [2026-09-24__20-28-49](jobs/2026-09-24__20-28-49/) | 1.104 | 1.093 | 2 h 37 | Fail on all-world rule; borderline |
| F3 | Fable 5.1 | [2026-09-24__23-50-11](jobs/2026-09-24__23-50-11/) | 1.008 | 0.989 | 1 h 44 | Pass |
| A1 | GPT-6-astra | [2026-09-24__19-42-59](jobs/2026-09-24__19-42-59/) | 1.054 | 1.047 | 46 min | Pass |
| A2 | GPT-6-astra | [2026-09-24__23-05-34](jobs/2026-09-24__23-05-34/) | 1.072 | 1.061 | 45 min | Pass |

Fable passed 2/3 and GPT-6-astra 2/2 completed trials. These independently written programs support solvability through the agent interface. This is not a matched-compute comparison between model generations: the newer-pair sessions lasted roughly 45–157 minutes, versus 13–26 minutes for the goal-line pair, within the same nominal three-hour limit. Harnesses, model behavior and compute consumed are intertwined. The small samples do not isolate a general model-generation effect.

Four jobs are excluded from substantive pass-rate claims:

| Job | Model | Reason |
|---|---|---|
| [2026-09-24__17-35-36](jobs/2026-09-24__17-35-36/) | GPT-6-astra | Account limit before a solution existed; verifier graded the starter |
| [2026-09-25__01-34-12](jobs/2026-09-25__01-34-12/) | GPT-6-astra | Operator stopped the run during verification after a program was written |
| [2026-09-25__01-51-10](jobs/2026-09-25__01-51-10/) | Fable 5.1 | Stopped at the beginning |
| [2026-09-24__19-41-42](jobs/2026-09-24__19-41-42/) | Fable 5.1 | Cancelled after 72 seconds when the loop was restarted |

There are **19 original model jobs: 15 included graded submissions, one excluded starter-only grade, and three jobs without a completed grade**. The original oracle attempts, no-op gate and task check are separate. New validation jobs are stored outside this historical series.

## 7. Failure analysis

The strongest supported finding is **harmful prior choices that the programs' validation did not resolve before submission**. That is more precise than saying the agents skipped accuracy checks. Transcript review shows that several failed programs performed genuine predictive validation and used it to change their implementations.

### What the first six programs actually checked

| Run | Observed checks | What those checks did not establish | Evidence |
|---|---|---|---|
| Opus 1 | Tried ridge values 0.1, 0.5, 1, 2 and 5; printed fitted parameter norms | Parameter shrinkage alone is not held-out forecast quality | [Trajectory](jobs/2026-09-23__19-48-37/t20-exact-forecast__c9h8h85/agent/trajectory.json), step 16 |
| GPT-5.5 2 | Trained on 180 matches, predicted the next 90, and compared log loss with a coin flip | Beating a weak baseline on one realized season does not establish proximity to the reference | [Transcript](jobs/2026-09-23__20-04-36/t20-exact-forecast__MteQG7J/agent/codex.txt), completed commands at lines 50 and 55 |
| Opus 3 | Generated known-state synthetic leagues, tested drift and recovery, and checked repeatability | Its chosen synthetic distributions and inferred reference score did not validate against the actual hidden evaluation worlds | [Trajectory](jobs/2026-09-23__20-29-40/t20-exact-forecast__3xxkPgb/agent/trajectory.json), steps 23–34 |
| GPT-5.5 4 | Ran two rolling season holdouts, then compared them again after adding player-season form | Small gains on realized winners did not establish that its prior strengths were appropriate for the forecast criterion | [Trajectory](jobs/2026-09-23__20-54-41/t20-exact-forecast__4E7U8Nh/agent/trajectory.json), steps 15–19 |
| Opus 5 | Tested repeatability, weaker regularization, neutral-skill behavior and range | Inspecting changed forecasts or symmetry is not a predictive comparison | [Trajectory](jobs/2026-09-23__21-13-35/t20-exact-forecast__JJfpdQx/agent/trajectory.json), steps 16–20 |
| GPT-5.5 6 | Backtested two seasons, compared recency settings and swept a probability hedge | These checks detected overdispersion, but the chosen correction did not settle the underlying prior-scale problem | [Trajectory](jobs/2026-09-23__21-34-46/t20-exact-forecast__n37qg89/agent/trajectory.json), steps 14–25 |

The Opus 3 final report called its synthetic results approximately 0.67 and 0.64 times an *estimated* reference. It derived that yardstick from the handbook's rough aggregate coin-flip comparison. The real reference was not available to the agent, and that aggregate hint does not determine reference regret on a self-generated world. This is a specific unsupported validation conclusion, not evidence that synthetic testing itself is unsound.

### A representative failure: GPT-5.5 run 2

This program used the public ball mechanism, fitted latent effects and simulated fixtures. Its final artifact was valid, repeatable and within the measured runtime and engine constraints. The missed criterion was forecast quality: **1.575×** reference regret overall and **1.613×** on held-out worlds, against a **1.10×** limit.

The agent did more than a smoke test. It withheld season 2, trained on seasons 0–1, and evaluated 90 historical matches. Its mean log loss was **0.6863946**, compared with **0.6931472** for the coin flip. That small improvement was real in the test it ran. It was also a weaker proposition than the submission required: beating a coin flip on realized outcomes does not establish being close to a stronger reference against stored probabilities. The agent explicitly described this as a noisy sanity check, so it would be unfair to claim it confused the two scoring targets. The trajectory does not show a comparative prior-scale search for this program. It ended the session with a useful directional check, but without stronger evidence about the assumption that the later intervention showed to be costly.

The later intervention makes the diagnosis more concrete. On held-out world c, multiplying this program's prior standard deviations by 0.33 reduced its regret ratio from **2.55 to 1.57**. This supports weak shrinkage as a contributor to that artifact's error. It does not prove that the agent could have selected that multiplier from the public data, or that the edit would pass the full task.

### Interventions and their limits

The historical analysis found prior scales that allowed too much variation in fitted player effects, with shrinkage penalties roughly 3–44 times below the relevant generating-scale quality penalty. The interventions changed one setting at a time and reran each program on **held-out world c**. The unedited forecasts first reproduced the archived world scores.

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

Evidence: [ablations.log](ablations.log), `dev/ablate_pilots.py`, and the submitted programs in the jobs above. The historical reviewer repeated these interventions independently, as recorded in Section 13.

The result supports a causal effect of those settings on these programs on this world. It does not establish that one edit would pass every world, that no other defects mattered, or that all ten failures shared the same cause. Runs 7–10 have forecast-resemblance evidence but no equivalent intervention here. The ablations are diagnostic reruns using reviewer knowledge, not new model trials.

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

Run either target model to satisfy the brief's model choice; both are shown for reproducibility. Credentials must be configured through the chosen harness/provider. Original trial evidence is included unchanged; the current revision’s fresh trial is identified separately in [VALIDATION.md](VALIDATION.md).

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

The agent receives public history, code and the handbook. The separate verifier receives the submission and a copy of the engine, plus its own eight league folders, stored probabilities, reference regrets and comparison forecasts. Only the privileged grader reads the private scoring files.

The deeper audit found two ways the original grader could cross that boundary: dereferencing a submitted symlink while copying the solution, and following an output CSV symlink while reading a forecast. In disposable offline containers with synthetic truth, both routes earned a false full pass despite the runner being unable to read the private file directly. That made a code change necessary.

The v0.1.1 verifier now:

- Rejects symbolic links and special files before staging a solution; the privileged copy never dereferences candidate links.
- Opens output files through directory descriptors without following links, then checks exactly one finite probability per required fixture, without duplicates or extra IDs.
- Keeps the original forecast values in memory, requires a successful repeat process, and compares probabilities by fixture identity. Reordered equivalent rows pass; overwriting both CSVs cannot hide a changed answer.
- Runs candidate code as `runner` with supplementary groups cleared, beside the pristine engine. Added engine files fail the integrity check, except generated bytecode.
- Stops the process group after completion or timeout, and runs the verifier container without network access.
- Clears old reward files on entry. A grader startup failure produces zero reward and an explicit error rather than reusing a prior pass.

The formula and two regret gates are unchanged. No language model decides the reward or judges the trajectory. [VALIDATION.md](VALIDATION.md) links the 24 behavioral checks, before/after boundary probes, current Harbor controls and archived-program replay. Eight applicable regression tests fail on the old grader and pass on the new one, including a false rejection of equivalent row ordering.

A zero still needs interpretation. Inspect `details.json`: `submission_error` identifies an invalid delivered artifact; per-world problems identify failed execution or malformed output; `grader_error` signals a verifier exception. Infrastructure failure is not model-failure evidence.

There are remaining boundaries to the assurance. Repeatability is tested on the visible world only. Process-group cleanup does not contain a deliberately detached process without stronger PID/cgroup supervision. The Docker probe tests the grader's file boundary, not every possible Harbor transfer or operating-system attack. A non-root local invocation does not reproduce the private-file privilege boundary. The runtime component can still credit a missing or quickly failing program as “in time”; forecast validity and functional correctness prevent a full pass. These limits do not invalidate the targeted fixes, but they prevent a claim of a complete hostile-code sandbox audit.

## 11. Fairness audit

| Question | Assessment |
|---|---|
| Are the task contract and scoring rule available? | The prompt and handbook state the schemas, formula, tolerances, runtime, determinism and engine constraints. The original wording overstated precision and understated the reference advantage; v0.1.1 corrects both without revealing private parameters. |
| Can the task be solved through the agent's interface? | On v0.1.0, the oracle and four supplementary submissions pass. The v0.1.1 oracle, both fresh Astra submissions and both fresh Fable submissions also pass. These support solvability, not equal information at design time. |
| Does the reference have an advantage? | Yes. It reads public inputs at runtime, but its base prior scales were chosen with knowledge of the generating spreads. The size of that advantage is not directly measured. |
| Do near-threshold failures count as strong evidence? | No. The fixed-rule verdict is retained, but the two borderline failures are flagged. Clear v0.1.0 failures support the historical target-model evidence; the revised contract has a separate fresh attempt in VALIDATION.md. |
| Were infrastructure failures separated? | The first oracle error and four excluded model jobs are listed separately. GPT run 8 is counted with an interruption flag and an exclusion sensitivity count. |
| Was the rule adjusted after model trials? | The numeric scoring rule is unchanged. Verifier/contract changes are versioned as v0.1.1 and frozen before its fresh model attempt. |
| Does AI-assisted design introduce possible bias? | Possibly. Cross-family passes and same-family failures provide context, but do not rule out design bias. Assistance is disclosed. |
| Is a human completion time measured? | No. Metadata contains an estimate; no human baseline was run. |

## 12. Evidence integrity and open work

The original `jobs/` tree contains 23 job directories: nineteen model jobs, two oracle attempts, one no-op gate and one task check. Sixteen model jobs have verifier output, including the excluded starter-only run; three ended without a completed grade.

A historical Harbor redaction replaced the literal token `true` with `[REDACTED]` in some records. That makes some archived JSON invalid and changes `store_true` in two programs. The audit and ablation tools restore that known literal in memory and leave raw evidence untouched. This restoration is documented; it is not permission to infer unknown redacted values.

The current audit checks trial configurations, reward fields, rounded regret summaries and artifact presence. It does not rerun every model or establish the complete correctness of every archived transcript. Current controls, targeted verifier regressions and the versioned runtime changes are recorded in [VALIDATION.md](VALIDATION.md).

Open work includes an independent-stream truth audit, a reference with learned prior scales, interventions on more worlds and programs, investigation of the visible-world performance pattern, a human baseline, and stronger adversarial process isolation.

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
| Verifier isolation and timeout weaknesses | Present in the historical runtime. v0.1.1 repairs demonstrated artifact/output-link and repeatability bypasses and adds process-group cleanup; residual limits remain in Section 10 |
| Data cache ignores some inputs | Still present; fresh regeneration after source changes must be deliberate |
| Calibration counting issues | Wicket/dismissal and no-result treatment affect realism; no recalibration is included |
| Missing development tests | This revision adds focused verifier-contract and submission-evidence checks; it is not a full simulator test suite |

The original experiment remains inspectable. v0.1.1 is a separate revision with its own controls and model evidence; historical results are not silently promoted to results on the revised contract.
