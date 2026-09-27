# Assumptions I made, and how I would challenge them

**Siddharth Shashank Kumar · t20-exact-forecast**

These assumptions let me move from an ambiguous brief to a runnable experiment. They are not all established facts. This table records the basis for each choice and the observation that would make me revise it.

| Assumption | Why I used it | Evidence and current status | What would change my mind |
|---|---|---|---|
| GPT-5.5-high / Opus 4.7 are the primary target pair | They appear in the brief's goal and explicit run requirement | The full brief also names GPT-6-astra-high / Fable 5.1. Both pairs were evaluated; the conflict remains explicit | Clarification that a clean failure of the newer pair is mandatory would require a new task evaluation |
| A synthetic league is a useful proxy for uncertainty handling | The task still requires estimation, validation and a reusable deliverable | Real data calibrate aggregates; the engine remains a simplified model | A solution can exploit a generator-specific shortcut without doing the intended inference |
| Giving the engine makes the task fairer | It removes ambiguity about match mechanics | All solvers can inspect the same code; the handbook describes hidden-effect families | Evidence that an undocumented rule or reader defect causes a substantive failure |
| Three seasons contain enough usable signal | The task needs to separate careful estimation from weak alternatives | The oracle and independently written agents pass; comparison methods miss the rule | A broader set of worlds shows that reference success relies on unusually favorable data |
| Pooled regret is more useful than requiring every world to pass | Individual worlds differ in noise and difficulty | Development analysis motivated pooling; a second held-out-only rule protects generalization | A method systematically neglects an important subset while still meeting both pooled limits |
| The reference is a useful standard | It is a working, inspectable statistical implementation | It passes through the public interface, but its base priors are designer-informed | A learned-prior reference materially changes the pass/fail picture |
| Stored probabilities are precise enough for clear failures | Large simulation batches are generated once | Truth and reference still have Monte Carlo error; the 1.14% pooled-reference estimate assumes zero cross-world covariance and is not a measured pooled SD | Rebuilding truth or reference estimates changes outcomes beyond the borderline cases |
| The allotted compute permits a sound solution | Difficulty should come from reasoning, not an arbitrary timeout | Original oracle verification took about 4.3 minutes; successful agent submissions exist | A competent alternative needs materially more time for reasons unrelated to poor implementation |
| A separate verifier container protects the answers | It separates private files from the agent session | The deeper audit found two privileged symlink-read routes. Both are rejected in v0.1.1 container probes; this is targeted assurance, not a complete sandbox audit | An artifact makes privileged code follow a candidate-controlled path into verifier-only files |
| One-setting interventions help diagnose the failure | They test whether a suspected modeling choice affects the score | Six programs, one held-out world; original outputs reproduced first. GPT runs 2, 4 and 6 also attempted predictive validation, so missing validation is not a general diagnosis | The effect disappears across other worlds or depends on an unrelated implementation change |

## The assumptions with the greatest consequence

The reference advantage and simulation uncertainty matter most to the fairness argument. I would measure both before tightening the task. An oracle pass proves that one solution works through the interface; it does not prove that the threshold is equally fair to every sound method.

The brief's model conflict is separate from task quality. The record supports clear failures of the goal-line pair. It does not establish a clean failure of the newer pair named elsewhere in the brief: both fresh Astra trials and both fresh Fable trials passed. I would not use the historical borderline Fable miss, or a code defect in a passing program, to claim the missing outcome.

## What a revision can and cannot establish

The original v0.1.0 jobs remain historical evidence. The verifier hardening is identified as v0.1.1 and validated separately; an archived-program replay is distinct from a new model trial. Documentation can clarify a flaw without pretending the original agent saw a revised prompt or ran against a revised verifier.

Changing the reference or pass rule would be a further measurement change. It would need a new bar analysis, fresh controls and new model evidence. Preserving a record is necessary for an honest comparison, but it is not a reason to leave a demonstrated verifier bypass in the submitted version.

See [DECISIONS.md](DECISIONS.md) for the reasoning behind the choices, [RUN_REPORT.md](RUN_REPORT.md) for observations, and [VALIDATION.md](VALIDATION.md) for the checks that were actually run.
