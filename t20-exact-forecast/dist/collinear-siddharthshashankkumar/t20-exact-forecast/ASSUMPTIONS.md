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
| Stored probabilities are precise enough for clear failures | Large simulation batches are generated once | Much more precise than a single realized result; independent-stream audit remains open | Rebuilding truth or reference estimates changes outcomes beyond the borderline cases |
| The allotted compute permits a sound solution | Difficulty should come from reasoning, not an arbitrary timeout | Original oracle verification took about 4.3 minutes; successful agent submissions exist | A competent alternative needs materially more time for reasons unrelated to poor implementation |
| The verifier measures the intended outcome | It scores probabilities and checks program behavior | Oracle, no-op and focused behavior checks pass; adversarial isolation is incomplete | A shortcut earns a full reward without solving the forecasting problem |
| One-setting interventions help diagnose the failure | They test whether a suspected modeling choice affects the score | Six programs, one held-out world; original outputs reproduced first | The effect disappears across other worlds or depends on an unrelated implementation change |

## The assumptions with the greatest consequence

The reference advantage and simulation uncertainty matter most to the fairness argument. I would measure both before tightening the task. An oracle pass proves that one solution works through the interface; it does not prove that the threshold is equally fair to every sound method.

The brief's model conflict is separate from task quality. The current record supports clear failures of the goal-line pair. It does not establish a clean failure of the newer pair named elsewhere in the brief. I would not use the borderline Fable result to hide that distinction.

## What is intentionally held constant

The agent-facing prompt, data, engine, oracle and verifier remain at the evaluated version. Documentation can explain an assumption more accurately without pretending that the agent received that clarification during the original trials.

A change to those runtime files, the reference or the pass rule would be a new version. It would need fresh controls, a newly fixed threshold where relevant, and new model evidence.

See [DECISIONS.md](DECISIONS.md) for the reasoning behind the choices, [RUN_REPORT.md](RUN_REPORT.md) for observations, and [VALIDATION.md](VALIDATION.md) for the checks that were actually run.
