# Learning what to trust

**Collinear take-home · Siddharth Shashank Kumar · September 2026**

This submission contains one Harbor task, **t20-exact-forecast**. An agent receives three seasons of a simulated cricket league and must write a program that forecasts the next season's matches. The challenge is deciding how much to trust a player's short history, then checking whether that decision holds up on unfamiliar leagues.

The task is runnable, with an oracle, a programmatic verifier, and archived model trials. Under the rule fixed before those trials, Claude Opus 4.7 passed **0/5** and GPT-5.5 passed **0/5**. One GPT result is borderline given uncertainty in the reference; another session was interrupted after producing its submission. Both are identified in the report. The clearest failures are well away from the threshold.

## Review the submission

1. [Start here](START_HERE.md) maps the canonical assignment requirements to the deliverables.
2. [Task overview](t20-exact-forecast/README.md) explains the idea and gives the run commands.
3. [Run report](t20-exact-forecast/RUN_REPORT.md) links the evidence, diagnoses the failures, and states the fairness and verifier limitations.
4. [Decision record](t20-exact-forecast/DECISIONS.md) explains my choices, rejected alternatives and changes of mind; [assumptions](t20-exact-forecast/ASSUMPTIONS.md) separates what is supported from what I still need to test.
5. [Design document](t20-exact-forecast/DESIGN_DOCUMENT.md) and redesigned architecture figures explain the system; [provenance](t20-exact-forecast/PROVENANCE.md) identifies sources and assistance.

The runnable task is [here](t20-exact-forecast/dist/collinear-siddharthshashankkumar/t20-exact-forecast/). For handoff, `make submission` from `t20-exact-forecast/` creates a zip containing exactly one task directory, including its report and evidence. The development templates elsewhere in this repository are not additional submissions.

The [full assignment](t20-exact-forecast/ASSIGNMENT_BRIEF.md) names two model pairs. The documents explain my interpretation and report both: this version establishes clear failures for the goal-line GPT-5.5 / Opus 4.7 pair, but does not establish a clean newer-pair failure.
