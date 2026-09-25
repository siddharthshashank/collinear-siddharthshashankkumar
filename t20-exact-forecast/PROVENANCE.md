# Provenance

`t20-exact-forecast`. Siddharth Shashank Kumar. What is new here, what is borrowed, where the data came from and under what licence, and how AI assistance was used.

## What is new

The task itself: a synthetic Twenty20 league calibrated from real data, with the match mechanism public and every magnitude hidden; a reusable forecasting interface; a ladder of comparison methods; a score against exact truth; and a pass rule committed before any model ran. The calibration analysis, the compact simulator, the world generator, the invented identities and transfers, the verifier, the packager and the experiments that chose and diagnosed the task were all built for this exercise. It is not a port of an existing benchmark, a public issue, a CTF, a competition solution or a tutorial. That is a statement about how it was built, not the result of an exhaustive search proving that no related task exists.

Two earlier tasks, a backtest audit and an exactly-once ingest service, were built first and are described in the decision record as the reason this task exists. They are not submitted for grading.

## What is borrowed

**The data.** The calibration constants are derived from the Cricsheet Indian Premier League ball-by-ball archive, maintained by Stephen Rushe: 1,243 matches and 295,557 deliveries, parsed by `dev/parse_archive.py`. (evidence: the script's printed counts; NOTES.md, the parser section) Cricsheet publishes its data under the Open Data Commons Attribution License 1.0, and `league/calibration.json` carries that attribution. No Cricsheet row is redistributed; only aggregates ship, and the raw archive is not tracked in the repository. The constants were reproduced from the raw archive by the scripts under `dev/` to within 0.0007 of an earlier build. (evidence: NOTES.md, the calibration file section) The task's worlds are freshly simulated leagues with invented players, teams and grounds; they are not renamed IPL fixtures.

**The methods.** Proper scoring rules and logarithmic regret (Gneiting and Raftery, 2007; Good, 1952), shrinkage and ridge penalties (James and Stein, 1961; Hoerl and Kennard, 1970), cross-validation (Stone, 1974), the Bradley-Terry model (1952), the Ornstein-Uhlenbeck process for form, split-half reliability (Spearman, 1910; Brown, 1910), and the published Twenty20 simulators (Swartz, Gill and Muthukumarana, 2009; Davis, Perera and Swartz, 2015) are all standard. The full list is in the design document's references. I am not claiming to have invented any of them; the contribution is the task.

**The software.** NumPy 2.4.4, pandas 3.0.2 and SciPy 1.17.1 under their own licences, Docker, Harbor, and the two model harnesses are infrastructure, not contributions.

## AI assistance

The design and every decision in it are my work and my responsibility. I designed and built the task with Claude, an assistant from the same model family as one of the models later tested, and I used AI assistance to organise, edit and check these documents. I do not claim unaided authorship.

Two consequences are worth stating. First, the evidence for ownership is the recorded sequence of hypotheses, alternatives, experiments, corrections and accepted limitations in the notes and the decision record, not a claim that every line was typed by hand. Second, because the assistant's family later passed the task, I checked that the pass was not family affinity: the agent's container held only the public task files, so nothing from the design work could reach it; the same family's previous model failed five times reading the same handbook; and a model from a different lab passed too. (evidence: RUN_REPORT.md, Sections 5 and 6, with job identities) Those three facts are in the design document, Section 9.

## Where the evidence is

| Material | What it supports |
|---|---|
| The code under `dev/`, `league/`, `forecasters/`, `scoring/`, `harbor/` and `package_task.py`, and the stored task data | Every mechanism, interface, constant and grading rule |
| The job records under `jobs/` | The two gates, the linter, and all eighteen model jobs of both generations, fifteen completed, each with its reward, per-world details, agent log and submitted program |
| `ablations.log` and `dev/ablate_pilots.py` | The one-constant interventions on the six first-round programs |
| The git history | The rule committed before the first pilot job |
| `NOTES.md` | The file-by-file study and the known-number checks |

Two things are not done and are stated as open work rather than implied: the truth-precision audit with independent random streams, and recording the hash of the Cricsheet archive at download time.
