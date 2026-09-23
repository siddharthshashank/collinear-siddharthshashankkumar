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

## 9. league/calibration.py

### What I am trying to do

`league/calibration.py` is where I draw a hard line between **numbers I measured from the cricket archive** and **numbers I chose when designing the simulated world**.

I keep those two categories separate because they have completely different justifications.

A measured number should answer a question like:

> **What evidence in the archive produced this value?**

A design number should answer a different question:

> **Why did I choose this value, and what behaviour was I trying to create?**

I represent those two categories with two classes:

```text
Calibration
Design
```

`Calibration` contains the quantities reconstructed from real IPL data through the earlier pipeline.

`Design` contains the assumptions I deliberately introduce when the archive cannot uniquely determine the answer.

This distinction is important in simulation modelling. Law (2015) separates input modelling from the broader construction and validation of the simulation model for exactly this reason. Sargent (2013) similarly distinguishes the validity of the input data and assumptions from the validity of the conceptual model and the behaviour of the final simulation.

If I mix measured quantities and design decisions into one anonymous collection of constants, it becomes very easy to forget which values have evidence behind them and which values exist because I made a modelling choice.

I want the opposite. I want every important number in the world to have a clear provenance.

---

### `Calibration`: the measured world

The first class is:

```python
@dataclass(frozen=True)
class Calibration:
```

I use a Python dataclass because this object is mostly a structured collection of named values.

The class holds quantities such as:

```text
over_logits
position_vectors
wickets_vector
pressure_vector
second_innings_vector
typical_wickets
par_rate
directions
spreads
era_step
runs_per_condition_unit
extras_per_ball
venue_sd_runs
batter_venue_sd_runs
real_targets
```

Every one of these comes from the calibration pipeline I built in the previous files.

The point of this class is not to estimate anything. Its job is to load those measurements once and expose them to the simulation engine through one consistent object.

---

### Why I make `Calibration` frozen

I declare the dataclass with:

```python
@dataclass(frozen=True)
```

The `frozen=True` part makes the dataclass immutable in normal use.

Once I create a `Calibration` object, I cannot casually write:

```python
calibration.era_step = 0.5
```

and silently change the underlying world.

That matters because calibration constants are supposed to represent measurements.

If one piece of the engine accidentally mutates them midway through a simulation, I no longer have one coherent data-generating process. I have a world whose rules can change because of a programming mistake.

Immutability therefore acts as a small defensive boundary.

It also makes verification easier. If the engine is supposed to remain untouched during the task, having a frozen calibration object reduces the number of ways internal code can accidentally rewrite its own constants.

Python's dataclass mechanism was introduced through PEP 557.

---

### Loading `calibration.json`

The `Calibration` class has one loader:

```python
@classmethod
def load(cls, path=None):
```

Its purpose is straightforward. It reads the JSON artifact built in File 8 and turns the numerical blocks into the arrays and dictionaries expected by the engine.

The default path is:

```python
Path(__file__).with_name("calibration.json")
```

This means the loader looks for `calibration.json` beside `calibration.py`.

I chose this deliberately.

The engine should not require some external configuration such as:

```text
CALIBRATION_PATH=/some/machine/specific/location/file.json
```

to find its own constants.

If the package contains:

```text
league/
    calibration.py
    calibration.json
```

then:

```python
Calibration.load()
```

is enough.

That makes the engine portable and keeps the task environment simpler.

I can still pass a different path explicitly when I want to test another calibration.

---

### Turning JSON lists into NumPy arrays

JSON stores numerical vectors as ordinary lists.

The engine performs vector arithmetic on these quantities, so I convert the relevant blocks into NumPy arrays while loading them:

```python
np.array(raw["over_logits"])
```

and similarly for the position vectors, wicket vector, pressure vector, second-innings vector, typical-wicket curve and par-rate curve.

I also convert every latent direction:

```python
{k: np.array(v) for k, v in raw["directions"].items()}
```

This gives the simulation code one consistent numerical representation.

Instead of repeatedly converting lists to arrays throughout the engine, I do the conversion once at the boundary where the JSON enters Python.

---

### Expanding batting-position groups

The fitted model did not estimate eleven independent batting-position effects.

That would waste information and make the later positions extremely noisy.

Instead, File 5 used four groups:

```text
positions 1–3
positions 4–5
positions 6–7
positions 8–11
```

The JSON therefore contains four fitted position vectors.

The simulation engine, however, knows the actual batting position of each player and wants to index directly by position.

I bridge those two representations with:

```python
groups = [0, 0, 0, 1, 1, 2, 2, 3, 3, 3, 3]
```

This says:

```text
position 1  -> group 0
position 2  -> group 0
position 3  -> group 0

position 4  -> group 1
position 5  -> group 1

position 6  -> group 2
position 7  -> group 2

position 8  -> group 3
position 9  -> group 3
position 10 -> group 3
position 11 -> group 3
```

I then expand the four fitted vectors into eleven directly indexable vectors:

```python
np.array(raw["position_vectors"])[groups]
```

So the final `Calibration` object has shape:

```text
(11, 6)
```

for batting-position effects even though only four distinct effects were estimated.

This is useful because the statistical model and the simulation engine want slightly different representations.

The fitting stage wants enough pooling to estimate reliable effects.

The engine wants direct indexing.

The loader is the right place to reconcile those two needs.

---

### What I expect the loader to produce

When I load the calibration produced by the previous pipeline, I expect the main shapes and headline quantities to agree with the reconstructed world.

The over logits should have shape:

```text
(20, 6)
```

because there are twenty overs and six outcome categories.

The expanded position matrix should have shape:

```text
(11, 6)
```

because the engine can now address every batting position directly.

I expect five latent directions:

```text
bat_style
bat_quality
bowl_type
bowl_quality
conditions
```

The batter-style spread should be around:

```text
0.3475
```

depending on the exact rounded calibration used.

The era step should be:

```text
0.0934
```

and the extras rate should be approximately:

```text
0.0764
```

per legal ball.

At this point `Calibration` gives the rest of the engine one object representing the measured statistical world.

---

### `Design`: the world I choose

The second class is:

```python
@dataclass(frozen=True)
class Design:
```

This is deliberately separate from `Calibration`.

The values in `Design` are not all direct estimates from the archive.

Some are derived from archive measurements but require another modelling step. Some are chosen specifically so that the simulator reproduces a validation target. Others are ordinary world-design choices for which the archive does not contain a unique correct answer.

I still make this class frozen because I want the design of a generated world to remain fixed once simulation begins.

But the epistemic meaning is different.

For `Calibration`, I ask:

> **Where was this number measured?**

For `Design`, I ask:

> **Why did I choose this number?**

---

### Talent and temporary form

One important design problem is how I represent player ability through time.

I do not want a player's skill to be completely permanent, because real form changes.

I also do not want a player to become statistically unrelated to himself from one season to the next.

I therefore think of current skill as containing two components:

```text
persistent talent
+
temporary form
```

The design uses:

```python
talent_share = 0.7
form_memory_years = 0.75
```

The fixed talent component contributes 70% of the long-run structure.

The remaining component changes over time and mean-reverts.

I model that temporary component using an Ornstein-Uhlenbeck process, the classical continuous-time mean-reverting stochastic process associated with Uhlenbeck and Ornstein (1930).

If form has an exponential correlation decay, the correlation one year apart is approximately:

$$
0.7 + 0.3e^{-1/0.75}
$$

which is about:

$$
0.78
$$

That is close to the underlying year-to-year batting-skill stability implied by the reliability analysis.

The raw season-to-season correlation was approximately:

```text
0.36
```

while season reliability was approximately:

```text
0.46
```

so correcting for attenuation gives roughly:

$$
\frac{0.36}{0.46}
\approx 0.78
$$

under the equal-reliability interpretation used here.

So `talent_share` and `form_memory_years` are design parameters, but they are not arbitrary. I chose them together so that the resulting hidden skill process has approximately the stability implied by the archive.

---

### Bowling type gap

I use:

```python
type_gap = 0.28
```

to create a visible distinction between the two broad bowling types.

The measured first bowling direction had a standard deviation of about:

```text
0.203
```

If I split bowlers into two equally sized groups separated by `0.28`, each group is centred roughly:

```text
0.14
```

away from the overall mean.

The between-group variance is therefore around:

$$
0.14^2
$$

while the total measured variance on the bowling-type axis is approximately:

$$
0.203^2
$$

So the public pace-versus-spin distinction explains roughly half of the measured variation along that axis.

The remaining variation stays hidden within the individual bowler values.

I prefer this to making bowling type explain the entire axis, because the real eigenvector is not literally a binary pace-versus-spin label. It is a continuous measured direction that happens to resemble that distinction.

---

### Batter split against bowling type

I use:

```python
split_sd = 0.10
```

to give individual batters a small difference between their quality against pace and their quality against spin.

I deliberately keep this effect modest.

File 6 showed that specific batter-bowler interactions repeated only weakly, with a correlation around:

```text
0.18
```

even among selected, well-sampled pairs.

That result argues against giving every batter a huge hidden matchup profile.

At the same time, broad stylistic differences between facing pace and spin are plausible and useful for the task.

So I include a small batter-specific split rather than either extreme of no matchup structure or enormous pair-specific effects.

---

### Batter-venue affinity

I use:

```python
affinity_share = 0.8
```

to decide how much of the measured batter-at-venue variation should be treated as genuinely personal.

File 6 found a small but positive repeatable batter-venue effect.

The total observed relationship can contain more than one mechanism. Some of it may be personal affinity for a ground, while some may arise because players repeatedly appear at home venues whose general conditions already suit them.

The simulator already has a venue-level effect and a home effect.

`affinity_share` tells me how much of the remaining measured batter-venue spread I assign to an individual batter's personal affinity.

This is therefore a decomposition choice applied to a measured quantity rather than a new empirical measurement.

---

### Recentering the league scoring level

I use:

```python
level_runs = -0.058
```

as a global scoring adjustment.

This exists because introducing player heterogeneity changes the league mean.

Even if player attributes are centred around zero, pushing probabilities through a nonlinear softmax does not guarantee that the average of many heterogeneous players equals the output of the zero-valued average player.

In general:

$$
f(\mathbb E[X])
\neq
\mathbb E[f(X)]
$$

for a nonlinear function $f$.

So once I introduce real variation in batter style, batter quality, bowling type, bowling quality and other effects, the average simulated score moves.

I use `level_runs` to recenter the resulting world on the real recent first-innings mean of approximately:

```text
188.5
```

runs.

The parameter itself is therefore a design adjustment chosen to hit a measured validation target.

---

### Day-to-day pitch variation

I use:

```python
day_sd_runs = 0.17
```

to represent variation in the pitch and conditions on a particular day.

The archive tells me that first-innings totals have a standard deviation around:

```text
37.4 runs
```

The simulator already produces substantial variation through player differences, stochastic ball outcomes, venue effects and match state.

I then choose the day-level spread so that the overall simulated score distribution is reasonably close to the real one.

With this value, the simulator's first-innings spread is around:

```text
35.5
```

runs.

That is still slightly below the archive's `37.4`, and I keep that miss documented rather than hiding it.

So `day_sd_runs` is not something I measured directly as "the real pitch SD." It is a design parameter chosen to make one important aggregate distribution realistic.

---

### Second-innings wear

I use:

```python
wear_runs = 0.053
```

to make second innings slightly more difficult in the absence of compensating conditions such as dew.

The real archive gives me a chase-success target of roughly:

```text
50.9%
```

for the recent period used in calibration.

Without a second-innings adjustment, the simulator's chasing side can become too successful.

I therefore introduce a small wear effect so that otherwise identical sides are closer to the empirical chase rate.

The resulting simulator still produces a chase rate around:

```text
53.1%
```

rather than exactly `50.9%`.

Again, I keep the discrepancy visible.

The point is not to overfit every aggregate target perfectly. The point is to produce a coherent world that is close to the important distributions while retaining simple, interpretable mechanisms.

---

### Home advantage

I use:

```python
home_runs = 0.025
```

as a small home-team scoring advantage.

In rough innings terms this is on the order of a few runs across a full T20 innings.

I treat this as a judgement parameter rather than claiming that `0.025` is an independently estimated causal home effect from the archive.

Estimating a clean home effect would require separating team strength, venue effects, schedule structure and potentially several other confounders.

For the task I only need a modest and plausible home advantage, so I document it as a design choice.

---

### Dew

I use:

```python
dew_share = 0.4
dew_runs = 0.044
```

to create a subset of evening environments where conditions become more favourable to the chasing side.

I do not claim that these exact values were identified from Cricsheet.

The ball archive does not directly contain a clean variable saying:

```text
dew severity = 0.044
```

The mechanism exists because dew is a plausible source of second-innings environmental variation, but both its frequency and magnitude are design choices in this world.

Their purpose is to create realistic variation around the general second-innings wear effect rather than treating every chase as occurring under identical conditions.

---

### Handedness and bowling-style interactions

I include:

```python
left_handed = 0.3
```

as the approximate share of generated batters who are left-handed.

I then use the small:

```text
type_table_runs
```

interaction to represent the idea that batter handedness and bowling style can matter slightly.

The table is:

```python
((0.0, -0.008),
 (0.0,  0.019))
```

where the rows correspond to right- and left-handed batters and the columns correspond to pace and spin.

These are deliberately small effects.

I do not want a simple public category such as handedness to overwhelm the hidden player-quality structure measured from the archive.

Instead it creates a modest, understandable matchup component that an agent could potentially learn and exploit.

---

### Pitch type and bowling style

I also include:

```python
pitch_table_runs
```

to create a small interaction between bowling type and pitch type.

The table is:

```python
((0.0,  0.019, -0.010),
 (0.0, -0.010,  0.019))
```

The rows correspond to pace and spin.

The columns correspond to:

```text
neutral
pace-friendly
turning
```

I use this to make pitch identity matter differently to different bowling styles.

Again, these are small design effects rather than archive-fitted coefficients.

The goal is not to claim that `0.019` is the exact real causal benefit of spin on a turning IPL pitch.

The goal is to create a coherent latent world in which public categorical information interacts with hidden player characteristics in a controlled way.

---

### Transfers

I set:

```python
transfer_share = 0.25
```

so that roughly a quarter of players change teams between seasons.

This parameter exists primarily for the forecasting task.

If every player stays on the same team forever, team identity becomes a very strong proxy for player quality.

A forecaster that models only teams could then recover much of the useful information without understanding individual players.

Transfers deliberately break that shortcut.

When players move, some predictive information moves with the player rather than remaining attached to the team name.

This makes a player-aware model meaningfully better than a pure team-history model.

So this is not an attempt to reproduce an exact empirical IPL transfer rate. It is a deliberate task-design choice that creates the information structure I want the agent to reason about.

---

### League size and roster structure

I use:

```python
teams = 10
```

with squad composition:

```python
squad_roles = (7, 4, 7)
```

meaning seven batters, four all-rounders and seven bowlers per squad.

A playing eleven uses:

```python
xi_roles = (5, 2, 4)
```

meaning five batters, two all-rounders and four bowlers.

The generated world contains:

```python
seasons = 3
weeks_per_season = 8
```

These values define the size and horizon of the environment rather than being statistical measurements.

They determine how much history the agent sees, how often players meet, how much transfer information can accumulate and how long the forecasting problem remains manageable.

They are therefore part of the task design rather than the cricket calibration.

---

### Three kinds of design number

The important thing for me is that not every number in `Design` has the same justification.

Some values are **derived from measured quantities**. `talent_share`, `form_memory_years`, `type_gap`, `split_sd` and `affinity_share` are choices that I connect directly to measurements from Files 4–6.

Some values are **chosen to reproduce a validation target**. `level_runs`, `day_sd_runs` and `wear_runs` exist because I need the final simulated league to have approximately the right mean score, score spread and chase behaviour.

Other values are **plain modelling judgements**. Home advantage, dew, handedness, pitch interactions, transfer frequency, league size and roster structure are mechanisms I deliberately introduce because the archive cannot uniquely determine them.

Keeping all three categories visible is important.

A reviewer can disagree with one of my design choices without that disagreement undermining the measurements in `Calibration`.

Likewise, a measured constant can be checked against its source data without pretending that the design decisions were statistically estimated.

---

### Why I put the reasons beside the numbers

I deliberately keep comments such as:

```python
day_sd_runs = 0.17
```

next to an explanation of why `0.17` exists.

I do not want a future reader to find a naked constant and have to reverse engineer its purpose.

If someone asks:

> **Where did `0.17` come from?**

the answer should be visible at the point where the number lives.

This is similar to the discipline of an architecture decision record. A design decision is much easier to review when the decision, its context and its consequence stay together.

For this task, that documentation also matters because some quantities are public and some are deliberately hidden from the forecasting agent.

I want to be able to state truthfully that every hidden mechanism has a recorded rationale rather than being an unexplained knob added until a pilot happened to fail.

---

### How the two classes fit together

The distinction I want the engine to preserve is:

```text
calibration.json
      |
      v
Calibration
      |
      |   measured from archive
      |
      +------------------------+
                               |
                               v
                         simulation world
                               ^
                               |
      +------------------------+
      |
      |   chosen mechanisms
      |
Design
```

`Calibration` defines the statistical structure I recovered from real cricket.

`Design` determines how I turn that measured structure into one particular artificial world.

The engine needs both.

Without `Calibration`, the world would be mostly invented.

Without `Design`, the archive would still leave many questions unanswered.

The important thing is that I never pretend they are the same type of evidence.

---

### Checks

When I load the rebuilt calibration I expect the over matrix to have shape:

```text
(20, 6)
```

and the expanded batting-position matrix to have shape:

```text
(11, 6)
```

I expect five latent directions, a batter-style spread around `0.3475`, an era step of `0.0934` and extras around `0.0764` per legal ball.

For the design object I expect ten teams, squad roles:

```text
(7, 4, 7)
```

playing-XI roles:

```text
(5, 2, 4)
```

and three seasons.

These checks are intentionally simple. This file is mostly plumbing and explicit design, not another statistical estimation stage.

---

### Limits

The largest limitation is also the point of the `Design` class: these values are not uniquely implied by the IPL archive.

Another competent simulator designer could choose a different form process, a different amount of dew, a smaller transfer rate or a different home advantage and still produce a defensible artificial world.

That is acceptable for this task because the grader's true probabilities are generated under the same hidden design choices.

The task does not require this artificial world to be the one uniquely true model of real IPL cricket.

What I do require is that the choices are plausible, internally consistent and documented.

The second limitation is that two important aggregate validation targets are still missed by a few percent. The simulated first-innings spread is about `35.5` rather than the archive's `37.4`, and the simulated chase rate is about `53.1%` rather than `50.9%`.

I prefer documenting those misses to adding more arbitrary constants solely to make every validation number exact.

The model is supposed to be a credible synthetic world, not an overfitted reproduction of every historical aggregate.

---

### The main idea

I think of this file as the place where I make the provenance of every simulator constant explicit.

`Calibration` answers:

> **What did I measure from cricket?**

`Design` answers:

> **What did I choose when the data could not decide the world for me?**

Keeping those two questions separate makes the simulation much easier to inspect, validate and defend.

### References

Law, A. M. (2015). *Simulation Modeling and Analysis* (5th ed.). McGraw-Hill Education.

Sargent, R. G. (2013). *Verification and validation of simulation models*. **Journal of Simulation, 7**(1), 12–24.

Uhlenbeck, G. E., & Ornstein, L. S. (1930). *On the theory of the Brownian motion*. **Physical Review, 36**(5), 823–841.

Python Enhancement Proposal 557. *Data Classes*.

## 10. league/engine.py

### What I am trying to do

`league/engine.py` is where I turn the calibrated ball model into actual innings and matches.

The design goal is that the **true league and every forecaster use exactly the same match engine**.

The engine knows the public rules of cricket and the public structure of the statistical ball model. It does not know whether the hidden player and venue values it receives are the true ones generated by the league or estimates produced by a forecasting model.

That distinction is central to the fairness of the task.

The true league can call the engine with the real hidden values. A forecaster can call the same engine with its own estimated values. The simulation code does not branch on whether those values came from the truth or from an agent.

In other words, the engine sees:

```text id="sua6wj"
public model
+
SkillBook
+
fixture
```

and produces match probabilities.

It does not see:

```text id="pukjow"
"this SkillBook is true"
```

or:

```text id="dbx5e2"
"this SkillBook came from a forecaster"
```

That symmetry is how I encode the fairness claim into the architecture.

The agent should not have to reverse engineer how a delivery works. I give it the engine. Its job is to infer the hidden quantities that should be passed into that engine.

---

### The public data structures

Before the simulation classes, I define a few small dataclasses describing the public world.

`PlayerTable` stores public information about every player:

```python id="lzxlrb"
@dataclass
class PlayerTable:
    role: np.ndarray
    hand: np.ndarray
    style: np.ndarray
```

The arrays are indexed by player ID.

`role` tells the engine what broad role a player has. `hand` records whether the batter is right- or left-handed. `style` records the bowling style, represented numerically as pace or spin for players who bowl.

I define:

```python id="syiyvv"
PACE, SPIN = 0, 1
```

so these public categories can be used directly as table indices.

`VenueTable` does the same for grounds:

```python id="98h1f2"
@dataclass
class VenueTable:
    home_team: np.ndarray
    pitch: np.ndarray
```

Each venue therefore has a public home team and a public pitch category.

The pitch is encoded as neutral, pace-friendly or spin-friendly.

The important distinction is that these are **public facts about the world**. They are not hidden skills.

---

### Fixtures

A `Fixture` contains everything needed to describe one upcoming match:

```python id="79tmf5"
@dataclass
class Fixture:
    match: int
    season: int
    home: int
    away: int
    venue: int
    home_xi: np.ndarray
    home_bowlers: np.ndarray
    away_xi: np.ndarray
    away_bowlers: np.ndarray
```

So the engine knows the two teams, the venue, the batting elevens and which five players will bowl for each side.

I deliberately make the line-ups explicit.

The engine does not decide who plays or who bowls. Those decisions are already part of the fixture.

This removes another strategic decision from the simulation and keeps the forecasting problem focused on estimating the hidden cricket strengths rather than modelling captaincy.

---

### History

The `History` dataclass represents everything the forecasting agent is allowed to learn from the past.

It contains:

```text id="gs8x0b"
ball-by-ball history
match-level history
public player information
public venue information
past fixtures
number of seasons observed
```

The important idea is that the agent sees historical outcomes and public structure, but not the hidden numbers that generated them.

That means the forecasting problem is genuinely an inference problem.

The historical league contains clues about player strength, venue effects, form and other hidden variables, but the agent has to reconstruct those quantities from observations.

---

### Batting and bowling cards

The `BattingCard` and `BowlingCard` classes are small intermediate representations used by the innings simulator.

The innings simulator does not want to understand the entire `SkillBook`.

It only needs the hidden values relevant to one batting side facing one set of bowlers in one particular match.

The `BattingCard` stores:

```text id="jd1z98"
style
quality
conditions
```

for the eleven batters.

The `BowlingCard` stores:

```text id="1twl2f"
kind
quality
```

for the five bowlers.

The `SkillBook.cards()` method builds these cards before an innings begins.

This keeps the inner ball loop small. The expensive conceptual work of combining player identity, venue, handedness and pitch effects is handled before those quantities are repeatedly used on every delivery.

---

### `BallModel`: the public part of a delivery

`BallModel` contains the public statistical structure of a ball.

Its constructor receives the calibration object and extracts the five public directions:

```python id="eld3te"
self.bs = d["bat_style"]
self.bq = d["bat_quality"]
self.wt = d["bowl_type"]
self.wq = d["bowl_quality"]
self.c  = d["conditions"]
```

I use short names because these vectors appear repeatedly inside the inner innings loop.

The important point is that these directions themselves are public.

The engine openly tells the agent:

```text id="93h8v2"
this is the direction for batting style
this is the direction for batting quality
this is the direction for bowling type
this is the direction for bowling quality
this is the conditions direction
```

What remains hidden are the scalar values multiplying those directions.

So an agent is not asked to discover the mathematical form of the model. It only has to infer where players and venues sit inside that public model.

---

### Chase pressure

The `pressure()` method recreates the same chase-pressure variable that I fitted in `fit_state.py`.

It calculates the required scoring rate:

```python id="ohjdhb"
need = np.clip(
    target - runs,
    1,
    None
) / ((120 - ball) / 6)
```

and compares it with the par scoring rate expected from that over onward:

```python id="pmf8l3"
np.log(
    need / self.cal.par_rate[ball // 6]
)
```

The final pressure is clipped to:

```text id="ccwdcw"
[-1.0, 1.2]
```

just as it was during fitting.

This consistency matters.

I do not want to fit a model with one definition of pressure and then simulate matches with a slightly different definition.

The simulator uses the same feature definition that created the fitted coefficient.

So if the required rate becomes much harder than normal, pressure becomes positive and the public pressure vector pushes the outcome probabilities toward the aggressive pattern learned from real cricket.

---

### Building the public situation logits

The `situation()` method constructs the public part of the six ball logits.

It begins with the over profile:

```python id="55l2n6"
cal.over_logits[over]
```

then adds the batting-position effect:

```python id="k2cn9j"
cal.position_vectors[position]
```

then adds the wicket-state effect:

```python id="71c5a9"
np.multiply.outer(
    wickets - cal.typical_wickets[over],
    cal.wickets_vector
)
```

This means the model cares about wickets lost **relative to what is normal at that point in the innings**, exactly as it did during fitting.

It then adds the second-innings effect and chase-pressure effect:

```python id="bb3w6q"
np.multiply.outer(
    chasing,
    cal.second_innings_vector
)

np.multiply.outer(
    pressure,
    cal.pressure_vector
)
```

So the public ball state is approximately:

$$
z_{\text{public}}
=
z_{\text{over}}
+
z_{\text{position}}
+
z_{\text{wickets}}
+
z_{\text{innings}}
+
z_{\text{pressure}}
$$

This is the same basic multinomial-logit structure I fitted in File 5.

The simulation therefore uses the fitted model rather than replacing it with a separate hand-written scoring rule.

---

### Converting logits into probabilities

Once I have the six logits, I convert them to probabilities using softmax:

```python id="7kqyzp"
p = np.exp(
    z - z.max(axis=1, keepdims=True)
)

return p / p.sum(axis=1, keepdims=True)
```

I subtract the row maximum before exponentiating for numerical stability, just as I did during fitting.

The result is one six-outcome probability distribution for every simulated copy of the innings.

At this point I have:

```text id="ncx17l"
P(W)
P(0)
P(1)
P(2)
P(4)
P(6)
```

for the current delivery.

---

### `InningsSimulator`: simulating many innings together

`InningsSimulator` turns the ball model into an innings.

The important implementation choice is that I do not simulate one innings at a time.

I simulate many copies in parallel.

If:

```text id="iq17iz"
n = 4000
```

then every state array has roughly 4,000 entries.

For example:

```python id="4xlmp7"
wickets = np.zeros(n, int)
runs = np.zeros(n, int)
live = np.ones(n, bool)
```

Each entry represents one independent Monte Carlo copy of the same innings.

This means one pass through the ball loop updates thousands of hypothetical innings at once using NumPy operations.

That is much faster than running thousands of separate Python-level match loops.

---

### The innings state

At the start of every simulated innings I track:

```text id="xqt0fe"
striker
partner
next batter
wickets
runs
whether the innings is still live
```

The batting positions are represented as indices from `0` to `10`.

Initially:

```python id="b1f5yu"
striker = 0
partner = 1
next_in = 2
```

So the first two batters begin at the crease and the third player is next in.

Every simulated copy maintains its own striker, partner, wicket count and run total because different random outcomes cause the copies to diverge.

---

### One innings is at most 120 legal-ball steps

The main loop is:

```python id="yjwmue"
for ball in range(120):
```

So I simulate a maximum of 120 legal balls.

The current over is:

```python id="h02fy9"
over = ball // 6
```

The ball model therefore operates in legal-ball time.

Wides and no-balls are handled separately as extras rather than increasing the loop length.

This is a simplification of real cricket, but it lets the calibrated six-outcome model remain tied to legal deliveries.

---

### Bowler rotation

I use five bowlers and rotate them by over:

```python id="w81l9u"
who = over % 5
```

So the pattern is:

```text id="32qzo2"
over 1  -> bowler 0
over 2  -> bowler 1
over 3  -> bowler 2
over 4  -> bowler 3
over 5  -> bowler 4
over 6  -> bowler 0
...
```

This guarantees that no bowler bowls consecutive overs.

That is consistent with the Laws of Cricket, where the same bowler may not bowl two overs consecutively.

I deliberately do not simulate captaincy decisions about bowling changes.

The rotation is fixed because I want the match result to depend on player strengths and match randomness, not on a hidden tactical policy that the forecasting agent has no way to model exactly.

---

### Combining public state and hidden skill

This is the core calculation in the innings simulator.

I first compute the public situation:

```python id="7h0yd7"
z = m.situation(
    over,
    striker,
    wickets,
    np.full(n, chasing),
    pressure
)
```

Then I add the striker's hidden batting style:

```python id="elc4d0"
np.outer(
    batting.style[striker],
    m.bs
)
```

and the striker's quality against the current bowler:

```python id="iqr7uv"
np.outer(
    batting.quality[striker, who],
    m.bq
)
```

Then I add the bowler's hidden type:

```python id="fuewjs"
bowling.kind[who] * m.wt
```

and bowling quality:

```python id="zcaxif"
bowling.quality[who] * m.wq
```

Finally I add the shared and meeting-specific conditions:

```python id="6oxgag"
np.outer(
    conditions + batting.conditions[striker, who],
    m.c
)
```

So conceptually my ball model is:

$$
z
=
z_{\text{situation}}
+
s_{\text{bat}}d_{\text{bat-style}}
+
q_{\text{bat}}d_{\text{bat-quality}}
+
t_{\text{bowl}}d_{\text{bowl-type}}
+
q_{\text{bowl}}d_{\text{bowl-quality}}
+
c\,d_{\text{conditions}}
$$

This is the key architectural idea.

The mathematical structure is public.

The directions are public.

The hidden values multiplying those directions are what the forecasting agent has to estimate.

---

### Why I call the innings a Markov process

Once the hidden `SkillBook` is fixed, the next-ball probabilities depend on the current match state and the players involved.

The state contains information such as:

```text id="7msdgv"
runs
wickets
ball number
striker
partner
current bowler
target
```

I do not explicitly carry the whole sequence of previous deliveries into the next prediction.

The past matters only through the current scoreboard and current players.

That gives the innings a Markov structure.

Published cricket simulators use similar state-based constructions. Swartz, Gill and Muthukumarana (2009) model scoring probabilities using the current cricket state, and Davis, Perera and Swartz (2015) build a Twenty20 simulator in which delivery probabilities depend on batsman, bowler, innings resources and chase conditions.

My model is not identical to theirs, but it follows the same general principle: construct the innings as a sequence of state-dependent random deliveries.

---

### Sampling the ball outcome

Once I have the six probabilities, I need to draw one outcome.

I use one uniform random number per simulation copy:

```python id="6m7wza"
gen.random(n)
```

and compare it against the cumulative probability distribution:

```python id="v4u3yq"
kind = np.minimum(
    (
        gen.random(n)[:, None]
        > p.cumsum(axis=1)
    ).sum(axis=1),
    5
)
```

Conceptually, if the cumulative probabilities are:

```text id="qmb4jd"
0.05
0.33
0.73
0.80
0.93
1.00
```

and the random draw is:

```text id="dc7tfg"
0.76
```

then the outcome lands in the fourth interval.

This is the standard inversion method for sampling from a discrete distribution, described in texts such as Devroye (1986).

The `np.minimum(..., 5)` guard prevents a tiny floating-point rounding issue from ever creating an invalid seventh category.

---

### Extras

After the batter outcome, I independently draw an extra run:

```python id="z1kpgn"
extra = (
    gen.random(n) < m.cal.extras_per_ball
) & live
```

The probability comes directly from the measured extras rate.

This is deliberately simple.

I do not separately simulate:

```text id="3s18pz"
wide
no-ball
bye
leg bye
```

with different mechanisms.

Instead I preserve their average contribution to team scoring through one independent extra-run process.

That keeps the engine consistent with the calibration level at which extras were measured.

---

### Optional ball-by-ball logging

The `log` argument lets the simulator record copy `0` ball by ball:

```python id="yqv5hw"
if log is not None and live[0]:
    log.append(...)
```

I do not record every Monte Carlo copy.

That would be enormous and unnecessary.

The league only needs one realized historical world to expose to the forecasting agent.

So copy `0` can be logged and written into the historical dataset while the other copies are used internally for probability estimation.

This keeps the roles of simulation and history generation separate without needing two different engines.

---

### Updating runs and wickets

I identify dismissals with:

```python id="7s2b5b"
out = (kind == 0) & live
```

If the batter is not dismissed, the run value comes from:

```python id="99ly8m"
RUNS[kind]
```

I then add the independently drawn extra:

```python id="yf4u2k"
runs += scored + extra
```

and update wickets:

```python id="kht82y"
wickets += out
```

A dismissed striker is replaced by the next batter:

```python id="n3gtdw"
striker = np.where(
    out,
    next_in,
    striker
)

next_in = next_in + out
```

This vectorized logic means different Monte Carlo copies can have completely different batters at the crease by the same ball number.

---

### Changing strike

I swap striker and non-striker when the number of batter runs is odd or when the over ends:

```python id="1moddc"
swap = (
    scored % 2 == 1
) ^ (
    ball % 6 == 5
)
```

The XOR is important.

If one of those conditions occurs, the batters swap.

If both occur, they effectively swap twice and the same batter remains on strike.

That reproduces the normal strike logic for ordinary scored runs at the end of an over.

I then update both positions with:

```python id="3fq2gj"
striker, partner = (
    np.where(swap, partner, striker),
    np.where(swap, striker, partner)
)
```

The implementation is compact, but it encodes an actual cricket rule rather than just bookkeeping.

---

### Ending the innings

An innings stops when ten wickets have fallen:

```python id="rtyy8p"
live &= wickets < 10
```

For a chase, it also stops when the target has been reached:

```python id="ydv9op"
live &= runs < target
```

Copies that have finished remain inside the arrays but are marked inactive.

This is useful for vectorization because I do not need to dynamically remove finished simulations from the batch.

They simply stop accumulating runs or wickets.

---

### `SkillBook`: everything hidden

`SkillBook` is the container holding the quantities the forecasting agent does not directly observe.

It contains hidden information about players, venues and the league environment.

For players it includes batting style, batting quality, the batter's pace-versus-spin quality split, bowling type and bowling quality.

For venues it includes the hidden venue level and dew state.

It also contains batter-venue affinities.

At the league level it carries the home lift, season era level, day-to-day pitch spread and second-innings wear effect.

This is the core hidden state of the simulated world.

The true league owns one `SkillBook`.

A forecaster can construct another.

The engine accepts either.

That is the symmetry I want.

---

### Building match-specific cards

The `cards()` method takes:

```text id="zrf6lb"
one batting eleven
one team
five opposing bowlers
one venue
```

and turns the full `SkillBook` into the smaller objects required by the innings simulator.

I first read the batter handedness:

```python id="pn2r5i"
hand = self.players.hand[xi]
```

and the public bowling styles of the five bowlers:

```python id="cjg2re"
how = self.players.style[bowlers]
```

I then construct each batter's quality against each bowling style.

If the bowler is pace, I add half the batter's split. If the bowler is spin, I subtract half:

```python id="tknxsa"
sign = np.where(
    how == PACE,
    0.5,
    -0.5
)
```

so the quality matrix becomes:

```python id="z8xomj"
self.quality[xi][:, None]
+
self.split[xi][:, None] * sign[None, :]
```

This means one batter can be slightly better against pace than spin while another can have the opposite profile.

---

### Matchup conditions

The `meeting` matrix combines the condition-like effects that depend on the specific batter, bowler and venue.

It contains the batter's affinity for the venue, the home-team lift, the public handedness-versus-bowling-style table and the public pitch-versus-bowling-style table.

Conceptually:

$$
\text{meeting effect}
=
\text{venue affinity}
+
\text{home lift}
+
\text{hand/style effect}
-
\text{pitch help to bowler}
$$

All of these move along the common `conditions` direction inside the ball model.

The important thing is that the structure of these interactions is public.

The hidden quantities are things like the player's venue affinity or the true venue level.

---

### Why `pair_effect()` returns zero

`SkillBook` contains:

```python id="x7k2yb"
def pair_effect(self, xi, bowlers):
    return 0.0
```

This may look unnecessary, but I keep it deliberately.

The true simulated world contains **no specific batter-bowler pair effect** because the repeatability analysis in File 6 did not justify one.

But I want a forecaster that believes head-to-head records matter to have a clean place to implement that belief.

A forecasting subclass can override:

```text id="d94rgh"
pair_effect()
```

without rewriting the engine.

This is useful architecturally because alternative modelling hypotheses can differ in the `SkillBook` while sharing the same match simulation machinery.

---

### Shared innings conditions

The `shift()` method returns the condition component shared by every delivery in an innings:

```python id="g2evs2"
return (
    self.venue_level[venue]
    + self.era
    + (
        self.venue_dew[venue] - self.wear
        if chasing
        else 0.0
    )
)
```

So first innings conditions contain the venue level and current era.

Second innings conditions additionally contain dew minus wear.

This creates the intended competition between two effects.

The surface can become slightly harder later in the match because of wear, while dew can make batting easier at some venues.

The innings therefore shares one environmental shift while individual batter-bowler meetings can still contribute their own smaller condition adjustments.

---

### `MatchSimulator`: turning innings into win probabilities

`MatchSimulator` wraps the innings simulator and computes the probability that the home team wins.

I do not simulate one toss outcome and call that the probability.

I explicitly evaluate both batting orders:

```python id="0v1obm"
(home first, away second)
(away first, home second)
```

and assign each one weight `0.5`.

This corresponds to a fair toss where the toss winner always chooses to chase.

That design choice removes toss strategy from the world.

I know who bats first only through the coin flip, not through another hidden captain decision rule.

---

### Shared day conditions

For every Monte Carlo copy I draw:

```python id="fsdrs7"
day = gen.normal(
    0.0,
    book.day_sd,
    n
)
```

This is the match-day pitch condition.

The same `day` value is used for both innings of a given simulated copy.

That is important.

If one simulated match has an unusually good batting surface, both teams should play on that same surface.

I do not want the first innings to draw one pitch and the second innings to draw another unrelated pitch.

So each Monte Carlo copy represents one coherent match environment.

---

### Simulating the first innings

For the team batting first, I call:

```python id="5sspl7"
self.innings.play(
    *book.cards(...),
    book.shift(
        f.venue,
        False
    ) + day,
    n,
    gen
)
```

The innings receives the batting card, bowling card and the shared first-innings conditions.

The result is an array of `n` first-innings totals.

If `n = 4000`, I now have four thousand possible first-innings scores for that fixture under the current `SkillBook`.

---

### Simulating the chase

The second innings uses:

```python id="pi6ft3"
target = set_ + 1
```

for each Monte Carlo copy.

This means every simulated chase has its own target because every first innings had its own randomly generated score.

The chasing side is then simulated under:

```text id="zp0ogj"
venue level
+
era
+
dew
-
wear
+
day condition
```

with chase pressure changing dynamically as the innings develops.

This is important because I do not estimate win probability by simulating two independent innings totals and comparing them afterward.

The second innings actually knows the target.

Its batting behaviour changes because the required rate changes.

That is exactly what the pressure term was built to represent.

---

### Ties

I calculate:

```python id="1je9ax"
second_wins = (
    (chase > set_).mean()
    + 0.5 * (chase == set_).mean()
)
```

A tie contributes half a win.

I do not simulate a full Super Over process.

For win-probability purposes, treating a tie as a fair 50/50 resolution is much simpler and keeps the probability well defined.

---

### Monte Carlo win probability

For each batting order I estimate how often the second side wins, convert that into a home-team win probability and then average the two toss possibilities.

The final result is:

```text id="vmpzh9"
P(home team wins)
```

under the supplied `SkillBook`.

This is a Monte Carlo estimate.

The principle goes back to the classical Monte Carlo framework described by Metropolis and Ulam (1949): when direct analytical evaluation is difficult, repeatedly simulate the stochastic system and estimate the desired probability from the fraction of successful outcomes.

A cricket innings has too many interacting states for me to derive a useful closed-form match probability.

Simulation is much simpler and matches the structure of the problem directly.

---

### Monte Carlo error

If the true win probability is approximately `0.5`, the standard error of a simple Monte Carlo proportion is roughly:

$$
\sqrt{
\frac{p(1-p)}{n}
}
$$

At:

```text id="3ndyd7"
n = 4000
```

the worst-case standard error is approximately:

$$
\sqrt{
\frac{0.25}{4000}
}
\approx 0.0079
$$

or about:

```text id="ozhvzk"
0.008
```

At:

```text id="x2k3ek"
n = 100000
```

it falls to roughly:

$$
\sqrt{
\frac{0.25}{100000}
}
\approx 0.0016
$$

That is why a forecaster can use a few thousand copies for practical estimation while the hidden truth can be computed with a much larger simulation budget.

---

### `PublicConstants`

`PublicConstants` is the boundary between the private calibration and what the forecasting agent is allowed to receive.

It contains the public structure required to run the ball model:

```text id="i8jwt8"
over profiles
position responses
wicket response
pressure response
second-innings response
typical wickets
par rates
five directions
extras rate
```

It deliberately excludes quantities such as the player spreads, venue spread and real validation targets.

Those quantities help generate the hidden world.

Giving them directly to the agent would reveal information it is supposed to infer.

So `PublicConstants` strips the calibration down to the structural rules of the game.

---

### Producing the public model

`PublicConstants.from_calibration()` converts the full private calibration into the subset that can be written to:

```text id="gkd13n"
public.json
```

Then:

```python id="pmzngm"
load_public_model()
```

reads that file and constructs:

```python id="d125tk"
BallModel(
    PublicConstants(raw)
)
```

This is the copy of the engine that can ship with the forecasting task.

The agent therefore receives the exact same ball mechanics used by the true league.

What it does not receive are the hidden numbers plugged into those mechanics.

---

### Why the public/private boundary matters

This separation is the central fairness property of the task.

I do not want the challenge to be:

> Guess my simulator implementation.

I want the challenge to be:

> Given the public simulator and historical observations, infer the hidden state well enough to forecast new matches.

So I reveal the model structure and hide the latent quantities.

This is closer to a real statistical inference problem.

The agent knows the family of models that generated the data but does not know the parameter values.

That also makes failures more meaningful.

If a model performs badly, I can distinguish a failure to infer the hidden state from a failure caused by undocumented simulator mechanics.

---

### Why the toss winner always chases

In this world the toss is a fair coin flip and the winner always chooses to chase.

Real IPL captains do not literally make that decision one hundred percent of the time.

I simplify it because I do not want another decision model inside the simulation.

If toss winners sometimes bat and sometimes bowl, I need another policy describing when they choose each option.

That policy could itself depend on venue, pitch, opponent and season.

Then a forecasting agent would have to model that policy too.

I remove the problem entirely.

The toss determines batting order probabilistically, and the rule afterward is fixed.

---

### Why bowlers follow a fixed rotation

I make a similar simplification for bowling.

Real captains choose bowlers tactically.

Those choices depend on matchups, current score, wickets, bowler form and tactical judgement.

If I tried to reproduce that faithfully, captaincy would become another hidden agent inside the environment.

Instead, five bowlers rotate over by over.

This respects the important structural restriction that the same bowler cannot bowl consecutive overs while keeping the sequence deterministic once the line-up is known.

The engine therefore models bowling ability without also requiring a captain-policy model.

---

### What I deliberately leave out

The engine has no explicit fielding-skill model.

It has no partnership chemistry.

It has no momentum variable.

It has no psychological state.

It has no ball-to-ball memory beyond what survives in the current scoreboard and striker state.

I make these omissions deliberately.

Every extra hidden mechanism would make the world harder to identify, harder to calibrate and harder to explain.

The task needs enough structure to create meaningful inference, but it also needs a true probability that I can compute accurately and defend.

So I prefer a relatively compact stochastic world whose important assumptions are visible.

---

### Checks

I use several sanity checks on the engine.

When I evaluate ordinary situations in overs 1, 10 and 20 at typical wicket states, the resulting ball distributions should reproduce the broad shape measured in `explore_overs.py`.

Early overs should contain many dots. Middle overs should contain many singles. Death overs should contain far more sixes and wickets.

When I increase wickets lost relative to normal, the model should become more defensive in the same way the fitted wicket vector predicted.

When I increase chase pressure, the model should shift toward more attacking outcomes and greater wicket risk.

These checks tell me that the engine is actually using the fitted situation responses rather than merely containing the right constants on disk.

---

### Innings-level checks

When I simulate many innings with average players, I expect the mean score to land around:

```text id="qr81qd"
189.5
```

with a standard deviation around:

```text id="7dg0uf"
30.0
```

for the particular average-player test.

I also test a chase of approximately:

```text id="u2j0es"
170
```

where about:

```text id="h62c6a"
75.6%
```

of those test chases succeed.

These are not the final league-validation numbers because the full league contains player variation, venue variation, pitch variation and other hidden structure.

They are unit-level checks that the innings mechanism behaves sensibly.

---

### Match-level symmetry checks

A particularly useful test is to simulate two identical sides.

If all player and condition values are equal except for Monte Carlo randomness, I should get a win probability close to:

```text id="5h0mml"
0.5
```

The observed check is approximately:

```text id="kqonvf"
0.507
```

which is consistent with a coin flip within simulation noise.

This is important because it catches accidental asymmetry.

If identical sides systematically produced something like:

```text id="4n6154"
0.58
```

then I would know that home/away ordering, batting-order logic or innings handling was introducing an unintended bias.

I also deliberately exaggerate the home effect in a test.

When I multiply the ordinary home lift by ten, the home win probability rises to roughly:

```text id="wys7nc"
0.656
```

That tells me the home mechanism is connected to the match outcome in the expected direction.

---

### Bugs this file exposed

Two simple implementation bugs were caught immediately.

The first version omitted the `BattingCard` class.

That caused the module to fail as soon as the relevant code path was imported or used.

The second typo used:

```text id="rbh76w"
RUN
```

instead of:

```text id="ai9bgi"
RUNS
```

when scoring outcomes.

That failed on the first attempted innings.

These were easy failures because they produced immediate errors.

The more dangerous bugs in this project are the ones that still return plausible cricket numbers, which is why the statistical checks from the earlier files matter so much.

---

### The main limitation of the engine

The engine is intentionally simpler than real cricket.

The Markov assumption means that two match histories leading to the same scoreboard, striker and bowler state are treated as equivalent even if the routes to those states were very different.

Real players may respond to recent boundaries, recent wickets, fatigue, confidence or tactical patterns.

I ignore that memory.

I also simplify extras into an independent extra-run draw, simplify the toss policy, simplify bowling changes and omit fielding.

These choices bound what I can claim.

I am not claiming to have built a perfect generative model of professional T20 cricket.

I am building a calibrated stochastic world that preserves enough of the important cricket structure to create a difficult but inspectable forecasting problem.

---

### How I think about this file

I think of `engine.py` as the **shared physics engine of the task**.

The true world uses it.

The forecaster uses it.

The public statistical rules live inside it.

The hidden quantities are supplied separately through `SkillBook`.

That gives me the architecture:

```text id="ma7nh5"
                 PUBLIC
                   |
                   v
            BallModel / Engine
                   ^
                   |
        +----------+----------+
        |                     |
        |                     |
 true SkillBook        estimated SkillBook
        |                     |
        v                     v
 true probability       forecast probability
```

The engine is identical on both sides.

Only the hidden values differ.

That is the central idea:

> **I make the mechanics of cricket public and shared. The forecasting problem is to infer the hidden player, venue and condition values well enough that the same engine produces the correct win probability.**

### References

Swartz, T. B., Gill, P. S., & Muthukumarana, S. (2009). *Modelling and simulation for one-day cricket*. **Canadian Journal of Statistics, 37**(2), 143–160.

Davis, J., Perera, H., & Swartz, T. B. (2015). *A simulator for Twenty20 cricket*. **Australian & New Zealand Journal of Statistics, 57**(1), 55–71.

Devroye, L. (1986). *Non-Uniform Random Variate Generation*. Springer-Verlag.

Metropolis, N., & Ulam, S. (1949). *The Monte Carlo method*. **Journal of the American Statistical Association, 44**(247), 335–341.

Marylebone Cricket Club. *Laws of Cricket*, 2017 Code, 3rd edition. Law 17.6 concerning bowlers changing ends and consecutive overs.

## 11. league/world.py

### What I am trying to do

`league/world.py` is where I stop describing the rules of cricket and actually create an artificial league that I own completely.

The earlier files gave me the calibrated structure of a ball, the hidden dimensions along which players and conditions vary, and the engine that turns those numbers into innings and matches. This file uses those pieces to generate one complete synthetic world: invented players, invented grounds, hidden player skills, hidden venue characteristics, three seasons of visible history and a set of future fixtures whose true win probabilities I can calculate.

The most important boundary in this file is between **public history** and **hidden truth**.

The forecasting agent is allowed to see things such as player identities, handedness, bowling style, team membership, venues, line-ups, match results and every historical delivery. Those facts eventually go into the `History` object.

The agent is not allowed to see the actual hidden style, quality, form, venue level, dew, venue affinity or other latent values that generated those observations.

Those values remain inside the `League`.

The only controlled way to use them for grading is through `TruthEngine`.

So the architecture I am trying to create is:

```text
hidden synthetic world
        |
        v
league/world.py
        |
        +----------------------+
        |                      |
        v                      v
visible History          hidden SkillBook
        |                      |
        v                      v
forecasting agent          TruthEngine
```

The agent sees the consequences of the hidden world, not the hidden world itself.

---

### One random stream defines one world

The constructor begins with:

```python
self.rng = np.random.default_rng(seed)
```

I deliberately use one NumPy random generator for the entire league.

That same random stream drives the creation of players, player skills, handedness, bowling type, venue characteristics, form evolution, transfers, line-ups, fixture order, tosses, pitch conditions and every ball of historical cricket.

The practical consequence is very important:

> **A seed defines a complete world.**

If I start with the same seed, the same calibration and the same design constants, the same sequence of random numbers is consumed in the same order and I regenerate the same synthetic universe.

For example:

```python
League(101)
```

does not merely mean "create roughly the same kind of league."

It identifies one particular stochastic realization of that league recipe.

This makes exact regression testing possible. If I rebuild the same world with the same inputs and suddenly obtain a different historical ball table, I know that something in the generation pipeline has changed.

It also lets me create several independent task worlds by changing only the seed. The statistical recipe remains fixed while the realized players, venues and match histories differ.

---

### Building the player population

The first large step is `_build_players()`.

Every team starts with the same squad structure defined in `Design`.

The squad contains:

```text
7 batters
4 all-rounders
7 bowlers
```

which gives:

```text
18 players per team
```

and with ten teams:

```text
180 players
```

in the league.

The code constructs those roles with:

```python
squad = np.repeat(
    [BATTER, ALLROUNDER, BOWLER],
    d.squad_roles
)
```

and then repeats the same squad template for every team.

This gives me a controlled league structure where all teams start with the same number of players in each role.

The identities and abilities differ, but squad composition itself does not become another source of accidental imbalance.

---

### Public player characteristics

Some player properties are public.

I generate handedness with:

```python
rng.random(n) < d.left_handed
```

using the share defined in `Design`.

I also generate whether a player bowls pace or spin.

All-rounders are assigned a spin probability of approximately:

```text
0.5
```

while the other bowling-capable roles use approximately:

```text
0.4
```

in this implementation.

These public attributes are stored in:

```python
PlayerTable
```

and eventually become visible to the forecasting agent.

That distinction matters.

The agent is allowed to know that a bowler is a spinner.

It is not allowed to directly know the exact hidden coordinate describing where that bowler lies along the measured bowling-type direction.

The public categorical label therefore gives useful information, but it does not reveal the full hidden state.

---

### Initial team membership

I assign the initial squads with:

```python
self.team_of = np.repeat(
    np.arange(d.teams),
    len(squad)
)
```

So the first eighteen players belong to team 0, the next eighteen to team 1 and so on.

This is only the initial assignment.

Later, the transfer process changes team membership between seasons while preserving the role structure of every squad.

That distinction is useful because player identity and team identity do not remain permanently attached.

---

### Hidden batting style

The first hidden player quantity I generate is batting style:

```python
self.style = rng.normal(
    0,
    sd["bat_style"],
    n
)
```

The standard deviation comes directly from the measured spread in the calibration.

So I am not inventing how much batters differ in style at this stage.

File 5 measured that spread from real player residuals, and File 7 converted it into simulator-ready units.

Here I simply draw a synthetic population from that measured distribution.

This hidden style value is permanent.

Unlike form, it does not drift from week to week.

Conceptually I am treating it as a persistent characteristic of how the batter plays rather than temporary performance.

---

### Hidden bowling type

Bowling type is slightly more complicated because I want the public pace-versus-spin label to explain part, but not all, of the measured bowling-style variation.

I first calculate the remaining within-group spread:

```python
within = np.sqrt(
    max(
        sd["bowl_type"] ** 2
        - (d.type_gap / 2) ** 2,
        1e-6
    )
)
```

Then I create:

```python
self.kind = (
    public_style_component
    + hidden_personal_component
)
```

A spinner receives one side of the public gap and a pace bowler the other:

```python
np.where(
    self.players.style == SPIN,
    0.5,
    -0.5
) * d.type_gap
```

and I add a player-specific normal draw around that group mean.

So two spinners are not identical.

Likewise, pace and spin explain only part of the measured first bowling direction.

This is deliberate.

The archive gave me a continuous direction. My public pace-versus-spin category provides some information about it, but the agent still has to infer individual differences from history.

---

### Talent plus form

The two quality variables are handled differently from style.

For batting quality and bowling quality, I split the total measured population variance into:

```text
fixed talent
+
temporary form
```

I first keep the measured total spreads:

```python
self.spread = {
    "quality": sd["bat_quality"],
    "bowl_quality": sd["bowl_quality"]
}
```

Then I generate fixed talent with:

```python
v * np.sqrt(d.talent_share)
```

as its standard deviation, and temporary form with:

```python
v * np.sqrt(1 - d.talent_share)
```

as its standard deviation.

This works because variances add.

If the total desired variance is:

$$
\sigma^2
$$

and I allocate a fraction $a$ to talent, then:

$$
\sigma^2_{\text{talent}}
=
a\sigma^2
$$

and:

$$
\sigma^2_{\text{form}}
=
(1-a)\sigma^2
$$

so their standard deviations are:

$$
\sigma\sqrt{a}
$$

and:

$$
\sigma\sqrt{1-a}
$$

respectively.

When I later add talent and form together, the total cross-sectional variance remains approximately the measured player variance.

This lets a player have a persistent ability while still moving above and below that long-run level over time.

---

### Pace-versus-spin batting split

I also give every batter a small hidden pace-versus-spin quality difference:

```python
self.split = rng.normal(
    0,
    d.split_sd,
    n
)
```

A positive value means the player's quality is shifted somewhat toward one bowling type, while a negative value shifts it toward the other.

This does not create a unique parameter for every batter-bowler pair.

That would contradict the weak head-to-head repeatability measured earlier.

Instead I use one broad matchup dimension per batter.

That creates real exploitable structure without introducing thousands of pair-specific hidden variables.

---

### Building grounds

The `_build_venues()` method creates one venue per team.

Each venue has a public pitch category:

```python
rng.integers(0, 3, d.teams)
```

which corresponds to the public categories used by the engine:

```text
neutral
pace-friendly
spin-friendly
```

The home team and pitch type are visible.

The actual venue scoring level is hidden.

That hidden level is drawn using the venue spread measured in File 6.

The calibration expresses that spread in runs per ball, while the engine applies environment effects as movement along the `conditions` direction.

So I convert using:

```python
self.cal.runs_per_condition_unit
```

and draw:

```python
self.venue_level = rng.normal(
    0,
    self.cal.venue_sd_runs / per,
    d.teams
)
```

This is an important unit conversion.

The statistical analysis measured:

```text
runs per ball
```

while the engine wants:

```text
units along the conditions vector
```

`runs_per_condition_unit` is the bridge between them.

---

### Hidden dew

Some venues also receive a hidden dew effect.

I first decide whether the venue experiences the simulated dew condition:

```python
rng.random(d.teams) < d.dew_share
```

and, if it does, assign:

```python
d.dew_runs / per
```

in engine units.

The agent can observe historical second-innings behaviour at that ground and potentially infer that something systematic is happening, but it is never directly told:

```text
venue 4 has dew = X
```

That is exactly the kind of hidden recurring structure the forecasting problem is intended to expose.

---

### Batter-venue affinity

I also generate a hidden affinity between every batter and every venue:

```python
self.affinity = rng.normal(
    0,
    self.cal.batter_venue_sd_runs
    * np.sqrt(d.affinity_share)
    / per,
    (len(self.team_of), d.teams)
)
```

So each player has a small personal tendency to perform better or worse at each ground.

Again, the scale comes from the measured batter-at-venue variation, while `affinity_share` determines how much of that measured spread I assign to genuine personal affinity.

This produces a large hidden matrix, but each individual effect is intentionally small.

The agent can only learn these values indirectly from repeated player-ground observations.

---

### Constructing the true `SkillBook`

The `skillbook()` method packages the current hidden state into the object consumed by `engine.py`.

For each drifting quality variable I calculate:

```python
now = {
    k: self.talent[k] + self.form[k]
    for k in self.spread
}
```

So the current batting and bowling qualities are the sum of permanent talent and current form.

The returned `SkillBook` contains the public player and venue tables, hidden batting style, current batting quality, the pace-spin split, hidden bowling type, current bowling quality, the small public-structure interaction tables, venue level, dew, venue affinity, home advantage, era, day variation and wear.

This is the true hidden state of the league at that moment.

The important thing is that the engine does not know how these values were created.

It simply consumes the `SkillBook`.

That keeps world generation and match mechanics separate.

---

### Converting cricket units into engine units

Several `Design` values are written in runs per ball because that is the easiest scale for me to reason about.

Examples include:

```text
home_runs
day_sd_runs
wear_runs
dew_runs
pitch interaction values
handedness interaction values
```

But `BallModel` does not directly add runs per ball.

It moves logits along the calibrated `conditions` direction.

So inside `skillbook()` I divide those quantities by:

```python
self.cal.runs_per_condition_unit
```

before passing them to the engine.

That lets me write the design in understandable cricket language while still keeping the internal model mathematically consistent.

---

### The era level

The current season also contributes an environment shift.

The code uses:

```python
self.cal.era_step
* (
    self.season
    - (d.seasons - 1) / 2
)
```

which centres the three simulated seasons around zero.

With three seasons, the offsets are approximately:

```text
season 0 -> -1 era step
season 1 ->  0
season 2 -> +1 era step
```

I then add:

```python
d.level_runs / per
```

to recenter the overall scoring environment.

So the synthetic league inherits the measured historical drift while remaining centred around the scoring level I calibrated.

---

### How form evolves

The `_drift()` method updates temporary form.

I use:

```python
keep = np.exp(
    -weeks
    / (
        self.d.form_memory_years * 52
    )
)
```

This is the exact exponential decay associated with an Ornstein-Uhlenbeck-style mean-reverting process.

If $F_t$ is current form, I conceptually update it as:

$$
F_{t+\Delta}
=
\kappa F_t
+
\epsilon
$$

where:

$$
\kappa
=
e^{-\Delta/\tau}
$$

and $\tau$ is the memory timescale.

A short gap gives $\kappa$ close to one, so most form survives.

A long gap gives a smaller $\kappa$, so old form becomes less informative.

Uhlenbeck and Ornstein (1930) introduced the mean-reverting stochastic process underlying this construction.

---

### Keeping the form variance stationary

If I only multiplied old form by `keep`, form would gradually collapse toward zero.

I therefore add fresh noise.

The new noise has standard deviation:

```python
sd * np.sqrt(
    (1 - talent_share)
    * (1 - keep ** 2)
)
```

so that:

$$
\operatorname{Var}(F_{t+\Delta})
=
\kappa^2\sigma_F^2
+
(1-\kappa^2)\sigma_F^2
=
\sigma_F^2
$$

The total form variance therefore remains constant over time.

This is what makes the process stationary.

Players move around their permanent talent levels, but the population does not gradually become more or less variable simply because time has passed.

---

### Why I use a dynamic form model

Without drifting form, a player's hidden quality would be completely fixed.

Then historical performance from season 1 would remain just as informative for a season 4 forecast as performance from the previous week.

That is not the world I want.

I want old history to retain information because talent is persistent, but I also want recent history to matter more because temporary form changes.

This is closely related to dynamic sports-rating models. Glickman (1999), for example, treats latent player strength as something that changes through time rather than as one permanently fixed parameter.

The exact model here is my own simplified construction, but the statistical idea is the same: ability is latent, observed indirectly and allowed to evolve.

---

### Weekly drift during a season

The league schedule is spread across eight weeks.

I calculate:

```python
per_week = int(
    np.ceil(
        len(pairs)
        / self.d.weeks_per_season
    )
)
```

and after each block of matches corresponding to roughly one week I call:

```python
self._drift(1)
```

So form does not remain frozen through the entire season.

A player can begin the season in one form state and slowly move over the following weeks.

That gives chronological history meaning.

Performance in the most recent matches can carry more information about current form than performance many months earlier.

---

### Off-season drift

Between seasons I call:

```python
self._drift(
    52 - self.d.weeks_per_season
)
```

before transfers occur.

Since the playing season occupies eight weeks in this simplified league, the remaining forty-four weeks form the off-season.

That long interval causes much more temporary form to decay.

Persistent talent remains unchanged, but a substantial part of temporary form is replaced by new noise.

This is important because the agent should not be able to carry the final observed performance of one season perfectly into the next.

---

### The final unseen off-season

After the third historical season finishes, I drift form **one more time**:

```python
self._drift(
    52 - self.d.weeks_per_season
)
```

and then perform another transfer step.

This is one of the most important pieces of uncertainty in the forecasting task.

The history ends before this final off-season state is observed.

So when the agent receives next-season fixtures, every player's current hidden quality contains a component that no historical record can reveal exactly.

Even a perfect estimator of the previous season's state cannot know the fresh random form innovation.

That means the true probabilities remain genuinely probabilistic rather than becoming deterministic if an agent reconstructs enough history.

---

### Transfers between seasons

The `_transfers()` method changes team membership after each season.

I do not move players arbitrarily across roles.

For each role separately I create a pool and select:

```python
int(
    len(pool)
    * self.d.transfer_share
)
```

players to move.

I then permute the team assignments among those movers.

Because swaps remain inside the same role, every team keeps the same squad shape.

A team does not suddenly end up with fifteen bowlers and no batters.

The statistical purpose of transfers is more important than the realism of the transfer mechanism itself.

If players stayed with the same team forever, team identity would become a strong proxy for the hidden player strengths.

A team-only forecasting model could then absorb a large amount of player information without actually learning players.

Transfers deliberately weaken that shortcut.

When a strong player changes teams, information about that player's ability should move with the player rather than remain attached to his old team.

---

### Choosing the playing eleven

Every match receives a fresh line-up.

For the current team I identify its full squad and then sample the required number of players from each role:

```python
self.d.xi_roles
```

which corresponds to:

```text
5 batters
2 all-rounders
4 bowlers
```

I concatenate those players to form the eleven.

The five bowling options are:

```text
4 specialist bowlers
+
1 all-rounder
```

The selected all-rounder is the first of the two chosen all-rounders.

The line-up is therefore stochastic even when the squad is fixed.

This creates another source of public variation that the agent must account for when forecasting a fixture.

Two matches between the same teams need not involve exactly the same players.

---

### Fixtures

The `_fixture()` method selects fresh elevens for the home and away side and returns a `Fixture`.

The venue is simply the home team's ground:

```python
venue = home
```

because the world contains one home venue per team.

This keeps the home/venue relationship straightforward.

The fixture therefore bundles the public information needed to play the match while the hidden abilities remain inside the current `SkillBook`.

---

### Building the historical seasons

`play_history()` creates the visible past that the forecasting agent will eventually receive.

I generate three seasons.

At the beginning of each later season, I first drift form through the off-season and apply transfers.

Then I create a double round robin:

```python
pairs = [
    (h, a)
    for h in range(self.d.teams)
    for a in range(self.d.teams)
    if h != a
]
```

With ten teams this produces:

$$
10\times9=90
$$

ordered home-away fixtures.

Every pair of teams therefore meets twice overall: once with each side at home.

I randomize the order of those ninety matches and spread them across the configured eight-week season.

---

### Why I use a double round robin

The real IPL format is more complicated.

The modern competition has ten teams but does not use a simple full home-and-away round robin for every pair before the playoffs.

I deliberately use a double round robin because it creates a cleaner statistical environment.

Every pairing receives two meetings per season.

That gives the agent more balanced historical evidence and removes schedule asymmetry as a major modelling problem.

It also gives more observations for player and venue inference while keeping the league small enough to simulate repeatedly.

So the schedule is inspired by cricket but designed for this forecasting task.

---

### Playing one historical match

For each scheduled pair I create a fixture and then freeze the current hidden world:

```python
book = self.skillbook()
```

That `SkillBook` represents the current player form, venue state and league conditions at that week.

I then draw the toss:

```python
toss = (
    fx.home
    if self.rng.random() < 0.5
    else fx.away
)
```

The toss winner always chases, following the simplification already encoded in the engine.

I therefore set the batting order from the toss result.

---

### One shared pitch for the match

Before playing the innings I draw:

```python
day = self.rng.normal(
    0.0,
    book.day_sd
)
```

This is the hidden pitch-on-the-day effect.

The same value is used for both innings.

That means a particularly good batting pitch benefits both teams in the same simulated match.

I do not independently redraw the surface between innings.

This is important for coherence: one match should happen in one environment.

---

### Playing history with one real copy

For historical matches I call the innings simulator with:

```text
n = 1
```

I am not estimating probabilities here.

I am creating one realized history.

That means each historical match contains one toss, one pitch draw and one random sequence of ball outcomes, exactly as a real observed match gives us one realization of an underlying probability process.

The true win probability may have been 70%, but history only shows whether the team happened to win this particular realization.

This is the same distinction that motivated the `ExactScorer` at the beginning of the project.

---

### Logging every delivery

For each innings I create:

```python
log = []
```

and pass it to the engine.

The engine records each ball with information about the batter, bowler, outcome, extras, wickets and runs before the delivery.

I then turn those logs into rows containing:

```text
season
match
innings
over
ball
batting team
bowling team
venue
batter
bowler
outcome
extra
batting position
wickets before
runs before
target
```

This becomes the detailed history available to the agent.

The hidden skill numbers do not appear in these rows.

The agent sees only their consequences.

---

### Match-level history

I also record one row per match containing:

```text
season
match
week
home team
away team
venue
toss winner
team batting first
first-innings total
second-innings total
winner
```

So the eventual `History` object contains both a granular ball table and a compact match table.

This lets a forecasting system choose its own level of modelling.

A simple approach could operate only on match results.

A stronger one could reconstruct player-level and state-level information from the full ball history.

---

### Tied historical matches

If the two innings totals are equal, I resolve the historical match with a coin flip:

```python
winner = (
    first
    if self.rng.random() < 0.5
    else second
)
```

I do not simulate a Super Over.

Again, this is a deliberate simplification.

The historical winner must be defined, but I do not want another miniature match mechanism solely for rare tied games.

---

### The final `History`

After all three seasons are complete, I build the two pandas DataFrames and return:

```python
History(
    balls,
    matches,
    players,
    venues,
    played,
    seasons
)
```

This is the public historical product of the synthetic world.

It contains everything an agent is supposed to know about the past.

The real hidden skills never appear inside it.

That separation is one of the strongest invariants in the repository.

---

### Drawing the future fixtures

After history has been played and the final unseen off-season has occurred, I can call:

```python
draw_fixtures(count)
```

to sample next-season matchups.

The possible pairs are the same ordered home-away team combinations used during history.

I randomize the list, take the requested number and assign match IDs beginning at:

```text
10000
```

This keeps forecast fixtures clearly separate from historical match IDs.

Each future fixture also receives fresh elevens.

So the forecasting agent knows the actual players selected for the upcoming match rather than having to predict team selection.

The remaining problem is estimating how good those players and conditions currently are.

---

### `TruthEngine`

`TruthEngine` is the only class intended to convert the hidden world into true fixture probabilities.

Its constructor stores:

```text
league
number of copies
chunk size
```

and `probabilities()` first obtains:

```python
book = self.league.skillbook()
```

This is the true current hidden state after the final off-season drift and transfers.

The forecasting agent never receives this object.

`TruthEngine` does.

That is the security boundary.

---

### Computing the true probability

For every future fixture I repeatedly call the same public `MatchSimulator` used everywhere else, but I give it the **true SkillBook**.

If the truth budget is:

```text
100000 copies
```

then conceptually I simulate that fixture one hundred thousand times under the true latent state and calculate how often the home team wins.

This gives the simulator-defined true probability:

$$
p_{\text{true}}
=
P(\text{home wins}\mid\text{true hidden world})
$$

That is the probability used by `ExactScorer`.

So the grading target is not the winner of one future simulated match.

It is the Monte Carlo approximation to the actual win probability implied by the hidden world.

---

### Chunking the truth computation

Large Monte Carlo batches use memory.

`TruthEngine` therefore divides the requested number of copies into chunks.

It calculates the number of parts:

```python
parts = max(
    1,
    int(
        np.ceil(
            self.copies / self.chunk
        )
    )
)
```

and then chooses a chunk size.

Each part independently estimates the fixture probability.

I finally average those chunk estimates.

This keeps memory bounded without changing the underlying Monte Carlo target.

---

### Deterministic truth seeds

The truth simulation does not consume the league's main random generator.

Instead, each fixture and chunk gets a deterministic generator:

```python
np.random.default_rng(
    [900_000 + fx.match, part]
)
```

This is a very useful separation.

The truth probability for a fixture is determined by:

```text
fixture ID
+
chunk number
+
hidden SkillBook
```

rather than by whatever random operations happened to occur immediately before grading.

That makes truth computation reproducible.

If I compute the same fixture probability twice with the same hidden state and configuration, I obtain the same Monte Carlo estimate.

It also means truth computation does not mutate the state of the league's historical random stream.

---

### Why `TruthEngine` is the only door to the hidden world

I want the rest of the repository to interact with hidden truth through a very narrow interface.

The agent can receive:

```text
History
future Fixtures
public engine
public constants
```

but it should not be handed:

```text
talent arrays
form arrays
venue levels
dew values
venue affinities
current true SkillBook
```

`TruthEngine` keeps those details behind one operation:

```text
fixtures
    ->
true win probabilities
```

That is exactly what the grader needs and nothing more.

A narrow interface makes accidental information leakage easier to inspect.

---

### Why the final off-season matters for task difficulty

The final off-season creates an important irreducible gap between history and truth.

At the end of the visible third season, the agent can estimate player talent and the form that existed at that time.

Then I apply another long form drift before the forecast fixtures.

Part of old form survives.

Part disappears.

Fresh form noise is introduced.

The agent knows the statistical process but not the fresh random innovation.

So even an ideal forecaster cannot know the current SkillBook exactly from history.

It can only form a posterior estimate.

That is useful because otherwise enough historical data could eventually reveal the entire hidden world and turn the forecasting problem into near-deterministic parameter recovery.

---

### Reproducibility check

One of the strongest checks for this file uses:

```python
League(101)
```

with the original calibration and design constants.

The expected historical world contains:

```text
270 matches
62,972 logged balls
```

with a first-innings mean around:

```text
192.11
```

and, most importantly, the resulting visible ball table matches the previously piloted world row for row.

That is a much stronger check than saying the averages are similar.

It means the sequence of realized events is identical.

The same players are created, the same matches are scheduled, the same tosses occur and the same ball outcomes are drawn.

That verifies the entire random-consumption path.

---

### Why the rebuilt calibration changes a few outcomes

With the calibration rebuilt by this repository rather than the exact original calibration file, seed `101` still produces approximately:

```text
62,972 balls
```

and a first-innings mean around:

```text
192.12
```

but a few outcomes can differ.

The reason is that simulation is path dependent.

Suppose one probability differs only in the fourth decimal:

```text
old P(six) = 0.0812
new P(six) = 0.0816
```

Most random draws will produce exactly the same outcome under both distributions.

But eventually a uniform random number may land inside the tiny interval where the two cumulative distributions disagree.

At that ball, one world may produce a six while the other produces something else.

Once the score changes, chase pressure can change.

The striker may change.

A wicket may occur at a different time.

The two innings can then follow different trajectories even though the original numerical difference was microscopic.

This is a useful demonstration of an important property of stochastic simulation:

> **Fixed seeds give exact reproducibility only when the entire model and random-consumption path are also fixed.**

---

### Why the piloted task keeps its original constants

Because of that sensitivity, reproducing calibration values to four decimal places is not sufficient if I want the exact historical world used in an earlier pilot.

A tiny parameter difference can eventually flip one random categorical draw and cause the future trajectory to diverge.

So if the objective is to reproduce the piloted task byte for byte, the task needs the exact calibration artifact used when that world was generated.

The rebuilt calibration is useful for demonstrating that the statistical pipeline reproduces the same model.

It is not automatically interchangeable with the original artifact for exact seeded replay.

That is why I separate **reproducibility of the method** from **identity of a particular generated world**.

---

### Scale of the historical world

With ten teams and a double round robin, every season contains:

$$
10\times9=90
$$

matches.

Across three seasons:

$$
90\times3=270
$$

matches are visible.

Those matches produce roughly:

```text
63,000 ball records
```

depending on how often innings finish early.

That is large enough to contain substantial evidence about players, teams and venues, but still small enough that noise remains important.

This balance is deliberate.

If I generated millions of matches, the hidden parameters would become too easy to estimate.

If I generated only a handful, almost no player signal would be learnable.

---

### How I think about the full information flow

At this point the architecture becomes:

```text
Calibration + Design + Seed
            |
            v
       league/world.py
            |
            v
    hidden synthetic world
            |
      +-----+------+
      |            |
      v            v
 visible past    hidden state
   History       SkillBook
      |            |
      v            v
 forecaster     TruthEngine
      |            |
      v            v
 estimated p     true p
      \            /
       \          /
        v        v
        ExactScorer
```

The same world creates both sides of the evaluation.

Historical observations come from the hidden state.

Future truth comes from the same hidden state after time has moved forward.

The forecaster sees the first and tries to infer the second.

---

### What I deliberately simplify

This synthetic league does not include playoffs.

It does not include rain interruptions or revised targets.

There are no injuries.

There is no economic transfer market.

Transfers are random.

Captaincy is not modelled.

The toss winner always chases.

Bowling rotations are fixed by the engine.

I make these simplifications deliberately.

The objective is not to reproduce every institution of the IPL.

The objective is to create a statistically grounded forecasting world in which the hidden truth is controllable, the public evidence is rich and the resulting probabilities can be calculated exactly enough for grading.

These simplifications therefore limit what the simulator can claim about real cricket, but they do not undermine the internal forecasting task.

The forecaster and the truth engine operate under exactly the same rules.

---

### The main idea

I think of `world.py` as the **world generator and keeper of truth**.

`engine.py` defines how cricket works.

`calibration.py` defines the measured constants and the chosen design.

`world.py` samples one concrete universe from those rules.

It creates the players, decides their hidden abilities, moves form through time, creates venues, schedules matches, generates the public history and then keeps the final hidden state private.

The agent gets the evidence.

`TruthEngine` gets the truth.

The central principle is:

> **I generate one fully specified hidden cricket world, reveal only its historical consequences, and grade forecasts against future probabilities computed from that same hidden world.**

### References

Uhlenbeck, G. E., & Ornstein, L. S. (1930). *On the theory of the Brownian motion*. **Physical Review, 36**(5), 823–841.

Glickman, M. E. (1999). *Parameter estimation in large dynamic paired comparison experiments*. **Journal of the Royal Statistical Society: Series C (Applied Statistics), 48**(3), 377–394.

## 12. league/league_io.py

### What I am trying to do

`league/league_io.py` defines the one public representation through which every part of the task sees a generated world.

By the time I reach this file, `world.py` already knows how to generate players, venues, match history and future fixtures. The problem now is how to package that information so that the task builder, reference forecasters, grader and forecasting agent all read exactly the same representation.

I do not want one part of the repository reading Python objects directly while another reconstructs its own interpretation of CSV files. That would create unnecessary opportunities for mismatches.

Instead, I define one explicit serialization boundary.

`save_league()` takes the generated `History` and future `Fixture` objects and writes the public task files.

`load_league()` reads those files back and reconstructs the same types of objects that the engine and reference forecasters expect.

So conceptually I want:

```text
generated world
      |
      v
 save_league()
      |
      v
public task files
      |
      v
 load_league()
      |
      v
History + Fixtures
```

Every consumer of the task therefore sees the world through the same interface.

Most importantly, nothing hidden crosses this boundary.

I write player roles, handedness, bowling style, venue type, historical balls, historical matches, line-ups and future fixtures.

I do **not** write hidden batting quality, hidden form, hidden bowling quality, venue level, dew, player-ground affinity or true fixture probabilities.

So this file is also an information-security boundary between:

```text
public evidence
```

and:

```text
hidden simulation truth
```

---

### Why I need a serialization layer at all

Inside Python, the league is represented using objects such as:

```text
History
Fixture
PlayerTable
VenueTable
```

Those are convenient for the simulator, but they are not a good distribution format for a task.

The agent needs files that are easy to inspect, easy to parse and independent of the internal state of a particular Python process.

I therefore convert the public world into seven CSV files and one JSON metadata file.

When the task is later loaded, I reconstruct the Python objects from those files.

That means the files are not merely an export for human inspection.

They are the actual public API of a generated league.

---

### Supporting two package layouts

At the top of the file I use:

```python
try:
    from league.engine import Fixture, History, PlayerTable, VenueTable
except ImportError:
    from engine.model import Fixture, History, PlayerTable, VenueTable
```

This is deliberate.

Inside the development repository, these classes live under:

```text
league.engine
```

but when the task is packaged for the agent, the same I/O file can live under a different package layout where those types are imported from:

```text
engine.model
```

I want the same source file to work in both places.

The fallback keeps the serialization logic identical between the development environment and the packaged task instead of maintaining two slightly different copies.

That matters because even a small difference between the builder's loader and the agent's loader could create a fairness problem.

---

### Turning line-ups into rows

The helper:

```python
_lineup_rows()
```

converts fixture line-ups into a flat table.

A `Fixture` contains arrays such as:

```text
home_xi
home_bowlers
away_xi
away_bowlers
```

which are convenient in Python but awkward to store directly in CSV.

I instead write one row per player per match.

Each row records:

```text
match or fixture ID
team
batting slot
player ID
bowling slot
```

The batting slot runs from:

```text
0 to 10
```

because there are eleven players in the batting order.

The bowling slot runs from:

```text
0 to 4
```

for the five players who bowl.

Players who do not bowl receive:

```text
-1
```

as their bowling slot.

The code first builds a mapping from player ID to bowling position:

```python
slot = {
    int(p): i
    for i, p in enumerate(five)
}
```

Then, as I enumerate the batting eleven, I can write both the player's batting position and whether that same player belongs to the five-person bowling rotation.

This representation lets me reconstruct both arrays later without storing complicated nested structures inside the CSV.

---

### `save_league()`

The main write function is:

```python
save_league(folder, history, fixtures)
```

Its job is to take the public products created by `world.py` and turn them into the files delivered with the task.

I first create the destination directory:

```python
folder = Path(folder)
folder.mkdir(
    parents=True,
    exist_ok=True
)
```

Then I write each component separately.

---

### `balls.csv`

The largest file is:

```text
balls.csv
```

It contains one row for every historical delivery recorded in `History.balls`.

This is the most detailed view of the visible league.

Each row contains information such as the season, match, innings, over, ball, batting team, bowling team, venue, batter, bowler, outcome, extra, batting position, wickets before the ball, runs before the ball and chase target.

This follows the same tidy-data principle I used when converting the original Cricsheet archive.

Each observation is one row and each variable has its own column, following Wickham's tidy-data formulation (2014).

That structure is useful because an agent can answer questions with ordinary filters and grouped calculations rather than parsing nested match objects.

---

### Writing outcomes as cricket labels

Internally, the engine uses integer outcome codes:

```text
0, 1, 2, 3, 4, 5
```

corresponding to:

```text
W, 0, 1, 2, 4, 6
```

I do not want the public CSV to contain unexplained integer codes.

Before writing `balls.csv`, I therefore convert:

```python
balls["outcome"] = np.array(
    ["W", "0", "1", "2", "4", "6"]
)[balls.outcome]
```

So a human opening the file sees:

```text
W
0
1
2
4
6
```

rather than:

```text
0
1
2
3
4
5
```

This does not change the information.

It simply makes the public artifact readable without requiring someone to look up an encoding table.

---

### `matches.csv`

I write:

```text
matches.csv
```

directly from:

```python
history.matches
```

This contains one row per historical match.

The ball file answers questions about individual deliveries.

The match file answers higher-level questions such as:

```text
Who played?
Who won the toss?
Who batted first?
What were the innings totals?
Who won?
```

A simple forecaster could therefore operate entirely from `matches.csv` without touching the detailed ball history.

A stronger forecaster can use both.

I deliberately expose multiple resolutions of the same public history so that the task does not force one particular modelling approach.

---

### `lineups.csv`

I write historical line-ups using:

```python
_lineup_rows(
    "match",
    history.played
)
```

to produce:

```text
lineups.csv
```

This file connects each historical match with the exact players who appeared.

That matters because team identity alone is not enough in this world.

Players transfer between teams, and a fresh eleven is selected for every match.

A forecaster therefore needs to know which players generated each historical observation.

The batting slot also tells the agent where the player appeared in the order, while the bowling slot identifies the five players who were actually used as bowlers.

Without this file, much of the player-level information built into the synthetic world would be inaccessible.

---

### `players.csv`

The `PlayerTable` uses numeric arrays internally.

I convert those into a human-readable table.

Instead of role codes such as:

```text
0
1
2
```

I write:

```text
batter
allrounder
bowler
```

Instead of handedness:

```text
0
1
```

I write:

```text
right
left
```

and instead of bowling-style codes I write:

```text
pace
spin
```

The resulting:

```text
players.csv
```

therefore contains the public attributes of all synthetic players.

These are facts the forecasting agent is explicitly allowed to use.

What does not appear in the file are the hidden latent coordinates generated in `world.py`.

So the player table might tell the agent:

```text
player 47 is left-handed and bowls spin
```

but it does not tell the agent:

```text
player 47 batting quality = 0.183
player 47 current form = -0.041
player 47 bowling quality = 0.097
```

Those remain hidden.

---

### `venues.csv`

I perform the same conversion for grounds.

The internal `VenueTable` contains the home-team ID and a numeric pitch code.

I write:

```text
neutral
pace
spin
```

rather than:

```text
0
1
2
```

into:

```text
venues.csv
```

So the agent knows the public pitch type associated with every ground and which team has that ground as its home venue.

Again, the hidden venue level, dew and batter-specific affinities are deliberately absent.

---

### `fixtures.csv`

The next-season matches to be forecast are written to:

```text
fixtures.csv
```

Each row contains:

```text
fixture ID
season
home team
away team
venue
```

These are the future matches whose probabilities the forecasting agent must estimate.

Their IDs are distinct from historical match IDs because `world.py` numbers future fixtures from `10000`.

That makes it difficult to accidentally confuse a past match with a forecast target.

---

### `fixture_lineups.csv`

The future fixtures also have their exact line-ups written to:

```text
fixture_lineups.csv
```

I use the same `_lineup_rows()` representation as for historical matches.

This is important because the agent is not being asked to predict team selection.

By the time it receives an upcoming fixture, it knows exactly:

```text
which eleven players will play
where they bat
which five players will bowl
```

The forecasting problem can therefore focus on estimating the hidden strengths of those players and conditions.

If line-ups were also uncertain, the task would mix two separate prediction problems.

I deliberately remove that ambiguity.

---

### `meta.json`

The final public file is:

```text
meta.json
```

At the moment it contains:

```json
{"seasons": ...}
```

This tells the loader how many historical seasons are present.

The file is small, but I prefer keeping global metadata separate from the tabular observations rather than encoding it awkwardly inside one of the CSV files.

---

### Why I use CSV

I use CSV because I want the public data format to be boring.

Almost every programming language can read it.

A reviewer can inspect it in a text editor.

A non-programmer can open it in a spreadsheet.

A forecasting agent can read it with pandas, R, Julia, JavaScript or almost any other data stack.

There is no custom binary serialization and no Python-specific object format required to understand the visible world.

RFC 4180 documents a common format and MIME type for CSV files (Shafranovich, 2005), although it also notes that CSV historically has multiple dialects rather than one universally enforced specification.

In this repository the ambiguity is much smaller because the same pandas library writes and reads the files.

I write headers and do not rely on unusual quoting or nested structures.

So the public representation stays simple.

---

### Why `"0"` must remain a string

One small line in `load_league()` is unusually important:

```python
balls = pd.read_csv(
    folder / "balls.csv",
    dtype={"outcome": str}
)
```

The outcome column contains labels such as:

```text
W
0
1
2
4
6
```

The `"0"` here is a cricket outcome label.

It does not mean the internal outcome code zero.

If I let pandas infer the type freely, the mixture of numeric-looking strings and `"W"` can lead to inconvenient parsing behaviour.

I therefore force the entire column to remain text.

Only after reading it do I deliberately map the labels back into engine codes:

```python
{
    "W": 0,
    "0": 1,
    "1": 2,
    "2": 3,
    "4": 4,
    "6": 5
}
```

This preserves the distinction between:

```text
public label "0"
```

and:

```text
internal code 0 = wicket
```

That is exactly the kind of small serialization detail that can create very confusing bugs if it is left implicit.

---

### Reconstructing the player table

When loading the league, I read:

```text
players.csv
```

and convert the human-readable labels back into the numeric representation expected by the engine.

Roles become:

```text
batter      -> 0
allrounder  -> 1
bowler      -> 2
```

Handedness becomes:

```text
right -> 0
left  -> 1
```

and bowling style becomes:

```text
pace -> 0
spin -> 1
```

I then construct:

```python
PlayerTable(...)
```

using those arrays.

The public CSV representation is therefore optimized for readability, while the engine representation is optimized for numerical indexing.

The loader is the explicit conversion boundary between them.

---

### Reconstructing the venue table

I do the same for:

```text
venues.csv
```

The pitch labels are mapped back as:

```text
neutral -> 0
pace    -> 1
spin    -> 2
```

and I rebuild:

```python
VenueTable(...)
```

with the home-team and pitch arrays.

So after loading, the engine sees exactly the same type of venue object that `world.py` originally created.

---

### Reconstructing fixtures

The helper:

```python
_fixtures()
```

rebuilds `Fixture` objects from two public tables.

The first table tells me the high-level fixture information:

```text
home
away
venue
season
fixture ID
```

The second table contains the player rows.

For each fixture I select all rows belonging to that ID:

```python
mine = lineups[
    lineups[key] == ident
]
```

Then I separate the home and away teams.

For each side I sort by:

```text
batting_slot
```

to reconstruct the eleven in batting order.

I separately select players with:

```text
bowling_slot >= 0
```

sort those rows by bowling slot and reconstruct the five-person bowling order.

The result is then passed back into:

```python
Fixture(...)
```

So the transformation is reversible:

```text
Fixture object
      |
      v
line-up CSV rows
      |
      v
Fixture object
```

That reversibility is one of the reasons I prefer an explicit normalized table over putting Python list representations directly into a CSV cell.

---

### Why I use batting and bowling slots

Player IDs alone are not sufficient to reconstruct the match.

The innings simulator needs the batting order because batting position affects the state model.

It also needs the five bowlers in their defined rotation order.

So I preserve both types of ordering explicitly.

`batting_slot` tells me where the player appears in the eleven.

`bowling_slot` tells me where that player appears among the five bowlers.

This avoids relying on accidental CSV row order.

The semantic order is stored as data rather than inferred from how the file happened to be written.

---

### Loading the `History`

After reading the balls, matches, players, venues and metadata, I reconstruct:

```python
History(
    balls,
    matches,
    table,
    grounds,
    [],
    seasons
)
```

The `played` list is empty in the loaded public object because the forecasting code does not need the original internal historical `Fixture` objects once the corresponding public tables have been written.

The historical line-up information already exists in:

```text
lineups.csv
```

and the next-season `Fixture` objects are reconstructed separately from:

```text
fixtures.csv
fixture_lineups.csv
```

The loader therefore returns:

```python
history, fixtures
```

which is exactly the interface expected by the reference forecasters.

---

### The public task folder

At this stage the visible world consists of eight files:

```text
balls.csv
matches.csv
lineups.csv
players.csv
venues.csv
fixtures.csv
fixture_lineups.csv
meta.json
```

Together they contain the historical evidence and future forecasting targets.

They do not contain the answer.

There is no:

```text
skills.csv
```

no:

```text
venue_levels.csv
```

no:

```text
true_probabilities.csv
```

and no serialized `SkillBook`.

This is the boundary I want.

---

### Why this matters for fairness

The task builder, reference forecasters and forecasting agent should not silently see different versions of the same league.

If the builder used Python objects containing extra information while the agent used CSV files with less information, I could accidentally build a reference model that has an unfair advantage.

By making `load_league()` the standard public loading path, I can make the reference forecasters consume exactly what the agent consumes.

Conceptually:

```text
                 public task folder
                        |
                        v
                  load_league()
                        |
             +----------+----------+
             |                     |
             v                     v
      reference model           agent model
```

Both begin from the same public representation.

That makes differences in performance much easier to attribute to modelling ability rather than data access.

---

### Save-load symmetry

Another property I care about is that the public world survives a round trip.

Conceptually:

```text
History + Fixtures
       |
       v
  save_league()
       |
       v
   eight files
       |
       v
  load_league()
       |
       v
History + Fixtures
```

The objects on the far side should contain the same public information as the objects I started with.

That means serialization is not supposed to alter the task.

It is merely a representation change.

---

### Byte-level reproducibility check

The strongest test I run is with the known seed-101 world and the original constants.

I generate that world, save it into a scratch folder and compare the resulting task files against the visible world used in the pilot.

The expected command:

```text
diff -rq ...
```

produces no output.

That means all eight public files are byte-identical.

This is stronger than checking that they contain approximately the same number of rows or the same means.

It means the serialization stage recreated exactly the same public task artifact.

At that point I have tested the complete chain from the calibrated world through history generation and into the files delivered to the agent.

---

### Load-back check

I then load those files again with:

```python
load_league(...)
```

and expect:

```text
62,972 historical balls
24 future fixtures
```

The first forecast fixture should have:

```text
fixture = 10000
home/away teams = 5 and 2
```

for the known reference world.

This check tells me that both halves of the I/O layer agree.

`save_league()` did not merely produce the correct-looking files.

`load_league()` can also reconstruct the data structures needed by the forecasting code.

---

### The bug this file caught

One simple bug occurred when `load_league()` was first typed.

The function constructed the `History` object and reconstructed the fixtures correctly, but the final:

```python
return history, fixtures
```

was missing.

So all the internal work happened and then Python implicitly returned:

```text
None
```

The first attempt to use the loader exposed the mistake immediately.

This is a simple coding bug, but it is also why I want end-to-end tests that actually use the public loading interface rather than only inspecting intermediate variables.

---

### Why this file is the end of the world-building chain

At this point I have moved through the entire pipeline:

```text
real IPL archive
      |
      v
parse the deliveries
      |
      v
measure innings structure
      |
      v
measure signal and noise
      |
      v
fit the state model
      |
      v
measure player and venue variation
      |
      v
build calibration
      |
      v
define simulation design
      |
      v
build match engine
      |
      v
generate hidden synthetic world
      |
      v
generate visible history
      |
      v
league_io.py
      |
      v
public task folder
```

The output of this file is the first representation that no longer needs to know anything about how the world was created.

A forecasting agent can begin from these files alone.

That is exactly where I want the private world-building pipeline to stop and the public forecasting task to begin.

---

### How I think about this file

I think of `league_io.py` as the **airlock between the private simulator and the public task**.

On one side I have a rich Python world containing hidden state, simulation objects and internal data structures.

On the other side I have a small set of plain files containing exactly what a forecaster is allowed to observe.

`save_league()` controls what passes through the airlock.

`load_league()` guarantees that everyone who enters through the public side reconstructs the same view.

The central idea is:

> **I serialize the synthetic league once, in one explicit public format, and make both the reference forecasters and the agent reconstruct their world from that same representation. Hidden simulation state never crosses this boundary.**

### References

Wickham, H. (2014). *Tidy Data*. **Journal of Statistical Software, 59**(10), 1–23.

Shafranovich, Y. (2005). *Common Format and MIME Type for Comma-Separated Values (CSV) Files*. RFC 4180, Internet Engineering Task Force.

## 13. forecasters/ladder.py

### What I am trying to do

`forecasters/ladder.py` is where I build the models that take the task before I give it to another model.

Up to this point I have built the world, exposed the public history, hidden the true latent variables and created an engine that both the truth and any forecaster can use. I now need to know whether the resulting forecasting problem actually has a meaningful difficulty gradient.

A hard task is not useful if every reasonable method gets essentially the same score. It is also not useful if even a careful model cannot beat a coin flip.

So I build a ladder of forecasters ranging from deliberately naive to fairly careful.

The lower tiers make recognisable mistakes. One ignores everything and predicts `0.5`. Another models teams but not players. Another fits the correct player-level structure but without enough shrinkage. Another throws away old seasons. Another believes too strongly in head-to-head records.

The strongest tier uses essentially the correct public statistical structure while still having to infer all hidden values from the same public history available to the agent.

This gives me empirical landmarks for the task.

I can see what careless forecasting looks like, what competent forecasting looks like and whether the gap between them is large enough to support a meaningful pass threshold.

The careful ball-model forecaster becomes the reference point against which I set that threshold.

---

### One interface for every forecaster

Every tier inherits from:

```python
class Forecaster:
    name = "forecaster"

    def fit(self, history):
        return self

    def predict(self, fixtures):
        raise NotImplementedError
```

I deliberately keep the interface small.

Every model receives the same public `History`.

Every model later receives the same future `Fixture` objects.

Every model must return one home-win probability per fixture.

That means the packager, evaluation scripts and grader do not need special logic for different models.

Conceptually every tier has the same shape:

```text
public history
      |
      v
    fit()
      |
      v
future fixtures
      |
      v
  predict()
      |
      v
home-win probabilities
```

Only the statistical assumptions inside the forecaster change.

That makes comparisons much cleaner.

---

### The coin-flip forecaster

The simplest tier is:

```python
class CoinFlip(Forecaster):
```

Its prediction method is simply:

```python
return np.full(len(fixtures), 0.5)
```

It ignores the teams, players, venues, history and engine.

Every match receives:

```text
P(home wins) = 0.5
```

This is intentionally unsophisticated.

It is also important because it gives me the natural baseline for the exact scoring system.

The task's starter solution behaves this way, so the agent begins from a valid forecast rather than from broken code.

A model that cannot beat this baseline has extracted essentially no useful predictive information from the history.

---

### Team ratings from match results

The next forecaster uses only historical winners and losers.

I implement a simple Bradley-Terry-style paired-comparison model in which every team has a latent strength and the league has one shared home advantage.

The model is:

$$
P(\text{home wins})
=
\sigma
\left(
s_{\text{home}}
-
s_{\text{away}}
+
h
\right)
$$

where $\sigma$ is the logistic function.

This follows the paired-comparison idea introduced by Bradley and Terry (1952).

I initialize every team strength and the home effect at zero:

```python
self.s = np.zeros(teams)
self.h = 0.0
```

Then I repeatedly calculate the current probabilities and move the parameters in the direction of the result residual:

```python
g = won - p
```

If the home side won more often than the current model expected, its strength tends to move upward and the away side's strength tends to move downward.

I also apply a small pull toward zero:

```python
-0.5 * self.s
```

so team ratings do not drift unnecessarily far when the evidence is weak.

This is deliberately a fairly simple implementation rather than a sophisticated rating system.

---

### Why the team model is an important baseline

This is roughly the sort of model someone might build from a league table.

It asks:

> Which teams have been good?

rather than:

> Which players made those teams good, and which of those players are appearing in the upcoming fixture?

That distinction is particularly important in my synthetic world.

Squads rotate.

Playing elevens change.

Players transfer between teams.

So the label:

```text
team 4
```

is only an imperfect summary of the hidden ability that will actually appear in the next match.

The team-rating model therefore tests whether the task can be solved simply by learning persistent team reputation.

On the piloted world it performs badly, with regret around:

```text
0.0393
```

compared with approximately:

```text
0.0208
```

for the coin flip.

So in this particular world, fitting team identity too confidently can actually be worse than admitting complete uncertainty.

That is useful evidence that the transfer and squad-rotation design is doing what I intended.

---

### `EstimatedBook`: a forecaster's version of the hidden world

The more serious forecasters eventually need to call the same match engine used by the true league.

To do that, they need their own estimated `SkillBook`.

I therefore define:

```python
class EstimatedBook(SkillBook):
```

This object has the same overall structure as the league's hidden `SkillBook`, but its values are estimates learned from public history.

The engine does not care whether it receives:

```text
true SkillBook
```

or:

```text
EstimatedBook
```

It simply plays cricket using the supplied numbers.

This preserves the symmetry established in `engine.py`.

The forecasting problem is therefore largely reduced to:

> **Estimate the hidden book well enough that the public engine produces the right match probability.**

---

### The optional head-to-head hook

`EstimatedBook` also contains:

```python
def pair_effect(self, xi, bowlers):
```

which normally returns zero.

If a forecaster has fitted specific batter-bowler effects, it can store them in:

```text
self.pairs
```

and this method constructs the corresponding batter-by-bowler interaction matrix.

This uses exactly the hook I deliberately left in `SkillBook`.

The true league has no specific pair effect.

The head-to-head forecaster is allowed to believe otherwise.

That lets me test the statistical cost of fitting a plausible but mostly nonexistent structure without changing the public engine.

---

### The main ball-model forecaster

The serious model is:

```python
class BallModelForecaster(Forecaster):
```

The key idea is that I do **not** ask it to relearn how cricket works.

The public engine already tells it the over profiles, batting-position effects, wicket response, chase-pressure response, latent directions and extras process.

So when I fit this model, I treat the public part of every historical ball as known.

I only estimate the hidden values that were added to that public part.

This is almost the inverse problem of `world.py`.

`world.py` begins with hidden values and generates balls.

The forecaster begins with balls and estimates the hidden values.

---

### Building the fitting table

The `_design()` method converts the entire historical ball table into flat NumPy arrays.

For every ball I extract quantities such as:

```text
batter
bowler
venue
season
match
outcome
```

I also calculate whether the innings is a chase:

```python
d["chasing"] = (
    b.innings.to_numpy() == 2
).astype(float)
```

and reconstruct the legal-ball index:

```python
ball = (
    b.over * 6 + b.ball
).to_numpy()
```

This lets me calculate exactly the same chase-pressure feature used by the engine.

---

### Reconstructing chase pressure exactly

For second innings balls I call:

```python
m.pressure(
    b.target.to_numpy(),
    b.runs_before.to_numpy(),
    ball
)
```

and use zero for first-innings balls.

This matters because I want the estimator to be structurally aligned with the simulator.

If the generator defines pressure one way and the forecaster defines it another way, poor performance could come from a feature mismatch rather than from genuinely difficult inference.

Instead, I reuse the public engine's own pressure function.

---

### Computing the public offset once

The most important part of `_design()` is:

```python
d["offset"] = m.situation(
    b.over.to_numpy(),
    b.position.to_numpy(),
    b.wickets_before.to_numpy(),
    d["chasing"],
    pressure
)
```

This computes the public six-logit contribution for every historical ball.

Once that is done, I do not need to estimate:

```text
over effects
position effects
wicket effects
second-innings response
chase-pressure response
```

because the agent already knows them.

They are fixed offsets.

The fit only has to explain what remains.

That is exactly the intended forecasting problem.

---

### The hidden quantities I try to recover

The estimator can fit families corresponding to the hidden world.

These include the league scoring level, batter style, batter quality, bowling-type mean, individual bowler type, bowling quality, venue level, dew, second-innings wear, era, home advantage and, for the shrunk model, per-match day effects.

Richer tiers can additionally fit the batter's pace-versus-spin quality split, handedness-by-bowling-style effects, pitch-by-bowling-style effects, batter-venue affinity and specific batter-bowler pair effects.

The important thing is that all of these enter through the public directions already exposed by the engine.

I am estimating **how much** to move along a direction, not inventing new six-dimensional effects.

---

### Representing the model as parameter blocks

The `_blocks()` method is the centre of the implementation.

Each block describes one family of unknown parameters.

A block tells me which parameter index applies to a ball, what coefficient multiplies that parameter, which public six-dimensional direction it acts along, which ridge penalty family it belongs to and how many parameters exist in the family.

For example, batter style uses:

```text
index     = batter ID
coefficient = 1
direction = bat_style
count     = number of players
```

so every historical ball faced by the same batter points back to the same latent batter-style parameter.

Venue effects work the same way using venue ID.

Dew uses venue ID but is multiplied only on chasing balls.

Wear is a league-wide value multiplied by negative chase status.

Home advantage is a single number multiplied by whether the batting team is at home.

This block representation lets me express a fairly large hierarchical model with one generic optimizer.

---

### Why the model is linear before softmax

For every ball, the logits take the form:

$$
z_i
=
z_{i,\text{public}}
+
\sum_j x_{ij}\theta_jd_j
$$

where the public offset is fixed and the unknown parameters enter linearly before softmax.

That structure matters statistically.

The multinomial negative log-likelihood is convex in these linear parameters.

I then add positive quadratic ridge penalties.

For the blocks without an explicit prior key, I still use a very small penalty:

```text
0.001
```

so the objective remains regularized.

This gives me a well-behaved optimization problem rather than the non-convex neural-network-style optimization that would arise if I tried to relearn arbitrary nonlinear features.

---

### The prior table

I encode the default ridge strengths in:

```python
PRIOR = {
    ...
}
```

For a Gaussian prior:

$$
\theta
\sim
\mathcal N(0,\sigma^2)
$$

the negative log-prior contributes a quadratic penalty proportional to:

$$
\frac{\theta^2}{2\sigma^2}
$$

so the corresponding ridge precision is:

$$
\lambda
=
\frac{1}{\sigma^2}
$$

For example:

```text
bat_quality ridge ≈ 44
```

corresponds to:

$$
\sigma
\approx
\frac{1}{\sqrt{44}}
\approx
0.151
$$

which is essentially the true batter-quality spread used in the synthetic world.

That gives the reference forecaster a real advantage.

I designed these starting prior scales with knowledge of the world-generation process.

An external agent knows the public engine and sees the data, but it is not handed the true latent population spreads.

I therefore treat the reference as a strong benchmark rather than as the minimum strategy a contestant could reasonably be expected to reproduce exactly.

---

### Shrinkage

Shrinkage is essential because many of the hidden parameters have very different amounts of evidence.

A batter with hundreds of historical deliveries can support a fairly precise estimate.

A player who appeared rarely cannot.

A batter-venue interaction may have only a tiny number of observations.

Without regularization, the optimizer can interpret random variation in those small samples as enormous hidden effects.

The ridge penalty pulls weakly supported parameters back toward zero.

This is closely related to the broader shrinkage principle associated with James and Stein (1961) and to ridge regression as developed by Hoerl and Kennard (1970).

The key practical idea for this task is simple:

> **Small samples should not be allowed to claim huge hidden skill differences without strong evidence.**

---

### Choosing how much to shrink

I do not use one arbitrary global amount of shrinkage and assume it is optimal.

For shrunk tiers I consider three scale multipliers:

```text
0.3
1.0
3.0
```

These multiply the family-specific ridge strengths in `PRIOR`.

I then choose among them using held-out predictive likelihood.

The first seasons are used for fitting.

The last historical season is held out.

For each scale I fit on the earlier seasons and calculate mean ball-level log-likelihood on the last season.

I then retain whichever scale predicts the held-out future season best.

This is a small form of cross-validation in the sense of Stone (1974).

---

### Why the validation split is chronological

I deliberately do not randomly shuffle balls into train and validation sets.

This is a forecasting problem.

The real question is:

> **Can information from earlier seasons predict a later season?**

So I use:

```python
train = d["season"] < seasons - 1
```

and score on the final season.

That prevents future-season observations from leaking into earlier parameter estimates.

It also tests shrinkage under the same kind of temporal shift the final forecaster will face.

---

### Extrapolating the held-out era

There is one complication.

If I train only on the earlier seasons, the held-out season's era parameter has never been fitted.

I therefore extrapolate it from the previous season trend:

```python
t["era"][-1] = (
    t["era"][-2]
    + (
        t["era"][-2] - t["era"][0]
    ) / max(seasons - 2, 1)
)
```

This prevents the validation score from cheating by fitting the held-out season's global scoring level directly.

The model has to predict that shift from the earlier trend.

---

### Why I remove match-day effects during validation

The shrunk model fits one latent day effect per historical match.

That is useful while fitting because some historical matches happened on unusually good or poor batting surfaces.

But a future match does not come with its true hidden day effect.

So when I calculate held-out predictive likelihood, I deliberately remove the `day` block.

The `_held_out()` method temporarily constructs the model without those match-specific values.

This asks the correct predictive question:

> **How well does the fitted persistent structure predict a genuinely new match whose day condition is unknown?**

Keeping the fitted day value would make held-out likelihood unrealistically optimistic.

---

### The penalized likelihood

Inside `_fit()` I compute the probability of the observed outcome for every historical ball.

The objective is:

$$
-\sum_i w_i\log p_i(y_i)
+
\frac{1}{2}
\sum_j\lambda_j\theta_j^2
$$

The first term rewards models that assign high probability to what actually happened.

The second term penalizes unnecessarily large hidden parameters.

The optional weights allow some tiers to ignore or downweight particular seasons.

The result is penalized maximum likelihood, or equivalently a Gaussian-prior posterior mode under the prior interpretation above.

---

### Exact gradient

I do not ask SciPy to numerically approximate the gradient.

I derive it from the multinomial model.

For each ball I calculate:

```python
R = (Y - p) * w[:, None]
```

which is the observed one-hot outcome minus the predicted probability vector, weighted by whether the ball is included.

For each block I project that residual onto the block's public direction:

```python
R @ direction
```

apply the block coefficient and aggregate it by parameter index using:

```python
np.bincount(...)
```

I then add:

```python
ridge * theta
```

for the derivative of the quadratic penalty.

That gives L-BFGS-B the objective and its analytical gradient together.

This is both faster and safer than repeatedly estimating derivatives by finite differences across thousands of parameters.

---

### Fitting with L-BFGS-B

I optimize using:

```python
scipy.optimize.minimize(
    ...,
    method="L-BFGS-B"
)
```

The model may contain hundreds or thousands of latent parameters, especially once player-venue or batter-bowler interactions are enabled.

L-BFGS is appropriate for this kind of large smooth optimization problem because it avoids storing a full dense Hessian.

The important point for the task is not the particular optimizer name.

It is that the underlying likelihood is structured enough for a conventional convex optimization method rather than requiring unstable black-box search.

---

### The unshrunk tier

When I construct a forecaster with:

```text
shrink = False
```

I remove the meaningful prior shrinkage and leave only a very small penalty.

This tier therefore trusts historical maximum-likelihood estimates much more aggressively.

Its characteristic mistake is believing small samples.

A batter who happened to hit several sixes in a small number of deliveries can be estimated as much more extreme than the evidence warrants.

On the piloted world this increases regret from roughly:

```text
0.0087
```

for the reference to:

```text
0.0122
```

for the unshrunk tier.

That difference is a direct demonstration that estimating player effects is not enough. I also need to estimate them conservatively.

---

### The last-season-only tier

Another tier uses:

```text
season_weights = [0, 0, 1]
```

so only the most recent historical season contributes to the final fit.

The motivation is understandable.

Because form changes over time, newer information should often be more relevant.

But this tier takes that logic too far.

It discards two-thirds of the available evidence, including valuable information about persistent talent.

On the piloted world it reaches regret around:

```text
0.0094
```

with its selected shrinkage scale around:

```text
0.3
```

It is fairly competitive, but still weaker than the full-history reference.

That result supports the world design: history is neither perfectly permanent nor instantly obsolete.

Old matches retain value because talent persists, while recent matches gain extra relevance because form drifts.

---

### The raw head-to-head tier

The head-to-head tier activates:

```text
head_to_head = True
```

and creates one parameter for every batter-bowler pair that ever appeared in the historical data.

The pair parameter acts along the common conditions direction through the `pair_effect()` hook.

I barely shrink this table:

```text
pair ridge = 0.05
```

which means it is intentionally allowed to believe observed pair differences quite strongly.

This is the model version of a fan saying:

> This batter owns this bowler.

File 6 already told me why that is dangerous.

Specific batter-bowler interaction residuals barely repeated across independent samples.

The true synthetic league therefore contains no such pair effect.

The head-to-head model spends a huge number of parameters fitting noise.

On the piloted world its regret is approximately:

```text
0.0493
```

which makes it the worst tier in the reported ladder.

That is a useful negative control.

The task punishes an intuitive but statistically unsupported modelling choice.

---

### Richer matchup structure

A more defensible richer tier uses:

```text
matchups = True
```

This adds the broad structures that actually exist in the simulated world.

The model fits each batter's pace-versus-spin quality split, the handedness-by-bowling-style table and the bowling-style-by-pitch table.

These are low-dimensional structured interactions rather than one parameter for every specific pair.

That is exactly the distinction I wanted the simulation to teach.

Broad repeatable structure can be useful.

Raw memorization of sparse head-to-head records is not.

---

### Venue affinity

With:

```text
affinity = True
```

the model also fits one batter-venue parameter for every player-ground combination.

This is a much larger table, so it is strongly regularized.

The true world does contain a small personal batter-venue effect, but File 6 showed that it is weak.

Accordingly, adding this richer structure changes the reference score only slightly.

That is useful.

It means the task is not secretly won by discovering one obscure interaction.

Most of the available performance comes from getting the basic regularized player model right.

---

### How little the richer interactions matter

The matchup and venue-affinity additions move the reference score by only about one percent in the piloted comparisons.

I like that result because it means the task does not depend on a hidden trick.

An agent does not have to reverse engineer every minor mechanism in `world.py` to become competitive.

The dominant gains come from understandable modelling decisions: use the public ball model, estimate players rather than only teams, pool information across seasons and regularize noisy parameters.

The smaller interactions are refinements rather than secret keys.

---

### Estimating uncertainty from curvature

After fitting the point estimates, I also calculate an approximate uncertainty for each fitted parameter.

For a parameter acting along direction $d$, the curvature contribution of one ball is based on:

$$
\mathbb E[d^2]
-
\mathbb E[d]^2
$$

under the model's predicted outcome distribution.

The code calculates:

```python
curvature = (
    (p @ direction ** 2)
    - (p @ direction) ** 2
) * w
```

and then aggregates the curvature for every parameter.

After adding the ridge precision, I use:

```python
1 / np.sqrt(curvature + ridge)
```

as an approximate posterior standard deviation.

This is a diagonal Laplace approximation.

I approximate the posterior around the optimum as Gaussian using the local curvature of the negative log-posterior, following the general Laplace-approximation idea described by Bishop (2006).

I keep only the diagonal uncertainty and ignore cross-parameter covariance, so this is intentionally approximate.

---

### Posterior-predictive forecasting

If:

```text
uncertainty > 0
```

I do not use only the fitted point estimates.

Instead I repeatedly draw plausible parameter sets:

```python
value
+
Normal(0, 1) * estimated_sd
```

construct an `EstimatedBook` for each draw, simulate the fixtures and average the resulting probabilities.

Conceptually I am approximating:

$$
P(\text{home wins}\mid\text{history})
=
\int
P(\text{home wins}\mid\theta)
P(\theta\mid\text{history})
\,d\theta
$$

rather than simply evaluating:

$$
P(\text{home wins}\mid\hat\theta)
$$

at the posterior mode.

That is the distinction between a plug-in forecast and a posterior-predictive forecast.

---

### Why posterior uncertainty did not help here

In the piloted task I tried this with sixteen draws.

It did not improve the score.

That does not mean parameter uncertainty is theoretically irrelevant.

The approximation itself is crude. I keep only diagonal curvature, ignore posterior correlations and treat the local Gaussian approximation as if it describes the full posterior.

There is also Monte Carlo noise because the fixed simulation budget has to be divided across posterior draws.

So this remains a useful modelling experiment, but it is not part of the strongest practical reference configuration.

---

### Converting fitted parameters into an estimated world

The `_book()` method is the bridge between statistical fitting and match simulation.

The optimizer gives me arrays of estimated latent parameters.

The engine wants a `SkillBook`.

`_book()` translates between them.

It reconstructs estimated batter style, batter quality, bowling type, bowling quality, venue level, dew, affinity, home effect, wear and the public matchup tables.

It then packages them as:

```text
EstimatedBook
```

which can be handed directly to `MatchSimulator`.

This completes the inverse relationship with the true world:

```text
world.py:
hidden SkillBook -> historical balls

ladder.py:
historical balls -> EstimatedBook
```

---

### Extrapolating next season's level

The forecast fixtures occur after the observed historical seasons.

I therefore need an estimate of the next season's general scoring environment.

I calculate:

```python
era_next = (
    fitted level
    + latest era value
    + extrapolated trend
)
```

rather than pretending the final historical season's level will remain unchanged forever.

This mirrors the synthetic world's own era drift.

The forecaster does not know the true future level, but it knows from the public history that the scoring environment has been changing.

So it extrapolates one step forward.

---

### Estimating match-day variation

The shrunk model also fits one hidden day effect per historical match.

Because those fitted effects are themselves shrunk toward zero, their observed fitted standard deviation understates the true latent day spread.

I therefore calculate:

```python
day_sd = np.std(self.t["day"]) * 1.25
```

for the shrunk reference.

The factor:

```text
1.25
```

is a practical correction for that shrinkage.

This is one of the more heuristic pieces of the reference forecaster.

It is not another archive-estimated constant.

Its purpose is to make future Monte Carlo matches contain a plausible amount of unobserved day-level variability rather than treating the fitted, shrunken historical day effects as the true population spread.

---

### Deterministic prediction

For the ordinary plug-in forecast I construct one `EstimatedBook` from the fitted values.

Then, for each future fixture, I call:

```python
sim.win_probability(...)
```

using a random generator seeded from:

```python
self.seed + fx.match
```

So a particular forecaster and fixture always use the same simulation stream.

This matters because the prediction itself is Monte Carlo.

Without a fixed seed, running the exact same fitted forecaster twice would produce slightly different probabilities.

That would make verification unnecessarily difficult.

The deterministic seeding means:

> **Same history + same code + same fixture = same forecast.**

This is the property the verifier later checks.

---

### Monte Carlo budget

The reference does not need the enormous simulation budget used for hidden truth.

Its purpose is to produce a strong practical forecast.

The piloted reference used:

```text
4,000 match copies
```

for the reported ladder score.

That leaves some Monte Carlo noise, but the noise is small enough for benchmarking and the deterministic seed makes it reproducible.

The hidden truth can use many more copies because truth is generated offline and only needs to be computed once.

---

### What each tier is testing

I think of the ladder as a set of controlled statistical mistakes rather than simply a list of different algorithms.

The coin flip tests what happens when I learn nothing.

The team-rating model tests whether aggregate team reputation is enough.

The unshrunk player model tests what happens when I fit the right structure but trust noisy estimates too strongly.

The last-season-only model tests what happens when I overreact to recency and throw away persistent historical signal.

The raw head-to-head model tests what happens when I add a large number of attractive but non-repeating interaction parameters.

The matchup and affinity tiers test whether modelling the smaller real interactions materially improves forecasting.

The uncertainty tier tests whether integrating over approximate parameter uncertainty improves over a plug-in estimate.

The reference combines the strongest broadly justified decisions.

That makes the ladder useful diagnostically.

When one tier performs worse, I can usually explain **which statistical mistake caused the loss**.

---

### The piloted ladder

On the piloted visible world, using the stored high-precision truth, the main results are approximately:

```text
reference              0.0087
last season only       0.0094
no shrinkage           0.0122
coin flip              0.0208
team ratings           0.0393
raw head-to-head       0.0493
```

Lower regret is better.

The ordering is more important to me than any individual fourth decimal.

The careful player-level model clearly beats the naive baselines.

Removing shrinkage hurts.

Discarding older seasons hurts a smaller amount.

Team-level modelling is poor because team identity is deliberately unstable.

And fitting raw pair effects is disastrous because those interactions mostly capture noise.

That is the kind of ladder I wanted.

---

### Why the reference score matters

The reference forecaster is not supposed to represent the theoretical Bayes-optimal solution.

It is a strong, transparent model I can reproduce.

That makes it useful for setting the task's grading threshold.

If the pass bar were based only on the coin flip, a weak solution could pass.

If I somehow set it against inaccessible Bayes-optimal performance, the task could become unfair.

The reference provides a practical middle ground.

I know it uses only public information.

I know exactly how it works.

I know its numerical score.

And I know which advantages it has because I designed it.

---

### The reference's unfair advantage over an external agent

One limitation deserves to be explicit.

The `PRIOR` table was chosen with knowledge of the true synthetic population scales.

For example, the batting-quality prior spread is almost exactly the true generated spread.

That means the reference begins with unusually good regularization scales.

An external model is not handed those hidden spreads.

It has to infer reasonable shrinkage from the public history.

I partly mitigate this by selecting a global scale multiplier through chronological validation, but the relative prior strengths between parameter families still contain designer knowledge.

So I use the reference as a benchmark, not as evidence that every competent agent should reproduce its exact methodology.

---

### Why I validate shrinkage rather than selecting it on the forecast fixtures

The future fixtures are the test set.

I never use their hidden truth to choose the shrinkage strength.

All model selection happens inside the visible historical period.

I fit on earlier seasons and validate on the last visible season.

Then I refit on all public history using the selected scale.

That preserves the separation between model development and evaluation.

The reference therefore follows the same basic information restrictions that I expect from an agent.

---

### The first coding bug caught here

One implementation error was simply indentation.

The first version of:

```python
def _blocks(...)
```

was indented eight spaces rather than four.

Python immediately reported the syntax/indentation problem on import.

That bug was easy to catch because the program could not run.

As with the other files, the much more dangerous mistakes are statistical ones that produce valid-looking numbers while fitting the wrong model.

The ladder itself is partly designed to expose those mistakes.

---

### How this fits into the architecture

At this point the forecasting side looks like:

```text
public task files
        |
        v
   load_league()
        |
        v
      History
        |
        v
      fit()
        |
        v
estimated hidden parameters
        |
        v
   EstimatedBook
        |
        v
same public MatchSimulator
        |
        v
forecast probabilities
```

while the truth side remains:

```text
hidden League
     |
     v
true SkillBook
     |
     v
same public MatchSimulator
     |
     v
true probabilities
```

The two branches therefore converge on the same engine.

That is the architectural property I care about most.

---

### How I think about this file

I think of `forecasters/ladder.py` as the **exam calibration before the exam is given**.

The synthetic league defines the questions.

`TruthEngine` defines the correct probabilities.

The ladder sends several students of different competence through the same public information.

Their scores tell me whether the test distinguishes good statistical reasoning from bad statistical reasoning.

The central idea is:

> **I build a sequence of increasingly careful forecasters that all use the same public data and engine, then use their exact-regret scores to measure the difficulty and discrimination of the forecasting task before any external model is evaluated.**

### References

Bradley, R. A., & Terry, M. E. (1952). *Rank analysis of incomplete block designs: I. The method of paired comparisons*. **Biometrika, 39**(3/4), 324–345.

Hoerl, A. E., & Kennard, R. W. (1970). *Ridge regression: Biased estimation for nonorthogonal problems*. **Technometrics, 12**(1), 55–67.

James, W., & Stein, C. (1961). *Estimation with quadratic loss*. In *Proceedings of the Fourth Berkeley Symposium on Mathematical Statistics and Probability*, Vol. 1, 361–379.

Stone, M. (1974). *Cross-validatory choice and assessment of statistical predictions*. **Journal of the Royal Statistical Society: Series B, 36**(2), 111–147.

Bishop, C. M. (2006). *Pattern Recognition and Machine Learning*. Springer.