# Validation record

These checks were performed for the documentation and packaging revision on **27 September 2026 UTC** (26 September in America/Chicago). They are separate from the original target-model trials.

## Fresh Harbor controls

Both runs used Harbor 0.23.0 and Docker Engine 29.2.1 on the local Apple-silicon Mac, with the task's pinned images and dependencies.

| Check | Result | Evidence |
|---|---|---|
| Oracle through Harbor | Overall, functional correctness, robustness, constraints and artifact quality all **1.0**; no trial exception | [Oracle job](validation/jobs/documentation-oracle/), [reward](validation/jobs/documentation-oracle/t20-exact-forecast__GozzCrT/verifier/reward.json) |
| No-op through Harbor | Overall, functional correctness and robustness **0.0**; constraints and artifact quality **1.0**; no trial exception | [No-op job](validation/jobs/documentation-nop/), [reward](validation/jobs/documentation-nop/t20-exact-forecast__ecNESW7/verifier/reward.json) |

Oracle verification took about 257 seconds. No-op verification took about 9 seconds. These timings describe this host, not a performance guarantee.

The oracle job used a relative output path. Harbor logged Docker Compose copy failures, recovered through its fallback copy paths, and completed successfully. The no-op job used an absolute output path. For custom job destinations, an absolute path avoids that warning in this environment.

Commands, from the source project's `t20-exact-forecast/` directory:

```sh
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle --jobs-dir ./validation/jobs --job-name documentation-oracle
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop --jobs-dir "$PWD/validation/jobs" --job-name documentation-nop
```

Use fresh job names when rerunning. Docker may reuse cached layers; this is a successful local container execution, not a claim that a second clean machine was tested.

## Runtime preservation and evidence audit

[task-runtime.json](validation/task-runtime.json) records SHA-256 hashes for the **118 evaluated runtime files** from commit `3c28a55`. The packager and audit require them to remain unchanged. Reviewer documentation and evidence are added outside the agent and verifier Docker build contexts.

`dev/audit_submission.py` checks:

- Required task files, executable shell scripts, eight graded worlds and exactly one packaged `task.toml`.
- Runtime hashes against the recorded baseline.
- Nineteen original model jobs, including all four exclusions.
- Target-model harness and high-effort configuration, reward fields, result/reward consistency, program artifacts and rounded per-world regret summaries.
- Local links in the current reviewer documents.

Its result is [evidence-audit.json](validation/evidence-audit.json). The archived per-world regrets are rounded, so reconstructed ratios use a tolerance of 0.002. Known redaction of the literal `true` is restored only in memory. Original evidence is preserved.

## Focused verifier checks

`dev/test_verifier_contract.py` exercises the frozen grader on small synthetic fixtures: known-probability success, coin-flip failure, missing fixtures, nonfinite and out-of-range values, engine edits, changed repeat output, missing programs, the two separate regret rules, and a hand-calculable log score.

The results and test names are in [verifier-contract.json](validation/verifier-contract.json). These checks test observable grader behavior. They do not claim to test network isolation, privilege boundaries, timeout process cleanup, simulator correctness or every possible adversarial submission.

From the source project directory:

```sh
make package
make audit
make submission
```

The archive builder verifies that the zip contains one task directory, preserves executable modes, passes the zip integrity check, and matches all 118 runtime hashes. It writes the archive's SHA-256 beside the zip.

## What was not rerun or changed

No fresh paid target-model trial or Harbor LLM review was added. The original target-model evidence is retained and indexed in [RUN_REPORT.md](RUN_REPORT.md). The synthetic worlds and original calibration were not regenerated, and the old independent review was not repeated in full.

The runtime preservation is deliberate: changing the grading rule, reference or agent-facing handbook would need a new evaluation. Known fairness, isolation and reproducibility limitations remain visible in the report.

## Decision-document and architecture revision

The full brief supplied in the follow-up is preserved in ASSIGNMENT_BRIEF.md. DECISIONS.md, ASSUMPTIONS.md and NOTES.md now explain the candidate's choices, unresolved assumptions and validation work, and are included in the one-task package.

Seven architecture diagrams were redrawn as editable SVGs with 2400 × 1440 PNG exports. The figures distinguish the public image, separate verifier, oracle route, grading gates and pre-pilot research. Their wording reflects the frozen runtime's actual limitations. The source and reproduction steps are in [figures/README.md](figures/README.md).

This revision rechecks the package, document links, figure artifacts and runtime hashes. It does not rerun paid model trials or change the evaluated task. The fresh control runs above remain the validation evidence for that unchanged runtime.
