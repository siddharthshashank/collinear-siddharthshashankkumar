# t20-exact-forecast

**Can an agent tell how much of a player's recent form is real?**

I built this task around a common forecasting mistake: treating a short, noisy record as a reliable estimate of ability. A program can run cleanly and still make that mistake. The task asks an agent to discover it, correct for it, and deliver a forecaster that works on leagues it has never seen.

The setting is a simulated Twenty20 cricket league. The agent gets three seasons of ball-by-ball history, the public match engine, and next season's fixtures and line-ups. It writes `solution/forecast.py`, which returns a home-win probability for each fixture. The verifier evaluates those probabilities across eight leagues against stored estimates generated using the hidden simulation state.

“Exact” in the task name refers to evaluating expected loss against probabilities rather than scoring a single match result. The probabilities themselves are Monte Carlo estimates, not closed-form truth. That distinction matters near the pass threshold.

![From calibration and task packaging to Harbor execution and evidence](figures/system_overview.png)

*Redrawn with Codex assistance from the repository and the earlier architecture by Rutvikk Kharod; [editable sources](figures/README.md) and [provenance](PROVENANCE.md).*

## What the runs show

| Model and harness | Graded submissions | Passes | Total regret / reference |
|---|---:|---:|---:|
| Claude Opus 4.7 · Claude Code · high effort | 5 | 0 | 1.364–1.703 |
| GPT-5.5 · Codex · high effort | 5 | 0 | 1.109–1.575 |
| Claude Fable 5.1 · Claude Code · high effort, supplementary | 3 | 2 | 1.008–1.104 |
| GPT-6-astra · Codex · high effort, supplementary | 2 | 2 | 1.054–1.072 |

The pass limit is **1.10×** the reference's regret, applied to all eight worlds and separately to the seven held-out worlds. A complete pass also requires valid output and the constraint checks. The limit was fixed before model trials.

The ten required-model submissions all missed the recorded rule. GPT-5.5's 1.109 result is borderline given uncertainty in the reference; a different GPT-5.5 session hit an account limit after writing its program. Excluding that interrupted session leaves 0/4 GPT-5.5 passes. The report accounts for four other excluded jobs, including one where the verifier graded the unchanged starter. These are not counted as substantive model failures.

For the first six submissions, inspection and one-constant interventions support a specific diagnosis: the programs gave short player histories too much weight, and their checks did not catch it. The interventions cover one world; they do not show that one edit would pass the full task. [Read the evidence and limitations](RUN_REPORT.md).

## Run the packaged task

Prerequisites: Docker with a running daemon, and **Harbor 0.23.0**, the version used for the archived jobs. Model trials also need access through the relevant harness/provider. Oracle and no-op runs do not need model credentials. Harbor's optional `check` command uses a language model and does need access.

From the **Git repository root**:

```sh
cd t20-exact-forecast
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
# Alternatively, use the other model allowed by the brief:
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
harbor view ./jobs
```

Expect `overall = 1.0` for the oracle and `overall = 0.0` for no-op. Inspect each trial's `verifier/reward.json`, `verifier/details.json` and `result.json`; a zero caused by a grader error is not evidence of model failure. Existing data and the packaged task are committed, so no calibration download or data regeneration is needed to run them.

## Rebuild and prepare the handoff

From this directory, with Python 3.12 available:

```sh
make venv PYTHON=python3.12
make package
make audit
make submission
```

`make submission` writes `submission/collinear-siddharthshashankkumar.zip` and a SHA-256 checksum. The archive contains exactly one Harbor task directory, with its documentation, original evidence and validation records. It does not include the `harbor/` development templates as a second task. The package's README has commands for running after extraction.

`make data` is only for regenerating the synthetic data; it is not a prerequisite for reviewing or running this submission. Its cache does not track every input, so a changed simulator needs an intentional fresh data build. Rebuilding the original calibration additionally needs the untracked Cricsheet archive, whose download hash was not recorded.

## Read further

| Document | Purpose |
|---|---|
| [Decisions](DECISIONS.md) | Why I chose this task, alternatives rejected, evidence that changed the design and accepted costs |
| [Assumptions](ASSUMPTIONS.md) | How I resolved ambiguity, what is supported, and what would make me revisit a choice |
| [Design](DESIGN_DOCUMENT.md) | Task idea, economic relevance, architecture and long-horizon difficulty |
| [Run report](RUN_REPORT.md) | Rules, trial identities, failure analysis, fairness audit and known verifier weaknesses |
| [Validation](VALIDATION.md) | Fresh checks and evidence added during this documentation revision |
| [Provenance](PROVENANCE.md) | Original work, data, licenses, drawings and AI assistance |
| [Engineering notes](NOTES.md) | How I checked each important boundary and what those checks caught |
| [Architecture figures](figures/README.md) | Seven consistent, editable diagrams with reproduction commands |

The full assignment is reproduced in [ASSIGNMENT_BRIEF.md](ASSIGNMENT_BRIEF.md), including the conflicting model names and my explicit interpretation. Current Markdown documentation takes precedence over the earlier `docs/DESIGN.pdf`, which is retained as a historical design artifact.
