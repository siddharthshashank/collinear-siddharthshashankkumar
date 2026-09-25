# Why I built this benchmark this way

**Decision record for `t20-exact-forecast` · Siddharth Shashank Kumar**

I want to test whether an AI agent can turn noisy history into reliable forecasts—and build checks that could prove its assumptions wrong.

The agent receives three seasons from an invented Twenty20 cricket league, a match simulator, and future fixtures. It must produce a reusable forecasting program. The central difficulty is deciding how much to trust apparent differences between players, then carrying that uncertainty through to match probabilities.

My creative starting point is an asymmetry: generating observations from known abilities is easier than recovering those abilities from observations. I use that gap to create a difficult problem with a checkable answer. The agent knows the mechanism; it must infer the hidden quantities.

This is a **retrospective decision record**, not a new preregistration. Implementation details belong in [DESIGN_DOCUMENT.md](DESIGN_DOCUMENT.md), trial evidence in [RUN_REPORT.md](RUN_REPORT.md), and authorship and source disclosures in [PROVENANCE.md](PROVENANCE.md). Every claim below is backed by the repository: the job records, the logs and the git history.

## D01 — Change the capability being tested, rather than add more files

**Choice.** Move from repairing a revision-aware backtest to estimating hidden quantities from noisy data.

**What changed my mind.** The backtest task came from a real work problem: a historical forecast must use information available at the time, not later revisions. Opus 4.7 passed versions with 8, 24 and 48 scripts; GPT-5.5 passed the 24- and 48-script versions. More violations increased the workload without producing the intended failure.

I also prototyped an ingestion service. Its reference passed 27,710 fault schedules, and its verifier caught five planted defects. I parked it because I expected the repair loop to be too small. That was a design judgment; I did not model-pilot it.

**Reason for the pivot.** A forecasting program can run, fit a model and pass ordinary checks while still making poor estimates. That makes the quality of the agent’s reasoning and verification consequential.

**Trade-off.** Statistical errors are harder to diagnose than broken invariants. I therefore needed comparison methods and targeted experiments, not just a final score. These prototypes do not establish that forecasting is generally harder than software repair.

## D02 — Use an IPL-inspired league with invented identities

**Choice.** Calibrate the simulator from real IPL ball records, then generate new players, teams and venues.

**Why IPL?** Ball records describe both the outcome and its context. Players recur often enough to estimate ability, but individual histories remain noisy. A T20 innings has at most 120 legal balls, keeping repeated simulation manageable. Win probabilities are also understandable without specialist cricket knowledge.

The archive analysis estimated full-season reliability around 0.46 for batting scoring rate and 0.27 for bowling economy. These values concern specific statistics and assumptions; they do not mean that a fixed share of every player’s performance is luck. They support a task where uncertain estimates should be pulled toward an average, a practice called *shrinkage*.

**Alternatives.** Real future matches would offer greater direct realism but slow feedback and noisy observed outcomes. An arbitrary toy process would be easier to construct but offer less justification for its structure.

**Trade-off.** This is not a validated IPL predictor. Invented identities make player-name recall unhelpful, but publishing benchmark answers still creates contamination risks. The novelty lies in this task’s combination of calibrated worlds, disclosed mechanics, hidden abilities and numerical evaluation—not in inventing cricket simulation or probability scoring.

## D03 — Judge the reported chance, rather than one match result

**Choice.** Compare forecasts with high-precision simulator win probabilities using expected logarithmic regret.

If a team has a 70% chance and loses, that result alone cannot establish that 70% was a bad forecast. Knowing the simulator’s underlying chance lets me remove that particular source of grading luck.

```text
q = clip(submitted_probability, 0.002, 0.998)
regret = p * log(p / q) + (1 - p) * log((1 - p) / (1 - q))
world_regret = mean(regret over the world's fixtures)
```

Here `p` is stored simulator truth and `q` is the submitted forecast.

**Why this score?** Logarithmic scoring makes a confident mistake costly, matching the uncertainty problem I wanted to test. Squared-error probability scoring would also be defensible. Clipping prevents infinite penalties from extreme submissions.

**Trade-off.** “Exact” refers to expected-loss arithmetic against a stored probability. That probability is estimated by simulation, not solved analytically. Historical sampling noise, finite world coverage and numerical uncertainty remain. A public-data solver also cannot observe every hidden change after the history ends.

## D04 — Give away the mechanism and make meaningful checking possible

**Choice.** Supply the engine, public constants, a working starter and an explicit contract. Withhold hidden abilities and their population magnitudes.

**Why?** A prose-only description could turn a mechanical misunderstanding into a false capability failure. Providing the actual simulator lets the agent focus on estimation. Disclosing the score, time limits and grading rule makes the target reviewable. The handbook also permits synthetic-league experiments and states that individual batter–bowler pairs have no separate hidden effect.

**Alternative.** Requiring the agent to discover undocumented mechanics would add difficulty, but it would change the capability being evaluated.

**Trade-off.** The engine gives the agent a powerful development tool. That is intentional. A smoke test should establish that a program runs; a statistical test should challenge whether its assumptions fit the history. Both must be possible. The benchmark is not designed to make the agent’s own verification unreliable.

The later pilots sharpened this principle: synthetic tests can help, but a test world created from an estimator’s own unsupported assumptions may simply approve those assumptions again.

## D05 — Keep the simulator limited, with an explanation for every constant

**Choice.** Separate measured, derived, tuned and chosen quantities rather than present all constants as discoveries from data.

| Kind | Example | Required explanation |
|---|---|---|
| Measured | Outcome frequencies; repeat correlations | Which records and filters were used? |
| Derived | Ability spread corrected for sampling noise | What assumptions justify the conversion? |
| Tuned | League level, day variation, innings wear | Which aggregate was used as a target? |
| Chosen | Transfers, form dynamics, simplified tactics | What behaviour is useful, and what realism is lost? |

Venue effects repeated more strongly than individual batter–bowler interactions in the analysis: correlations around 0.71 and 0.178 respectively. I retained venue differences and small type-level interactions without adding a parameter for every pair. Weak repeatability supports caution; it does not prove that real pair effects do not exist.

**Alternative.** Fielding, partnerships and captain decisions could make a richer simulator, but each adds hidden quantities and another realism claim to defend.

**Validation and cost.** The three-league check produced mean first-innings score 189.2 against archive 188.5, and spread 35.0 against 37.4. Mean, spread and chase rate informed tuning, so their agreement is not independent validation. Other summaries, including wickets and the over-by-over profile, provide additional checks. The remaining mismatch stays visible.

**Reopen when** a new mechanism materially improves independent realism checks or changes which methods succeed—not merely because it makes the simulator larger.

## D06 — Make several decisions depend on one another

**Choice.** Give three seasons of history, changing line-ups and team membership, and require one program to work on unseen worlds.

The early 109-match experiment did not produce a forecaster that beat a coin flip. I increased the history to 270 matches. Difficulty should come from using evidence well, not from supplying so little that useful inference becomes impractical.

The dependency chain is deliberate:

1. Reconstruct the state before each ball and join records correctly.
2. Estimate player and venue effects while distinguishing signal from noise.
3. Validate how strongly to trust those estimates without using future information.
4. Simulate fixtures and deliver complete, repeatable forecasts within the runtime.

An error in an early stage can survive into a plausible-looking final CSV. Transfers also make persistent player estimates more useful than treating a team name as permanent ability.

**Alternative.** Fixed rosters, supplied abilities or one visible league would remove substantial parts of this chain.

**Trade-off.** Long-horizon describes linked work and state tracking, not a minimum session length. A short successful solution remains a success. The durable deliverable and its interface are specified in [instruction.md](instruction.md).

## D07 — Establish a ladder and a working oracle, while acknowledging its advantage

**Choice.** Compare coin flip, team ratings, unshrunk player estimates, last-season-only estimates, raw head-to-head estimates and a regularised reference before interpreting model failures.

**Why a ladder?** A threshold alone cannot show whether better modelling matters. On the eight graded worlds, the named weaker tiers total at least 1.50 times reference regret. That is evidence about these methods on these worlds, not every conceivable weak approach.

The reference reloads public files through the public reader. The oracle runs that forecasting method and achieves 1.000 times stored reference regret; it does not copy stored answer probabilities. This is a concrete witness that the interface, runtime and grader admit a successful program.

**Important trade-off.** I selected the reference’s starting prior scales knowing the synthetic population scales. Public-only inputs at runtime do not erase designer knowledge used during development. Chronological selection of a global multiplier does not remove the full advantage either. The oracle establishes operational solvability more strongly than equal starting information.

Focused regularisation changes improved failed programs on one world; they do not isolate or measure the entire designer-information advantage. The newer pair's passes offer additional evidence that agents can learn useful scales from public history.

**Next version.** Evaluate a reference that learns its spreads from public data. Any replacement needs new comparison experiments and a separately registered bar; it cannot silently change the meaning of existing results.

## D08 — Pool the evidence, then freeze the rule

**Initial choice.** Require acceptable regret separately on every world.

**What changed it.** Eight development worlds exposed a conflict: reference re-simulation variation reached 5.9% on one world, while unshrunk estimates were only around 6–7% worse on two others. Under the chosen three-times-noise criterion, a per-world allowance could not both accommodate variation and consistently separate the methods.

**Decision.** Sum world regrets and apply a 10% allowance twice:

```text
all_ok  = sum(candidate_regret) <= 1.10 * sum(reference_regret)
held_ok = sum(candidate_regret[held_out])
          <= 1.10 * sum(reference_regret[held_out])
```

The development pooled unshrunk ratio was 1.30. Pooled variation across four re-simulated repeats was about 1.1%. This supported room between ordinary variation and the tested weaker methods; it was not a universal error bound.

**Trade-off.** A weak world can be compensated by others. Checking the seven held-out worlds separately prevents the visible world from masking poor held-out performance. Conversely, acceptable held-out performance does not waive the all-world requirement.

**Chronology.** Development seeds differ from graded seeds. The author reports that `harbor/bar.json`, with relative tolerance 0.10 and absolute tolerance zero, was committed before the first pilot and retained through later near misses and passes. This report does not independently verify the commit hash. Retrospective diagnosis must never be described as preregistration evidence.

## D09 — Spend precision on the answer and separate execution from quality

**Choice.** Store truth from 100,000 simulations per batting order—200,000 paths per fixture—while the reference uses 4,000 per order. Keep truth and grading in the verifier boundary, beside a pristine engine.

**Why?** Expensive truth generation happens once. Repeated grading is then deterministic and cheaper, with finer numerical precision than an ordinary forecast. Under independent-path assumptions, the worst-case probability standard error is about 0.0011; that is not a bound on the regret ratio.

**Remaining precision issue.** Fixture-number-based truth streams are reused across worlds. Separately generated abilities do not imply independent truth-estimation errors. Rebuilding complete truth sets with independent streams is an outstanding stability check, especially for borderline verdicts.

The verifier separately records forecast quality, held-out performance, artifact validity and constraints. A valid but inaccurate program should not be described as a packaging failure. The intended execution boundary also prevents a submission from changing its own answers or score; local execution without privilege separation does not demonstrate equivalent isolation.

**Trade-off.** Extra boundaries require their own checks. An oracle pass or linter pass is evidence, not a complete security proof. Deterministic packaging from committed inputs also differs from reproducing calibration from an upstream archive. Reproduction details and known limitations belong in [RUN_REPORT.md](RUN_REPORT.md).

## D10 — Let the evidence narrow the explanation, and retain inconvenient results

**Choice after the pilots.** Treat proximity to ladder forecasts as a diagnostic lead, then use program inspection and focused interventions to test it.

Nine of ten older forecasts mostly or wholly resembled the unshrunk tier. Inspection covered the first six programs; interventions covered only held-out world c. Stronger regularisation improved the first five, removing more than half their excess above reference in **four of five** cases. Run 5 changed two penalties, so these were not uniformly one-constant experiments.

Run 6 corrected an initial interpretation: resemblance to the reference concealed broad priors partly compensated by pulling final probabilities toward one half. A forecast fingerprint does not uniquely identify its cause.

The strongest verification lesson came from run 3. It did create synthetic tests, but generated them using the same overly broad assumptions as its estimator. Its checks could succeed without challenging the faulty premise.

| Model results | Passed / completed runs |
|---|---:|
| Claude Opus 4.7 | 0 / 5 |
| GPT-5.5 | 0 / 5 |
| Claude Fable 5.1 | 2 / 3 |
| GPT-6-astra | 2 / 2 |

The GPT-5.5 account-limit interruption remains flagged; excluding it gives 0/4. Newer-model interruptions and exclusions are recorded separately in [RUN_REPORT.md](RUN_REPORT.md). Fable’s failed artifact scored 1.104 overall and 1.093 on held-out worlds: it failed the unchanged all-world requirement.

**Interpretation.** These small samples show different observed outcomes across the tested model versions. They do not prove general generation separation, eliminate family-affinity effects or establish one cause for every failure. Newer passes strengthen the practical solvability evidence while limiting claims that the task reliably defeats the newest pair named in the brief. I retain that result rather than move the bar afterward.

Future changes should first address reference fairness, numerical stability and broader causal checks. Their value must be demonstrated in a newly identified version. The current submission’s purpose and reading order are in [README.md](README.md).
