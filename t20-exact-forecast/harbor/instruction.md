# Forecast a simulated T20 league, graded against the exact truth

`/app/league/` holds three seasons of ball-by-ball history for a simulated Twenty20 league and the fixtures for the coming season.
`/app/docs/handbook.md` explains the league, the engine that generated it, what is hidden, and exactly how forecasts are graded.
`/app/engine/` is that engine, with every hidden value left out.

## What to deliver

A program at `/app/solution/forecast.py` that, given a league folder, writes the probability that the home side wins each fixture:

    python solution/forecast.py --league <folder> --out <file.csv>

A starter that says 0.5 for everything is already there. Replace it. Everything your program needs must live under `/app/solution/`.
Do not change `/app/engine/`.

## How it is graded

The grader runs your program on this league and on leagues it generates the same way that you have not seen. Because the leagues are simulated, the true win probability of every fixture is known, and your forecast is graded by its expected log loss against that truth.
No match result is used. You pass if your regret, summed over the leagues, is within the stated tolerance of a reference forecaster's sum, on all leagues together and on the unseen leagues on their own. The handbook gives the formula, the tolerance, the time limit, and the rules your program must follow.
Only a perfect result counts as solved.