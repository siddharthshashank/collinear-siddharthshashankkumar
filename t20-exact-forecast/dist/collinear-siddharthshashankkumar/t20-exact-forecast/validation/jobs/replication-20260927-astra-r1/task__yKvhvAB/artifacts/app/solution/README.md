Run from the workspace root:

```sh
python solution/forecast.py --league league --out forecasts.csv
```

The program fits the public engine's multinomial delivery likelihood. Gaussian
random effects describe batting style, batting and bowling talent, bowling type,
pace/spin splits, ground affinity, and match conditions. Quality also has an
AR(1) form process at half-season resolution. Empirical Bayes updates estimate
variance components, with weak hyperpriors to stabilize sparse components.

Predictions average over a joint Laplace posterior for the fitted effects and
additional off-season form uncertainty. Each fixture uses 65,536 simulations for
each batting order, including shared match conditions, extras, chase pressure,
and half-credit for ties. All random seeds are fixed. Parameters are learned
from the league supplied on the command line; no fitted data are bundled.

Dependencies: Python standard library, NumPy, SciPy, pandas, and the supplied
unchanged `engine` package. Numerical libraries are limited to two threads.

Development checks compared the simulator against the public engine with
identical inputs and random streams, and checked player-effect generalization
on season three after fitting seasons one and two. The hidden grading targets
and reference forecasts are not available locally.
