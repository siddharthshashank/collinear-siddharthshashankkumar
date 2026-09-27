Run from the workspace root:

```sh
python solution/forecast.py --league league --out predictions.csv
```

The program fits the public multinomial ball model with hierarchical player and
condition effects. Player quality follows a persistent talent plus correlated
form model. Variance parameters are estimated by Laplace marginal likelihood;
future skills include off-season uncertainty. Predictions average over the
joint parameter posterior and 65,536 simulated matches for each toss outcome.
All random seeds are fixed. No fitted values or league-specific caches are used.

`forecast.py`, `inference.py`, and `simulation.py` are the runtime files. They use
only the supplied engine, NumPy, pandas, SciPy, and the standard library. A run on
the supplied league takes approximately 2.5 minutes in this environment.

Run `python solution/test_simulation.py` to check exact agreement with the
supplied innings engine, symmetry for identical teams, and deterministic seeds.
The hidden probabilities and reference grading results are not available locally.
