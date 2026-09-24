# League handbook

## The job

This is a simulated Twenty20 cricket league with ten teams. You have three seasons of ball-by-ball history in `league/` and a list of
fixtures for the coming season with the announced line-ups. For every fixture, give the probability that the home side wins.

You deliver a program. It is run on this league and on other leagues of the same kind that you have not seen, so it has to learn
everything it needs from the league folder it is given.

    python solution/forecast.py --league <folder> --out <file.csv>

The output file has two columns, `fixture` and `p_home`, with one row per fixture in `<folder>/fixtures.csv`.

## How a forecast is graded

The league is simulated, so the true probability that the home side wins each fixture is known exactly. Your forecast is graded against
that number. No match is played and no result is used, so luck has no part in the grade.

For a fixture with true probability `p` and forecast `q`, the penalty is `p*ln(p/q) + (1-p)*ln((1-p)/(1-q))`. It is zero when `q = p` and
grows quickly when a forecast is confident and wrong. Forecasts are clipped to [0.002, 0.998]. Your regret on a league is the
average penalty over its fixtures.

Your regret is compared with that of a reference forecaster. The reference uses only the files you have, the engine you have, and standard
statistical practice. It plays each fixture 4,000 times. Your program is run on this league and on seven leagues you have not seen. You pass
if your regret, summed over all eight leagues, is at most 10 percent above the reference's sum, and the same holds for the seven
unseen leagues on their own. Simulation noise in your own forecasts counts against you, so play each fixture enough times.

For orientation, summed over leagues like these a coin flip (0.5 everywhere) has a little under twice the reference's regret. On a single
league anything can happen. Some leagues have little to predict, and there the reference itself can be close to the coin flip.

## The files in a league folder

| file | one row per | columns |
|---|---|---|
| `balls.csv` | legal ball | `season, match, innings, over, ball, batting_team, bowling_team, venue, batter, bowler, outcome, extra, position, wickets_before, runs_before, target` |
| `matches.csv` | match | `season, match, week, home, away, venue, toss_winner, batted_first, first_total, second_total, winner` |
| `lineups.csv` | player in a past match | `match, team, batting_slot, player, bowling_slot` |
| `players.csv` | player | `player, role, hand, bowling_style` |
| `venues.csv` | venue | `venue, home_team, pitch` |
| `fixtures.csv` | fixture to forecast | `fixture, season, home, away, venue` |
| `fixture_lineups.csv` | player in a fixture | `fixture, team, batting_slot, player, bowling_slot` |

`outcome` is one of `W, 0, 1, 2, 4, 6`. `extra` is 1 when the ball also produced one extra run. `position` is the batter's place in the
order, from 0. `target` is 0 in the first innings. `bowling_slot` is -1 for players who do not bowl. `engine/league_io.py` reads a folder
into the objects the engine uses.

## How a ball works (all of this is public)

`engine/model.py` is the engine, and `engine/public.json` holds its public constants. They are the exact definition; this section
describes them in words.

Every legal ball has six possible outcomes. Their probabilities come from a sum of effects on the log scale:

1. a profile for the over being bowled (`over_logits`), a shift for the batter's position (`position_vectors`);
2. the match situation: how many more wickets have fallen than is usual at that over (`wickets_vector`), and in the second innings a
   constant shift plus the chase pressure, which is the log of the required run rate over the usual rate from that over on, clipped to
   [-1, 1.2] (`second_innings_vector`, `pressure_vector`, `par_rate`);
3. the batter's **style** and **quality**, the bowler's **type** and **quality**, and the **conditions**, each a single number that moves
   the six outcomes along a fixed public direction (`directions`).

On top of the ball, with a fixed probability one extra run is added (`extras_per_ball`). Batters bat in line-up order. The strike changes
on an odd number of runs and at the end of each over. The five bowlers bowl in rotation, one over each in turn. An innings ends after 120
legal balls, ten wickets, or when the target is reached. The toss is a coin flip and the winner always chases. A tied match is settled by
a coin flip.

## What is hidden, and how it is built

* **Batters.** Style does not change. Quality is a fixed talent plus a form component that drifts slowly over months and is pulled back
  toward zero. A batter's quality can differ a little against pace and against spin. Every player bats, so every player has these values.
* **Bowlers.** Type is related to the public bowling style and does not change. Quality is talent plus slowly drifting form.
* **Conditions.** A level for each venue; a league-wide level that moves from season to season and keeps moving; a pitch-on-the-day
  effect drawn afresh for every match and shared by both innings; dew at some venues, which helps the chase; a small general
  disadvantage for the side batting second; a lift for batters at their home ground; a personal liking of each batter for each venue;
  small league-wide effects of batting hand against bowling style and of pitch type on bowling style.
* There is **no** effect that belongs to one specific batter against one specific bowler.
* Between seasons about a quarter of the players change teams, and line-ups rotate heavily from match to match.

The fixtures are played at the start of the next season. Skills are as they stand at that moment, after one more off-season of drift.

## Rules for your program

* Everything it needs must be under `solution/`. The entry point is `solution/forecast.py`. It may import `engine`, which the grader
  supplies unchanged, and `numpy`, `pandas`, `scipy` and the Python standard library. Do not change anything under `engine/`.
* It must give the same output every time it is run on the same folder. Fix your random seeds.
* It has 12 minutes per league on two CPU cores and must not use the network.
* The engine is yours to use in any way you like, including to test your own method on leagues you simulate yourself.

## Source

Calibration constants derived from data sourced from Cricsheet (cricsheet.org), licensed under the Open Data Commons Attribution License
(ODC-BY 1.0). Only aggregate constants are included. Players, teams and venues are invented.