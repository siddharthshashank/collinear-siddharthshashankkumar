Run from any working directory:

```sh
python /app/solution/forecast.py --league /app/league --out forecasts.csv
```

The forecaster fits the engine's six-outcome likelihood to all historical balls.
It estimates player style, pace/spin quality splits, bowling type, venue and
player/venue effects, home advantage, season conditions, shared match conditions,
and chase conditions. Player quality combines persistent talent with a correlated
form process, fitted at half-season intervals and projected through the offseason.
Random-effect scales are estimated by Laplace marginal likelihood with weak
regularization for poorly identified variance components.

Predictions integrate 1,024 joint approximate posterior skill draws, including
uncertainty in future form, through the public match rules. Each fixture uses
49,152 simulations for each batting order, or 98,304 simulated matches. Seeds and
numerical thread counts are fixed. Only the supplied league data, the public
engine, NumPy, pandas, SciPy, and the standard library are used.

Validation on the supplied league:

- The simulation matches the engine's innings totals exactly with identical
  random draws for 2,048 first innings and 2,048 chases.
- Training on seasons 0 and 1 gives mean ball log loss 1.48188 on season 2,
  compared with 1.48919 for fitted role averages and 1.49125 for the public
  situation model alone. This is a predictive diagnostic, not the hidden grade.
- Repeated full runs produce byte-for-byte identical forecast CSVs.
- The full command takes approximately two minutes on this environment, below
  the twelve-minute limit.

`check_simulator.py` checks simulation equivalence. `validate_fit.py <league>`
performs the historical forward-validation diagnostic. Neither is needed to
produce forecasts. `predictions.csv` contains the supplied league's forecasts.

The hidden truth and reference forecasts are not supplied, so the grading
threshold cannot be measured locally.
