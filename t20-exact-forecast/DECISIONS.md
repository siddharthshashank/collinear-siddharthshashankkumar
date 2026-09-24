# Decisions

## The pass rule

The submission is run on eight worlds, one visible and seven held out, with 24 fixtures each. It passes if its regret summed over all eight is at most 1.10 times the reference forecaster's sum, and the same must hold on the seven held-out worlds on their own. Forecasts are clipped to [0.002, 0.998]. The truth is computed at 100,000 copies per batting order; the reference plays each fixture 4,000 times per order. The program must give identical output twice, leave the engine untouched, and finish each world within 12 minutes. The grading quantity is regret, never the skill score.

## Where the rule came from

My first rule applied the tolerance on every world. A bar analysis on eight worlds that are never graded, seeds 1001 to 1008, showed it was unsound: simulation noise reached 5.9 percent of the reference's regret on one world while the nearest careless tier sat only 6 to 7 percent above the reference on two, and on one world in eight a coin flip beat the reference. No tolerance could both absorb the noise and exclude the careless tier. So regret is summed over the eight graded worlds, where the noise falls to about 1.1 percent and the careless tiers sit at 1.30 times the reference or worse; ten percent is about nine times the noise and a third of the way to the closest careless tier. On this task's own eight graded worlds the careless tiers sit at 1.50, 1.58, 1.89, 3.23 and 4.00 times the reference's sum.

## Pre-registration

`harbor/bar.json`, carrying the rule, was committed before any model ran on this task (the commit "Harbor metadata, pass bar, lock file, instruction" precedes the first pilot job). The rule was not moved at any point afterwards. A tolerance of 1.12 would have passed GPT-5.5's third run at 1.109 on all eight worlds and 1.117 on the held-out seven, the closest any run has come without passing. I report that sensitivity rather than act on it; a bar that moves after a score is seen is not a bar.

## Pilots

Ten trials in the real Harbor harness after `bar.json` was committed: five of Claude Opus 4.7 under Claude Code at high reasoning effort and five of GPT-5.5 under Codex at high effort, alternating, on 23 and 24 September 2026. Opus 4.7 passed 0 of 5 and GPT-5.5 0 of 5. No run came near a time limit; every run wrote a complete, valid, deterministic forecast and left the engine untouched. Nine of the ten carry the unshrunk fingerprint. Run 8 delivered its program and was then cut short by my account's usage limit at 13 minutes; it is counted and flagged, and excluding it changes nothing. The six first-round programs were reread and each rerun with one constant changed; every one moved toward the reference as the fingerprint predicted, and the near miss beat the reference on one world once its priors were halved (`ablations.log`). The rule was not moved on that finding either.

## Smaller decisions

The design document's validation table had carried numbers from a run made before the second-innings wear constant was raised; my own validation run found the stale numbers and the table is the re-validation (chasers 0.510 against 0.509; spread of totals 35.0 against 37.4, still a limitation). The agent session directories under `jobs/*/agent/sessions/` are excluded from the repository because they hold the harness's local state. The reference forecaster's prior scales were chosen knowing the true spreads; the ablations measure that advantage, and it is recorded as a limitation rather than removed, because removing it needs a fresh bar analysis and a fresh committed rule before any pilot.
