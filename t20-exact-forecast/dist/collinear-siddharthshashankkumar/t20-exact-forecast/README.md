# t20-exact-forecast

**Collinear take-home · Siddharth Shashank Kumar**

This is the one runnable Harbor task in the submission. An agent receives three seasons of a simulated cricket league and must produce a reusable program that forecasts future home-win probabilities. The challenge is handling uncertainty in short player histories and validating the resulting forecasts.

Start with [my decision record](DECISIONS.md) for the choices and changes of mind, [assumptions](ASSUMPTIONS.md) for how I handled uncertainty, and [engineering notes](NOTES.md) for the checks. [The design](DESIGN_DOCUMENT.md) explains the architecture, [the run report](RUN_REPORT.md) supplies the evidence, and [provenance](PROVENANCE.md) identifies sources and assistance. [VALIDATION.md](VALIDATION.md) records fresh checks added during the documentation revision.

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
| `tests/` | Separate verifier image, grader, fixtures and private scoring data |
| `solution/solve.sh` | Oracle installer |
| `DECISIONS.md`, `ASSUMPTIONS.md`, `NOTES.md` | Candidate reasoning, assumptions, alternatives, iteration and checks |
| `figures/` | Seven professional diagrams, editable SVGs and rendering sources |
| `RUN_REPORT.md` | Rules, controls, trials, failure analysis, fairness and reproduction |
| `jobs/` | Original job records, including failures and exclusions |
| `validation/` | Runtime hashes, evidence audit and fresh checks |
| `ASSIGNMENT_BRIEF.md` | Canonical requirements supplied for this submission |

Reviewer documents, oracle code and private evidence are outside the agent image. The Dockerfile copies only the public `environment/app/` contents into the agent workspace.

The goal-line models recorded 0/5 Opus 4.7 passes and 0/5 GPT-5.5 graded-submission passes. The full brief also names a newer pair; the assignment note explains the ambiguity and why this version does not claim a clean failure of that pair. One GPT result is borderline and one session was interrupted; the report makes both qualifications explicit. The task uses fixed Monte Carlo probability estimates, not mathematically exact truth.

The evaluated runtime remains unchanged. Known limits include a designer-informed reference, incomplete network/process isolation in the frozen verifier, and unpinned transitive dependencies. These are disclosed in the report rather than described as solved.

For source development and package regeneration, see the [GitHub repository](https://github.com/siddharthshashank/collinear-siddharthshashankkumar). Historical working notes and the earlier PDF are available there; current Markdown documentation follows the canonical brief.
