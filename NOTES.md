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

## 3. dev/explore_overs.py

`explore_overs.py` asks a simple question:

> **What normally happens on a ball in each over of an IPL innings?**

It does not train a model. It does not predict matches. It simply looks at real IPL data and counts how often each type of outcome happens in overs 1 through 20.

This follows the basic idea of **exploratory data analysis** described by Tukey (1977): before building a statistical model, first look at the raw structure of the data and understand its patterns.

The script loads the ball-by-ball table created by `parse_archive.py`:

```python
balls = pd.read_pickle("data/balls.pkl")
```

It then keeps seasons from **2019 onward** and only the first two innings:

```python
balls = balls[(balls.season >= 2019) & (balls.innings <= 2)].copy()
```

The reason for using recent seasons is that T20 cricket changes over time. Batting strategies, scoring rates, fielding rules and team tactics are not the same as they were in the early IPL seasons. Using recent data makes the simulator more representative of modern IPL cricket.

The next step determines whether a delivery is a **legal ball**:

```python
balls["legal"] = ~balls.wide & ~balls.noball
```

A normal delivery counts toward the six balls of an over. A wide or no-ball does not. This follows the Laws of Cricket, where wides and no-balls do not count as one of the six legal deliveries of an over (MCC, Law 17.3, with related provisions in Laws 21 and 22).

The most important line in the file is:

```python
balls["balls_before"] = (
    balls.groupby(["match", "innings"], sort=False).legal.cumsum()
    - balls.legal
)
```

This calculates **how many legal deliveries had already been bowled before the current ball**.

For example, at the beginning of an innings:

```text
First legal ball   -> 0 legal balls before it
Second legal ball  -> 1 legal ball before it
Third legal ball   -> 2 legal balls before it
```

`cumsum()` produces a running count, but it includes the current delivery. Subtracting `balls.legal` removes the current delivery from that count.

That small subtraction is important. Without it, every delivery would count itself and the boundaries between overs would shift by one ball.

Once `balls_before` is known, converting a delivery into its over number is straightforward:

```python
legal["over"] = (legal.balls_before // 6).astype(int) + 1
```

Balls `0–5` belong to over 1, balls `6–11` belong to over 2, and so on.

The script keeps only the first 120 legal deliveries:

```python
legal = balls[
    balls.legal & (balls.balls_before < 120)
].copy()
```

A standard T20 innings contains at most 20 overs, or 120 legal deliveries. Cricket records can occasionally contain unusual situations such as an umpire allowing too many balls in an over. Under MCC Law 17.5, an over that has been miscounted still stands. Instead of creating an artificial 21st over, the script simply excludes deliveries beyond the first 120 legal balls.

Each legal ball is then placed into one of **six outcome categories**:

```text
W   bowler wicket
0   dot ball
1   one run
2   two or three runs
4   four or five runs
6   six or more runs
```

The code doing this is:

```python
legal["kind"] = np.select(
    [
        legal.bowler_wicket,
        legal.runs_bat == 0,
        legal.runs_bat == 1,
        legal.runs_bat.isin([2, 3]),
        legal.runs_bat.isin([4, 5]),
    ],
    ["W", "0", "1", "2", "4"],
    "6",
)
```

A three is grouped with a two, and a five is grouped with a four. These outcomes are rare, so giving them their own categories would create very small sample sizes without adding much useful information.

This type of simplified ball-outcome representation is common in cricket simulation work. Swartz, Gill and Muthukumarana (2009) model cricket deliveries using a small set of scoring outcomes and dismissals, and Davis, Perera and Swartz (2015) use a similar idea when constructing a Twenty20 cricket simulator.

A run out is not counted as `W` here because `W` specifically represents a wicket credited to the bowler. A run out still affects the innings, but it is caused by running or fielding rather than by the direct batter-versus-bowler interaction being measured here.

Finally, the script calculates the proportion of each outcome within every over:

```python
shares = pd.crosstab(
    legal.over,
    legal.kind,
    normalize="index"
)[["W", "0", "1", "2", "4", "6"]]
```

`pd.crosstab()` counts how many times each outcome happens in each over. `normalize="index"` converts those counts into proportions.

So if over 1 contains:

```text
51.7% dot balls
24.0% singles
14.2% fours
2.3% sixes
3.3% wickets
```

those values describe what a typical ball in the first over looks like in the historical data.

The output clearly shows that different overs behave differently.

For over 1:

```text
W      0      1      2      4      6
0.033  0.517  0.240  0.044  0.142  0.023
```

Around **52% of balls are dots**, while only around **2% are sixes**.

By over 10:

```text
W      0      1      2      4      6
0.037  0.276  0.472  0.067  0.094  0.054
```

Singles dominate. Almost **47% of balls produce one run**.

By over 20:

```text
W      0      1      2      4      6
0.108  0.223  0.284  0.111  0.137  0.138
```

Both aggressive scoring and wickets become much more common. Sixes occur on roughly **14% of balls**, and bowler wickets occur on roughly **11%**.

This pattern matches normal T20 strategy. During the early powerplay, fielding restrictions create opportunities for boundaries. During the middle overs, teams often rotate the strike with singles. At the death, batters take much larger risks, so both sixes and dismissals increase.

The importance of overs and wickets also connects to the resource-based view of cricket developed by Duckworth and Lewis (1998). Their method treats **overs remaining and wickets remaining as the two main resources available to a batting side**. This script shows why over number matters so much: the probability distribution of what happens on a ball changes substantially depending on when that ball occurs.

The final check:

```text
125465 legal balls
```

is particularly important. It confirms that the legal-ball calculation has reproduced the expected dataset size. A previous implementation accidentally allowed each ball to count itself when calculating `balls_before`, causing over boundaries to shift and dropping hundreds of deliveries. The total number of legal balls exposed the bug even though the resulting percentages still looked believable.

The central idea is therefore simple:

> **`explore_overs.py` measures the natural shape of a modern IPL innings.**

It asks how likely a dot, single, two, four, six or bowler wicket is in each of the twenty overs. These empirical probabilities later provide the foundation for the simulator's over-level scoring model.

### References

- Duckworth, F. C., & Lewis, A. J. (1998). *A fair method for resetting the target in interrupted one-day cricket matches*. Journal of the Operational Research Society, 49.
- Davis, J., Perera, H., & Swartz, T. B. (2015). *A simulator for Twenty20 cricket*. Australian & New Zealand Journal of Statistics, 57.
- Marylebone Cricket Club. *Laws of Cricket*, 2017 Code. See Law 17 concerning overs and related provisions in Laws 21 and 22 for no-balls and wides.
- Swartz, T. B., Gill, P. S., & Muthukumarana, S. (2009). *Modelling and simulation for one-day cricket*. Canadian Journal of Statistics, 37.
- Tukey, J. W. (1977). *Exploratory Data Analysis*. Addison-Wesley.

## 4. dev/explore_reliability.py

`explore_reliability.py` asks one important question:

> **When a batter has a good or bad season, how much of that performance represents real ability, and how much is random variation?**

A batter's observed scoring rate is not pure skill. Even equally skilled players can produce different season numbers because of randomness, opponents, pitches and limited sample size. This script estimates how much we should trust a batter's observed scoring rate before using it to forecast future performance.

The script starts with recent IPL data:

```python
faced = balls[(balls.season >= 2023) & ~balls.wide].copy()
```

Only seasons from 2023 onward are used so that the estimate represents the modern IPL. Wides are removed because a wide does not count as a ball faced by the batter.

The main idea is a **split-half reliability test**. For every batter and season, matches are numbered in order and alternated between two groups:

```python
faced["half"] = faced.groupby(
    ["batter", "season"]
).match.transform(lambda s: pd.factorize(s)[0] % 2)
```

Conceptually:

```text
Match 1 -> half 0
Match 2 -> half 1
Match 3 -> half 0
Match 4 -> half 1
Match 5 -> half 0
Match 6 -> half 1
```

If scoring rate mostly reflects **real batting skill**, players who score quickly in one half should also tend to score quickly in the other. If the numbers mostly reflect noise, performance in one half will tell us little about performance in the other.

This comes from the classical test-theory model:

$$
X = T + E
$$

where `X` is the observed performance, `T` is the player's underlying ability and `E` is measurement noise or random variation. Lord and Novick (1968) give the standard treatment of this framework.

The script calculates each batter's runs per ball separately in the two halves:

```python
halves = faced.groupby(
    ["batter", "season", "half"]
).runs_bat.agg(rate="mean", n="size").unstack()
```

It then keeps only batter-seasons with at least **60 balls in each half**:

```python
halves = halves[
    (halves[("n", 0)] >= 60) &
    (halves[("n", 1)] >= 60)
]
```

This avoids treating very small samples as meaningful estimates of ability.

The correlation between the two halves is then calculated:

```python
r = halves[("rate", 0)].corr(
    halves[("rate", 1)]
)
```

The result is approximately:

```text
r = 0.302
```

If batting rate were almost perfectly stable, this correlation would be close to `1`. If it were almost entirely noise, it would be close to `0`. A correlation of about `0.30` tells us that genuine batting skill is present, but that a half-season measurement still contains substantial noise.

The `0.302` value describes a **half-season**. A full season contains roughly twice as much information, so it should be more reliable. The script therefore applies the **Spearman-Brown formula**, developed independently by Spearman (1910) and Brown (1910):

$$
\text{reliability}
=
\frac{2r}{1+r}
$$

With an odd-even correlation of `0.302`, this gives a full-season reliability of approximately:

$$
0.464
$$

In simple terms:

> **About 46% of the variation in these season-level batting rates behaves like persistent signal, while the remainder behaves like measurement noise.**

This does **not** mean that exactly 54% of every individual batter's season was caused by luck. Reliability describes the variance across a population of measurements, not a literal decomposition of every player's season.

It is also not correct to give every batter exactly 46% weight. Reliability increases when more evidence is available. A batter observed for 400 balls should be trusted more than a batter observed for only 120 balls. A useful approximation is that reliability grows with sample size roughly like:

$$
\frac{n}{n+k}
$$

where `n` is the amount of data and `k` represents how much evidence is required before signal begins to dominate noise. The later reference forecaster handles this **player by player**, shrinking players with little data more strongly and players with large samples less strongly.

This is the forecasting idea known as **regression toward the mean**, described by Galton (1886). If a player's observed number is extreme, some of that extremeness is likely to be noise. A good forecast therefore pulls the estimate toward the league average rather than accepting the raw number completely.

The same general idea appears in statistical shrinkage. James and Stein (1961) showed that when many noisy quantities are estimated simultaneously, pulling individual estimates toward a common centre can improve overall estimation. Efron and Morris (1977) famously illustrated this idea using baseball batting averages.

The script separately estimates the spread of observed batting performance:

```python
whole = faced.groupby(
    ["batter", "season"]
).runs_bat.agg(rate="mean", n="size")

whole = whole[whole.n >= 120]
```

There is a small but important distinction between the two samples. The reliability correlation uses **185 batter-seasons with at least 60 balls in each half**, while the spread calculation uses **227 batter-seasons with at least 120 balls overall**. They are therefore related but not identical groups.

The observed standard deviation is approximately:

```text
0.2047 runs per ball
```

But some of that observed spread is caused by noise.

Reliability describes the fraction of **variance** attributable to stable differences. Because standard deviation is the square root of variance, the estimated spread of underlying skill is:

$$
\sigma_{\text{true}} = \sigma_{\text{observed}} \sqrt{\text{reliability}}
$$

which the code calculates as:

```python
whole.rate.std() * np.sqrt(reliability)
```

Using the observed spread of `0.2047` and reliability of `0.464` gives:

```text
true spread = 0.1394 runs per ball
```

So the raw season data makes qualifying IPL batters appear to differ by about `0.20` runs per ball, while the estimated spread of persistent batting ability is closer to `0.14`.

This matters for forecasting because using the full observed spread would make the model too confident about differences between players. A batter who happened to have an unusually strong short period could be treated as permanently elite, while a batter who experienced a poor period could be treated as permanently weak.

That overconfidence is particularly costly when forecasts are evaluated using logarithmic scoring, because confident mistakes receive much larger penalties.

The reliability estimate here applies specifically to **batting scoring rate measured as runs off the bat per ball faced**. It should not be assumed to apply to every cricket statistic. Different measurements contain different amounts of signal and noise. For example, the same type of analysis later used for bowling produces substantially lower season reliability, around `0.27`, while wicket-taking is even less repeatable. Reliability therefore has to be estimated for the particular quantity being modelled.

The script's expected output is:

```text
185 batter-seasons with 60+ balls in each half
odd-even correlation r = 0.302
reliability of a full season = 0.464
observed spread of strike rate = 0.2047 runs per ball over 227 batter-seasons
true spread = 0.1394 runs per ball
```

The central lesson is simple:

> **Do not treat a batter's observed season statistics as his exact underlying ability.**

A season contains both repeatable skill and random variation. `explore_reliability.py` measures how much of each appears in batting scoring rate so that later forecasting models can shrink uncertain estimates toward the league average instead of becoming overconfident.

### References

- Brown, W. (1910). *Some experimental results in the correlation of mental abilities*. **British Journal of Psychology, 3**, 296–322.
- Efron, B., & Morris, C. (1977). *Stein's paradox in statistics*. **Scientific American, 236**(5), 119–127.
- Galton, F. (1886). *Regression towards mediocrity in hereditary stature*. **Journal of the Anthropological Institute, 15**, 246–263.
- James, W., & Stein, C. (1961). *Estimation with quadratic loss*. **Proceedings of the Fourth Berkeley Symposium on Mathematical Statistics and Probability, 1**, 361–379.
- Lord, F. M., & Novick, M. R. (1968). *Statistical Theories of Mental Test Scores*. Addison-Wesley.
- Spearman, C. (1904). *The proof and measurement of association between two things*. **American Journal of Psychology, 15**.
- Spearman, C. (1910). *Correlation calculated from faulty data*. **British Journal of Psychology, 3**, 271–295.

## 5. dev/fit_state.py

`de/fit_state.py` does two related jobs.

First, it learns **how the situation of a cricket match changes what is likely to happen on the next ball**. Second, after accounting for that situation, it asks **how real batters and bowlers systematically differ from an average player**.

This separation is important. A batter hitting more sixes may genuinely be a power hitter, or he may simply have faced more balls at the death when everybody hits more sixes. The model first learns the effect of the situation and only then looks for player differences.

### Reconstructing the state before every ball

The script begins with the same recent IPL ball-by-ball data used in the earlier analysis:

```python
balls = balls[(balls.season >= 2019) & (balls.innings <= 2)].copy()
```

It determines which deliveries are legal and then reconstructs the scoreboard **immediately before each delivery**.

```python
balls["balls_before"] = innings.legal.cumsum() - balls.legal
balls["wk_before"] = innings.wicket_any.cumsum() - balls.wicket_any
balls["runs_before"] = innings.runs_total.cumsum() - balls.runs_total
```

The subtraction matters because `cumsum()` already includes the current delivery. The model needs to know what the batter saw **before the bowler delivered the ball**, not what the scoreboard looked like afterward.

So a state might look like:

```text
63 legal balls bowled
2 wickets lost
87 runs scored
```

These variables describe how many resources the batting team has already spent. This connects naturally to the resource interpretation of cricket developed by Duckworth and Lewis (1998), where overs and wickets remaining are the two central resources of an innings. Similar state-dependent ideas are used in cricket simulation work by Swartz, Gill and Muthukumarana (2009) and Davis, Perera and Swartz (2015).

For the second innings, the script also calculates the target:

```python
balls["target"] = balls.match.map(first_total) + 1
```

If the first team scored 180, the chasing team needs 181.

### Wickets relative to what is normal

Simply saying that a team has lost three wickets is not enough. Three wickets after four overs is disastrous; three wickets after eighteen overs is normal.

The script therefore measures wickets relative to what teams usually have lost at that stage:

```python
L["wk_excess"] = L.wk_before - L.over.map(typical_wk)
```

Suppose teams normally have lost about two wickets at a particular stage.

Then:

```text
actual wickets = 2  -> wk_excess = 0
actual wickets = 4  -> wk_excess = +2
actual wickets = 1  -> wk_excess = -1
```

This gives the model a single variable describing whether the batting side is unusually healthy or unusually damaged for that point in the innings.

### Measuring chase pressure

The script also measures how difficult a chase has become.

It first estimates the scoring rate that IPL teams normally achieve from each point of an innings to the end. Then, during a chase, it calculates the rate currently required to reach the target.

The pressure variable is approximately:

$$
\text{pressure}
=
\log
\left(
\frac{\text{required scoring rate}}
{\text{normal scoring rate from here}}
\right)
$$

If the required rate is normal, pressure is around zero.

If the chasing team needs to score faster than normal:

```text
pressure > 0
```

If the required rate is comfortable:

```text
pressure < 0
```

The logarithm is useful because ratios become symmetric. Needing twice the normal rate and needing half the normal rate have equal-sized effects in opposite directions on a logarithmic scale.

The value is clipped between `-1.0` and `1.2` so that bizarre situations such as needing forty runs from one ball do not dominate the statistical fit.

### Batting position

The model also records approximately where a player bats.

The order in which players first appear as batter or non-striker is used to construct batting position. Positions 1–3 form the baseline, while the model adds separate effects for:

```text
positions 4–5
positions 6–7
positions 8+
```

This matters because a number-eight batter does not have the same scoring profile as a top-order batter even when they face a similar match situation.



### The six possible outcomes

Every legal ball is placed into one of six categories:

```text
W = bowler wicket
0 = dot ball
1 = one run
2 = two or three runs
4 = four or five runs
6 = six or more runs
```

The purpose of the model is therefore to estimate six probabilities for every ball.

For example:

```text
P(W) = 0.05
P(0) = 0.28
P(1) = 0.41
P(2) = 0.07
P(4) = 0.12
P(6) = 0.07
```

These probabilities change depending on the over, season, innings, wickets lost, chase pressure and batting position.

### The multinomial logistic model

The script builds a matrix called `X`.

Each row represents one ball.

Each column represents one feature of the situation, such as:

```text
Over 1
Over 2
...
Over 20

Season 2020
Season 2021
...

Second innings
Extra wickets lost
Chase pressure
Batting position 4–5
Batting position 6–7
Batting position 8+
```

There are **33 situation variables** in total.

The model gives each outcome a numerical score:

$$
z_k = \sum_j x_j B_{jk}
$$

and then converts the six scores into probabilities using the **softmax function**:

$$
p_k =
\frac{e^{z_k}}
{\sum_m e^{z_m}}
$$

This is multinomial logistic regression: the multi-category extension of ordinary logistic regression. McFadden (1974) developed the conditional-logit framework for modelling choices between multiple alternatives.

The intuition is simple:

> Every feature pushes some outcomes upward and others downward, and softmax turns all those pushes into six probabilities that add to one.



### Why one outcome has to be fixed at zero

There is a mathematical ambiguity in softmax.

Suppose the six scores are:

```text
1, 2, 3, 4, 5, 6
```

Adding ten to every score gives:

```text
11, 12, 13, 14, 15, 16
```

but the resulting probabilities are exactly the same.

Therefore the model needs a reference point.

This code chooses **one run** as the reference outcome:

```python
FREE = [0, 1, 3, 4, 5]
```

The coefficient for outcome index `2`, corresponding to one run, is fixed at zero.

Everything else is therefore learned relative to a single.

For display, the code later centres each six-number row around zero. This changes the appearance of the coefficients but not their meaning or probabilities.



### How the model learns the coefficients

The model asks:

> Given the match situation, how much probability did I assign to what actually happened?

Its loss is the negative log-likelihood:

$$
-\sum_i \log p_{i,y_i}
$$

If the model gives high probability to what happened, the penalty is small. If it gives very low probability to what happened, the penalty is large.

This is the same logarithmic-loss principle used in the earlier `ExactScorer`.

The gradient of the loss is particularly clean:

$$
X^\top(P-Y)
$$

where `P` contains the predicted probabilities and `Y` contains the outcomes that actually occurred. Bishop (2006) derives this form for multinomial logistic models.

The script provides this gradient directly to SciPy instead of making the optimizer approximate it numerically:

```python
gradient = (X.T @ (p - Y))[:, FREE].ravel() + 1e-2 * theta
```

That makes optimization substantially faster.



### Why there is a ridge penalty

The loss also contains a tiny penalty:

$$
\frac{1}{2}\lambda \|\theta\|^2
$$

with:

```text
lambda = 0.01
```

This is **ridge regularization**, associated with Hoerl and Kennard (1970).

Its practical purpose here is to discourage unnecessarily large coefficients and help give the optimization problem a well-defined solution.

Because the penalty is very small relative to the amount of data, it acts mainly as numerical stabilization rather than strong shrinkage.



### Why the optimization is well behaved

The multinomial-logit negative log-likelihood is convex in its coefficients. Adding the positive quadratic ridge term makes the problem strictly convex.

Boyd and Vandenberghe (2004) give the general convex-optimization theory behind this.

In practical terms:

> There is one best solution rather than many unrelated local minima.

The script finds it using **L-BFGS-B**, a limited-memory quasi-Newton optimizer described by Liu and Nocedal (1989) and Byrd et al. (1995).

The expected fit converges in roughly:

```text
145 iterations
```



### Why the code subtracts the largest score

Before calculating exponentials, the code does:

```python
z -= z.max(1, keepdims=True)
```

This looks like it changes the model, but it does not.

Softmax has the property:

$$
\operatorname{softmax}(z)
=
\operatorname{softmax}(z-c)
$$

for any constant `c` added or removed from all six scores.

The subtraction simply prevents huge values such as:

```text
exp(1000)
```

from overflowing the computer's floating-point representation.

This shifted calculation is the numerically stable way to compute softmax and log-sum-exp, discussed in detail by Blanchard, Higham and Higham (2021).



### What the fitted situation effects say

Once the model has been fitted, its coefficients show how match situations change behavior.

For example, one additional wicket lost relative to normal produces approximately:

```text
dots    +0.128
sixes   -0.095
```

on the model's log-odds scale.

The interpretation is intuitive:

> A team that has lost more wickets than usual becomes more defensive.

Chase pressure produces the opposite behavior:

```text
sixes    +0.351
dots     -0.392
wickets  +0.191
```

When the required rate becomes difficult, batters attack more aggressively. That reduces dots and increases sixes, but it also increases dismissals.

Players batting at number eight or lower show another distinctive pattern: more dots and dismissals and fewer boundaries.



### Separating player ability from match situation

This is the second major job of the file.

Suppose a batter hit unusually many sixes.

That does **not automatically mean he has a special six-hitting ability**. Perhaps he happened to face far more balls in overs 18–20 than most players.

The fitted situation model lets the script ask a fairer question:

> Given the exact situations this batter faced, how many sixes would an average IPL batter have been expected to hit?

For each player, the code therefore calculates:

```text
observed outcomes
versus
expected outcomes from the situation model
```

For example:

```text
                     Observed    Expected

Wickets                  15         14
Dots                    120        130
Singles                  95        110
Twos                     25         30
Fours                    50         48
Sixes                    45         18
```

This player hit far more sixes than an average player would have been expected to hit in the same situations.

That is evidence of an individual player characteristic rather than simply match context.



### Player "tilts"

The code summarizes this difference using:

```python
tilt = np.log((observed + 0.5) / (expected + 0.5))
```

In simple terms:

```text
observed > expected -> positive tilt
observed < expected -> negative tilt
```

Taking a logarithm makes proportional differences easier to combine.

The `0.5` added to each count prevents problems when an outcome was never observed. This is a traditional continuity correction associated with Anscombe (1956).

The six values are then centred so that their average is zero:

```python
tilt -= tilt.mean(1, keepdims=True)
```

The result describes **how the player's outcome distribution differs from average**.



### Removing differences caused by sampling noise

There is still another problem.

Imagine two completely identical batters.

If each faced only 300 balls, they would not produce exactly the same number of fours, singles and sixes simply because cricket is random.

Therefore the raw differences between players exaggerate the amount of real player variation.

The script estimates this sampling noise and subtracts it from the observed covariance:

$$
\hat{\Sigma}_{\text{true}}
=
\hat{\Sigma}_{\text{observed}}
-
\hat{\Sigma}_{\text{noise}}
$$

This is the multivariable version of the same idea used in `explore_reliability.py`:

> **Observed variation = real variation + measurement noise.**

Measurement-error models such as Fuller (1987) formalize this distinction, while Tipping and Bishop's probabilistic PCA framework (1999) similarly separates structured latent variation from noise.



### Finding the main ways players differ

After noise is removed, the code performs an eigenvalue decomposition:

```python
values, vectors = np.linalg.eigh(covariance)
```

This is conceptually similar to **principal component analysis**.

Instead of giving every player six unrelated numbers, it asks:

> What combinations of those six outcomes explain most of the genuine differences between players?

The eigenvectors give those directions.

The eigenvalues say how much real player variation lies along each one.

So instead of inventing player attributes such as:

```text
power = 8
aggression = 6
control = 7
```

the script lets the real IPL data determine which player dimensions actually exist.



### What it discovers about batters

Among **103 batters with at least 300 balls**, roughly:

```text
71% of real player variation -> first direction
13%                          -> second
10%                          -> third
```

The first direction looks approximately like:

```text
more sixes
fewer singles
fewer twos
more wickets
little change in dots
little change in fours
```

That is naturally interpreted as something like:

```text
power hitter <--> accumulator
```

Importantly, this is mostly a **style axis**, not simply a good-player versus bad-player axis.

One end takes more risks, hits more sixes and gets dismissed more often. The other accumulates more singles and twos.

The data produced this direction first; the human label `"style"` was applied afterward.

The second major batting direction is much more closely related to dismissal probability and therefore behaves more like a **quality dimension**.



### What it discovers about bowlers

The same procedure is applied to bowlers with at least 300 deliveries.

Among approximately **110 bowlers**, the first direction explains around:

```text
43% of real variation
```

and the second around:

```text
36%
```

The strongest direction largely trades the probability of conceding fours against the probability of conceding sixes.

That pattern can plausibly separate different bowling styles, such as pace and spin, although the interpretation is applied after seeing the data rather than imposed beforehand.



### Why the eigenvector sign is fixed

There is a small mathematical detail in:

```python
first = vectors[:, 0] * np.sign(vectors[5, 0])
```

An eigenvector has no natural direction.

These two vectors describe exactly the same axis:

```text
[ 0.2, -0.5, 0.7]
[-0.2,  0.5,-0.7]
```

So the code simply adopts a convention:

> The first player direction always points toward more sixes.

That makes results reproducible and easier to interpret.



### The gradient bug this analysis exposed

One particularly important lesson from this file is that numerical bugs do not always crash a program.

The incorrect gradient was once written as:

```python
+ 1e-2 + theta
```

instead of:

```python
+ 1e-2 * theta
```

The program still ran.

The optimizer even reported success.

But the fitted coefficients were subtly wrong.

That is dangerous because the numbers still looked believable.

A standard defensive check is `scipy.optimize.check_grad`, which compares the analytic gradient with a finite-difference approximation. A production version of this calibration should include such a test.



### Expected checks

The fitted dataset contains:

```text
125,465 legal balls
33 model columns
165 free coefficients
```

because five outcome coefficients are learned for each of the 33 predictors while the single-run outcome is fixed as the reference:

$$
33 \times 5 = 165
$$

The optimizer should converge in approximately:

```text
145 iterations
```

The main player-direction results are approximately:

```text
Batters
103 regular players
first-direction spread = 0.347
variation shares = [0.71, 0.13, 0.10]

Bowlers
110 regular players
first-direction spread = 0.203
variation shares = [0.43, 0.36, 0.16]
```

Tiny differences in the final decimals can occur because numerical optimizers stop once they fall within a tolerance.

Finally, the fitted coefficients and player directions are written to:

```text
data/state_fit.json
```

This file becomes part of the calibrated simulator.



### The main idea

The easiest way to understand `fit_state.py` is as a two-stage question.

First:

> **Given the over, wickets, score, chase pressure and batting position, what would an average IPL player probably do on this ball?**

Then:

> **After accounting for all of that context, how do real players consistently behave differently from that average?**

The first part learns the **state of the game**.

The second part learns the **hidden dimensions of player style and ability**.

Together they stop the simulator from confusing circumstances with talent. A batter is not labelled a power hitter merely because he happened to bat at the death; he has to hit more sixes than an average batter would have hit **in those same situations**.

### References

- Anscombe, F. J. (1956). *On estimating binomial response relations*. **Biometrika, 43**.
- Bishop, C. M. (2006). *Pattern Recognition and Machine Learning*. Springer, Section 4.3.
- Blanchard, P., Higham, D. J., & Higham, N. J. (2021). *Accurately computing the log-sum-exp and softmax functions*. **IMA Journal of Numerical Analysis, 41**, 2311–2330.
- Boyd, S., & Vandenberghe, L. (2004). *Convex Optimization*. Cambridge University Press.
- Byrd, R. H., Lu, P., Nocedal, J., & Zhu, C. (1995). *A limited memory algorithm for bound constrained optimization*. **SIAM Journal on Scientific Computing, 16**.
- Davis, J., Perera, H., & Swartz, T. B. (2015). *A simulator for Twenty20 cricket*. **Australian & New Zealand Journal of Statistics, 57**.
- Duckworth, F. C., & Lewis, A. J. (1998). *A fair method for resetting the target in interrupted one-day cricket matches*. **Journal of the Operational Research Society, 49**.
- Fuller, W. A. (1987). *Measurement Error Models*. Wiley.
- Hoerl, A. E., & Kennard, R. W. (1970). *Ridge regression: biased estimation for nonorthogonal problems*. **Technometrics, 12**.
- Liu, D. C., & Nocedal, J. (1989). *On the limited memory BFGS method for large scale optimization*. **Mathematical Programming, 45**.
- McFadden, D. (1974). *Conditional logit analysis of qualitative choice behavior*. In P. Zarembka (Ed.), *Frontiers in Econometrics*. Academic Press.
- Swartz, T. B., Gill, P. S., & Muthukumarana, S. (2009). *Modelling and simulation for one-day cricket*. **Canadian Journal of Statistics, 37**.
- Tipping, M. E., & Bishop, C. M. (1999). *Probabilistic principal component analysis*. **Journal of the Royal Statistical Society: Series B, 61**.

## 6. dev/fit_constants.py

`dev/fit_constants.py` answers the design questions that the main ball-by-ball model cannot answer by itself.

It asks things like:

> **Do grounds genuinely behave differently? Are batter-versus-bowler matchups real or mostly noise? How much should we trust a bowler's season? How many extra runs occur outside the batter's scoring? And what real IPL statistics should the simulator reproduce before we trust it?**

The general rule throughout this file is simple:

> **An effect is treated as real only if it repeats in independent data.**

This is the same idea used in `explore_reliability.py`. If something appears in one half of the data but disappears in another, it is probably noise. If it consistently appears in both halves, it is evidence of a real underlying effect.



### Extras per Legal Ball

The first calculation measures how many team runs come from **extras rather than the batter**.

```python
recent.runs_total - recent.runs_bat
```

This includes wides, no-balls, byes and leg byes.

Under the Laws of Cricket, these runs are recorded separately from runs credited to the striker (MCC Laws 21–23).

The code divides total extras by the number of legal balls:

```python
legal = (~recent.wide & ~recent.noball).sum()
```

and obtains approximately:

```text
extras_per_legal_ball = 0.0764
```

That corresponds to roughly:

```text
0.0764 × 120 ≈ 9 runs per full innings
```

The simulator therefore adds a small amount of extra scoring on top of the six batter outcomes learned earlier.

This is deliberately treated as a **league-level constant** rather than a hidden skill for every bowler. Although wides and no-balls can reflect bowling control, their repeatability is too weak here to justify another player parameter.



### Batter and Bowler Season Reliability

The next function repeats the split-half experiment from `explore_reliability.py`, but now it can be applied to either batters or bowlers.

```python
season_reliability(who, floor)
```

For a batter, the measured rate is:

```text
runs off the bat / balls faced
```

For a bowler, it is:

```text
runs off the bat conceded / balls bowled
```

Each player's season is split into alternating matches, the rates in the two halves are correlated, and the **Spearman-Brown correction** converts half-season reliability into full-season reliability (Spearman, 1910; Brown, 1910).

The approximate results are:

```text
Batter season reliability ≈ 0.46
Bowler season reliability ≈ 0.27
```

The important lesson is that bowling season statistics are even noisier than batting statistics.

A reliability of `0.27` means only about 27% of the observed variation in this bowling measure behaves like persistent signal across the sampled seasons.

It does **not** mean exactly 73% of every bowler's season was luck. It means the observed differences between bowlers contain a large amount of unstable variation.

This is why the later forecaster should shrink bowling estimates toward the league average more strongly than batting estimates.



### Removing the Change in Scoring Across Seasons

Before testing venues or player interactions, the script removes the league-wide scoring level for each season:

```python
faced["res"] = (
    faced.runs_bat
    - faced.groupby("season").runs_bat.transform("mean")
)
```

This creates a **residual**.

A residual simply means:

> How much higher or lower was this ball's batting score compared with the normal scoring level of that season?

This is necessary because IPL scoring has changed over time.

Suppose one ground hosted many matches in a high-scoring modern season while another hosted more matches in an older, lower-scoring period. Comparing their raw scoring rates would make the first venue look better for batting even if the grounds themselves were identical.

Subtracting the season mean removes much of this time trend before venue and matchup effects are measured.



### Do Grounds Really Differ?

The `venue_spread()` function tests whether grounds have persistent scoring characteristics.

Each ground's matches are divided into two halves. The average residual scoring level is calculated separately in each half.

Then the script asks:

> If a ground was unusually high-scoring in one half of the data, was it also unusually high-scoring in the other half?

For the 18 grounds with enough data, the repeat correlation is approximately:

```text
r = 0.71
```

That is strong repeatability.

It suggests that venue differences are not merely random.

The estimated true standard deviation is about:

```text
0.045 runs per ball
```

Across a 120-ball innings:

```text
0.045 × 120 ≈ 5.4 runs
```

So moving from a typical venue to a roughly one-standard-deviation high-scoring venue corresponds to about five runs per innings.

That is large enough to matter.

Therefore:

> **The simulator should contain a genuine venue effect.**

The conversion from observed spread to true spread uses the same reliability logic as the batter analysis in File 4.



### Testing Specific Matchups

The `interaction()` function answers a harder question:

> Does a particular combination behave differently from what we would expect based on its individual parts?

Examples include:

```text
specific batter × specific bowler
specific batter × venue
specific bowler × venue
```

Suppose Virat-like Batter A is generally excellent and Bowler B generally concedes many runs.

If Batter A scores heavily against Bowler B, that alone is not evidence of a special matchup.

We first need to remove:

```text
Batter A's normal level
Bowler B's normal level
```

and ask whether there is anything left that belongs specifically to the pair.

That is what this section does.



### Why Player Levels Are Removed Separately Inside Each Half

The code removes each participant's average within the same:

```text
season
+
half of the data
```

For example:

```python
faced.groupby([key, "season", "half"]).res.transform("mean")
```

This detail is important.

If the average were calculated using both halves together, information from half 1 would leak into the correction applied to half 2 and vice versa.

That would make the two supposedly independent measurements statistically dependent and could artificially push the repeat correlation downward.

So each half is cleaned independently before the two halves are compared.



### Turning Repeatability Into a True Effect Size

Suppose the measured interaction in each half follows the classical model:

$$
X = T + E
$$

where:

- `T` is the real persistent interaction,
- `E` is sampling noise.

If the repeat correlation between halves is `r`, then:

$$
\frac{r}{1-r}
$$

gives the ratio of real variance to noise variance under this model (Lord & Novick, 1968).

The code then estimates:

$$
\sigma^2_{\text{true}}
=
\frac{r}{1-r}
\cdot
\frac{\operatorname{Var}(\text{residuals})}{n}
$$

where `n` is approximately the number of balls observed for each pair.

The more balls available, the smaller the sampling noise of the pair average.



### Batter vs Bowler

For batter-bowler pairs with at least 30 balls in each half, the repeat correlation is only about:

```text
0.178
```

across roughly:

```text
113 well-sampled pairs
```

That is weak.

So even among pairs that have met many times, head-to-head performance does not repeat strongly.

The conclusion is:

> **There is little evidence that a large hidden parameter should exist for every individual batter-bowler pair.**

The simulator can still model broad matchup properties, such as a batter performing differently against pace and spin, but it does not need thousands of pair-specific hidden values.

This resembles findings in baseball where historical batter-pitcher matchup records contain much less predictive information than fans often assume. Tango, Lichtman and Dolphin discuss this problem in *The Book: Playing the Percentages in Baseball* (2007).



### Batter at Venue

The batter-venue interaction repeats at approximately:

```text
0.188
```

across around:

```text
309 sufficiently sampled pairs
```

This is still weak, but it is positive.

It suggests that some batters may genuinely perform slightly better or worse at particular grounds even after accounting for their overall batting level and the general venue effect.

The simulator therefore keeps a **small batter-at-venue effect**, rather than a large one.



### Bowler at Venue

The bowler-venue repeat correlation is approximately:

```text
-0.026
```

which is effectively zero.

A negative number this close to zero provides no useful evidence of repeatability.

So:

> **The simulator does not need a bowler-specific venue preference.**

The venue itself matters, but individual bowlers do not show a stable additional venue effect in this analysis.



### Real-Cricket Targets

The final major part of the file calculates statistics that the simulator must reproduce.

These are **validation targets**, not model parameters.

That distinction matters.

The simulator is not directly told:

```text
"Make the mean first-innings score 188.5."
```

Instead, it is built from the lower-level ball model, player effects, venue effects and other mechanisms.

Then a simulated league is run and checked against real cricket.

This follows standard simulation validation practice: compare the distributions generated by the simulation with the distributions observed in the system being imitated (Sargent, 2013).

Davis, Perera and Swartz (2015) use the same general philosophy in validating a Twenty20 cricket simulator.



### First-Innings Score

For recent seasons, the mean first-innings total is approximately:

```text
188.5 runs
```

with a standard deviation of approximately:

```text
37.4 runs
```

So the simulator should not merely reproduce the average score. It should also reproduce the amount of variation between innings.

A simulator producing every first innings between 185 and 192 would have the right mean but would still be unrealistic.



### Wickets

The first innings averages approximately:

```text
5.9 bowler wickets
```

This checks whether the simulator has the correct balance between scoring and dismissals.



### Chase Success

The chasing side wins approximately:

```text
50.9%
```

of the relevant matches in the calibration data.

But overall chase percentage is not enough.

The script also calculates chase success by target size.

Conceptually:

```text
Target below 160     -> chasing side often succeeds
160–179              -> harder
180–199              -> harder again
200–219              -> difficult
220+                 -> very difficult
```

The observed success rate falls from roughly:

```text
81% for small targets
```

to approximately:

```text
21% for targets of 220+
```

A believable simulator must reproduce this relationship.

If every target had roughly the same chase probability, the simulated game would be structurally wrong even if its overall win rate happened to be correct.



### Scoring by Over

The script also records the average scoring rate for each first-innings over.

This lets `validate_world.py` later check whether the simulator recreates the familiar structure of a T20 innings:

```text
powerplay
middle overs
death overs
```

A simulator could have the correct final score while producing it in the wrong way.

For example:

```text
Real cricket:
moderate middle overs + explosive death

Bad simulator:
same scoring rate in all 20 overs
```

Both could average 188 runs, but only one resembles actual cricket.

That is why per-over scoring is part of validation.



### What Gets Saved

All fitted constants and validation targets are written to:

```text
data/constants_fit.json
```

The output contains quantities such as:

```text
extras_per_legal_ball
batter season reliability
bowler season reliability

venue:
    number of qualifying venues
    repeatability
    true scoring spread

batter_vs_bowler:
    number of pairs
    repeatability
    estimated true spread

batter_at_venue
bowler_at_venue

real_targets:
    first innings mean
    first innings spread
    wickets
    chase rate
    scoring by over
    chase success by target
```

This file therefore becomes another major calibration artifact used by the simulator.



### The Main Design Decisions Produced by This File

The statistical calculations translate directly into simulator architecture.

```text
Finding                               Simulator decision

Ground repeatability = 0.71      ->   Give venues a hidden scoring level

Batter reliability ≈ 0.46       ->   Moderate shrinkage of batter estimates

Bowler reliability ≈ 0.27       ->   Stronger shrinkage of bowler estimates

Batter × bowler repeat ≈ 0.18   ->   No large pair-specific matchup effect

Batter × venue repeat ≈ 0.19    ->   Allow a small batter-ground effect

Bowler × venue repeat ≈ 0       ->   No bowler-ground interaction

Extras ≈ 0.0764 / legal ball    ->   Add league-level extras process
```

This is the most important role of `fit_constants.py`.

It does not merely calculate descriptive cricket statistics.

It decides **which hidden variables deserve to exist in the simulated world**.

If an effect repeats, the simulator may represent it.

If it does not repeat, the simulator should resist the temptation to model noise as if it were skill.



### Why This Matters

Without this file, it would be easy to build an overly complicated simulator containing:

```text
special batter-bowler rivalries
large player-ground bonuses
stable wicket-taking ability
large venue-specific bowling effects
```

because all of those can appear convincing when looking at historical averages.

But historical averages mix signal with sampling noise.

`fit_constants.py` asks a stronger question:

> **Does the effect appear again when we look at independent data?**

That turns the simulator from a collection of plausible cricket assumptions into something much closer to a statistically calibrated model.

### References

- Brown, W. (1910). *Some experimental results in the correlation of mental abilities*. **British Journal of Psychology, 3**, 296–322.
- Davis, J., Perera, H., & Swartz, T. B. (2015). *A simulator for Twenty20 cricket*. **Australian & New Zealand Journal of Statistics, 57**.
- Lord, F. M., & Novick, M. R. (1968). *Statistical Theories of Mental Test Scores*. Addison-Wesley.
- Marylebone Cricket Club. *Laws of Cricket*, 2017 Code. Laws 21–23 concerning no-balls, wides, byes and leg byes.
- Sargent, R. G. (2013). *Verification and validation of simulation models*. **Journal of Simulation, 7**.
- Spearman, C. (1910). *Correlation calculated from faulty data*. **British Journal of Psychology, 3**, 271–295.
- Tango, T., Lichtman, M., & Dolphin, A. (2007). *The Book: Playing the Percentages in Baseball*. Potomac Books.

## 7. dev/build_calibration.py

`build_calibration.py` is the point where I stop doing new statistical measurement and start turning everything I already measured into the actual language of the simulator.

Up to this point, the calibration pipeline has produced two major files:

```text
data/state_fit.json
data/constants_fit.json
```

`state_fit.json` contains the fitted ball-state model from `fit_state.py`: over effects, season effects, batting-position effects, chase-pressure effects, wicket-state effects, and the directions along which real batters and bowlers differ.

`constants_fit.json` contains the other measurements that do not naturally belong inside the multinomial ball model: extras, venue variation, player reliability, interaction tests and the real-cricket statistics that the simulated league should eventually reproduce.

These files contain the information I need, but they are still expressed in the units that were convenient for the statistical analysis. Some values are logits, some are eigenvectors, some are correlations, some are standard deviations, and some are real cricket quantities such as runs per ball.

What I want from `build_calibration.py` is therefore:

> **Take everything I measured in Files 5 and 6, standardize it, convert it into interpretable simulator units, and package it into one coherent calibration.**

There is no new measurement happening here. I am not going back to the ball archive and estimating another effect. Every value in this file is derived from something I already measured.

---

### Loading the Previous Fits

I start by loading:

```python
fit = json.loads(Path("data/state_fit.json").read_text())
con = json.loads(Path("data/constants_fit.json").read_text())
```

I think of these two inputs as describing different layers of the cricket world.

`fit` tells me how the six ball outcomes change with:

```text
over
season
innings
wickets
chase pressure
batting position
player style
player quality
bowling type
bowling quality
```

`con` tells me things such as:

```text
extras rate
venue spread
batter reliability
bowler reliability
batter-bowler repeatability
batter-venue repeatability
real scoring targets
```

The job of this script is to make these different measurements speak the same language.

---

### The Six Ball Outcomes

The six outcomes remain:

```text
W   wicket credited to bowler
0   dot ball
1   one run
2   two or three runs
4   four or five runs
6   six or more runs
```

For translating probability changes into runs, I use:

```python
RUNS = np.array([0, 0, 1, 2, 4, 6])
```

A wicket and a dot both score zero runs off the bat, while the other entries represent the run value associated with each outcome class.

---

### Standardizing Every Direction

The player analysis in `fit_state.py` produced several six-dimensional directions.

For example, one batter direction looked broadly like:

```text
more sixes
fewer singles
fewer twos
more dismissals
```

I interpreted that as a batter style direction.

But the raw eigenvectors coming from the previous fit are not yet suitable for direct use. I therefore define:

```python
def unit(v, positive=None, negative=None):
    v = np.array(v, float)
    v = v - v.mean()
    v = v / np.linalg.norm(v)

    if positive is not None and v[positive] < 0:
        v = -v

    if negative is not None and v[negative] > 0:
        v = -v

    return v
```

This function does three things:

```text
centre the direction
normalize its length
fix its sign
```

Each one has a different reason.

---

### Why I Centre the Directions

The simulator ultimately converts six scores into probabilities using softmax.

Suppose the scores are:

```text
1, 2, 3, 4, 5, 6
```

and I add ten to every value:

```text
11, 12, 13, 14, 15, 16
```

The resulting probabilities are unchanged.

That is because:

$$
\operatorname{softmax}(z)
=
\operatorname{softmax}(z+c)
$$

when the same constant $c$ is added to every outcome.

So a common offset across all six numbers carries no information.

I remove that meaningless part with:

```python
v = v - v.mean()
```

After centering, the six values sum to zero.

Now the vector represents only the relative movement between outcomes.

That makes it easier for me to read the direction as:

```text
this outcome becomes more likely
this outcome becomes less likely
this one barely moves
```

rather than carrying around an arbitrary shared offset.

---

### Why I Normalize the Directions

Next I calculate:

```python
v = v / np.linalg.norm(v)
```

so that:

$$
\|v\|_2 = 1
$$

for every direction.

This lets me cleanly separate two ideas.

The **direction** tells me how the six outcomes change together.

The **spread** tells me how much real players differ along that direction.

Without normalization, those two ideas would be mixed together.

One vector could simply contain larger numbers than another because of how the eigendecomposition returned it.

After normalization, I can say:

```text
one unit of batter style
one unit of batter quality
one unit of bowling type
```

and know that "one unit" means the same mathematical distance in all three cases.

This is the standard interpretation of eigenvectors and principal-component directions described by Jolliffe (2002).

---

### Why I Fix the Sign

Eigenvectors also have an arbitrary sign.

If:

```text
[ 0.3, -0.4, 0.8 ]
```

is an eigenvector, then:

```text
[-0.3,  0.4,-0.8 ]
```

is mathematically the same axis.

That is fine for linear algebra, but it is confusing for a simulator and for anyone reading the calibration.

I therefore choose fixed conventions:

```text
bat_style
    positive means more sixes

bat_quality
    positive means fewer dismissals

bowl_type
    positive means more sixes conceded

bowl_quality
    positive means fewer fours conceded
```

The sign choice does not alter the statistical result. It simply makes the coordinates stable and readable.

If I did not fix the signs, a rerun could theoretically flip an eigenvector and suddenly make:

```text
+1 bat_style
```

mean the opposite cricket behaviour even though nothing substantive had changed.

---

### Measuring the Era Trend

The situation model from `fit_state.py` gave every season its own six-number effect.

Conceptually I have:

```text
2019 -> six outcome effects
2020 -> six outcome effects
2021 -> six outcome effects
...
2026 -> six outcome effects
```

with 2019 acting as the baseline.

Now I want to compress that sequence into a simpler description of how the game is moving over time.

For each outcome I fit a straight line:

```python
trend = np.array([
    np.polyfit(years, effects[:, k], 1)[0]
    for k in range(6)
])
```

`np.polyfit(..., 1)` is fitting:

$$
y = a + bx
$$

using ordinary least squares.

The slope $b$ tells me how that outcome's logit changes per season.

Doing this separately for all six outcomes produces a six-dimensional trend vector.

Ordinary least squares is the standard linear fitting method discussed in Hastie, Tibshirani and Friedman (2009).

---

### Era Direction Versus Era Speed

I then centre the trend:

```python
trend -= trend.mean()
```

because the common offset still carries no softmax information.

Then I calculate:

```python
era_step = float(np.linalg.norm(trend))
```

The value is approximately:

```text
0.0934 per season
```

I interpret the result as two separate pieces.

The normalized trend tells me:

> **In what direction is the game's outcome distribution moving?**

The magnitude tells me:

> **How fast is it moving in that direction each season?**

So conceptually:

```text
conditions direction = shape of the change

era_step = speed of the change
```

If later seasons contain relatively fewer dots and more boundaries, that pattern appears in the direction.

`era_step` tells me how strongly the simulator should move along that direction from one season to the next.

---

### Why I Reuse the Era Trend as the Conditions Axis

I call the normalized era trend:

```text
conditions
```

and I use it as the common direction for several environmental effects.

These can include:

```text
season era
venue scoring level
pitch conditions
dew
day-specific batting conditions
```

My reasoning is that these factors can all make batting broadly easier or harder.

A better batting environment generally means something like:

```text
fewer dots
more boundaries
more runs
```

Rather than creating an independent six-dimensional direction for every environmental cause, I let them move the ball probabilities along one measured axis.

This is a modelling simplification.

The data directly supports the historical season trend.

The stronger assumption is that venue conditions, pitch, dew and era all change outcomes in roughly the same shape.

I make that choice because it keeps the simulator compact and identifiable. The archive does not contain enough clean information to estimate several separate condition axes with the same confidence.

---

### Moving the Over Profiles Into the Modern Era

The twenty over effects from `fit_state.py` are relative to the model's baseline season.

I do not want the simulator's default game to look like the IPL in 2019.

I want it to look like the recent IPL.

So I calculate the average season effect across:

```text
2023
2024
2025
2026
```

with:

```python
recent = np.mean([
    fit["season_effects"][s]
    for s in ("2023", "2024", "2025", "2026")
], axis=0)
```

and add that to every over:

```python
overs = np.array(fit["overs"]) + recent
```

The result is a:

```text
20 × 6
```

matrix.

Each row is an over.

Each column is one of:

```text
W, 0, 1, 2, 4, 6
```

These become the simulator's `over_logits`.

This is the starting distribution for a ball before any batter, bowler, venue or match-state adjustments are applied.

The question at this stage is:

> **What would an average ball in this over look like in the modern IPL?**

Everything else modifies that baseline.

---

### Creating a Typical Ball

The hidden directions are mathematically meaningful, but a six-number vector is still difficult to interpret.

I want to translate them into cricket language.

To do that, I create a representative "typical ball."

I convert each over's logits to probabilities:

```python
p = np.exp(overs)
p /= p.sum(1, keepdims=True)
```

and then average over the twenty overs:

```python
p = p.mean(0)
```

Now `p` contains approximately:

```text
P(W)
P(0)
P(1)
P(2)
P(4)
P(6)
```

for a representative IPL ball.

I do not use this averaged distribution to simulate matches.

It exists only so that every direction can be interpreted at the same reference point.

---

### Translating a Direction Into Runs Per Ball

Suppose I move a small amount $s$ along a direction $d$.

The logits become:

$$
z_k(s)=z_k+s d_k
$$

The softmax derivative in that direction is:

$$
\frac{\partial p_k}{\partial s}
=
p_k
\left(
d_k-\sum_j p_jd_j
\right)
$$

This is the usual derivative of the multinomial softmax model described by Bishop (2006).

Expected runs are:

$$
\mathbb E[R]
=
\sum_k p_kR_k
$$

with:

$$
R=(0,0,1,2,4,6)
$$

Therefore:

$$
\frac{\partial\mathbb E[R]}{\partial s}
=
\sum_k p_kd_kR_k
-
\left(\sum_k p_kd_k\right)
\left(\sum_k p_kR_k\right)
$$

I compute that with:

```python
value = lambda d: float(
    (p * d * RUNS).sum()
    - (p * d).sum() * (p * RUNS).sum()
)
```

This answers a very useful question:

> **If I move one unit along this hidden direction, approximately how much does expected scoring change in runs per ball?**

That converts an abstract vector into a cricket quantity.

---

### Translating a Direction Into Wicket Risk

I do the same for wicket probability.

Since the wicket outcome is index zero, I use:

```python
risk = lambda d: float(
    p[0] * (d[0] - (p * d).sum())
)
```

Now every direction has two readable summaries:

```text
runs_per_unit
wicket_risk_per_unit
```

This lets me explain what the hidden axis actually means.

---

### Batter Style Versus Batter Quality

This translation is particularly helpful for the two batter directions.

The first direction, `bat_style`, is worth approximately:

```text
+0.258 runs per ball
+0.021 wicket probability per ball
```

for one unit.

So moving toward the positive end means:

```text
score much faster
but
accept more dismissal risk
```

That is why I interpret it as:

```text
accumulator <----> power hitter
```

rather than:

```text
bad <----> good
```

The second direction, `bat_quality`, is different.

One unit is worth roughly:

```text
+0.054 runs per ball
-0.047 wicket probability per ball
```

So the batter scores somewhat faster while also becoming much harder to dismiss.

That looks much more like a genuine quality axis.

The separation matters because I do not want the simulator to confuse aggression with skill.

---

### The Five Directions I Keep

The final standardized directions are:

```python
directions = {
    "bat_style": ...,
    "bat_quality": ...,
    "bowl_type": ...,
    "bowl_quality": ...,
    "conditions": ...
}
```

I can think about the hidden structure as:

```text
Batter
    style
    quality

Bowler
    type
    quality

Environment
    conditions
```

The important point is that I did not simply invent variables called "style" and "quality" because they sounded plausible.

The first four directions came from real between-player covariance after correcting for match state and sampling noise.

The fifth came from the fitted historical season trend.

The labels came after the directions were measured.

---

### Measuring How Widely Players Vary

A direction only tells me **how** players differ.

I also need to know **how much** they differ.

From `fit_state.py`, the first-axis standard deviations are already available:

```text
batter first direction = 0.347
bowler first direction = 0.203
```

These were calculated after subtracting estimated sampling noise from the player covariance.

So I treat them as estimates of real population spread, rather than the raw spread of noisy observed statistics.

---

### Recovering the Second-Direction Spread

The JSON contains the first-axis standard deviation and the shares of variation associated with the main eigen-directions.

In principal-component analysis:

$$
\operatorname{Var}_j = \lambda_j
$$

and therefore:

$$
\sigma_j = \sqrt{\lambda_j}
$$

So:

$$
\frac{\sigma_2}{\sigma_1}
=
\sqrt{
\frac{\lambda_2}{\lambda_1}
}
$$

and because the stored variance shares are proportional to the eigenvalues:

$$
\sigma_2
=
\sigma_1
\sqrt{
\frac{\text{share}_2}
{\text{share}_1}
}
$$

The code therefore calculates:

```python
bat_quality_sd = (
    bat_style_sd
    * np.sqrt(bat[1] / bat[0])
)
```

and the equivalent quantity for bowlers.

This gives approximately:

```text
bat_style       0.347
bat_quality     0.150

bowl_type       0.203
bowl_quality    0.187
```

Jolliffe (2002) gives the standard PCA interpretation of eigenvalues as variances along principal directions.

---

### Why the Spreads Matter

These numbers eventually control how different the invented players are from one another.

Conceptually, a generated batter can have hidden values on scales such as:

```text
style   ~ population with SD 0.347
quality ~ population with SD 0.150
```

and a bowler:

```text
type    ~ population with SD 0.203
quality ~ population with SD 0.187
```

If I made these spreads too large, the simulated league would contain unrealistically extreme players and forecasting would become too easy.

If I made them too small, every player would behave almost the same and most apparent player differences would be noise.

These spreads therefore control both realism and task difficulty.

That is why I want them measured from the archive rather than guessed.

---

### Reproducibility Check

`build_calibration.py` also has an optional comparison mode.

If I give it another calibration file:

```text
python dev/build_calibration.py old_calibration.json
```

it compares every major block against the newly rebuilt version.

For each block I flatten the values into one long vector and calculate:

$$
\max_i
\left|
x_i^{\text{new}}
-
x_i^{\text{old}}
\right|
$$

In plain English:

> **What is the single largest numerical disagreement anywhere in this block?**

I compare blocks such as:

```text
over_logits
position_vectors
wickets_in_hand_vector
chase_pressure_vector
second_innings_vector
typical_wickets_by_over
par_rate_from_over
directions
spreads
era_step
runs_per_unit
wicket_risk_per_unit
extras_per_legal_ball
venue_level_sd_runs
batter_venue_sd_runs
```

This is my end-to-end check that the calibration can actually be reproduced from the source data and code.

Peng (2011) describes this broader idea of reproducible computational research: the analysis should be sufficiently specified that the reported numerical results can be recreated.

---

### Why Tiny Differences Remain

The expected largest difference is approximately:

```text
0.0007
```

Most blocks differ by:

```text
0.0000
```

or:

```text
0.0001
```

The small remaining discrepancy comes mainly from `fit_state.py`.

L-BFGS-B stops when its numerical convergence criteria are satisfied. It does not produce an infinitely precise symbolic optimum.

Tiny floating-point and optimization differences can therefore survive into:

```text
coefficients
eigenvectors
normalized directions
derived cricket-unit values
```

and eventually appear in the fourth decimal of the final calibration.

A maximum difference around `0.0007` is therefore consistent with reproducing the same calibration to the precision the simulator actually uses.

---

### Limits

The first important limitation is that I compress the fitted season effects into a straight-line trend.

That assumes the era evolves approximately steadily.

A sudden structural change caused by a major rule change or tactical shift would not be represented well by one constant `era_step`.

The second limitation is the single `conditions` axis.

I assume venue level, pitch, dew and era all move outcome probabilities in broadly the same direction.

That keeps the model identifiable, but reality may contain several distinct environmental directions.

I deliberately prefer one well-measured direction over several weakly identified ones.

---

### References

- Bishop, C. M. (2006). *Pattern Recognition and Machine Learning*. Springer. Section 4.3 discusses multinomial logistic regression and the softmax derivative.
- Hastie, T., Tibshirani, R., & Friedman, J. (2009). *The Elements of Statistical Learning* (2nd ed.). Springer.
- Jolliffe, I. T. (2002). *Principal Component Analysis* (2nd ed.). Springer.
- Peng, R. D. (2011). *Reproducible research in computational science*. **Science, 334**, 1226–1227.

---

## 8. league/calibration.json

`league/calibration.json` is the final artifact produced by the calibration pipeline.

If `build_calibration.py` is the compiler, I think of `calibration.json` as the compiled statistical description of the cricket world.

The earlier files worked directly with raw historical data, fitted models, residuals, correlations and eigenvectors.

The simulator should not have to know how any of that was estimated.

It should be able to open one file and find everything it needs.

That is the purpose of:

```text
league/calibration.json
```

---

### What the File Contains

The JSON contains the simulator-ready ball model:

```text
over_logits
position_vectors
wickets_in_hand_vector
chase_pressure_vector
second_innings_vector
typical_wickets_by_over
par_rate_from_over
```

It also contains the hidden directions:

```text
bat_style
bat_quality
bowl_type
bowl_quality
conditions
```

and their population spreads:

```text
bat_style       0.347
bat_quality     0.150
bowl_type       0.203
bowl_quality    0.187
```

It includes the human-readable interpretation of those directions through:

```text
runs_per_unit
wicket_risk_per_unit
```

and it includes the other calibrated quantities from `fit_constants.py`:

```text
extras_per_legal_ball
venue_level_sd_runs
batter_venue_sd_runs
measured interaction results
real_targets
```

So the file contains both the mechanisms that generate the world and the measurements that later tell me whether that world looks realistic.

---

### `over_logits`

The `over_logits` block contains twenty rows of six values.

Conceptually:

```text
over 1  -> W, 0, 1, 2, 4, 6 scores
over 2  -> W, 0, 1, 2, 4, 6 scores
...
over 20 -> W, 0, 1, 2, 4, 6 scores
```

These profiles have already been moved from the 2019 baseline to the average recent-era level.

They are therefore the simulator's default view of modern IPL scoring.

Every simulated delivery begins with the appropriate over profile.

Then the rest of the model modifies it.

---

### Situation Vectors

The JSON also contains effects such as:

```text
wickets_in_hand_vector
chase_pressure_vector
second_innings_vector
position_vectors
```

These come directly from the fitted multinomial state model.

For example, `wickets_in_hand_vector` tells the simulator how the six ball-outcome probabilities should move when a batting side has lost more wickets than usual.

`chase_pressure_vector` tells it how behavior changes when a chasing side needs to score faster than the normal rate from that point onward.

`position_vectors` account for the difference between top-order, middle-order and tail-end batting.

The important point is that these are not hand-written cricket rules.

They are fitted from the ball archive.

---

### Player Directions

The `directions` section contains:

```text
bat_style
bat_quality
bowl_type
bowl_quality
conditions
```

Each is a centered, unit-length six-number vector.

These vectors describe the shape of the hidden variation.

For a batter, I do not need six unrelated ability parameters.

I can represent much of the real variation with:

```text
style
quality
```

Similarly, a bowler receives:

```text
type
quality
```

This gives the generator a compact latent representation of player differences.

---

### Player Spreads

The `spreads` section tells me how widely the player population should be distributed along those directions.

For example:

```text
bat_style = 0.347
```

means that the real population contains considerably more variation in batting style than:

```text
bat_quality = 0.150
```

The generator uses these scales when creating fictional players.

The numbers are important because they determine how distinguishable real player skill is from random match variation.

If I overstate them, players become too obviously different.

If I understate them, everyone becomes nearly interchangeable.

---

### Conditions and Era Drift

The JSON also stores:

```text
conditions
era_step
```

The `conditions` vector describes the shape of movement toward a more batting-friendly or more bowling-friendly environment.

`era_step` controls how much the league moves along that direction each season.

The measured value is approximately:

```text
0.0934
```

per season.

So I can let the simulated league evolve through time rather than treating every season as identical.

---

### Cricket-Unit Interpretations

The blocks:

```text
runs_per_unit
wicket_risk_per_unit
```

are mainly there to make the latent variables understandable.

For example, instead of only seeing a vector for `bat_style`, I can read its approximate consequence in cricket terms:

```text
more runs per ball
but also more dismissal risk
```

Likewise, `bat_quality` can be understood as a direction that improves scoring while substantially reducing wicket probability.

These values do not create a separate model.

They are interpretations of the same directions already stored in the JSON.

---

### Venue Effects

The calibration contains:

```text
venue_level_sd_runs
```

because `fit_constants.py` found that venue scoring differences repeat strongly across independent halves of the data.

The approximate venue repeat correlation was:

```text
0.71
```

which was strong enough for me to conclude that a genuine venue-level effect belongs in the world.

The calibration therefore gives the world generator a measured scale for venue variation.

It also contains:

```text
batter_venue_sd_runs
```

because batter-at-venue effects showed a small positive repeat signal.

By contrast, I do not create an equivalent bowler-at-venue hidden effect because that interaction did not repeat.

---

### Why There Is No Large Batter-Bowler Pair Parameter

The calibration also preserves the measured interaction result for:

```text
batter_vs_bowler
```

but it does not turn every historical batter-bowler pair into a hidden simulator parameter.

That is deliberate.

The repeat correlation was weak.

So although head-to-head history can look convincing when viewed retrospectively, the independent-half test suggested that most of it is noise.

The simulator therefore represents broader style interactions rather than thousands of bespoke player-pair rivalries.

---

### Extras

The JSON stores:

```text
extras_per_legal_ball
```

which is approximately:

```text
0.0764
```

runs per legal delivery.

This lets the simulator produce realistic team totals without trying to absorb wides, no-balls, byes and leg byes into the six batter outcomes.

The value is treated as a league-level property because the analysis did not find enough stable individual variation to justify another hidden bowler dimension.

---

### Real Validation Targets

The `real_targets` block contains the real-world statistics that the simulated league should later reproduce.

Examples include:

```text
first-innings mean
first-innings standard deviation
first-innings wickets
chasing-side win rate
runs per over
chase success by target band
```

These values do not directly force the simulation.

They are validation targets.

For example, if real first innings average approximately:

```text
188.5 runs
```

I do not hard-code:

```text
make simulated mean = 188.5
```

into the engine.

Instead, I generate matches using the lower-level mechanics and then check whether the resulting league naturally produces approximately the right score distribution.

That distinction is fundamental.

A simulation should be validated on the consequences of its mechanisms, not by directly inserting the final quantities it is supposed to reproduce.

---

### Why the Source Attribution Is Stored in the JSON

The first field preserves the provenance of the calibration:

```text
Calibration constants derived from data sourced from Cricsheet
(cricsheet.org), licensed under the Open Data Commons Attribution
License (ODC-BY 1.0). Aggregates only.
```

The calibration contains no individual historical player records, match diaries or raw deliveries.

It contains fitted and aggregated quantities.

But those quantities are derived from Cricsheet data, so I keep the source attribution directly with the derived artifact.

This means someone can copy or inspect the calibration without losing track of where its measurements came from.

---

### Why I Round the File to Four Decimal Places

The calibration is mostly rounded to:

```text
4 decimal places
```

This is intentional.

Values such as:

```text
0.3471
```

already contain more numerical precision than the underlying cricket measurements really justify.

Writing:

```text
0.347129847162
```

would suggest that the sixth or tenth decimal means something.

It does not.

There is sampling uncertainty in the archive, modelling approximation, numerical optimization tolerance and the simplifications of the simulator itself.

Four decimal places are more than enough for downstream simulation while keeping the file readable and reproducible.

---

### Why This File Is the Boundary Between Calibration and Simulation

Up to `league/calibration.json`, I am still reconstructing the statistical world from real cricket.

After this file, the simulator can operate without the original historical archive.

That creates a clean boundary:

```text
REAL CRICKET
     |
     v
raw archive
     |
     v
statistical measurement
     |
     v
noise correction
     |
     v
state fitting
     |
     v
calibration
     |
     v
league/calibration.json
-----------------------------
     |
     v
SIMULATED CRICKET
```

Everything above the line is about estimating the world.

Everything below the line can be about generating a new one.

---

### Why I Do Not Claim This Is the Exact Original Task World

This repository's `league/calibration.json` is rebuilt by this pipeline.

It is not manually copied from the calibration file used by the original piloted task.

The difference matters.

Even a change of:

```text
0.0007
```

in one calibration value could eventually lead to different:

```text
invented players
venue values
match outcomes
league histories
forecast probabilities
```

because simulation compounds small changes through many random draws.

So reproducing the calibration procedure is not the same thing as reproducing the exact original generated world.

A task generated from this rebuilt calibration should therefore have its own:

```text
world generation
validation
gates
pilot runs
```

That is why this reconstruction stops at the calibration stage rather than claiming that it has recreated the previously piloted task bit-for-bit.

---

### How I Think About `calibration.json`

The easiest mental model for me is:

> **`league/calibration.json` is the physics sheet for the artificial cricket universe.**

The original archive contained hundreds of thousands of deliveries.

The final JSON compresses that historical evidence into statements such as:

```text
how over 1 differs from over 20

how extra wickets change batting behaviour

how chase pressure changes risk-taking

how top-order and tail-end batting differ

what a power-hitter direction looks like

what a batter-quality direction looks like

what bowling-style variation looks like

how much players really differ

how much venues really differ

how many extras occur

how quickly the era is changing
```

The ball archive is huge.

The calibration is compact.

That compression is the whole point.

---

### Pipeline Up to This Point

At this stage my pipeline is:

```text
Cricsheet IPL archive
        |
        v
dev/parse_archive.py
        |
        v
data/balls.pkl
        |
        +-------------------------------+
        |                               |
        v                               v
dev/explore_overs.py        dev/explore_reliability.py
        |                               |
        +---------------+---------------+
                        |
                        v
               dev/fit_state.py
                        |
                        v
              data/state_fit.json


data/balls.pkl
        |
        v
dev/fit_constants.py
        |
        v
data/constants_fit.json


data/state_fit.json
        +
data/constants_fit.json
        |
        v
dev/build_calibration.py
        |
        v
league/calibration.json
        |
        v
calibrated simulator
```

The transformation can be summarized as:

```text
raw historical cricket
        ↓
clean ball-level data
        ↓
exploratory structure
        ↓
reliability measurement
        ↓
state model
        ↓
player directions
        ↓
venue and interaction constants
        ↓
standardized simulator parameters
        ↓
league/calibration.json
```

The central idea for this file is:

> **`league/calibration.json` is the compact statistical blueprint of the cricket world I measured. The simulator can now use that blueprint without needing the historical archive or the fitting code.**

### References

- Bishop, C. M. (2006). *Pattern Recognition and Machine Learning*. Springer.
- Jolliffe, I. T. (2002). *Principal Component Analysis* (2nd ed.). Springer.
- Open Data Commons. *Open Data Commons Attribution License (ODC-BY) v1.0*.
- Peng, R. D. (2011). *Reproducible research in computational science*. **Science, 334**, 1226–1227.