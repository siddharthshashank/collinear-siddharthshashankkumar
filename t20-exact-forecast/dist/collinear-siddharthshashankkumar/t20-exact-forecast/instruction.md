# Forecast a simulated T20 league

`/app/league/` holds three seasons of ball-by-ball history for a simulated Twenty20 league and the fixtures for the coming season.
`/app/docs/handbook.md` explains the league, the engine that generated it, what is hidden, and exactly how forecasts are graded.
`/app/engine/` is that engine, with every hidden value left out.

## What to deliver

A program at `/app/solution/forecast.py` that, given a league folder, writes the probability that the home side wins each fixture:

    python solution/forecast.py --league <folder> --out <file.csv>

A starter that says 0.5 for everything is already there. Replace it. Everything your program needs must live under `/app/solution/`.
Do not change `/app/engine/`. Submit ordinary files and directories under `solution/`, without symbolic links or special files.

## How it is graded

The grader runs your program on this league and seven held-out leagues generated the same way. Stored win probabilities were estimated with large, fixed Monte Carlo batches using the hidden state. Your forecast is graded by expected log loss against those estimates; no new match outcome is sampled during grading.
You pass if your regret, summed over the leagues, is within the stated tolerance of a reference forecaster's sum, on all leagues together and on the unseen leagues on their own. The handbook gives the formula, the tolerance, the time limit, and the rules your program must follow.
Only a perfect result counts as solved.
