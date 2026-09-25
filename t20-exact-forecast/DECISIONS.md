# Why I built this benchmark this way

Decision record for `t20-exact-forecast` · Siddharth Shashank Kumar

## What I am trying to test

I want to know whether an AI agent can turn a noisy history into reliable forecasts, and build checks that challenge its own assumptions before submitting its answer.

The agent receives three seasons of ball-by-ball history from an invented Twenty20 cricket league, the match simulator, and future fixtures and line-ups. It must deliver a reusable forecasting program. The challenge is to work out which apparent differences between players are worth trusting, then carry those estimates through to match probabilities on unfamiliar leagues.

The central design choice is to give the agent the mechanism but withhold the hidden quantities. I can generate observations from known player abilities more easily than a solver can recover those abilities from the observations. That lets me create a difficult inference problem whose answers I can check. I compare forecasts with high-precision estimates of the simulator's win probabilities, rather than with one lucky or unlucky match result.

This is a retrospective account of the decisions. It is **not a new preregistration**: the evidence for what was fixed before the pilots is the commit of `harbor/bar.json` ("Harbor metadata, pass bar, lock file, instruction"), which precedes the first pilot job, 2026-09-23__19-48-37, in the git log. `NOTES.md` explains the implementation and its checks. The design document explains the complete system. `RUN_REPORT.md` holds commands, job identities and results. This file explains choices that could reasonably have gone another way.

## The decisions at a glance

| Decision | Why it matters | When |
|---|---|---|
| D01. Test inference and verification | More files did not make the first task difficult for the tested models | Before the forecasting pilots |
| D02. Use an IPL-inspired league | Repeated, noisy observations and a bounded simulator make the problem realistic and checkable | Before pilots |
| D03. Score probabilities against simulator truth | Separate forecast quality from the luck of one future result | Before pilots |
| D04. Publish the mechanism | Make estimation the challenge, with clear rules and a usable self-check route | Before pilots |
| D05. Calibrate a limited model | Preserve useful real structure without pretending to reproduce all of cricket | Before pilots |
| D06. Couple the work across several stages | Require a durable forecasting method, not a one-off answer | Before pilots |
| D07. Use a reference ladder and executable oracle | Establish meaningful comparisons and a working solution | Before pilots; one limitation stands |
| D08. Pool regret and freeze the bar | Resolve a conflict between simulation variation and method separation | Changed before pilots, committed, never moved |
| D09. Spend more simulation on the grading truth | Make scoring more precise than a practical forecast | Before pilots; a precision audit remains |
| D10. Separate the submission from the verifier | Make forecast quality and execution failures distinguishable | Before pilots |
| D11. Treat fingerprints as leads | Keep observed failure separate from its explanation | After the pilots |
| D12. Report both generations and the inconvenient runs | The near miss, the interrupted runs, and a bar that the next generation clears | After the pilots |
| D13. Housekeeping decisions | The slug, the session directories, Harbor's redaction, the engine's typo | Throughout |

## D01 — Test inference rather than keep enlarging the first task

**Choice.** I moved from a revision-aware backtest repair task to a forecasting task with hidden statistical quantities.

**What changed my mind.** The backtest task came from a real problem in my work: a forecast must use the data available when it was issued, not later revisions. I built and tested it. Opus 4.7 passed versions containing 8, 24 and 48 scripts; GPT-5.5 passed the 24- and 48-script versions. Adding violations increased the workload without producing the target failure.

**Alternative.** I also built a small ingestion-service prototype with exhaustive fault schedules. The reference passed 27,710 schedules and the verifier caught five planted defects. I parked it because I expected its small repair-and-test loop to be too easy for the target models. That was a judgment about likely difficulty; I did not run a model pilot on it.

**Reason for the pivot.** Forecasting offered a different challenge. A program can run correctly, fit the documented model and still make poor estimates. The agent must decide whether its evidence supports its assumptions, not just whether its tests turn green.

**Limit.** These experiments show what happened on the tasks I built. They do not show that strong agents can solve every task with an explicit rule, or that data inference is always harder than software repair.

## D02 — Why IPL-inspired cricket?

**Choice.** I used real IPL ball records to calibrate a league with invented players, teams and venues.

Four properties made this a useful setting:

- Ball-level records let me separate the situation of a match from the apparent ability of a player.
- Players recur across many observations, but individual seasons remain noisy. That creates a real need to pull uncertain estimates toward an average, usually called *shrinkage*.
- A T20 innings has at most 120 legal balls. The match has enough structure to reward modelling, while remaining practical to simulate many times.
- A match win probability is easy to explain. A forecast of 70% should describe a chance, not promise a win.

The archive analysis put full-season reliability at about 0.46 for batting scoring rate and 0.27 for bowling economy. Those are estimates for particular statistics under the analysis assumptions, not statements that a fixed percentage of every player's performance is luck. They made uncertainty in player estimates a defensible source of difficulty.

**Alternative.** Real future matches would preserve real identities, but results would arrive on their own schedule and a small set of outcomes would be a noisy grading target. An entirely invented toy process would be easier to build but harder to connect to a recognisable forecasting problem.

**Cost accepted.** This is an IPL-inspired statistical world, not a validated tool for predicting the actual IPL. Invented identities prevent player-name lookup from supplying the hidden abilities; they do not remove every possible contamination risk once benchmark answers are published.

**Originality claim.** The contribution is this particular task: a calibrated synthetic league, public mechanism, hidden abilities, reusable forecasting interface, comparison ladder and preregistered grading procedure. I am not claiming to have invented cricket simulation, shrinkage or probability scoring. The same reasoning problem appears when estimating conversion rates, equipment failures or demand from limited histories; transfer to those domains has not been measured here.

## D03 — Grade the probability, not the outcome

**Choice.** For each fixture, compare the submitted probability with a high-precision estimate of the simulator's win probability. Use expected logarithmic regret: the extra expected penalty caused by reporting the wrong chance.

For true probability `p` and submitted probability `q`:

```text
q = clip(q, 0.002, 0.998)
regret = p * log(p / q) + (1 - p) * log((1 - p) / (1 - q))
world_regret = mean(regret across that world's fixtures)
```

**Why this instead of match results?** If a team has a 70% chance and loses, that one result does not establish that the forecast was bad. Scoring against the underlying chance removes this source of luck from the verdict. Historical sampling noise and numerical approximation still remain.

**Why logarithmic rather than squared-error scoring?** Both are defensible probability scores. I chose the logarithmic score because a confident mistake is especially costly, which matches the uncertainty problem I wanted to test. Clipping prevents one extreme submission from creating an infinite penalty. This is a design preference, not proof that other proper scores are unsuitable.

**Limit.** "Exact" describes the expected-loss calculation against a stored probability. The stored probabilities are estimated by simulation, not obtained in closed form. Even a good public-data forecaster cannot observe every hidden change that happened after the history ended.

## D04 — Publish the mechanism and make meaningful checking possible

**Choice.** Ship the match engine and public constants. Explain the structure of hidden abilities and conditions, the output contract, the score, the limits and the grading rule. Withhold the hidden values and their population magnitudes.

**Why this instead of a prose-only simulator description?** If an agent reproduces a mechanic incorrectly because a description is incomplete, the task measures ambiguity. Shipping the engine lets the agent concentrate on learning the unknown quantities and use the same mechanics when forecasting. A working coin-flip starter makes the output contract concrete.

The handbook explicitly permits agents to simulate leagues and evaluate their own methods against constructed truth. It also states that there is no hidden effect for one particular batter–bowler pair. Those are deliberate disclosures: recognising an undisclosed permission or guessing an omitted mechanism should not be necessary for success.

**Cost accepted.** Publishing the engine removes reverse engineering as a source of difficulty and gives agents a strong development tool. That is appropriate for the capability being tested.

**Verification principle.** A smoke test can show that a program runs. A useful statistical check must also challenge whether its assumptions fit the supplied history. Both checks should be possible. Making the agent's own checks unreliable is not a design objective. The pilots showed exactly this distinction: the programs that passed built checks tied to the real league's estimates; the one failed program that built a check aimed it at a world generated from its own priors.

## D05 — Use measurements to constrain the world, and label the choices

**Choice.** Keep a compact simulator, with each constant traceable to a measurement, a transformation of measurements, tuning against an aggregate, or an explicit modelling choice.

**Evidence.** The archive supported repeatable venue differences more strongly than individual batter–bowler interactions: repeat correlations of about 0.71 for grounds and 0.178 for the selected, well-sampled player pairs. I represented venue levels and small type-level interactions without adding an unrestricted effect for every pair. Weak repeatability is a reason to be conservative here, not proof that real pair effects do not exist.

| Kind of number | Example | What the record must explain |
|---|---|---|
| Measured | Outcome profiles and repeat correlations | Data, filters and estimation procedure |
| Derived | A spread corrected for sampling noise | Assumptions behind the conversion |
| Tuned | League level, day variation and innings wear | Target used and what was adjusted |
| Chosen | Transfers, form process and simplified tactics | Behaviour sought and realism sacrificed |

**Alternative.** A richer cricket simulator could add fielding, partnerships and captain decisions. I excluded those mechanisms because each would add quantities the agent must infer and another modelling claim I would need to justify.

**Validation and cost.** The three-league check produced a mean first-innings score of 189.2 against 188.5 in the archive and a score spread of 35.0 against 37.4. I keep the remaining spread mismatch visible. Mean score, score spread and chase rate informed tuning, so agreement on them is not independent validation. Wickets, the over-by-over profile and chase success by target are the checks that were not tuned against. An earlier version of the validation table carried numbers from before the wear constant was raised; my own rerun found and replaced them.

**Revisit if** a mechanism materially improves held-out realism or changes which forecasting methods succeed. More detail alone is not enough reason to add it.

## D06 — Make the deliverable depend on several linked decisions

**Choice.** Provide three seasons of history, changing team membership and line-ups, and require one program that also works on unseen worlds.

The first ladder experiment used 109 historical matches and no forecaster beat a coin flip. I increased the history to 270 matches. Difficulty should come from using evidence well, not from withholding so much evidence that the available methods cannot recover useful signal. Transfers and changing line-ups make player estimates more useful than treating a team name as a permanent ability.

| Subgoal | What the agent must resolve | Why a later step depends on it |
|---|---|---|
| Understand the records | Reconstruct the situation before each ball and join players to fixtures | Wrong state or joins corrupt the estimates |
| Estimate hidden quantities | Separate player effects, conditions and noise | An overconfident fit creates overconfident match forecasts |
| Validate assumptions | Choose how much to trust limited history without using future information | A check built from the same mistaken assumptions can approve a poor model |
| Forecast and package | Simulate fixtures, meet the interface and runtime, and repeat deterministically | The result must be a usable program across leagues |

**Alternative.** One visible league, fixed rosters or a supplied table of player abilities would remove substantial parts of this dependency chain.

**Cost accepted.** The task is long-horizon because the decisions interact, not because every session must be long. A short successful solution would still be a success; GPT-6-astra passed in 45 minutes.

## D07 — Use a ladder for comparison and an oracle for solvability

**Choice.** Build recognisable comparison methods before interpreting model results: coin flip, team ratings, player estimates without shrinkage, last-season-only estimates, a raw head-to-head table and a regularised reference.

**Why a ladder?** One pass mark says little about the kind of task I built. The ladder tests whether useful modelling choices make a meaningful difference. On the eight graded worlds, the weaker tiers have totals at least 1.50 times the reference; this claim concerns those named tiers, not every possible weak method.

The reference is fitted after reloading the public files through the public reader. The oracle installs an executable version of that forecaster and passes the verifier at exactly 1.000 times the stored reference. It does not copy the stored answer probabilities. This establishes a working solution under the public runtime interface.

**Important cost.** The reference's starting prior scales were selected by me, knowing the synthetic population scales. It uses public files at runtime, but its design has information an external solver is not handed. Choosing a global multiplier by chronological validation does not erase that advantage. The oracle therefore demonstrates operational solvability more strongly than it demonstrates equal starting information.

**What the pilots added.** The ablations measured the advantage: changing a failed program's prior scale alone removed half or more of its excess regret. And the newer generation removed the advantage on its own: both passing Fable programs estimated every prior scale from the league by marginal likelihood, which is the reference I had listed as the next version. A reference of that kind should anchor the next version's bar. It requires new comparison experiments and a newly registered bar, and it must not replace the current reference underneath existing results.

## D08 — Change the aggregation unit, then freeze the bar

**Initial choice.** Require acceptable regret on every world separately.

**Evidence that changed it.** Three early worlds made the reference look stable. Across eleven worlds its skill ranged from −0.21 to 0.73. Eight separate development worlds then exposed the specific grading problem: reference re-simulation variation reached 5.9% on one world, while the unshrunk tier was only about 6–7% worse than the reference on two others. A three-times-noise allowance could not also reject those tiers on every world.

**Decision.** Add the world regrets before applying the tolerance. Apply the same rule separately to the seven held-out worlds:

```text
all_worlds_ok = sum(submission_regret) <= 1.10 * sum(reference_regret)
held_out_ok  = sum(submission_regret[held_out]) <= 1.10 * sum(reference_regret[held_out])
```

On the development worlds, the pooled unshrunk tier was 1.30 times the reference, last-season-only 1.93 and coin flip 1.90. The relative variation of the pooled score, computed from the same four re-simulated repeats summed across the eight worlds, was about 1.1%. That supported a 10% allowance with room between ordinary variation and the tested weaker methods. It does not establish a universal error bound.

**Alternative rejected.** Raising a per-world percentage would change the threshold without resolving the conflict under the chosen noise criterion.

**Cost accepted.** A method can be weak on one world and still pass. The second aggregate check prevents strength on the visible world from compensating for insufficient performance across the held-out group. Eight worlds are finite coverage, not proof of generalisation to every possible league. Fable's second run showed the held-out check working in the other direction: it passed on the seven unseen worlds and failed on all eight because of the one it could see.

**What stays frozen.** Development seeds 1001–1008 are separate from the graded seeds 101, 202, 303, 404, 505, 606, 707 and 808. The rule file specifies relative tolerance 0.10, absolute tolerance 0 and clipping at 0.002. It was committed before the first pilot job and has not moved since, through a near miss at 1.109, a nearer one at 1.104, and the newer pair's passes. Changes to the generator, reference, truth precision or grading semantics require a separately identified version and a new pre-pilot analysis. Post-pilot diagnostics may explain old results; they cannot become pre-pilot evidence retrospectively.

## D09 — Make the grading truth more precise than a practical forecast

**Choice.** Generate stored truth with 100,000 simulated matches per batting order, 200,000 paths per fixture. The reference uses 4,000 per batting order. Store the grading probabilities so repeated grading is deterministic.

**Why this instead of using the same simulation budget for both?** Small numerical fluctuations in a practical predictor should not be matched by equally large uncertainty in the answer used to judge it. Spending more at dataset-build time keeps individual grading runs cheap.

**Precision claim.** If the 200,000 path outcomes are treated as independent, the worst-case standard error is about 0.0011 for the estimated probability. That is not automatically a bound on the total regret ratio or a guarantee that every near-threshold verdict is stable.

**Remaining limitation.** Separately generated worlds do not imply independent truth-estimation errors: the truth code reuses fixture-number-based random streams across worlds. A stronger precision audit would regenerate complete truth sets with independent stream families and check the stability of the aggregate comparisons. That audit has not been done.

## D10 — Make the execution boundary part of fairness

**Choice.** Package one Harbor task with separate agent and verifier environments. The agent receives public files. The verifier holds truth and reference outputs, executes the submission beside a pristine engine, and checks the required files in the agent's engine copy against it.

**Why this instead of grading inside the modified agent environment?** The program being evaluated should not control the answer files or the implementation of its own score. The unprivileged runner is part of the container boundary; a local grader invocation without that privilege separation checks behaviour, not equivalent isolation.

The interface accepts a probability for every required fixture. The grader checks numerical validity, forecast quality, held-out performance, repeatability, engine integrity and runtime. Its separate reward fields distinguish a valid but inaccurate forecast from a broken deliverable:

```text
functional_correctness * (
    0.50 * robustness
  + 0.25 * constraint_satisfaction
  + 0.25 * artifact_quality
)
```

Only full reward counts as solved. Three hours are available for the agent session; each forecast invocation has a separate 720-second limit. Packaging fills handbook values from the rule file and builds the oracle from the ladder implementation to reduce drift. Harbor's own linter passes all 22 checks.

**Limits accepted and recorded.** The verifier makes no network calls, but its no-network mode is not declared, because Docker Desktop on macOS rejects it. A deterministic package rebuild from committed inputs is different from independently rebuilding the calibration from a changing upstream archive. Pinning dependencies helps reproducibility; preserving input snapshots and manifests is also necessary. Neither a linter pass nor an oracle pass proves that every possible security or grading failure has been excluded.

## D11 — Treat a failure fingerprint as a lead, then test the explanation

**Choice after the pilots.** Use proximity to a ladder forecast to generate a hypothesis. Strengthen that hypothesis through program inspection and focused interventions, while keeping their coverage explicit.

| Evidence | What it supports | What it does not establish |
|---|---|---|
| Ten failing grades | These submitted programs failed the frozen forecasting rule | A universal pass rate for either model |
| Nine forecasts mostly or wholly nearest the unshrunk tier | A recurring pattern consistent with insufficient shrinkage | Identical code or one shared cause |
| Inspection of the first six programs | Concrete information about their priors and self-checks | The implementation choices in runs 7–10 |
| One-constant changes to those programs on held-out world c | Regularisation choices materially affected that world's scores | A complete causal account or a pass across all eight worlds |
| Five newer-pair forecasts, all nearest the reference | The next generation does what the failures did not | That any single design element caused the difference |

Run 6 corrected my initial interpretation. Its forecasts were close to the reference on seven worlds, which might suggest an appropriate fit. Reading the program instead found broad priors combined with a final pull of probabilities toward one half. The fingerprint did not distinguish those mechanisms.

The interventions lowered the first five programs' regret ratios on world c from 2.70 to 1.36, 2.55 to 1.57, 2.17 to 1.64, 2.29 to 1.60 and 2.10 to 1.27. All improved; four of the five removed more than half their excess above the reference. These were focused regularisation changes, not uniformly one scalar edit: run 5 changed two quality penalties. Halving run 6's prior spreads while retaining its output adjustment brought its ratio from 1.42 to 0.91 on that world. That motivates an all-world check; it does not substitute for one.

**The deeper lesson.** Run 3 did build synthetic validation leagues. It generated them using the same overly broad ability assumptions as its estimator, and verified recovery in a world that already agreed with those assumptions. The passing Fable programs built the same kind of generator with spreads set from the real league's estimates, and one of them noticed when its synthetic coin flip disagreed with the handbook's yardstick. The capability gap is therefore more specific than "the agent forgot to test": a check must be tied to the observed data and capable of contradicting the model being checked.

## D12 — Report both generations, the near miss and the interrupted runs

**Reporting decision.** Report every trial, distinguish the completed artifact from the opportunity the agent had to improve it, and count both generations under the same frozen rule.

| Model and harness | Completed runs | Passed | Qualification |
|---|---|---|---|
| Claude Opus 4.7 / Claude Code, high effort | 5 | 0 | |
| GPT-5.5 / Codex, high effort | 5 | 0 | One session ended at the account usage limit after a forecaster was written; excluding it gives 0 of 4 |
| Claude Fable 5.1 / Claude Code, high effort | 3 | 2 | The miss, 1.104 on all eight worlds, passed the held-out seven at 1.093; a fourth run was stopped at its start |
| GPT-6-astra / Codex, high effort | 2 | 2 | One run ended at the usage limit before a program existed; one had a complete program when I stopped the loop during verification |

All ten older-pair artifacts were valid, deterministic, within execution limits and with the engine unchanged; their failed grades concern forecast quality. Run 6 scored 1.109 across all worlds against 1.10; a 1.12 rule would have passed it, and I retain the registered verdict. The interrupted GPT-5.5 session did not receive its full opportunity to iterate.

The newer pair's five completed forecasts all resemble the reference on every world. Their closing messages describe prior scales learned from the league by marginal likelihood, posterior-predictive simulation, and checks against generated leagues or a hold-out of the real league. In all five the visible world was the worst or second-worst world, and F2's miss is entirely that world; I did not ablate why.

**What this establishes.** The task separates generations, not vendors. The pair the brief's goal line names fails ten times out of ten for one diagnosed cause; both models of the next generation, from two labs, clear the bar on their first completed attempts by the route the design predicted. A model from a different lab passing, while the same family's previous model failed five times reading the same handbook, also answers the question I had to ask because the task was designed with an assistant of Fable's family: the passes are not family affinity. What it does not establish is a task that fails the newest generation. If that is the pair the brief means, the task as calibrated is not hard enough, and the levers are known: anchor the bar on a reference that learns its spreads, shorten the history, or add the off-season circuit. Each needs a fresh bar analysis and a fresh committed rule before any pilot.

**Next-version priorities.** The learned-spreads reference as the bar's anchor; repeated truth calculations to assess borderline stability; interventions beyond one world and the first six programs; the cause of the visible-world pattern; a complete independent rebuild record. These are open work, not accomplishments implied by the current results.

## D13 — Housekeeping decisions

**The slug.** The brief asks for a stable slug "such as" `collinear-candidate/<task-name>`. I used `collinear-siddharthshashankkumar/t20-exact-forecast`, chosen before any pilot and never changed. "Such as" makes the example a format, not a fixed prefix; what matters is that the name never moves once runs exist under it.

**Session directories.** A commit swept in Claude Code's session state under `jobs/*/agent/sessions/`, including session key files. I removed them from the index, ignored the path, amended before pushing, and scanned every job file for tokens. The reward, details and agent logs stay; they are the evidence.

**Harbor's redaction.** Harbor redacts the values of environment variables passed with `--ae`, and one value was the word `true`, so every literal `true` in the archived artifacts became `[REDACTED]`, breaking `details.json` parsing and `action="store_true"` in two archived programs. The ablation script and the summaries restore it; the restored programs reproduce the verifier's numbers to the last digit.

**The engine's typo.** Harbor's linter noted one typo in a comment in `engine/model.py`. I left it. Any change to the engine's bytes makes the shipped task differ from the one the pilots saw.

**Stopping the loop.** I stopped the newer-pair loop after four of its six runs. The two runs it interrupted are recorded as excluded with their reasons, not counted as failures.

## Evidence map

| ID | Where | What it holds |
|---|---|---|
| E1 | Design document §§4.1–4.2 and 7 | The earlier prototypes and their pilots; the ingestion prototype was not model-piloted |
| E2 | `NOTES.md` §§4–9; design document §§5.4–5.8; `dev/explore_reliability.py`, `dev/fit_constants.py`, `league/calibration.py` | Calibration rationale, measurements and design choices |
| E3 | `NOTES.md` §1; `scoring/exact.py`; `harbor/bar.json` | The score and the clipping rule |
| E4 | `task_src/docs/handbook.md`, `league/engine.py`, `task_src/solution/forecast.py` | Public contract, mechanics and starter |
| E5 | Design document §5.12; `dev/validate_world.py` | Aggregate validation; three aggregates were tuning targets |
| E6 | Design document §§5.13–5.15 and 7; `forecasters/ladder.py`, `league/world.py`, `task_data/` | Ladder, history-length experiment, generated worlds |
| E7 | `NOTES.md` §21; `harbor/solution/`; jobs 2026-09-23__19-38-27 (oracle) and 2026-09-23__19-33-46 (starter) | Solvability witness; the designer-informed priors remain a limitation |
| E8 | `NOTES.md` §17; design document §5.16; `dev/bar_analysis.py`, `harbor/bar.json`, the git log | Bar rationale, the rule, and its commit before the first pilot job |
| E9 | `league/world.py::TruthEngine`; `dev/make_task_data.py` | Simulation budgets and seed construction |
| E10 | `harbor/task.toml`, `harbor/tests/grader.py`, the Dockerfiles, `package_task.py`; job 2026-09-24__12-21-19 (linter) | Execution, reward and packaging |
| E11 | Design document §§6.2–6.3; `dev/ablate_pilots.py`, `ablations.log` | The six-program reading and the interventions on world c |
| E12 | Design document §§6 and 6.4; `RUN_REPORT.md`; `jobs/` | Every trial of both generations with job identities, the near misses and the excluded runs |

The external calibration source is the Cricsheet IPL archive, under ODC-BY 1.0. The statistical and simulation methods build on established work cited in `NOTES.md`. This record's contribution is the reasoning connecting those methods to this benchmark's choices.
