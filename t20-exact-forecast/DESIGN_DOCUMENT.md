# Learning what to trust

## A forecasting task for AI agents, graded against the exact truth

**Author:** Siddharth Shashank Kumar
**Task:** `collinear-siddharthshashankkumar/t20-exact-forecast`
**Repository:** github.com/siddharthshashank/collinear-siddharthshashankkumar

---

### The whole thing in one paragraph

I built a task in which an AI coding agent is handed three seasons of ball-by-ball records from a made-up Twenty20 cricket league, the exact engine that plays the matches, and next season's fixtures with the named line-ups. The agent must write a program that says, for each fixture, how likely the home side is to win. Because I generated the league, I know the true probability of every fixture, so I can grade each forecast on how far it is from the truth rather than on whether one match happened to go one way. The same engine was calibrated to real Indian Premier League data so the league behaves like cricket, but every player, team and ground is invented, so nothing the agent knows about real cricket helps it. The pass mark was fixed and committed before any model tried the task. The two models the brief names failed it ten times out of ten for the same reason, and the next generation of the same two model families passed it four times out of five, by doing exactly what the failures skipped.

---

## 1. What problem is this solving?

**What are we trying to measure?** Whether an AI agent can look at a pile of noisy records, work out how much of what it sees is real and how much is chance, turn that judgement into numbers, and check its own work before handing it in. That skill is the core of every forecasting job I have done: estimating conversion rates, failure rates, demand, disease counts, always from less data than you would like. The failure mode is always the same too. The pipeline runs, the numbers come out, they look plausible, and they are wrong because a short lucky streak was treated as a real difference.

**Why does a benchmark for this need to exist?** Because the usual way of grading forecasts cannot see that mistake. If you grade a forecast on what actually happened, luck decides the grade. A forecaster who says "70 percent" and loses was not necessarily wrong; three times in ten that is exactly what should happen. Over a whole season of matches the luck averages out somewhat, but on this task's 192 graded fixtures the noise from outcomes alone is about twice the gap between a careful forecaster and a careless one. So a results-graded task would be flipping a coin about which agent is better. I wanted a task where the grade is about the forecast and nothing else.

**Why does it matter to a company like Collinear?** Frontier agents are already good at tasks with a written rule to follow. My first attempt at this take-home was that kind of task, a repository of forecast scripts with a subtle rule violated in forty-eight places, and the strongest models fixed every one. What separates a strong agent from a weak one now is judgement under uncertainty, and the ability to build a check that could tell it it is wrong. That is what this task isolates, and it does so in a way that a computer can grade without a human in the loop.

---

## 2. Why cricket, and why the IPL?

**Why a sport at all?** Sport gives you thousands of small, repeated, independent observations of the same people under measurable conditions, with an outcome everyone understands. A "70 percent chance the home side wins" needs no explanation; a synthetic target in an invented domain does.

**Why Twenty20 cricket?** Three reasons that matter for the task, not for the sport.

- A T20 match is small. An innings is at most 120 legal balls, so a whole match can be simulated in a few milliseconds, and a probability can be estimated to high precision by playing the same fixture hundreds of thousands of times.
- A ball is a rich observation. Every delivery records who bowled it, who faced it, where, in what situation, and what happened, one of six outcomes plus extras. That is exactly the kind of record from which you can separate a player's ability from the situation he was in.
- Players recur, but never enough. A batter faces a few hundred balls a season, a bowler bowls a few hundred. That is enough to learn something and not enough to be sure, which is the whole difficulty of the task.

**Why the IPL specifically?** Because Cricsheet publishes every ball of every IPL match since 2008 in a clean, free, open-licensed archive: 1,243 matches and 295,557 deliveries. I could measure how real cricket behaves from real data, rather than guess, and then build a league that behaves the same way.

**What did the real data tell me?** The most important number in the whole design. If you rank batters by their scoring rate in one half of a season and check the other half, the correlation is about 0.46; for bowlers' economy it is about 0.27. In plain terms, roughly half of what separates one batter's season from another's is chance, and for bowlers more than half. Anyone who takes a player's recent numbers at face value will be badly overconfident. That is the trap at the centre of the task, and it is real cricket's trap, not one I invented.

---

## 3. Why a simulated league instead of real matches?

**Why not just use the real IPL?** Three reasons.

1. With real matches there is no truth to grade against, only results, and results carry the luck described above.
2. Real players have reputations. An agent that knows Virat Kohli is good would get credit for memory, not for inference.
3. Real matches happen once. A simulated league can be generated as many times as I like, so I can test an agent's program on seven leagues it has never seen.

**What does a simulated league give up?** Any claim about real cricket. The world is a statistical model of the IPL, not the IPL. That is fine, because the task is about inference, and I am careful throughout to say that the league behaves like cricket on the measures I checked, not that it is cricket.

**Isn't a synthetic world artificial in a way that makes the task easy?** It would be if the simulator were a toy. That is why the next section spends effort on calibration: the effects in the world are the ones that measurably exist in the real archive, at the sizes they exist, and the things that do not exist in the real data were left out.

---

## 4. How the world is built

![The calibration pipeline: from the Cricsheet archive to one constants file, with the validation loop](figures/calibration_pipeline.png)

**How does real data become a simulator?** Six scripts read the archive and produce one file of constants. In plain terms they do four things.

1. Reconstruct the situation before every ball: which over, how many wickets down, how far behind or ahead of the required rate.
2. Measure how the situation changes what happens next: the odds of a boundary, a dot ball, a wicket, in every situation.
3. Measure how much players differ from each other, and how much of that difference is real. This is where the 0.46 and 0.27 come from.
4. Measure which other effects repeat. Grounds differ and the difference repeats year to year (correlation 0.71), so venues are in the world. A particular batter against a particular bowler barely repeats (0.18 on the best-sampled pairs), so there is no such effect in the world.

**Why leave out things a cricket fan would expect, like a batter's record against a specific bowler?** Because I tested whether they exist and they do not, at least not detectably in fifteen years of data. Putting a fan's intuition into the world would plant noise and call it skill. Leaving it out, and telling the agent it is out, turns a common mistake into a documented trap: an agent that builds head-to-head tables is fitting nothing. The worst rung on the comparison ladder (Section 7) is exactly that method.

**How does the world stay honest about what was measured and what I chose?** Every constant in the world belongs to one of two groups. Measured constants come straight from the archive. Chosen constants, such as how many players change teams each year, how fast form drifts, how much the home side is helped, are my decisions, and each one carries its reason in the code. Some chosen numbers were tuned so that the league matches real cricket on three aggregates; those three aggregates therefore cannot count as independent validation, and I say so.

**What does the league look like?** Ten teams, 180 invented players, three seasons of a double round robin, 270 matches of history. A quarter of the players change teams each off-season and every match fields a fresh eleven, so a team's name tells you little and you have to model the players. The graded fixtures come after a further off-season, so every player's form has drifted a little since the last ball the agent saw. The toss winner always chases and bowlers rotate in a fixed pattern, because a captain's decisions would be a second hidden thing to model, and one is enough.

**Does it behave like cricket?** On the checks I ran, yes. Three simulated seasons against the real archive: average first-innings score 189.2 against 188.5; chasing side wins 51.0 percent against 50.9; wickets per innings 5.83 against 5.9; the run rate over by over matches with correlation 0.977. The spread of totals is a little narrow, 35.0 against 37.4, and I left that as a known gap rather than add a hidden term to close it.

**What did the checks catch while building it?** A dismissal label typo, an off-by-one in the count of legal balls, and a wrong term in a gradient that produced plausible-looking but wrong coefficients. Every stage was checked against a number known independently before moving on, which is why I trust the constants that shipped.

---

## 5. What the agent gets, and what it must deliver

**What is in the agent's folder?** Seven CSV files describing three seasons of a league (every ball, every match, every line-up, the players, the grounds, the coming fixtures and their named elevens), a handbook, a starter program that forecasts 0.5 for everything, and the match engine as Python code with its public constants.

**Why give the agent the engine?** This is the decision most people ask about. If I described the mechanics in words, an agent could get a detail wrong for a reason that is not its fault, and the task would be measuring my prose. Shipping the engine means every forecaster, mine and the agent's, plays matches by the identical rules; the only thing that differs is what each believes about the players. The task then tests estimation, which is what I want, not reverse engineering, which is not.

**Then what is hidden?** Every magnitude. The engine ships with the constants that describe the game in general, how a situation changes the odds, how often extras happen. It does not ship the spread of player abilities, the speed of form drift, the size of the home advantage, the effect of dew, or of course any individual player's ability. The handbook says all of these exist and how they enter the game; it never says how big they are. Knowing the shape of the unknowns and having to estimate their size is exactly the statistician's job.

**Why tell the agent so much, including the traps?** Because a task can be hard for two reasons: the agent cannot know the rules, or the agent cannot know the quantities. Only the second is fair. So the handbook states every file, every column, the scoring formula, the tolerance, the time limit, the ball model in words, the structure of everything hidden, and that there is no head-to-head effect. It even says that a coin-flip forecast has a little under twice the regret of a good forecaster, and that the agent may use the engine to generate leagues of its own and test its method against known truth. Unknown quantities are allowed; unknown rules are not.

**What must the agent deliver?** One program, `solution/forecast.py`, that takes a league folder and writes a CSV of probabilities. It runs on the visible league and on seven leagues the agent never sees. It must give the same output twice, finish each league inside twelve minutes, use no network, and leave the engine untouched.

**Why is this a long-horizon task?** Not because a session must be long, but because the pieces depend on each other. Reading the records wrong corrupts the estimates; over-trusting the estimates produces overconfident probabilities; a check built from the same wrong assumptions approves the wrong model; and all of it has to become a program that works on leagues it has never seen. GPT-6-astra passed in 45 minutes; a short good solution is still a good solution.

---

## 6. How the whole system fits together

![The whole system: calibration, the synthetic world, task build and packaging, the Harbor runtime, and the evidence](figures/system_overview.png)

Reading the drawing left to right: real data becomes constants (A); constants plus one random seed become a league whose public history goes to the agent and whose hidden state goes to the truth engine (B); eight such leagues, their truths and a reference forecaster's regrets are built and packaged into one Harbor task (C); Harbor runs the agent in one container and the grader in another (D); and every run leaves a record that the documents are built from (E).

![Task build and packaging: eight worlds become one Harbor task directory with a public side and a private side](figures/task_build_and_packaging.png)

**Why eight worlds?** One is visible during development. Seven are held out, built by the same recipe from different seeds. A program that was tuned to the visible league and does not generalise fails on the seven. Eight also drives the noise in the grade down to about one percent, which Section 7 relies on.

**Why one packaged directory?** Harbor, Collinear's harness, runs a task from one directory: an instruction, a `task.toml`, an environment image for the agent, a tests image for the verifier, and a solution that proves the task solvable. The packager assembles that directory from the source trees so that the agent side and the verifier side cannot drift apart, and fills the handbook's numbers from the same rule file the grader reads.

---

## 7. How a forecast is graded

**Why grade the probability and not the result?** Because the result is one noisy draw. For each fixture I hold the true home-win probability, computed by playing the fixture 100,000 times per batting order on the same engine with the hidden values, and the score is how far the forecast is from that truth. No match is played for grading; there is no luck in the grade.

**Why "regret", and why logarithmic?** Regret is the extra penalty you pay for reporting the wrong probability instead of the true one, under a proper score, which is a score that rewards honesty: you cannot do better in expectation than by reporting what you believe. I chose the logarithmic version rather than the squared-error version because it punishes confident mistakes hardest, and confident mistakes were the failure I expected agents to make. Forecasts are clipped to the range 0.002 to 0.998 so that one reckless zero cannot give an infinite penalty; true probabilities in this world sit between about 0.2 and 0.8, so the clip never touches an honest forecast.

**Compared with what? Why a reference forecaster?** A raw regret number means nothing on its own, and worlds differ in how much there is to predict. So the grade is relative: the agent's total regret divided by the regret of a reference forecaster that I built from ordinary statistics, a penalised likelihood fit with cross-validated shrinkage and simulation on the engine, using only the same files the agent gets.

![The research ladder: the reference and five careless tiers, the bar analysis on worlds that are never graded, and the pass bar as committed](figures/research_ladder.png)

**Why a ladder of careless methods?** To know what the pass mark means. Five methods a hurried person might use were built alongside the reference: a coin flip, team ratings, player estimates without shrinkage, last season only, and a raw head-to-head table. On the eight graded worlds their total regret is 1.89, 3.23, 1.58, 1.50 and 4.00 times the reference's. The pass bar is 1.10. So a pass means the agent did something the careless methods do not, and a failure can be attributed: the grader reports which rung each forecast most resembles.

**Why sum over eight worlds instead of judging each?** Because I tested the per-world rule first, on eight development worlds that are never graded, and it was unsound. On one world the reference's own simulation noise was 5.9 percent of its regret; on two others the careless "no shrinkage" method was only 6 to 7 percent worse than the reference; and on one world a coin flip beat the reference outright, because there was little to predict that year. No single tolerance could absorb the noise and exclude the careless methods. Summed over eight worlds, the noise falls to about 1.1 percent and the careless methods sit at 1.30 times the reference or worse. So the rule is on the sum.

**Why 10 percent?** It is about nine times the noise and a third of the way to the nearest careless method. It is a choice, tied to two measured numbers.

![The pass rule and the reward composition: one rule applied to all eight worlds and again to the seven held out; the constraint and artifact checks; how the keys combine](figures/grading_rule.png)

**Why apply the rule twice?** Once on all eight worlds, and again on the seven held-out worlds alone, so that a strong result on the one visible world cannot carry a weak method. This turned out to matter in both directions (Section 9).

**What else is checked?** That the output is complete and valid, that the program gives identical output twice, that the engine was not modified, and that each league finished in time. These are separate reward keys, so a valid but inaccurate forecast is distinguishable from a broken one. The overall score is the pass on all eight worlds, multiplied by a weighted mix of the held-out pass, the constraint checks and the output validity; only a full 1.0 counts as solved.

**Why fix the rule before running any model?** Because a pass mark chosen after seeing the scores is not a pass mark. The rule file, `harbor/bar.json`, was committed before the first pilot job, and it has not moved since, through a near miss at 1.109 and a nearer one at 1.104. I report how sensitive the verdicts are to the number; I do not act on it.

---

## 8. How cheating is prevented

![The Harbor runtime: the agent container with public inputs only, and the separate verifier container with the private truth, the pristine engine and the grader](figures/harbor_runtime.png)

**Why two containers?** Because an agent optimises for the reward, and reading the answers would be the shortest route to it. The truth, the reference's regrets and the rule live only in the verifier container, which the agent never sees. Only two things cross from the agent's side: its solution folder and its copy of the engine.

**What stops the program from reading the answers at grading time?** The verifier runs the agent's program as a separate unprivileged user, and the private files are unreadable to that user. The program runs beside a pristine copy of the engine, not the agent's copy; the agent's copy is only hashed, to prove it was not edited. If the hash differs, the run fails the constraint check.

**Why run it twice?** To prove determinism. A forecast that changes between runs cannot be reproduced, and a program that plants randomness could be fishing for a lucky draw.

**Does this prove the task cannot be gamed?** No verifier can prove that. What I can say is that Harbor's own task linter passed all 22 of its checks, including the anti-cheating ones, and that in eighteen model jobs no run attempted to touch the engine or the private files.

---

## 9. What happened when models tried it

### The pair named in the brief's goal line

Five runs each of Claude Opus 4.7 under Claude Code and GPT-5.5 under Codex, both at high reasoning effort, alternating, after the rule was committed.

| Run | Model | Total regret, times the reference | Held-out worlds only | Session |
|---|---|---:|---:|---|
| 1 | Opus 4.7 | 1.533 | 1.492 | 16 min |
| 2 | GPT-5.5 | 1.575 | 1.613 | 25 min |
| 3 | Opus 4.7 | 1.573 | 1.537 | 25 min |
| 4 | GPT-5.5 | 1.545 | 1.543 | 19 min |
| 5 | Opus 4.7 | 1.396 | 1.376 | 21 min |
| 6 | GPT-5.5 | 1.109 | 1.117 | 20 min |
| 7 | Opus 4.7 | 1.364 | 1.345 | 22 min |
| 8 | GPT-5.5 | 1.362 | 1.341 | 13 min, cut short by my account's usage limit after the program was written |
| 9 | Opus 4.7 | 1.703 | 1.661 | 23 min |
| 10 | GPT-5.5 | 1.409 | 1.398 | 26 min |

Opus 4.7 passed 0 of 5. GPT-5.5 passed 0 of 5, or 0 of 4 if the interrupted run is excluded; I count it and flag it, since its program was complete and graded. Every run produced a valid, deterministic forecast inside its limits, so every verdict is about forecast quality and nothing else.

**What went wrong, in plain words?** Nine of the ten forecasts most resemble the "no shrinkage" rung of the ladder, the method that takes every player's recent numbers at face value. I read the first six programs to be sure. All six fit the right model and wrote sound code; all six set the one number that controls how much to trust a player's short history between 3 and 44 times too weak, and none had a check that could have told them so. Four checked only that the program ran and was deterministic. One checked that identical teams get 0.5. One, run 3, did build a validation check, generated its own leagues and scored itself well inside the bar; but it generated those leagues with the same over-trusting assumption as its estimator, so the check confirmed the assumption instead of testing it. That is the single most useful thing the task produced: a sharp check aimed at the wrong world.

**How do I know that was the cause and not a guess?** I changed that one number in each of the six programs and re-graded them on one held-out world. Every one moved most of the way to the reference: 2.70 to 1.36, 2.55 to 1.57, 2.17 to 1.64, 2.29 to 1.60, 2.10 to 1.27 times the reference. Four of the five cut their excess error by more than half; the fifth by 45 percent. The near miss, run 6, is the clearest case: it looked like the reference on seven worlds, but its priors were still too loose and it had softened every output toward 0.5 to compensate. Removing the softening made it worse; correcting the priors made it beat the reference on that world. The near miss was a hedged wrong answer.

### The pair named in the brief's opening section

After the ten runs I ran the newer pair on the same frozen task under the same rule.

| Run | Model | Total regret, times the reference | Held-out worlds only | Session | Verdict |
|---|---|---:|---:|---|---|
| F1 | Claude Fable 5.1 | 1.027 | 1.015 | 2 h 02 | pass |
| F2 | Claude Fable 5.1 | 1.104 | 1.093 | 2 h 37 | fail on all eight by 0.4 points; pass on the held-out seven |
| F3 | Claude Fable 5.1 | 1.008 | 0.989 | 1 h 44 | pass, better than the reference on the held-out worlds |
| A1 | GPT-6-astra | 1.054 | 1.047 | 46 min | pass |
| A2 | GPT-6-astra | 1.072 | 1.061 | 45 min | pass |

Three further runs were excluded, with their job records kept: one GPT-6-astra run hit my account's usage limit at five minutes before writing a program, one had a complete program when I stopped the loop during its verification, and one Fable run was stopped at its start. So the newer pair passed four of five completed runs; every one of their forecasts most resembles the reference on every world.

**What did they do differently?** Their closing messages, kept in the job records, describe the two things the failures lacked. They estimated the trust-in-short-histories number from the data itself, by the standard method statisticians call marginal likelihood, instead of setting it by hand. And they checked themselves against leagues they generated from the handbook's description, with the spreads set from the real league's own estimates, or against a held-out slice of the real league. One Fable run noticed that its generated leagues disagreed slightly with the handbook's coin-flip yardstick and reasoned about which side was off. That is run 3's check, aimed at the right world.

**Why did the one Fable run miss?** Entirely on the visible world: 1.191 there against 1.093 on the seven it never saw. In fact all five newer-pair runs did worst or second-worst on the visible world, which suggests each did some tuning on the league it could see that did not carry over. The held-out rule was written to stop a visible-world result from carrying a weak method; here it caught the reverse, a method that was fine everywhere except the world it could tune to.

**What does all this mean?** The task separates generations, not vendors. The models the brief's goal line names fail ten times out of ten for one diagnosed cause; both models of the next generation, from two different labs, pass on their first completed attempts by the route the design predicted. So the pass bar sits where the design intended, between the two generations. It also answers a question I had to ask, because I built this task with the help of an assistant from Fable's family: a model from the other lab passed too, and the same family's previous model failed five times reading the same handbook, so the passes are not family affinity. What the task does not do, as calibrated, is fail the newest generation. If that is what the brief means, Section 12 lists the levers, and each needs a fresh bar and a fresh committed rule before any pilot.

---

## 10. Is it fair, and is it original?

**Fair to the agent?** Everything the grader checks is stated in the handbook. The reference uses only the agent's files, loaded through the agent's reader. A solution that installs the reference forecaster passes at exactly 1.000 times its stored regret, which proves the task is solvable from the agent's side of the fence. The agent's own runs never came near a time limit. And the yardstick and the self-check route are given away in the handbook rather than left for the agent to discover.

**The one advantage I should own.** The reference's trust-in-short-histories numbers were set by me, knowing the true spreads. The reference sees only public files at run time, but its design knows something an outside solver is not handed. The 10 percent tolerance softens this; it does not remove it. The ablations measured what it is worth, about half of a careless program's excess error, and the passing programs removed it on their own by estimating those numbers from data. The next version's reference should do the same, behind a fresh committed rule.

**Original?** The task is new: a calibrated synthetic league with a public mechanism and hidden magnitudes, a reusable forecasting interface, a comparison ladder, an exact-truth score and a rule committed before any pilot. It is not a port of a benchmark, a competition, a CTF or a tutorial. The statistics inside it are standard, and I say so; the contribution is the task, not the methods.

---

## 11. Limitations, plainly

- The world is a model of the IPL, not the IPL. Nothing here says anything about real matches.
- The reference's prior scales were designer-informed, as above.
- Ten runs of the older pair and five of the newer are small samples. Zero of five is consistent with a true pass rate as high as about 45 percent; four of five is consistent with anything from about 30 to 99 percent.
- The cause of the failures is confirmed by intervention for six of ten programs, on one world, one constant each. The other four are attributed by resemblance only. The newer pair's visible-world pattern was not investigated.
- The truth is a very precise estimate, not a closed-form number, and the random streams behind it are shared across worlds by fixture number, so the eight worlds' small truth errors are not fully independent.
- The verifier makes no network calls, but its no-network mode is not declared, because Docker Desktop on macOS rejects it.
- A comment typo in the engine, found by Harbor's linter, was left in place: changing the engine after the pilots would change the task.
- The task does not fail the newest generation. Whether that is a limitation depends on which pair the brief means.

---

## 12. What I would do next

1. Anchor the pass bar on a reference that learns its spreads from the data, which is what the passing programs built. Fresh bar analysis, fresh committed rule, fresh pilots.
2. If the goal is a task the newest generation fails: shorten the history, or add an off-season circuit whose records are noisier, and re-derive the bar. Never change difficulty under an existing rule.
3. Repeat the truth calculations with independent random streams to confirm that the borderline verdicts are stable.
4. Extend the interventions to a second world and to the four programs that were only read by resemblance, and investigate why the newer pair does worst on the visible world.
5. Record the hash of the Cricsheet archive at download time, so the calibration is reproducible byte for byte from the outside.

---

## 13. How to run it

From the repository root, with Docker and Harbor installed:

```sh
make venv                      # numpy 2.4.4, pandas 3.0.2, scipy 1.17.1
make data                      # eight worlds and their truths (about 25 minutes)
make package                   # the Harbor task directory under dist/
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle     # expect 1.000
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop        # expect 0.000
harbor check dist/collinear-siddharthshashankkumar/t20-exact-forecast              # 22 of 22
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
harbor run -p dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
```

Every job, including all eighteen model jobs, is under `jobs/` with its reward, per-world details, agent log and submitted program. Full commands, versions and resource limits are in [RUN_REPORT.md](RUN_REPORT.md).

---

## Where to read more

- [DECISIONS.md](DECISIONS.md): every decision that could have gone another way, with the alternative, the cost and whether it still stands.
- [RUN_REPORT.md](RUN_REPORT.md): environment, commands, every run with its job identity, exclusions and the ablation log.
- [PROVENANCE.md](PROVENANCE.md): what is new, what is borrowed, the data licence, and the use of AI assistance.
- [NOTES.md](NOTES.md): a file-by-file study of the pipeline, written while checking each part against known numbers.
- `docs/DESIGN.pdf`: the extended version of this document, with the full derivations and drawings.
