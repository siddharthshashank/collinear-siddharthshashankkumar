# t20-exact-forecast

**Collinear take-home · Siddharth Shashank Kumar**

This is the one runnable Harbor task in the submission. An agent receives three seasons of a simulated cricket league and must produce a reusable program that forecasts future home-win probabilities. The challenge is handling uncertainty in short player histories and validating the resulting forecasts.

Read this overview first, then [my decision record](DECISIONS.md), then [the run report](RUN_REPORT.md). [Assumptions](ASSUMPTIONS.md) and [engineering notes](NOTES.md) support the reasoning; [the design](DESIGN_DOCUMENT.md) explains the architecture. [VALIDATION.md](VALIDATION.md) distinguishes the current version's checks from historical trials.

## Version and evidence

This is **v0.1.1**. It hardens the verifier against symbolic-link and private-output leaks, requires exact fixture coverage, compares repeat forecasts by fixture ID, cleans up child processes and prevents stale rewards from surviving a failed run. `tests/docker-compose.yaml` disables verifier networking; the Dockerfiles install hash-locked dependencies. The agent-facing instructions now disclose probability uncertainty and the reference's design advantage accurately.

Current validation: **oracle passes all components**; a fresh **GPT-5.5-high** attempt fails forecast quality at **1.230×** total / **1.246×** held-out reference regret, with artifact and constraint scores **1.0** and no infrastructure exception. The limit is **1.10×**.

The original **v0.1.0** jobs remain historical evidence. Fresh controls, an archived-program replay and current model evaluation are recorded in [VALIDATION.md](VALIDATION.md). Because the handbook changed, replaying an old program does not establish what a new agent would do with the revised task.

## Run after extraction

Prerequisites: a running Docker daemon and Harbor 0.23.0. Model runs also require access through the chosen model harness/provider. Oracle and no-op runs need no model credentials.

From the extracted `collinear-siddharthshashankkumar/` directory:

```sh
harbor run -p ./t20-exact-forecast -a oracle
harbor run -p ./t20-exact-forecast -a nop
harbor run -p ./t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
# Alternative target model allowed by the assignment:
harbor run -p ./t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
harbor view ./jobs
```

Expected controls: oracle `overall = 1.0`; no-op `overall = 0.0`. A zero reward must be read alongside `verifier/details.json` and the trial's `result.json` to distinguish forecast failure from infrastructure failure.

New jobs are written next to the task directory. The task's own `jobs/` contains original evidence; inspect it with `harbor view ./t20-exact-forecast/jobs`.

## What is included

| Path | Purpose |
|---|---|
| `instruction.md` | Agent prompt and deliverable |
| `task.toml` | Metadata, timeouts, resources and environment configuration |
| `environment/` | Pinned agent image, public engine, data, handbook and starter |
| `tests/` | Separate offline verifier, Compose network policy, grader, fixtures and private scoring data |
| `solution/solve.sh` | Oracle installer |
| `DECISIONS.md`, `ASSUMPTIONS.md`, `NOTES.md` | Candidate reasoning, assumptions, alternatives, iteration and checks |
| `figures/` | Seven architecture diagrams, editable SVGs and rendering sources |
| `RUN_REPORT.md` | Rules, controls, trials, failure analysis, fairness and reproduction |
| `jobs/` | Original job records, including failures and exclusions |
| `validation/` | Runtime hashes, evidence audit and fresh checks |
| `ASSIGNMENT_BRIEF.md` | Canonical requirements supplied for this submission |

Reviewer documents, oracle code and private evidence are outside the agent image. The Dockerfile copies only the public `environment/app/` contents into the agent workspace.

In the historical series, the goal-line models recorded 0/5 Opus 4.7 passes and 0/5 GPT-5.5 graded-submission passes. The full brief also names a newer pair; the assignment note explains the ambiguity and why this version does not claim a clean failure of that pair. One GPT result is borderline and one session was interrupted; the report makes both qualifications explicit. The task uses fixed Monte Carlo probability estimates, not mathematically exact truth.

The data, engine, oracle and scoring inputs remain unchanged. The current 119-file runtime consists of 109 unchanged historical files, nine revised files and one new Compose file, documented in `validation/runtime-revision.json`. Statistical limits remain: the reference has designer-informed priors, simulation uncertainty is not fully measured, and the model samples are small. The report keeps those limits separate from the verifier defects fixed in this version.

For source development and package regeneration, see the [GitHub repository](https://github.com/siddharthshashank/collinear-siddharthshashankkumar). Historical working notes and the earlier PDF are available there; current Markdown documentation follows the canonical brief.
