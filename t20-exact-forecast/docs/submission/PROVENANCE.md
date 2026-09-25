# Provenance, attribution and evidence boundaries

**Project:** `collinear-siddharthshashankkumar/t20-exact-forecast`  
**Author:** Siddharth Shashank Kumar  
**Submission:** Markdown design record for the Collinear take-home assignment

This note separates the task's original contribution, its external foundations and the evidence available for its claims. The [design document](DESIGN_DOCUMENT.md) explains the system; [DECISIONS.md](DECISIONS.md) explains the choices; [RUN_REPORT.md](RUN_REPORT.md) records results and their qualifications.

## What was created for this assignment

This task was created for this exercise: an invented T20 league whose player abilities and conditions are hidden, but whose match mechanism is public. The submitted program must infer useful quantities from ball records and forecast new fixtures across several worlds.

The project-specific work comprises the calibration analysis; the compact ball and match simulator; the population and history generator; invented identities, transfers and future fixtures; the public input and forecast interfaces; the comparison ladder; the reference-relative grading rule; the agent/verifier separation; and the experiments used to choose and diagnose the task. Together these turn a familiar forecasting problem into a controlled evaluation of inference and verification.

This is the **net-new claim**. It is not a claim to have invented cricket simulation, regularisation, probability scoring, synthetic-data evaluation or Harbor. It is not a port of an existing benchmark, public issue, CTF, competition solution or tutorial. That is a statement about how it was built, not the result of an exhaustive search proving that no related task exists.

The earlier revision-aware backtest task and ingestion prototype are included as decision evidence. They are not additional tasks submitted for grading. The reasoning behind abandoning them is retained in [DECISIONS.md](DECISIONS.md).

## External data and its transformation

The real-world calibration source is the **Cricsheet Indian Premier League ball-by-ball archive**, maintained by Stephen Rushe. Cricsheet supplies match data in several formats, including the YAML format used by the project's parser. See the official [data downloads](https://cricsheet.org/downloads/) and [project attribution](https://cricsheet.org/about/).

The calibration used **1,243 matches and 295,557 deliveries**; the counts are printed by `dev/parse_archive.py`, and the constants were reproduced from the raw archive by the scripts under `dev/` to within 0.0007 of an earlier build. The analysis converted nested match files into delivery records, applied the documented filters, and estimated aggregate outcome profiles, reliability and contextual effects. Some model values were derived from those estimates; others were tuned or chosen explicitly.

The task worlds are newly simulated histories with invented identities. They are not renamed copies of actual IPL fixtures or player records. Real observations inform the population's statistical shape; they do not supply the forecast answers. The benchmark is consequently IPL-inspired, not an endorsed or validated predictor of actual IPL matches.

**Recorded data attribution:** Calibration constants are derived from Cricsheet data. The project notes identify the source licence as **Open Data Commons Attribution 1.0 (ODC-BY 1.0)** and preserve that attribution with the derived constants. The [ODC-BY 1.0 text](https://opendatacommons.org/licenses/by/1-0/) defines the cited licence.

**Licence.** Cricsheet publishes its data under the Open Data Commons Attribution License 1.0 (ODC-BY 1.0), and the derived constants file carries that attribution with a link to the [licence text](https://opendatacommons.org/licenses/by/1-0/). No Cricsheet row is redistributed; only aggregates ship.

## Established methods and software

Expected logarithmic regret builds on established proper-scoring-rule theory. A proper score rewards an honest probability assessment in expectation; it does not turn a finite simulator estimate into mathematical certainty. The benchmark's clipping, simulation budgets and reference-relative pass rule are separate design choices. The relevant methodological source is Gneiting and Raftery, *Strictly Proper Scoring Rules, Prediction, and Estimation*, JASA 102(477), 359–378 (2007), [DOI: 10.1198/016214506000001437](https://doi.org/10.1198/016214506000001437).

The prototype uses the Python scientific stack rather than newly implementing numerical optimisation or table processing. The runtime lock pins NumPy 2.4.4, pandas 3.0.2 and SciPy 1.17.1. These upstream projects provide their own licence notices: [NumPy](https://numpy.org/doc/stable/license.html), [pandas](https://pandas.pydata.org/docs/getting_started/overview.html#license), and [SciPy](https://scipy.org/faq/#what-are-scipys-licensing-terms). These dependencies, Harbor and the model harnesses are infrastructure, not original project contributions. This Markdown submission does not redistribute their binaries or assign a new licence to them.

## Authorship and AI assistance

The design and its decisions are my work and my responsibility. I designed and built the task with Claude, an assistant of the same family as one of the tested models, and I used AI assistance to organise, edit and check these documents.

Accordingly, this submission does not claim unaided authorship or that every implementation line was independently written by hand. The evidence for ownership is the recorded sequence of hypotheses, alternatives, experiments, corrections and accepted limitations. AI assistance is not evidence that a design claim is correct. A different model family's success does not by itself prove the absence of design influence; the argument that closes it is in the design document: the agent's container held only the public task files, and the same family's previous model failed five times reading the same handbook.

## Where the evidence is

| Material | What it supports | Boundary |
|---|---|---|
| The code under `dev/`, `league/`, `forecasters/`, `scoring/`, `harbor/` and `package_task.py`, and the stored task data | Mechanisms, interfaces, constants and grading semantics | Reading code is not a fresh end-to-end reproduction; the calibration was reproduced from the raw archive to within 0.0007 |
| The job records under `jobs/` | The two gates, the linter, and every model run of both generations with reward, details, agent log and submitted program | Archived `details.json` files carry Harbor's redaction of the word `true`; the summaries restore it in memory |
| `ablations.log` and `dev/ablate_pilots.py` | The one-constant interventions on held-out world c | One world, six programs |
| The git history | The rule committed before the first pilot job | |
| These documents | Explain the design and the evidence | They create no new pilot, preregistration or experimental result |

The truth-precision audit with independent random streams has not been performed, and the hash of the upstream archive snapshot was not recorded at download time. Both are stated as open work rather than implied as done.
