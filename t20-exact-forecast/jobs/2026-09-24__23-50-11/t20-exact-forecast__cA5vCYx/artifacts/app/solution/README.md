# Forecaster

    python solution/forecast.py --league <folder> --out <file.csv>

* `fit.py` — fits the engine's ball model to the history as a multinomial logistic regression: one scalar per hidden
  quantity (batter style, per-season batter quality, pace/spin split, bowler type, per-season bowler quality, venue
  level, season level, per-match pitch effect, per-venue chase shift, wear, affinity, home lift, hand-by-style and
  pitch-by-style tables), each along its public direction, with Gaussian priors. Prior variances are estimated by
  Laplace-EM; season-level quality has a talent + AR(1) form structure with the drift rate shared by batters and bowlers.
* `forecast.py` — extrapolates the posterior one off-season ahead and plays each fixture 10,000 times per batting order
  with the engine's innings mechanics, each copy using its own draw of the hidden numbers from the Laplace posterior,
  so the forecast is the posterior mean of the [REDACTED] win probability. Seeds are fixed; runtime is about a minute on two
  cores with time guards for slower machines.
