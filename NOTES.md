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

### References

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

## 2. dev/parse_archive.py

`parse_archive.py` converts Cricsheet's IPL ball-by-ball match files into one clean table with one row for every delivery. The purpose is not to calculate cricket statistics yet. It simply turns many complicated YAML match files into a format that is much easier to analyze later on.

The raw data comes from Cricsheet, which publishes ball-by-ball cricket data in YAML format. Each IPL match contains general information such as the date, venue and teams, followed by every innings and every delivery. For each delivery, Cricsheet records the batter, non-striker, bowler, runs, extras and wickets. The archive is maintained by Stephen Rushe and released under the Open Data Commons Attribution License.

The parser converts this nested structure into a flat pandas table. Each row represents one delivery and each column represents one property of that delivery, such as the batter, bowler, runs scored or whether the ball was a wide. This follows the idea of **tidy data**, where each observation is a row and each variable is a column (Wickham, 2014). Once the data has this shape, later questions such as "how often are sixes hit in over 18?" become simple group-and-count operations.

The resulting table is stored in a pandas `DataFrame`, following the tabular data structures described by McKinney (2010). It is then saved as `data/balls.pkl` using pandas' pickle format so that later scripts can load the processed dataset quickly instead of parsing more than a thousand YAML files again.

PyYAML is used to read each match file. The code prefers `CSafeLoader`, which uses the compiled `libyaml` implementation when available, and falls back to the normal Python loader otherwise. This is purely a performance choice; both loaders produce the same Python dictionaries and lists.

Cricsheet represents an innings using a dictionary containing one item. For example:

```text
{"1st innings": {...}}
```

The line

```python
(label, body), = innings.items()
```

extracts that single key-value pair. The unusual trailing comma is useful because Python will raise an error if the dictionary unexpectedly contains more than one item. This prevents malformed data from being silently interpreted incorrectly.

The same idea is used for individual deliveries, which look roughly like:

```text
{0.1: {...}}
```

The delivery label such as `0.1` is saved as `over_ball` so that deliveries can later be reconstructed in their original order.

For each delivery, the parser stores both `runs_bat` and `runs_total`. These are different because not every run scored by the team belongs to the batter. For example, runs from wides and no-balls can be recorded as extras rather than batter runs. Under the Laws of Cricket, wides and the no-ball penalty are extras rather than runs credited to the striker (MCC Laws 21 and 22). Keeping both values allows later code to measure batting performance separately from team scoring.

Wides and no-balls are also stored as Boolean flags. This matters because they do not count as one of the six legal balls in an over. The MCC Laws of Cricket specify that wides and no-balls do not count toward the legal-ball count of an over (MCC Law 17.3, with related provisions in Laws 21 and 22). Later analysis can therefore reconstruct the true number of legal deliveries rather than simply counting every recorded delivery.

The parser also keeps two different wicket indicators. `bowler_wicket` represents dismissals credited to the bowler, while `wicket_any` represents almost any dismissal that reduces the batting side's available wickets.

For example, a **run out** counts as a wicket for the batting side but is not credited to the bowler. Therefore:

```text
run out
    wicket_any     = True
    bowler_wicket  = False
```

The `NOT_BOWLER` tuple currently excludes run outs, retired hurt and obstructing the field when calculating bowler wickets. This follows cricket scoring conventions, although a few extremely rare dismissal types could also be excluded in a more complete production implementation.

Super overs are ignored. Cricsheet may record a super over as an additional innings, but a super over is a special tie-breaking procedure rather than an ordinary innings. Since the later calibration is intended to describe normal IPL play, innings whose labels contain `"super"` are skipped.

The match header contributes mainly the **date** and **venue**. The date is later converted into a season by taking its calendar year:

```python
balls["season"] = balls["date"].str[:4].astype(int)
```

This works for the IPL because its seasons have historically remained within a single calendar year, including unusual seasons such as 2020 and the split 2021 season. The venue is kept so that later scripts can study whether scoring conditions differ between grounds.

The parser intentionally does not calculate player ability, venue effects, over-level scoring rates or forecasting probabilities. Its responsibility is much simpler: **take messy match diaries and produce a trustworthy ball-level dataset**. This separation makes later statistical calculations easier to inspect and debug.

The final table contains columns such as:

```text
match
date
venue
innings
team
over_ball
batter
non_striker
bowler
runs_bat
runs_total
wide
noball
bowler_wicket
wicket_any
season
```

The processed data is saved under `data/`, which is ignored by Git. This makes sense because the file is derived data that can be regenerated from the original Cricsheet archive rather than something that needs to be stored permanently in the repository.

The parser is also checked against known totals. For the IPL match on 5 April 2017, the parsed deliveries sum to 379 team runs, corresponding to Sunrisers Hyderabad's 207 and Royal Challengers Bangalore's 172. Across the full calibration archive, the expected totals are 1,243 matches, 295,557 recorded deliveries, 9,871 wides, 1,221 no-balls, 13,466 bowler wickets and 401,423 runs. These checks act as simple regression tests: if a future change produces different totals, something in the parser probably changed.

The key idea is therefore straightforward: **`parse_archive.py` is the data-cleaning layer of the simulator.** Cricsheet provides detailed but deeply nested match records; this script turns them into a simple table where every later cricket measurement can be expressed as filtering, grouping and counting.

### References

- Cricsheet. *Ball-by-ball cricket data archive*. Maintained by Stephen Rushe. Open Data Commons Attribution License 1.0.
- Marylebone Cricket Club. *Laws of Cricket*, 2017 Code. In particular Laws 17, 21 and 22 concerning overs, no-balls and wides.
- McKinney, W. (2010). *Data structures for statistical computing in Python*. Proceedings of the 9th Python in Science Conference.
- Wickham, H. (2014). *Tidy Data*. Journal of Statistical Software, 59(10).
- PyYAML documentation and `libyaml` documentation for the safe C-backed YAML loader.