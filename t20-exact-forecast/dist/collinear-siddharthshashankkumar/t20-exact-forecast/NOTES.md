# Engineering notes: how I checked the work

**Siddharth Shashank Kumar · t20-exact-forecast**

I used checks at the boundaries of the pipeline because a mistake in an early stage can survive all the later code. This document explains what I checked and what the result meant. It is a retrospective summary of the development record; the original detailed notes remain in `docs/NOTES_FULL.md` in the source repository.

## 1. Establish a score I could reason about

Before comparing forecasting methods, I needed a score with simple known cases. Reporting the stored probability should produce zero regret. A confidently wrong probability should cost more than a cautious error. Clipping should keep endpoint forecasts finite.

The earlier notes record a guessed expected value that was wrong even though the score implementation was right. That is a useful reminder: an assertion is not independent evidence if its expected value has no derivation.

The current focused checks include the Bernoulli case `p = 0.7, q = 0.5`, evaluated from the formula, along with zero-regret and finite-clipping checks.

**Files:** `scoring/exact.py`, `dev/test_verifier_contract.py`. **Evidence:** [validation](VALIDATION.md).

## 2. Check the records before fitting a model

The parser distinguishes legal deliveries from extras, batter runs from team runs, and bowler wickets from all dismissals. Those distinctions affect the rates passed into the simulator.

The development notes record corrections to a dismissal label and legal-ball indexing. Later review found further edge cases in dismissal and no-result handling. I therefore treat the calibration as useful and inspectable, not exhaustively verified.

**Why it mattered:** a plausible aggregate can be built from inconsistent definitions. A model fitted afterward would not expose that by itself.

**Files:** `dev/parse_archive.py`, `dev/explore_overs.py`, `dev/fit_state.py`.

## 3. Separate stable effects from noisy estimates

I explored repeatability before deciding which effects belonged in the simulated league. Venue effects repeated more clearly than some player–venue or batter–bowler interactions. That informed the simplifications in the generator.

I kept measured constants distinct from chosen constants. Some choices reproduce a target; others bound the problem or make the scenario realistic enough to inspect. A reviewer should be able to disagree with a choice without having to infer which numbers were measurements.

**Why it mattered:** this is the same discipline the task asks of the solver. Adding more parameters is not automatically a better account of the evidence.

**Files:** `dev/explore_reliability.py`, `dev/fit_constants.py`, `league/calibration.py`. **Rationale:** [decisions 4–5](DECISIONS.md#4-i-limited-realism-to-what-i-could-explain-and-inspect).

## 4. Verify the public/private boundary

The generator knows hidden abilities and conditions. The agent should receive the observed records and public mechanism only. The reference reloads the public representation before fitting, which helps check that the task is solvable through the shipped interface.

That check does not eliminate the reference's designer-informed prior scales. I now separate runtime inputs from design knowledge in the fairness discussion.

The historical notes also identify a useful boundary problem: `History.played` is documented but left empty by the reader. Historical line-ups remain available in `lineups.csv`. This is a documented defect in the frozen version.

**Files:** `league/league_io.py`, `dev/make_task_data.py`, `package_task.py`.

## 5. Test the proposed threshold before testing agents

The comparison methods gave the raw score meaning. The bar analysis then tested whether a per-world threshold could tolerate reference noise while still separating weaker methods.

It could not do both consistently in the observed development worlds. That led to pooling. The resulting 10% tolerance was committed before the model pilots.

The later review changed the interpretation of near misses, not the recorded threshold. Repeatable grading against a stored denominator is different from a denominator with no estimation uncertainty.

**Evidence:** [bar.log](bar.log), [decision 7](DECISIONS.md#7-i-abandoned-a-per-world-threshold-after-checking-its-noise), [run report](RUN_REPORT.md#2-the-rule-behind-every-verdict).

## 6. Run the complete path, including the obvious controls

The first oracle run caught an installation error that a shell syntax check missed. That made the end-to-end gate valuable: the reference had to be installed, invoked through the required interface, and scored by the actual verifier.

The no-op program supplies a different check. A program can be valid, deterministic and fast while failing the core forecast requirement. Its score should make that distinction visible.

Fresh executions during the documentation work reproduced those controls: oracle 1.0 on every component; no-op 0.0 overall with valid output and constraints.

**Evidence:** [original controls](RUN_REPORT.md#4-positive-and-negative-controls) and [fresh validation](VALIDATION.md).

## 7. Read the failed artifact before writing the explanation

A forecast's nearest comparison method is a useful clue. I did not treat it as a causal explanation.

The recorded follow-up inspected the first six programs and reran them with one prior or hedge setting changed. Reproducing the unedited score first made the edited result interpretable. The direction of the change supported overconfident estimation as a contributor to those failures.

The scope matters: one world, six programs. Extending that claim to all worlds or all ten runs would require more experiments.

**Evidence:** [ablations.log](ablations.log), `dev/ablate_pilots.py`, [failure analysis](RUN_REPORT.md#7-failure-analysis).

## 8. Preserve the experiment while improving the handoff

The documentation revision adds an evidence audit, focused verifier checks and a one-task archive. Runtime hashes distinguish a clearer explanation from an altered task.

The current architecture figures are editable SVGs generated from a common source. They distinguish data flow from visibility, show the oracle as an alternative control route, and label the actual network-policy limitation. These details prevent a polished figure from overstating what the implementation enforces.

**Evidence:** [validation](VALIDATION.md), [figure sources and reproduction](figures/README.md).

## Checks I still owe the task

I would next test independent simulation streams, a learned-prior reference, stricter verifier isolation and more intervention worlds. I would also run a human baseline. Those checks address the most consequential assumptions; adding another attractive diagram or another aggregate match would not substitute for them.

The [assumption register](ASSUMPTIONS.md) makes those open questions explicit.
