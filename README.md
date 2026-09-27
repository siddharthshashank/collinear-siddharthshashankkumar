# Learning what to trust

**Collinear take-home · Siddharth Shashank Kumar · September 2026**

This submission contains one Harbor task, **t20-exact-forecast**. An agent receives three seasons of a simulated cricket league and writes a program that forecasts the next season's matches. The challenge is deciding how much to trust a player's short history, then finding evidence that the decision holds up on unfamiliar leagues.

The current package is **v0.1.1**. It fixes verifier artifact and output boundaries, enforces an offline verifier, and corrects the prompt's claims about probability precision and the reference's design advantage. The data, engine, oracle and numerical scoring rule remain unchanged. [Validation](t20-exact-forecast/VALIDATION.md) records a passing oracle and a fresh GPT-5.5-high forecasting failure: **1.230×** total / **1.246×** held-out reference regret against a **1.10×** limit, with valid artifacts, satisfied constraints and no infrastructure exception.

The original **v0.1.0** series recorded 0/5 Opus 4.7 passes and 0/5 GPT-5.5 graded-submission passes. One GPT result is borderline and another session was interrupted after writing its program. Those trials remain historical evidence; they are not relabeled as attempts on the revised prompt.

## Review in three steps

1. [Task overview](t20-exact-forecast/README.md): the problem, architecture and reproduction commands.
2. [Decisions](t20-exact-forecast/DECISIONS.md): why I chose this approach, what changed my mind and which tradeoffs remain.
3. [Evidence](t20-exact-forecast/RUN_REPORT.md): trial records and failure analysis, with current checks in [Validation](t20-exact-forecast/VALIDATION.md).

[Start here](START_HERE.md) maps the assignment to the delivered files. [Assumptions](t20-exact-forecast/ASSUMPTIONS.md) and [engineering notes](t20-exact-forecast/NOTES.md) support the decision record; [provenance](t20-exact-forecast/PROVENANCE.md) identifies data, authorship and assistance.

For handoff, `make submission` from `t20-exact-forecast/` creates a zip containing exactly one task directory, including the report and evidence. The [assembled task](t20-exact-forecast/dist/collinear-siddharthshashankkumar/t20-exact-forecast/) is the Harbor entrypoint; the other source directories are development material.

The [canonical brief](t20-exact-forecast/ASSIGNMENT_BRIEF.md) names conflicting model pairs. I prioritize its repeated goal/run requirement and report both pairs. The historical series contains clear GPT-5.5 / Opus 4.7 failures; it does not establish a clean failure of the newer pair named elsewhere in the brief.
