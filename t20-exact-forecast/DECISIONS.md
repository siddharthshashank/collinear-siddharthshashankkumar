# Why I built it this way

Decision record for `t20-exact-forecast`. Siddharth Shashank Kumar.

This file answers the "why not the other way?" questions. Each entry says what I decided, why, what else I could have done, what the choice cost, and whether it still stands. Everything here is backed by the repository: the code, the job records under `jobs/`, the logs and the git history. The design document explains the system; the run report holds the results; this file explains the choices.

The one fact that matters most for reading it: the pass rule was committed before any model ran, in the commit "Harbor metadata, pass bar, lock file, instruction", which precedes the first pilot job, `2026-09-23__19-48-37`, in the git log. Decisions D14 onward were taken after that commit and none of them touched the rule.

---

## D1. Test judgement under uncertainty, not rule-following

**What I decided.** To build a forecasting task with hidden statistical quantities, instead of continuing with my first task, a repository of backtests that silently used revised data.

**Why.** The backtest task came from a real problem in my work and I built it properly: forty-eight scripts, one written rule, a verifier. Then Claude Opus 4.7 and GPT-5.5 solved it at every size.[^1] Adding more files added work, not difficulty. The lesson was that a capable agent implements anything it can read. What it cannot read is how much to trust a number.

**What else I could have done.** I also built a small ingest service under a declared fault model, with 27,710 fault schedules and five planted defects.[^2] It had a good verifier and a tight fix-and-test loop, and I judged that loop would be closed by the top models too. I did not pilot it; that was a judgement call.

**What it cost.** Two weeks of work on the other two tasks became design evidence rather than a submission.

**Stands.**

## D2. Cricket, calibrated from the IPL archive, with everyone invented

**Why cricket.** Small matches that simulate fast, rich ball-level records, players who recur but never enough to be sure, and an outcome everyone understands.

**Why the IPL archive.** Cricsheet publishes every ball since 2008 under an open licence; I could measure real behaviour instead of inventing it. The key measurement, that only about half of a batter's season-to-season difference is real, is the trap at the centre of the task.[^3]

**Why invented players and grounds.** Knowing a real player's reputation would substitute memory for inference. In the world, only statistics survive from reality; no name does.

**What else I could have done.** Real matches, graded on results: luck decides. An uncalibrated toy league: easy to dismiss.

**What it cost.** No claim about real cricket. Cricket knowledge is worth nothing to the agent, as intended.

**Stands.**

## D3. Grade against the exact truth of a world I own

**What I decided.** For every fixture the grader holds the true home-win probability, computed on the same engine with the hidden values, and scores a forecast by its distance from that truth.

**Why.** A result is one noisy draw. On 192 fixtures the noise from results alone is about twice the gap between a careful and a careless forecaster.[^4] Grading against the truth removes luck from the grade entirely.

**What it cost.** The world has to be synthetic, which is D2's cost again.

**Stands.**

## D4. Logarithmic regret, clipped, with skill reported but never graded

**Why logarithmic rather than squared error.** Both are honest scores. The logarithmic one charges most for confident mistakes, and confident mistakes were the failure I expected and the one every failed run showed.

**Why clip at 0.002.** So that one reckless zero cannot give an infinite penalty. True probabilities sit between about 0.2 and 0.8, so the clip never touches an honest forecast.[^5]

**Why report skill but not grade it.** A skill score is a ratio of two honest scores, and a ratio is not itself honest. It is printed for readers only.

**Stands.**

## D5. Ship the engine; hide only the magnitudes

**What I decided.** The agent gets the match engine as code with its general constants. The spreads of player ability, the speed of form drift, the size of home advantage and dew, and every player's ability are hidden.

**Why.** If I described the mechanics in prose and the agent got a detail wrong, the task would be measuring my prose. With the engine shipped, every forecaster plays by identical rules and differs only in what it believes about the players. Estimation is the test.

**What else I could have done.** Hide the mechanics too. That would add difficulty of the wrong kind: not knowing the rules.

**What it cost.** The agent gets a powerful development tool, and reverse engineering is off the table as a source of difficulty. Both are intended.

**Stands.**

## D6. Tell the agent everything about the structure, including the traps

**What I decided.** The handbook states every file, column, rule, formula, tolerance and time limit; the ball model in words; the structure of everything hidden; that there is no batter-versus-bowler effect; that a coin flip has a little under twice a good forecaster's regret; and that the agent may generate leagues on the engine and test itself against known truth.

**Why.** A task can be hard because the rules are unknown or because the quantities are unknown. Only the second is fair.

**What it cost.** An agent that uses the yardstick and the self-check route has an easier time. The runs show that having the route is not the same as using it well: one Opus run built the check and aimed it at the wrong world.

**Stands.**

## D7. Only effects that repeat in independent halves of the archive

**What I decided.** An effect enters the world only if it shows up again when the archive is split in two. Grounds repeat (0.71): in. Batter at a ground repeats weakly (0.19): in, small. Bowler at a ground repeats at about zero: out. A specific batter against a specific bowler repeats at 0.18 on the best-sampled pairs: out, replaced by one pace-versus-spin tendency per batter.[^6]

**Why.** Every plausible cricket effect can be written into a simulator. The question is which ones exist. Putting a fan's intuition in would plant noise and call it skill.

**What it cost.** A cricket expert would say the world is too simple. The head-to-head rung of the ladder is the worst of all five as a result, which is the trap working.

**Stands.**

## D8. Measured constants and chosen constants kept apart, with reasons

**What I decided.** Two classes in the code: measured values from the archive, and chosen values, each with a comment saying why: derived from a measurement, tuned to hit a real aggregate, or plain judgement.

**Why.** So a reviewer can dispute a choice without touching a measurement, and so the three tuned aggregates are visibly not independent validation.

**Stands.**

## D9. A compact engine, and no captain

**What I decided.** Six ball outcomes plus extras, a scoreboard-and-striker state, no fielding, partnerships or memory. The toss winner always chases, five bowlers rotate in a fixed pattern.

**Why.** Every extra mechanism is another quantity the agent must infer and another claim I must justify. A captain's decision policy would be a second hidden agent inside the world.

**What it cost.** Realism claims shrink further. Grading is unaffected, since the truth is computed under the same rules.

**Stands.**

## D10. Three seasons, a quarter of players transferring, a fresh eleven each match

**Why three seasons.** The first ladder ran on 109 matches of history and nobody, careful or careless, beat the coin flip.[^7] 270 matches is where good methods separate from careless ones without the task becoming a parameter-recovery exercise.

**Why transfers and changing elevens.** So a team's name is weak evidence and the agent has to model players. The team-ratings rung is worse than a coin flip as a result.

**Stands.**

## D11. Eight worlds, one visible and seven held out

**Why.** A program tuned to the one visible league must also work on seven it never saw. Eight worlds also cut the noise in the summed grade to about one percent, which D12 needs.

**What it cost.** Generalisation is tested within one generator family, not beyond it.

**Stands.**

## D12. Sum regret over the eight worlds, then apply one tolerance, twice

**What I decided first.** A tolerance on every world separately.

**What changed my mind.** I ran the reference on eight development worlds that are never graded, re-simulating it four times to measure its own noise, and fitting the two nearest careless methods to measure separation. Noise reached 5.9 percent on one world; the careless "no shrinkage" method was only 6 to 7 percent above the reference on two; on one world a coin flip beat the reference. No single tolerance could absorb the noise and exclude the careless methods.

**What I decided instead.** Add the world regrets before applying the tolerance, and apply the same rule to the seven held-out worlds on their own. Summed, the noise is about 1.1 percent (the spread of the four re-simulated repeats summed across the eight worlds) and the careless methods sit at 1.30, 1.93 and 1.90 times the reference.[^8]

**What it cost.** A method can be weak on one world and still pass. The second application of the rule stops a strong visible world from carrying a weak method, and Fable's second run showed it working in reverse: a pass on the seven unseen worlds, a fail on all eight because of the one it could see.

**Stands.**

## D13. Ten percent, committed before any pilot, never moved

**Why ten.** About nine times the summed noise, a third of the way to the nearest careless method. A choice, tied to two measured numbers.

**Why commit first.** A bar chosen in sight of the scores is not a bar. `harbor/bar.json` was committed before the first pilot job, the handbook's numbers are filled from it at packaging, and it has not changed through a near miss at 1.109, a nearer one at 1.104, and the newer pair's passes.[^9] A tolerance of 1.12 would have passed the first near miss; I report that and do not act on it.

**Stands.**

## D14. A reference built from the agent's files, with its advantage stated

**What I decided.** The bar's denominator is the careful forecaster from the ladder, loaded through the agent's own reader and fitted from the reloaded public files, so it sees nothing the agent cannot. Its prior scales were set by me, knowing the true spreads. That advantage is stated in the design document.

**What else I could have done.** A reference that learns its spreads from the data. I built one in an earlier round and it scored six to seven percent lower regret than the hand-set reference[^10], and I did not adopt it, because adopting it needs a fresh bar analysis and a fresh committed rule before any pilot, and the ten pilots had already run under the current one.

**What it cost.** The tolerance softens the advantage; it does not remove it. The ablations put its worth at about half of a careless program's excess error. The passing programs removed it themselves by learning the spreads, which is the strongest reason to make that the next reference.

**Stands, with the limitation recorded.**

## D15. Truth at 100,000 copies per batting order, stored

**Why so many.** The answer used to judge a forecast should be far more precise than the forecast. 200,000 played matches per fixture put the truth's error at about 0.001 per probability, a quarter of one percent of the reference's regret.[^11] Spending it once at build time keeps every grading run cheap and deterministic.

**What it cost.** Twenty-five minutes of build time, and one caveat: the random streams behind the truth are shared across worlds by fixture number, so the worlds' tiny truth errors are not fully independent. Recorded as future work.

**Stands.**

## D16. A separate verifier, an unprivileged runner, a pristine engine

**Why.** The reward has to be earned by forecasting. The truth lives in a container the agent never sees; the program runs as a user that cannot read the private files; it runs beside a pristine engine while the agent's engine is only hashed. Harbor's linter passed all 22 checks, including the anti-cheating ones.[^12]

**What it cost.** A laptop run of the grader has no such boundary, which is the intended difference between a local check and the real gate.

**Stands.**

## D17. My own prefix in the task's name

**Why.** The brief asks for a stable slug "such as" `collinear-candidate/<task-name>`. I read "such as" as a format and used `collinear-siddharthshashankkumar/t20-exact-forecast`, chosen before any pilot and never changed, which is the property that matters.

**Stands.**

## D18. Five pilots per model, alternating, in the native harnesses at high effort

**Why five.** After three per model the picture was clear and time remained; two more rounds ran unattended while the documents were written. Five is still a small sample and the documents say so.

**Recorded.**

## D19. The near miss stays a failure

**What happened.** GPT-5.5's third run missed by 0.9 points on all eight worlds and 1.7 on the held-out seven. A tolerance of 1.12 would have passed it.

**Why it stays a failure.** The rule was fixed first. The ablations later showed the near miss was too-loose priors compensated by softening every output toward 0.5, not correct regularisation.

**Stands.**

## D20. Count the interrupted run and flag it

**What happened.** GPT-5.5's fourth run wrote a complete program, then Codex reported my account's usage limit and the session ended at 13 minutes. The program was graded: 1.362, same fingerprint as the others.[^13]

**Why count it.** The verdict is a valid observation of that program. The interruption was my account's, not the model's, so the run is weaker evidence about what the model could have done with its full budget; it is flagged everywhere it appears. Excluding it changes no conclusion.

**Recorded.**

## D21. Read the programs, then intervene, rather than trust the fingerprints

**Why.** A fingerprint, which ladder rung a forecast most resembles, is a lead, not a cause. Reading the six first-round programs found prior scales 3 to 44 times too weak and no accuracy checks. Changing that one constant per program and re-grading on one world confirmed it: every program moved most of the way to the reference, four of five by more than half their excess, the fifth by 45 percent, and the near miss beat the reference once its priors were halved.[^14]

**What it cost.** One world, six programs. Runs 7 to 10 are attributed by resemblance only.

**Recorded.**

## D22. Run the newer pair on the frozen task, and report their passes

**Why.** The brief names two pairs. Running the newer one on the same task under the same rule is the only way to say where the bar sits between generations. It also settled a question I owed the reader: since I built the task with an assistant from Fable's family, a pass by Fable alone could be affinity. GPT-6-astra passing too, and Opus 4.7 failing five times reading the same handbook, closes that.[^15]

**What I would not do.** Change the task to turn those passes into failures without a new version, a new bar analysis and a new committed rule.

**Stands.**

## D23. Stop the loop after four of its six runs

**Why.** Three completed Fable runs and two completed GPT-6-astra runs already answered the question; the last two would have refined a rate I do not need to be precise. The two interrupted runs are recorded as excluded with their reasons, not as failures.

**Recorded.**

## D24. Housekeeping

- **Session directories.** A commit swept in Claude Code's session state, including key files. Removed from the index, ignored, amended before pushing, and every job file scanned for tokens.
- **Harbor's redaction.** Harbor redacts the value of every environment variable passed on the command line, and one value was the word `true`, so every `true` in the archived artifacts became `[REDACTED]`. The summaries and the ablation script restore it in memory; the archived files are untouched; the restored programs reproduce the verifier's numbers exactly.
- **The engine's comment typo.** Found by the linter, left in place: any change to the engine's bytes makes the shipped task differ from the one the pilots saw.
- **The validation table.** An earlier version carried numbers from before the wear constant was raised. My own rerun found and replaced them; the small remaining gap in the spread of totals stays visible.

---

## What the record claims, and what it does not

The task is original, calibrated, solvable by an oracle that uses only the agent's files, verified by a program against exact truth, failed ten times out of ten by the pair the brief's goal line names under a rule committed first, for a cause confirmed by intervention, and passed four times out of five by the next generation by the route the design predicted. It does not claim a universal pass rate for any model, anything about real cricket, a bar free of the reference's advantage, or a task that fails the newest generation. Those are the items under future work, in that order.

## Evidence footnotes

[^1]: the audit task's records, in my earlier repository
[^2]: the ingest prototype's records, in my earlier repository
[^3]: `dev/explore_reliability.py`; `league/calibration.json`
[^4]: NOTES.md, the scorer section
[^5]: `task_data/private/*/truth.csv`
[^6]: `dev/fit_constants.py`; the interaction block of `league/calibration.json`
[^7]: `results/ladder_v2.jsonl`, the first entries
[^8]: `bar.log`; NOTES.md, the bar analysis section
[^9]: `harbor/bar.json`; the git log
[^10]: that experiment's records are in my earlier repository, not this one
[^11]: `dev/make_task_data.py`; NOTES.md, the task-data section
[^12]: job `2026-09-24__12-21-19`
[^13]: job `2026-09-24__00-10-13`
[^14]: `ablations.log`
[^15]: jobs `2026-09-24__19-42-59` and `2026-09-24__23-05-34`; the five Opus jobs in RUN_REPORT.md
