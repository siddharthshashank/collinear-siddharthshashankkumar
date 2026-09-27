# Validation record

The current submission is **v0.1.1**. It repairs demonstrated verifier flaws and corrects the agent-facing description of probability precision and the reference. Original v0.1.0 trials remain historical evidence; they are not relabeled as runs of the revised task.

## What was frozen before the new trial

The v0.1.1 runtime was committed in [e83f997](https://github.com/siddharthshashank/collinear-siddharthshashankkumar/commit/e83f9972f310c8e66f1ea916eb5c75db70f9b5bf) before the fresh GPT-5.5-high attempt. The committed [revision manifest](validation/runtime-revision.json) records each changed file, its before/after SHA-256 and the reason for the change.

Of the historical 118 runtime files, **109 are unchanged and nine are revised**; one Docker Compose file is added, making **119 current runtime files**. The public engine, league data, private probability estimates, reference regrets, oracle and numeric scoring rule are unchanged. The original [baseline manifest](validation/task-runtime.json) is preserved.

The revised handbook gives the reference's design advantage and Monte Carlo precision accurately, and states the output/artifact constraints explicitly. Those disclosures could affect a model's approach. An old-program replay is therefore a regression check, not a substitute for a new model attempt.

## Current Harbor runs

All current runs use Harbor 0.23.0, Linux containers under Docker Engine 29.2.1 on the local Apple-silicon Mac, two requested CPU cores and 4 GB per environment.

| Run | Kind | Result | Evidence |
|---|---|---|---|
| `revision-oracle` | Included solution through Harbor | All five reward components **1.0**; no exception | [Job](validation/jobs/revision-oracle/) |
| `revision-nop` | Coin-flip starter through Harbor | Overall/functional/robustness **0.0**; constraints/artifact **1.0**; no exception | [Job](validation/jobs/revision-nop/) |
| `revision-replay-gpt55` | Archived GPT-5.5 run 2 regraded; no model call | Same failure: **1.575×** total / **1.613×** held-out regret; valid artifact and constraints | [Job](validation/jobs/revision-replay-gpt55/) |
| `revision-gpt55-high` | Fresh GPT-5.5, native Codex, high effort | **Overall 0.0**: **1.230×** total / **1.246×** held-out regret; constraints/artifact **1.0**, no exception | [Job](validation/jobs/revision-gpt55-high/) |

The oracle completed in 5 minutes 13 seconds including setup and cleanup; no-op completed in 41 seconds. The archived-program replay completed in 21 minutes and reproduced the original rewards and rounded regret ratios exactly. The fresh model trial completed in 32 minutes 4 seconds, including 18 minutes 4 seconds of agent execution and 12 minutes 42 seconds of verification. Each initial forecast run took 75–87 seconds, below the 720-second per-world limit; the successful repeat took 84 seconds. These are observations on this host, not performance guarantees. Docker can reuse image layers. This is local container validation, not a claim that a second clean machine was tested.

## Eight-trial replication

The [replication report](REPLICATION_REPORT.md) records a separate fixed batch of eight new attempts, with two slots per requested model. The [plan](validation/replication-20260927/plan.json) was committed before the batch began. Its [snapshot binding](validation/replication-20260927/snapshot-binding.json) explains the reviewer-README-only package-hash change while checking the unchanged 119 runtime files. These runs do not replace the control, replay or first fresh model records above.

All eight completed normally, with **five passes and three forecasting failures**: GPT-5.5 **1/2** passes, Opus **0/2**, Astra **2/2**, and Fable **2/2**. There were no retries or infrastructure exceptions. The [complete evidence audit](validation/replication-20260927/audit.json) checks native completion, declared model/effort/version, task identity, rewards, per-world scores, exact published copies and the result figure's input binding. A model pass is accepted by the audit; it does not require failures. Every launcher credential scan returned zero matches.

The evidence collector also has [15 passing accounting regressions](validation/replication-20260927/accounting-tests.json), separate from the 24 verifier tests below. They check that passes and failures are both accepted as completed observations, provider interruptions remain distinct, missing identity or grading evidence is rejected, and neither a completed failure nor an exhausted agent budget can be replaced by a later passing attempt. These tests use constructed native-event records and archived grading fixtures; they do not run models or establish container isolation. From the source directory, `python3 dev/test_replication_audit.py` reproduces them.

### A check of Fable's first submitted card builder

The [matchup diagnostic](validation/replication-20260927/fable-r1-matchup-audit.json) checks a specific implementation finding: the first Fable program chooses batting style adjustments from its own bowlers, then simulates against the opposition's bowlers. The public engine chooses both from the opposition. Six constructed cases reproduce the mismatch; six equal-style controls agree. Different opposing style vectors occur in 185 of the 192 shipped fixtures, so the discrepancy can be reached by the task's inputs.

The diagnostic executes only the reviewed card-building method bodies, with source hashes checked first. It does not train a model, run a forecast or use hidden probability labels. It establishes the feature-selection error, not how much it changes the aggregate score. The verifier determines whether the submitted program passes despite that error.

From the source directory, run `.venv/bin/python dev/audit_fable_matchups.py` using the pinned task dependencies. From the extracted submission, run `python reviewer_tools/audit_fable_matchups.py`. Both layouts produce the same evidence record; the publication audit binds that record to the helper, three archived source files and the 24 public world-data files it inspects.

## What the deeper audit caught

| Problem in v0.1.0 | v0.1.1 behavior | Verification |
|---|---|---|
| Root followed a solution symlink targeting private verifier files | Reject links/special files before staging; never dereference them during privileged copy | Offline container probe: false 1.0 becomes 0.0 |
| Root followed an output CSV symlink into private truth | Open path components without following links; require a regular file | Offline container probe: false 1.0 becomes 0.0 |
| Repeat could fail after writing CSV, or overwrite both compared files | Require successful repeat; compare with immutable first predictions | Focused regressions |
| Same fixture probabilities in a different row order could fail | Align both outputs by fixture ID | Valid reordered output receives 1.0 |
| Extra/duplicate fixtures and added engine files could escape checks | Check exact fixture membership and engine inventory | Focused regressions |
| Timeout cleanup covered only the immediate process | Terminate the process group, including ordinary background descendants | Child-process regression |
| A retry could retain an earlier reward | Clear prior reward/details before grading; report startup failure | Entrypoint behavior and Harbor controls |

**24 focused tests pass**: eleven contract checks and thirteen hardening regressions. Eight applicable regressions were also run against the original grader; all eight failed as expected, with zero test errors. The tests therefore demonstrate real behavior changes rather than merely matching the new implementation.

Evidence: [contract checks](validation/verifier-contract.json), [hardening checks](validation/verifier-hardening.json), [regressions before the fix](validation/verifier-regressions-before.json), and [before/after container boundary probes](validation/verifier-boundary.json). The probe uses synthetic truth and checks direct runner reads are denied before testing the symlink routes. It does not claim to audit Harbor's entire artifact-transfer implementation.

Repeatability still covers only the visible world. Process-group cleanup does not contain a deliberately detached process without stronger PID/cgroup supervision. These checks are not a complete hostile-code sandbox assessment.

## Network and environment reproduction

The verifier service declares `network_mode: none` in `tests/docker-compose.yaml`. [Docker inspection](validation/network-isolation.json) confirms the actual running Harbor verifier containers had no network. The installed Harbor nftables capability probe returned false on this Docker Desktop kernel, so its baseline policy is explicitly public with a metadata explanation; Docker enforces the verifier restriction directly. The agent environment remains public for harness installation and model API access.

The base image is digest-pinned. All five Python packages in the Linux task dependency closure are locked by version and distribution hashes. NumPy, pandas and SciPy retain the original versions; python-dateutil and six are now explicitly locked to the versions already used. Both Dockerfiles require hashes during installation. Native harness installers remain separate provider tooling; their versions are captured in the trial logs.

Both packaged images also passed fresh application-layer builds with `--no-cache --platform linux/amd64`, followed by offline package-inventory checks. The [build record](validation/clean-builds/report.json) includes commands, exit codes, context hashes, image IDs and logs. This reused the digest-pinned base on the existing host; it is not an empty-cache or second-machine test. All five locked dependencies were installed at the recorded versions in both images.

## Reproduce the checks

From the source project's `t20-exact-forecast/` directory, using new job names:

```sh
make package
make audit
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle --jobs-dir "$PWD/validation/jobs" --job-name my-oracle
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop --jobs-dir "$PWD/validation/jobs" --job-name my-nop
python3 dev/regrade_archived.py --job-name my-archived-replay
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
harbor view ./validation/jobs
make submission
```

The fresh trial uses the existing Codex sign-in through Harbor's `CODEX_AUTH_JSON_PATH` option; credentials are not committed. Other users can configure their own native harness or provider credentials. Use an absolute jobs directory for reliable Docker log copying on this host.

The regrade helper restores only documented literal redactions in a temporary copy and checks the restored engine against the pristine engine. Its restoration record lists before/after hashes. Original jobs are never edited. The helper is also included in the zip as `reviewer_tools/regrade_archived.py` and can run from the extracted task.

`make audit` verifies runtime hashes, nineteen historical model jobs, local links including heading anchors, exact copied evidence, and the seven figure exports. The [revision audit](validation/revision-audit.json) additionally binds all four new jobs to the current Harbor task digest, checks fresh execution versus regrade provenance, reconciles rewards with per-world results, and checks the build evidence against current inputs. It accepts either a legitimate model pass or a failure; it never requires a failure to pass the audit. The archive builder checks one task directory, executable entrypoints and ZIP integrity. Packaging is staged and verified before replacing the previous task; archive replacement follows successful ZIP validation.

## Earlier validation, kept separately

The earlier documentation revision ran [documentation-oracle](validation/jobs/documentation-oracle/) and [documentation-nop](validation/jobs/documentation-nop/) against the unchanged v0.1.0 runtime. They passed the positive and negative controls respectively. The oracle's 257-second verification used a relative output path and Harbor recovered from Docker-copy warnings through its fallback; later runs use absolute destinations.

No synthetic worlds or calibration data were regenerated. The old independent human review was not repeated. Current documents correct the pooled-reference uncertainty claim, account for actual model validation attempts, and distinguish the committed archived-series rule from earlier development experiments. Seven revised SVG/PNG diagrams describe current data flow and privilege boundaries; [figure sources](figures/README.md) reproduce them.
