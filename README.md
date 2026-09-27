# Learning what to trust

**Collinear take-home · Siddharth Shashank Kumar · September 2026**

This submission contains one Harbor task, **t20-exact-forecast**. An agent receives three seasons of a simulated cricket league and must write a program that forecasts the next season's matches. The challenge is deciding how much to trust a player's short history, then checking whether that decision holds up on unfamiliar leagues.

The task is runnable, with an oracle, a programmatic verifier, and archived model trials. Under the rule fixed before those trials, Claude Opus 4.7 passed **0/5** and GPT-5.5 passed **0/5**. One GPT result is borderline given uncertainty in the reference; another session was interrupted after producing its submission. Both are identified in the report. The clearest failures are well away from the threshold.

## Review the submission

1. [Start here](START_HERE.md) maps the canonical assignment requirements to the deliverables.
2. [Task overview](t20-exact-forecast/README.md) explains the idea and gives the run commands.
3. [Run report](t20-exact-forecast/RUN_REPORT.md) links the evidence, diagnoses the failures, and states the fairness and verifier limitations.
4. [Design document](t20-exact-forecast/DESIGN_DOCUMENT.md) explains the choices behind the task; [provenance](t20-exact-forecast/PROVENANCE.md) identifies original work and external sources.

The runnable task is [here](t20-exact-forecast/dist/collinear-siddharthshashankkumar/t20-exact-forecast/). For handoff, `make submission` from `t20-exact-forecast/` creates a zip containing exactly one task directory, including its report and evidence. The development templates elsewhere in this repository are not additional submissions.

The supplied assignment sections 4–9 are the source of truth. Additional model trials are reported as context, not as replacements for the required GPT-5.5-high or Opus 4.7 evidence.
