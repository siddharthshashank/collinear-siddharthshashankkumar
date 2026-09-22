# Project Notes - t20-exact-forecast

## 1. scoring/exact.py

`ExactScorer` measures how close a model's predicted probability is to the **true probability** of an event.

Suppose the simulator knows that a cricket team has a **70% chance of winning**. A forecasting model might predict 65%, 50%, or 95%. Instead of waiting for the actual match result and judging the model based on whether the team happened to win or lose, the scorer directly compares the model's prediction with the known 70% truth.

This is especially useful in a simulation because individual match results contain luck. A team with a 70% chance of winning will still lose roughly 30% of the time. If a model correctly predicts 70% and the team happens to lose, the forecast itself was still correct. Simulation studies are valuable for exactly this reason: the true data-generating process is known, so methods can be evaluated directly against that truth rather than noisy observed outcomes (Morris, White & Crowther, 2019).

The main quantity calculated by the scorer is called **regret**. Regret means the amount of avoidable error introduced by the forecast. If the true probability is `0.70` and the model also predicts `0.70`, regret is zero. If the model predicts `0.65`, regret is small. If it predicts `0.20`, regret is much larger.

The scorer is based on the **logarithmic scoring rule**, introduced by Good (1952). The basic idea is simple: predictions should be rewarded when they assign high probability to the correct outcome and heavily punished when they are confidently wrong.

For example, predicting 55% when the truth is around 70% is a moderate mistake. Predicting 1% when the true probability is 70% is much worse because the model has expressed extreme confidence in the wrong direction.

The regret used in the code is

```text
R(q) = p log(p / q) + (1 - p) log((1 - p) / (1 - q))
```

where `p` is the true probability and `q` is the model's forecast.

This expression is the **Kullback-Leibler divergence**, introduced by Kullback and Leibler (1951). In simple terms, it measures how different the model's probability distribution is from the true probability distribution. It is always zero or positive, and it becomes zero only when the model reports the true probability (Cover & Thomas, 2006).

The logarithmic score is also a **strictly proper scoring rule**. This means that if a forecaster genuinely believes the probability is 70%, its best strategy is to report 70%, rather than exaggerating to 90% or hiding uncertainty by reporting 50%. Gneiting and Raftery (2007) discuss this property in detail. In plain English, the scoring system rewards honest probability estimates.

The scorer clips predictions into the range `[0.002, 0.998]`. This prevents forecasts of exactly `0` or `1`, which would otherwise create infinite penalties when they are wrong because `log(0)` is undefined. Selten (1998) discusses how logarithmic scoring can become extremely harsh near these probability extremes. The clipping keeps that behavior under control without affecting normal forecasts.

The class also creates a simple baseline forecaster that predicts **50% for every match**. This is stored as `self.coin`. It represents a model that knows nothing and treats every fixture like a coin flip.

The `skill()` function compares the model's regret with this 50/50 baseline:

```text
skill = 1 - model_regret / coin_regret
```

A skill score of `1` means a perfect forecast. A score of `0` means the model is no better than predicting 50% every time. A negative score means the model performs worse than the coin-flip baseline.

This type of normalization follows the general idea of forecast **skill scores**, where a model is measured relative to a reference prediction (Murphy, 1988). However, the underlying regret is the more important quantity for grading because transformed skill scores can sometimes introduce undesirable incentives or hedging behavior (Murphy, 1973).

The logarithmic score also has a useful interpretation from betting and information theory. Kelly (1956) showed that when bets are sized according to estimated probabilities, incorrect probabilities reduce long-run wealth growth. The loss in optimal long-run growth is closely related to the same KL-divergence quantity used here. Cover and Thomas (2006) develop this connection further.

The key idea is therefore simple: **the scorer is not asking whether the model guessed who won the match. It is asking whether the model correctly estimated how likely each outcome was.** Because the simulator knows the true probabilities, it can evaluate the quality of those probability estimates without being distorted by random match outcomes.

## References

- Brier, G. W. (1950). *Verification of forecasts expressed in terms of probability*. Monthly Weather Review, 78, 1–3.
- Cover, T. M., & Thomas, J. A. (2006). *Elements of Information Theory* (2nd ed.). Wiley.
- Gneiting, T., & Raftery, A. E. (2007). *Strictly proper scoring rules, prediction, and estimation*. Journal of the American Statistical Association, 102, 359–378.
- Good, I. J. (1952). *Rational decisions*. Journal of the Royal Statistical Society: Series B, 14, 107–114.
- Kelly, J. L. (1956). *A new interpretation of information rate*. Bell System Technical Journal, 35.
- Kullback, S., & Leibler, R. A. (1951). *On information and sufficiency*. Annals of Mathematical Statistics, 22, 79–86.
- Morris, T. P., White, I. R., & Crowther, M. J. (2019). *Using simulation studies to evaluate statistical methods*. Statistics in Medicine, 38, 2074–2102.
- Murphy, A. H. (1973). *Hedging and skill scores for probability forecasts*. Journal of Applied Meteorology, 12, 215–223.
- Murphy, A. H. (1988). *Skill scores based on the mean square error and their relationships to the correlation coefficient*. Monthly Weather Review, 116, 2417–2424.
- Selten, R. (1998). *Axiomatic characterization of the quadratic scoring rule*. Experimental Economics, 1, 43–61.