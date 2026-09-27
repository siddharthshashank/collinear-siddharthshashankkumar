# T20 forecaster

Run from the workspace root:

```sh
python solution/forecast.py --league league --out predictions.csv
```

The program learns from the supplied league on each invocation. It uses only the
public engine, NumPy, pandas, SciPy, and the standard library. There are no stored
player estimates or dependencies on the development league.

`fit.py` fits the engine's six-outcome ball likelihood, including its exact
public situation offsets. Gaussian random effects represent player style,
batting and bowling quality, pace/spin splits, bowling type, venue affinity,
venue conditions, match conditions, and the public hand and pitch interactions.
Quality combines persistent talent with correlated form in two periods per
season. Empirical Bayes updates estimate the main prior scales using the joint
Laplace covariance. The next-season estimate conditions on the full history.

`simulate.py` integrates approximate posterior uncertainty and future form
innovations. It applies a first-order posterior skew correction and respects the
nonnegative home lift. Both toss results receive equal weight. Each uses 49,152
simulations; coupling their random draws reduces Monte Carlo error. The innings
logic, extras, rotation, chase pressure, wickets, and ties follow the engine.
All random seeds are fixed, and BLAS is limited to two threads.

Development checks included forward prediction of the third season, analytic
gradients against finite differences, exact innings agreement with the engine
under identical random draws, deterministic repeat forecasts, and symmetry for
identical sides. Hidden grading probabilities are not part of these checks.
