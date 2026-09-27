# T20 forecaster

```sh
python solution/forecast.py --league /path/to/league --out probabilities.csv
```

The program reads only the supplied league folder and the public engine. It uses NumPy, pandas, SciPy, and the standard library. All seeds are fixed, and numerical libraries are limited to two threads.

The ball likelihood uses the public engine's exact situation offsets and outcome directions. Gaussian hierarchical effects describe player styles, talents, changing form, pace/spin splits, venue affinities, pitch and hand interactions, home advantage, dew, season levels, and shared match conditions. Effect variances are estimated by Laplace marginal likelihood with weak regularization. Player quality combines persistent talent with a mean-reverting seasonal form process; annual form persistence is assumed to be 0.55.

Forecasts integrate joint posterior skill uncertainty and another offseason of form changes. The simulator uses 1,024 antithetic parameter draws and 65,536 match simulations for each batting order. Both innings share the match's pitch effect. Paired random numbers across toss orders reduce simulation error. Ties count as half a win.

For diagnostics, add `--verbose`. `--samples N` changes the simulation count.

```sh
python solution/test_forecast.py
```

The tests check likelihood gradients, Hessians, the Laplace correction, exact agreement with the supplied innings simulator under identical random draws, and symmetry of the toss average. Additional development checks used simulated histories with known hidden parameters; these do not establish the unavailable hidden grader's result.

On the supplied league, two complete runs took 128.7 and 129.7 seconds and produced byte-identical CSV files. `forecast.csv` contains the supplied league's forecasts.
