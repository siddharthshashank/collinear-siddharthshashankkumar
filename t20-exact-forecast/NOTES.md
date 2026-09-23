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

### What I am trying to do

`scoring/exact.py` defines how I grade a forecaster.

For every future fixture I have two probabilities. The first is the true home-win probability generated by the hidden synthetic world,

$$
p = P(\text{home wins}),
$$

and the second is the probability reported by the forecaster,

$$
q.
$$

I want the score to measure how much information the forecaster loses by reporting $q$ instead of the truth $p$.

The important advantage of this project is that I actually own the data-generating process. I do not only observe which team happened to win one realization of a match. I can simulate the hidden world many times and estimate its underlying win probability very accurately.

That means I can grade:

```text
forecast probability
        against
true probability
```

rather than:

```text
forecast probability
        against
one noisy match result
```

This is the central reason I call the scorer `ExactScorer`.

The truth is not mathematically exact because `TruthEngine` still estimates it by large Monte Carlo simulation, but for grading purposes I treat those high-precision probabilities as the underlying truth of the task.

---

### Initializing the scorer

The class starts with:

```python
class ExactScorer:

    def __init__(self, truth, floor=0.002):
        self.truth = np.asarray(truth, float)
        self.floor = floor
        self.coin = self.regret(
            np.full(len(self.truth), 0.5)
        )
```

I store the true probabilities as a NumPy array.

I also store:

```text
floor = 0.002
```

which I later use to stop a forecast from becoming exactly zero or exactly one.

Finally, I calculate:

```python
self.coin
```

which is the regret of a forecaster that predicts:

$$
q=0.5
$$

for every fixture.

I keep this because the coin flip is my natural baseline.

It gives me a simple reference point for saying whether a forecast extracted useful information from the world.

---

### The quantity I actually grade

The core method is:

```python
def regret(self, forecast):
```

For every fixture I have the true probability $p$ and forecast $q$.

The score is:

$$
R(q)
=
p\ln\frac{p}{q}
+
(1-p)\ln\frac{1-p}{1-q}.
$$

I average this quantity over all graded fixtures.

The implementation is:

```python
p = self.truth

q = np.clip(
    np.asarray(forecast, float),
    self.floor,
    1 - self.floor
)

return float(
    np.mean(
        p * np.log(p / q)
        +
        (1 - p)
        * np.log((1 - p) / (1 - q))
    )
)
```

Lower is better.

The ideal forecast:

$$
q=p
$$

has regret:

$$
R(p)=0.
$$

Any disagreement between $q$ and $p$ produces positive regret.

---

### Where the formula comes from

The formula starts from the logarithmic scoring rule.

Suppose a forecaster reports home-win probability $q$.

If the home team actually wins, the log loss is:

$$
-\ln q.
$$

If the home team loses, the loss is:

$$
-\ln(1-q).
$$

This is the logarithmic score associated with Good's discussion of rational probability forecasts (Good, 1952).

Normally, if I only had the observed match result, I would calculate one of those two values.

But in my simulator I know the true probability that the home team wins.

The home side wins with probability $p$ and loses with probability $1-p$.

So instead of waiting for one result, I can calculate the expected log loss directly:

$$
L(q)
=
-p\ln q
-
(1-p)\ln(1-q).
$$

This quantity answers:

> **If I could replay this exact fixture infinitely many times under the hidden world, what average log loss would this forecast receive?**

That is much closer to what I actually want to measure.

I want to judge whether the forecaster understood the probability-generating process, not whether it happened to get lucky on one match outcome.

---

### The best possible expected loss

If the forecaster knows the true probability and reports:

$$
q=p,
$$

its expected loss becomes:

$$
L(p)
=
-p\ln p
-
(1-p)\ln(1-p).
$$

This value is not generally zero.

Even a perfect forecaster cannot remove the randomness from cricket.

For example, if:

$$
p=0.7,
$$

then even the correct forecast still assigns a 30 percent probability to the away side winning.

So the match result itself remains uncertain.

$L(p)$ is the irreducible uncertainty, or entropy, of that binary event.

I do not want to punish the forecaster for this unavoidable randomness.

I only want to charge it for the extra loss caused by using the wrong probability.

So I define regret as:

$$
R(q)
=
L(q)-L(p).
$$

Expanding this gives:

$$
R(q)
=
p\ln\frac{p}{q}
+
(1-p)\ln\frac{1-p}{1-q}.
$$

That is exactly the formula used in the code.

---

### KL divergence

This regret is the Kullback-Leibler divergence between two Bernoulli distributions.

The true world is:

$$
\operatorname{Bernoulli}(p)
$$

and the forecaster claims:

$$
\operatorname{Bernoulli}(q).
$$

So:

$$
R(q)
=
D_{\mathrm{KL}}
\left(
\operatorname{Bern}(p)
\|
\operatorname{Bern}(q)
\right).
$$

Kullback and Leibler introduced this divergence in their 1951 paper on information and sufficiency.

The information inequality described in Cover and Thomas tells me:

$$
D_{\mathrm{KL}}(P\|Q)\ge0,
$$

with equality only when the two distributions agree.

In this binary case:

$$
R(q)\ge0
$$

and:

$$
R(q)=0
\iff
q=p.
$$

That is exactly the behaviour I want from the grader.

---

### Why the true probability is uniquely optimal

The expected log loss is:

$$
L(q)
=
-p\ln q
-
(1-p)\ln(1-q).
$$

Differentiating with respect to $q$ gives:

$$
\frac{dL}{dq}
=
-\frac{p}{q}
+
\frac{1-p}{1-q}.
$$

Setting this equal to zero gives:

$$
-\frac{p}{q}
+
\frac{1-p}{1-q}
=
0.
$$

Rearranging gives:

$$
q=p.
$$

The second derivative is:

$$
\frac{d^2L}{dq^2}
=
\frac{p}{q^2}
+
\frac{1-p}{(1-q)^2},
$$

which is positive for probabilities strictly between zero and one.

So $L(q)$ is strictly convex and has one unique minimum:

$$
q=p.
$$

This is what Gneiting and Raftery (2007) call a **strictly proper scoring rule**.

A forecaster minimizes its expected score by reporting what it actually believes the probability to be.

It gains nothing by intentionally exaggerating or suppressing its probability.

That property is extremely important for a forecasting task.

---

### What regret looks like near the truth

Close to the true probability, KL regret behaves approximately like:

$$
R(q)
\approx
\frac{(q-p)^2}
{2p(1-p)}.
$$

So locally it resembles squared error, but scaled by:

$$
p(1-p).
$$

This gives me useful intuition.

When the true fixture is close to:

$$
p=0.5,
$$

there is substantial natural uncertainty.

When the true fixture is closer to an extreme, making a similarly sized probability error can represent a much larger informational mistake.

The log score therefore cares not just about absolute distance, but also about how confidently the wrong distribution was stated.

---

### Why confident mistakes hurt

Suppose:

$$
p=0.7.
$$

Two forecasts are both twenty percentage points away:

$$
q=0.5
$$

and:

$$
q=0.9.
$$

Their absolute error is identical:

$$
|q-p|=0.2.
$$

But their regret is not identical.

For:

$$
q=0.5,
$$

the regret is approximately:

$$
0.082.
$$

For:

$$
q=0.9,
$$

the regret is approximately:

$$
0.154.
$$

So the confident forecast costs almost twice as much.

That is behaviour I want.

Predicting 90 percent when the truth is only 70 percent is a more serious probabilistic claim than simply saying the match is a coin flip.

The scorer should reflect that.

---

### Why I grade against truth instead of match results

This is one of the most important design decisions in the whole task.

Suppose I graded forecasts using the future match winners.

Even if I had the perfect forecast:

$$
q=p,
$$

the observed log loss would still fluctuate because the match itself is random.

A team with a true win probability of 70 percent still loses roughly 30 percent of its realizations.

With only around 192 graded fixtures, this result noise is large enough to interfere with the difference between a strong forecaster and a weaker one.

The estimated outcome-based log-loss noise is around:

```text
0.014 per match
```

which is more than twice the gap I care about between some of the forecasting tiers.

That means a model could cross or miss the pass threshold because the future teams happened to win or lose, rather than because its probability estimates were better.

Owning the synthetic world lets me remove that problem.

For every fixture I calculate the hidden win probability using `TruthEngine`, and I score the forecast directly against that probability.

The observed future winner is unnecessary for grading.

This is one of the major advantages of simulation studies described by Morris, White and Crowther (2019): because the data-generating process is known, statistical methods can be evaluated against known underlying quantities rather than only against noisy observations.

---

### Why I use logarithmic regret instead of Brier score

I could have used the Brier score.

For a binary outcome, the Brier score is essentially squared probability error and is also strictly proper.

Brier introduced it in 1950 for probabilistic forecasts.

So this is not a case where one score is valid and the other is invalid.

Both are defensible.

I choose logarithmic regret mainly because of how it treats confident errors.

The Brier score treats errors quadratically.

The log score becomes much harsher when a forecaster assigns very little probability to something the true distribution considers plausible.

That is exactly the failure mode I expect in this task.

A model may overinterpret noisy player histories, head-to-head records or recent form and produce probabilities that are much too extreme.

I want the grader to notice that.

The failed model runs also showed this behaviour in practice.

---

### Why I do not use the locality argument as the main justification

A common theoretical argument for the logarithmic score is that it is local: the score for an observed outcome depends only on the probability assigned to that outcome.

Bernardo's 1979 result gives a uniqueness argument for the logarithmic score under appropriate locality and propriety conditions when there are at least three outcomes.

My task is binary:

```text
home win
not home win
```

In the binary case that argument does not cleanly distinguish the log score from every other proper scoring rule in the way it does for larger outcome spaces.

So I do not rely on that as the reason for choosing it here.

My practical reasons are simpler.

The log score penalizes unjustified confidence strongly, and that is exactly the error structure I want this task to expose.

---

### The gambling interpretation

The regret also has a useful interpretation in terms of long-run growth.

If a bettor repeatedly stakes according to its probability belief, the optimal long-run growth strategy is connected to the Kelly criterion.

Reporting or acting according to $q$ when the true probability is $p$ reduces the achievable asymptotic growth rate relative to using the correct probability.

That shortfall is connected directly to KL divergence.

Kelly's 1956 paper developed this information-growth connection, and Cover and Thomas discuss it in their treatment of gambling and information theory.

I like this interpretation because it makes the score less abstract.

Regret measures information loss, but it can also be understood as the long-run price of betting with the wrong beliefs.

---

### Why I clip forecasts

The logarithmic score has one practical problem.

Suppose a forecaster says:

$$
q=0
$$

for a home win.

If:

$$
p>0,
$$

then:

$$
p\ln\frac{p}{q}
$$

contains:

$$
\ln 0,
$$

and the regret becomes infinite.

The same problem occurs for:

$$
q=1
$$

when the away side still has positive probability.

I do not want one numerical probability of exactly zero to destroy an entire task score.

So I clip:

```python
q = np.clip(
    q,
    0.002,
    0.998
)
```

The most extreme allowed probability is therefore:

```text
0.2%
```

or:

```text
99.8%
```

The largest single logarithmic term from the floor is roughly:

$$
-\ln(0.002)
=
\ln(500)
\approx
6.21.
$$

So extreme overconfidence is still punished heavily, but it remains finite.

Selten (1998) discusses the concern that logarithmic scoring can become excessively harsh near the boundaries. The clip is my practical answer to that problem.

The true probabilities in this task live roughly between:

```text
0.2 and 0.8
```

so the clipping boundary is far outside the region where an accurate forecast should normally operate.

It therefore protects numerical robustness without changing the location of the realistic optimum.

---

### The coin-flip yardstick

During initialization I calculate:

```python
self.coin = self.regret(
    np.full(len(self.truth), 0.5)
)
```

This gives me the regret of refusing to distinguish among fixtures.

The coin flip says:

> I have learned nothing about which home teams are more or less likely to win.

That makes it a useful natural denominator for a descriptive skill score.

---

### The skill number

I define:

```python
def skill(self, forecast):
    return (
        1.0
        - self.regret(forecast)
        / self.coin
    )
```

or mathematically:

$$
\text{skill}
=
1
-
\frac{\bar R(q)}
{\bar R(0.5)}.
$$

This is easy to interpret.

A perfect forecast has:

$$
\bar R(q)=0
$$

and therefore:

$$
\text{skill}=1.
$$

The coin flip has:

$$
\bar R(q)
=
\bar R(0.5)
$$

and therefore:

$$
\text{skill}=0.
$$

A model worse than the coin flip has negative skill.

So if I report:

```text
skill = 0.75
```

I can read it roughly as:

> **The forecaster removed 75 percent of the avoidable regret of the coin-flip baseline.**

---

### Why skill is descriptive, not the grading rule

I do not use the skill value itself for the pass/fail rule.

The actual grading comparison is based on regret.

This distinction matters because transforming a proper score into a relative skill score can alter its incentive properties.

Murphy discussed this issue in his work on probability-forecast skill scores and hedging.

A skill score normalized against a baseline is convenient to interpret, but the normalized ratio is not automatically guaranteed to preserve all of the propriety properties of the original score.

With a reasonably large collection of forecasts the distinction may be small in practice, but I do not need to rely on that approximation.

The task can simply grade the original proper quantity.

So:

```text
regret = grading quantity
skill  = human-readable summary
```

---

### `report()`

The `report()` method adds two descriptive diagnostics to regret and skill.

It returns:

```text
regret
skill
mean_abs_error
slope
```

The first two describe overall forecasting performance.

The other two help me understand **how** the forecast failed.

---

### Mean absolute error

The simplest diagnostic is:

```python
np.abs(q - self.truth).mean()
```

which calculates:

$$
\frac{1}{N}
\sum_i
|q_i-p_i|.
$$

This answers:

> **On average, how many probability points away from truth were the forecasts?**

It is not the grading rule because it does not distinguish confident and cautious errors the way logarithmic regret does.

But it is immediately understandable.

If:

```text
mean_abs_error = 0.06
```

I know the forecaster was about six percentage points away from the true probabilities on average.

---

### The spread slope

The more interesting diagnostic is:

```python
slope = np.polyfit(
    logit(q),
    logit(self.truth),
    1
)[0]
```

where:

$$
\operatorname{logit}(x)
=
\ln\frac{x}{1-x}.
$$

So I regress:

$$
\operatorname{logit}(p)
$$

on:

$$
\operatorname{logit}(q).
$$

This gives me a measure of how widely the forecasts spread compared with the truth.

Cox (1958) discussed this type of coefficient as a measure of probability spread. In later prediction literature it is commonly described as a calibration slope.

Here I have a cleaner situation than ordinary applied calibration studies because I know the true probabilities themselves.

I therefore regress true logits directly on forecast logits rather than fitting a logistic regression against noisy binary outcomes.

---

### Interpreting slope = 1

If:

$$
\text{slope}=1,
$$

then the forecasts vary across fixtures by approximately the same amount as the truth.

For example, if the true league contains fixtures around:

```text
0.35
0.45
0.55
0.70
```

then a well-spread forecast should show a comparable amount of probability variation.

This does not by itself guarantee perfect forecasting because the intercept and individual errors also matter.

But a slope around one tells me the forecast has roughly the correct degree of dispersion.

---

### Interpreting slope below 1

Suppose:

$$
\text{slope}<1.
$$

Then the forecast logits vary more widely than the truth logits.

That means the model is **overconfident**.

For example, the truth may vary roughly between:

```text
0.4 and 0.6
```

while the forecaster spreads predictions from:

```text
0.2 to 0.8.
```

The forecasts are exaggerating differences between fixtures.

This is exactly the behaviour that raw player estimates or noisy head-to-head models can create.

One failed GPT-5.5 run produced a slope around:

```text
0.33
```

which means its forecasts were spreading roughly three times as aggressively as the underlying truth.

That is a very informative failure signature.

The model was not merely inaccurate. It was systematically too certain that it had identified large differences among teams.

---

### Interpreting slope above 1

If:

$$
\text{slope}>1,
$$

the forecast probabilities do not spread enough.

The model is **under-confident**.

For example, perhaps true fixture probabilities range from:

```text
0.3 to 0.7
```

but the forecaster keeps everything around:

```text
0.45 to 0.55.
```

The forecast recognizes the ordering only weakly and stays too close to a coin flip.

So the slope lets me distinguish two very different forms of bad forecasting:

```text
too extreme
```

versus:

```text
not extreme enough.
```

Regret alone cannot describe that distinction as clearly.

---

### Why I return `nan` for a constant forecast

The code checks:

```python
np.ptp(q) > 1e-9
```

before computing the slope.

`np.ptp(q)` is the range of the forecast probabilities.

If every forecast is identical, such as the coin flip:

```text
0.5, 0.5, 0.5, ...
```

there is no forecast variation from which a slope can be estimated.

The x-axis of the regression is effectively constant.

So I return:

```text
nan
```

rather than pretending the slope has a meaningful value.

---

### A simple numerical check

I use:

$$
p=0.7
$$

as an easy hand check.

If the forecast is:

$$
q=0.7,
$$

then:

$$
R(q)=0.
$$

That is the most important check: reporting the truth must produce zero regret.

For:

$$
q=0.5,
$$

I get approximately:

$$
R(0.5)=0.082.
$$

For:

$$
q=0.9,
$$

I get approximately:

$$
R(0.9)=0.154.
$$

So two forecasts with the same absolute probability error are treated differently because the more confident error makes a stronger incorrect claim.

For:

$$
q=0.6,
$$

the forecast removes roughly 74 percent of the coin flip's regret, giving skill around:

```text
0.74
```

for this one-fixture example.

These small checks make the mathematical behaviour easy to verify independently of the rest of the repository.

---

### Checking the full report

I also use the example:

```text
truth:
0.70, 0.40, 0.55

forecast:
0.90, 0.20, 0.60
```

The individual regrets are approximately:

```text
0.1537
0.1047
0.0051
```

giving mean regret around:

```text
0.088
```

The coin-flip regret for these truths is approximately:

```text
0.036
```

so the forecast is worse than the coin flip and its skill becomes approximately:

```text
-1.452
```

The mean absolute probability error is:

```text
0.15
```

and the spread slope is approximately:

```text
0.35
```

That final number immediately tells me what kind of failure occurred.

The forecasts are much more dispersed than the truth.

The model is severely overconfident.

---

### Why I care about checking the expected values themselves

One of the original expected numbers for this test was guessed before the calculation was performed.

The guess was wrong.

The implementation was right.

I keep that episode in the notes because it illustrates an important engineering point:

> **A test is only useful if the expected value is independently trustworthy.**

Writing an assertion around a guessed number does not create correctness.

For mathematical code like this, I want either a hand derivation, an independently calculated reference or a property that must hold.

Examples of stronger checks here are:

$$
R(p)=0,
$$

$$
R(q)\ge0,
$$

and the fact that more extreme wrong forecasts should receive larger penalties.

---

### Bugs caught while typing the file

One bug was purely syntactic: a tab was mixed with spaces.

Python caught that immediately.

The other was:

```python
np.asarray(truth, floor)
```

when the intended call was:

```python
np.asarray(truth, float)
```

The second positional argument to `np.asarray` is the data type.

I wanted to convert the truth probabilities to floating-point values, not pass the clipping floor as a dtype.

These bugs were easy to expose because this scorer is small enough to test independently before attaching it to the rest of the task.

---

### How this file fits into the whole task

At the end of the project, the scoring path is:

```text
hidden synthetic world
        |
        v
TruthEngine
        |
        v
true fixture probabilities p
        |
        +------------------+
                           |
public history             |
        |                  |
        v                  |
forecaster                 |
        |                  |
        v                  |
forecast probabilities q   |
        |                  |
        +--------+---------+
                 |
                 v
          ExactScorer
                 |
                 v
             regret
```

This separation is important.

`TruthEngine` defines what the world actually believes.

The forecaster defines what the agent believes.

`ExactScorer` measures the informational distance between those two beliefs.

No realized future match result is required.

---

### How I think about this file

I think of `scoring/exact.py` as the part of the task that converts owning the simulator into a grading advantage.

In a normal forecasting benchmark I only get one future.

A team either wins or loses, and the score inevitably contains outcome noise.

In this synthetic world I know the probability distribution behind that future.

That means I can ask the cleaner question:

> **How close was the forecaster's probability distribution to the probability distribution that actually generated the world?**

The logarithmic regret gives me that quantity directly.

The central principle is:

> **I grade probability estimates against the hidden probability itself, not against one random realization of that probability. This removes outcome luck from the verdict and makes unjustified confidence expensive.**

### References

Good, I. J. (1952). *Rational decisions*. **Journal of the Royal Statistical Society: Series B, 14**, 107–114.

Gneiting, T., & Raftery, A. E. (2007). *Strictly proper scoring rules, prediction, and estimation*. **Journal of the American Statistical Association, 102**, 359–378.

Kullback, S., & Leibler, R. A. (1951). *On information and sufficiency*. **Annals of Mathematical Statistics, 22**, 79–86.

Morris, T. P., White, I. R., & Crowther, M. J. (2019). *Using simulation studies to evaluate statistical methods*. **Statistics in Medicine, 38**, 2074–2102.

Brier, G. W. (1950). *Verification of forecasts expressed in terms of probability*. **Monthly Weather Review, 78**, 1–3.

Bernardo, J. M. (1979). *Expected information as expected utility*. **Annals of Statistics, 7**, 686–690.

Kelly, J. L. (1956). *A new interpretation of information rate*. **Bell System Technical Journal, 35**.

Selten, R. (1998). *Axiomatic characterization of the quadratic scoring rule*. **Experimental Economics, 1**, 43–61.

Murphy, A. H. (1973). *Hedging and skill scores for probability forecasts*. **Journal of Applied Meteorology, 12**, 215–223.

Murphy, A. H. (1988). *Skill scores based on the mean square error and their relationships to the correlation coefficient*. **Monthly Weather Review, 116**, 2417–2424.

Cox, D. R. (1958). *Two further applications of a model for binary regression*. **Biometrika, 45**(3/4), 562–565.

Cover, T. M., & Thomas, J. A. (2006). *Elements of Information Theory* (2nd ed.). Wiley.

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

---

## 14. dev/validate_world.py

### What I am trying to do

`dev/validate_world.py` is where I stop asking whether the simulator is internally consistent and start asking a harder question:

> **Does the synthetic league actually behave like the real cricket data I calibrated it from?**

Up to this point, I have checked individual pieces separately. I checked that the over profiles look sensible, that the player spreads are measured correctly, that the engine responds to wickets and chase pressure in the expected direction, and that the world generator is reproducible.

Those checks are necessary, but they are not enough.

A simulator can contain individually reasonable components and still produce unrealistic league-level behaviour once all of those components interact.

This file therefore performs an **operational validation** of the finished world.

I generate several complete synthetic leagues, pool their visible match and ball histories, and compare the resulting distributions with the real targets measured earlier in `fit_constants.py`.

The question is no longer:

```text
Does this function work?
```

or:

```text
Does this coefficient have the right sign?
```

The question is:

> **When all the mechanisms run together, does the world produce something recognizably like the cricket system I intended to imitate?**

This is the kind of validation Sargent (2013) describes as operational validity: comparing the output behaviour of the simulation with the behaviour of the real system.

Davis, Perera and Swartz (2015) follow the same broad philosophy when validating their Twenty20 cricket simulator against real match characteristics.

---

### What I compare

I do not try to compare every possible statistic in the archive.

Instead, I focus on six summaries that cover different parts of the generated game.

I compare the mean first-innings total, the standard deviation of first-innings totals, the average number of bowler wickets in the first innings, the probability that the chasing side wins, the scoring profile across the twenty overs, and chase success as a function of the target.

Together these tell me whether the simulator gets both the centre and shape of the game approximately right.

A simulator could match the mean score while having completely unrealistic variance.

It could match the average score and still produce the wrong death-over pattern.

It could reproduce first-innings scoring while making chasing far too easy.

So I deliberately check several different aspects of the generated world rather than one headline average.

---

### Why I simulate three complete leagues

The validation function begins with:

```python
def summary(design, seeds=(1, 2, 3)):
```

I generate three independent leagues rather than validating on one synthetic history.

Each league contains:

```text
270 matches
```

across three seasons.

One league is already fairly large, but the summaries still contain Monte Carlo variation.

For example, if the first-innings standard deviation is around:

```text
35 to 37 runs
```

then a single league of 270 first innings gives the estimated mean a standard error on the order of:

```text
2 runs
```

Similarly, a chase probability around `0.5` estimated from only a few hundred matches can easily move by several percentage points simply because of sampling noise.

Pooling three leagues gives me:

```text
810 matches
```

and substantially more ball-level observations.

That makes the comparison more stable.

I use fixed seeds:

```text
1, 2, 3
```

so the validation itself is reproducible.

If I rerun this script without changing the design or calibration, I should obtain the same synthetic validation sample.

---

### Generating the validation worlds

For every seed I create:

```python
League(seed, design=design)
```

and call:

```python
play_history()
```

This means the validation does not use a special simplified simulator.

It runs exactly the same league-generation pipeline that produces the forecasting task.

Each validation league contains invented players, hidden player abilities, form drift, transfers, venues, pitch effects, tosses, line-ups, match-day conditions and individual ball outcomes.

I collect the match tables into:

```python
M
```

and the ball tables into:

```python
B
```

and add the league seed to each row.

I then concatenate all three worlds.

The resulting validation sample is therefore just a larger pooled version of the same world an agent would eventually observe.

---

### First-innings data

Most of my validation summaries use the first innings.

I isolate those balls with:

```python
first = B[B.innings == 1]
```

First innings are particularly useful for checking the basic scoring model because they are not influenced by a target.

That lets me examine the scoring distribution without the extra behavioural response created by chase pressure.

The chase-specific behaviour is validated separately.

---

### Mean first-innings total

The simplest target is:

```python
M.first_total.mean()
```

This asks whether the overall scoring level of the simulated league is correct.

The real target measured from the archive is approximately:

```text
188.5 runs
```

In the current re-validation run, the simulator produces approximately:

```text
189.2 runs
```

That difference is small.

It tells me that the global scoring level, player variation, venue effects, era adjustment and other mechanisms combine to produce roughly the intended average.

This is particularly important because introducing player heterogeneity changes the league mean through nonlinear softmax effects.

That is why `level_runs` existed in the `Design` object.

This validation checks whether that recentering actually worked in the full league.

---

### Spread of first-innings totals

I also calculate:

```python
M.first_total.std()
```

The real archive has a first-innings standard deviation around:

```text
37.4 runs
```

while the current simulator produces approximately:

```text
35.0 runs
```

This is one of the remaining mismatches.

The mean is close, but the simulated league is still slightly too concentrated around that mean.

In plain language, real IPL innings contain somewhat more extreme low and high totals than my synthetic world generates.

That difference is not enormous, but I keep it visible as a limitation.

I do not want to keep adding hidden noise terms only to force every validation statistic to match exactly.

The world needs to be credible, not mechanically overfitted to every aggregate number.

---

### Bowler wickets

The first-innings wicket calculation uses:

```python
first[first.outcome == 0]
```

because outcome code zero corresponds to:

```text
W
```

in the ball model.

I group those dismissals by league and match.

Some innings contain no bowler wickets, so after grouping I reindex against all matches and fill missing values with zero.

This detail matters.

Without the reindexing, an innings with no wickets would disappear from the grouped table entirely and the average would be biased upward.

The final statistic is therefore:

```python
wk.mean()
```

across all first innings.

The real archive target is approximately:

```text
5.9 wickets
```

and the simulated world currently produces approximately:

```text
5.83
```

which is very close.

This tells me that the dismissal process is behaving plausibly at the innings level, not only ball by ball.

---

### Reconstructing runs from the ball history

For the over profile I rebuild scoring from the historical balls.

The ball outcome codes correspond to:

```text
W, 0, 1, 2, 4, 6
```

with representative run values:

```python
np.array([0, 0, 1, 2, 4, 6])
```

I then add the independently generated extras:

```python
runs = (
    np.array([0, 0, 1, 2, 4, 6])[first.outcome]
    + first.extra
)
```

This reconstructs the scoring process in the same coarse representation used by the simulator.

I then calculate the average scoring rate for every over.

---

### Runs per over

For each over I calculate:

```python
runs.groupby(first.over).sum()
/
first.groupby("over").size()
*
6
```

The numerator is the total number of modeled runs scored in that over across the validation leagues.

The denominator is the number of legal deliveries observed in that over.

Multiplying by six expresses the result as approximately:

```text
runs per six-ball over
```

rather than runs per ball.

This produces a twenty-number simulated over profile.

I compare it against:

```python
real["runs_per_over_first_innings"]
```

from the archive calibration.

---

### Why I use the correlation across overs

I do not only ask whether every individual over has exactly the same run rate.

I also calculate:

```python
np.corrcoef(
    real_over,
    per_over
)[0, 1]
```

This asks whether the **shape** of the scoring profile is reproduced.

The current correlation is approximately:

```text
0.977
```

across all twenty overs.

That is strong.

It means the simulator reproduces the major temporal structure of a T20 innings.

The early overs, middle overs and death overs rise and fall in approximately the same pattern as the archive.

A correlation of `0.977` does not mean the simulated values are numerically identical in every over.

It means the overall shape is very close.

That is exactly what I care about here.

---

### Inspecting representative overs

For readability I print only selected overs:

```text
1, 4, 7, 11, 15, 18, 20
```

rather than dumping all twenty values into the terminal.

These points give me a quick view across the powerplay, middle overs and death overs.

I still calculate the correlation using all twenty.

So the abbreviated printout is only for human inspection.

The validation itself uses the complete profile.

---

### Chase success

At the match level I identify a successful chase with:

```python
chase_won = M.winner != M.batted_first
```

Because there are only two teams in a match, this means the side batting second won.

The overall chase-success rate is then:

```python
chase_won.mean()
```

The real target is approximately:

```text
0.509
```

and the current simulator produces approximately:

```text
0.510
```

This is one of the strongest matches in the current validation.

The second-innings wear and dew mechanisms, together with the fitted chase-pressure response, now combine to produce almost exactly the archive-level chase rate.

---

### Chase success by target

A single chase-success number can hide a bad model.

A simulator could get:

```text
51%
```

overall simply because easy and hard targets happen to balance incorrectly.

I therefore split targets into bands.

The bands are approximately:

```text
below 160
160–179
180–199
200–219
220 and above
```

For each band I calculate the fraction of chases won.

This checks that the simulator gets the **difficulty gradient of chasing** approximately right.

A target of 150 should not behave like a target of 230.

---

### What the target bands currently look like

In the current simulation, chase success falls from roughly:

```text
0.85
```

for targets below 160 to approximately:

```text
0.24
```

for targets of 220 or more.

The corresponding archive values are approximately:

```text
0.81
```

and:

```text
0.21
```

at those extremes.

So the synthetic league is slightly more chase-friendly at both ends, but the overall shape is very similar.

The important behaviour is present:

> **As the target rises, successful chases become progressively less likely.**

This tells me that chase pressure is not merely shifting the global second-innings average. It is interacting with the target in a plausible way.

---

### What changed from the earlier validation

An earlier design document contained validation numbers around:

```text
mean total     190.6
score spread    35.5
chase rate       0.531
```

Those values came from a run performed before I increased the second-innings wear constant.

The document explicitly noted that the change had not yet been revalidated.

This script is the re-validation.

With the current design I now get approximately:

```text
mean total     189.2
score spread    35.0
chase rate       0.510
```

The major improvement is the chase rate.

The old world allowed chasing too easily.

After increasing the wear effect, the simulated chase rate now sits essentially on top of the real target:

```text
simulated  0.510
real       0.509
```

The first-innings spread remains somewhat too small.

I keep that discrepancy in the documented limitations rather than pretending it disappeared.

---

### Confirming the change against the original constants

I also repeated the validation using the original calibration constants.

That run produced approximately:

```text
mean total     189.1
score spread    35.0
chase rate       0.509
```

This is important because it tells me the improved chase behaviour is not an artefact of the slightly rebuilt calibration.

The current wear design works similarly under the original constants.

The design document and run report were therefore corrected to reflect the new validated numbers.

---

### Why I keep validation separate from calibration

There is an important methodological distinction here.

Files 2 through 8 measure parameters from real data.

Files 9 through 11 use those measurements and design assumptions to construct a synthetic world.

File 14 now asks whether the **consequences** of that constructed world resemble the real system.

Those are different operations.

If I used the same summary statistic both to directly force a parameter and then claimed the resulting match as independent validation, the validation would be weak.

Some design constants are intentionally chosen with aggregate targets in mind, so this validation is not a completely untouched test set in the machine-learning sense.

Its role is different.

It checks whether the complete interacting simulator remains close to all of the major cricket summaries simultaneously.

That is why I think of it as operational validation rather than predictive out-of-sample evaluation.

---

### Optional wear experiments

The script also contains a small tuning mode.

Normally:

```python
grid = [Design()]
```

so I validate the default design.

If I call the script with an extra command-line argument, it instead constructs alternative designs using:

```python
replace(
    Design(),
    wear_runs=w
)
```

for different values of `wear_runs`.

This is how I explored the effect of second-innings wear.

I can change one design constant while leaving every other mechanism fixed and see how the resulting league-level chase behaviour moves.

That is much more informative than changing several constants simultaneously and guessing which one caused the improvement.

---

### Why `dataclasses.replace()` is useful here

`Design` is a frozen dataclass.

I do not want to mutate it in place.

So:

```python
replace(
    Design(),
    wear_runs=w
)
```

creates a new design object that is identical to the default except for one chosen field.

This is useful for controlled experiments.

Conceptually I can compare:

```text
same simulator
same calibration
same seeds
same design
except one constant
```

That makes the effect of the changed parameter much easier to interpret.

---

### Why fixed seeds matter during design tuning

When I compare two wear settings, I use the same league seeds.

That creates a form of common-random-number comparison.

The two designs experience corresponding random worlds rather than entirely unrelated Monte Carlo samples.

I am not claiming that every ball remains identical after the parameter change, because altered probabilities eventually cause paths to diverge.

But using the same initial seeds still reduces unnecessary differences in how the comparison is constructed.

More importantly, it makes every reported design run reproducible.

---

### The current validation summary

The current validated world therefore looks roughly like:

```text
                     simulated      real

first-innings mean       189.2      188.5

first-innings SD          35.0       37.4

bowler wickets             5.83       5.9

chasing-side wins          0.510      0.509

over-profile correlation   0.977      1.000 reference

chase <160                 0.85       0.81

chase >=220                0.24       0.21
```

I do not expect every entry to be identical.

What I want is a world that reproduces the main statistical structure closely enough that forecasting inside it resembles forecasting cricket rather than forecasting an arbitrary toy process.

The current world does that reasonably well.

---

### What this validation tells me

The first-innings mean tells me the overall level is right.

The innings standard deviation tells me the synthetic world is still slightly too stable.

The wicket count tells me the dismissal process is close.

The overall chase rate tells me second-innings balance is now calibrated well.

The over-profile correlation tells me the timing of scoring across an innings is realistic.

The target-band analysis tells me chase difficulty changes in the correct way as the target rises.

No one summary proves the simulator is realistic.

Together they give a much stronger picture.

---

### What this validation does not prove

A good match on these six quantities does not mean the simulator reproduces every property of real T20 cricket.

I am not validating fielding patterns, individual player distributions, partnership lengths, innings momentum, over-specific wicket correlations, captaincy, injuries, toss strategy, playoff behaviour or many other real phenomena.

A simulator can agree on several aggregate summaries while still differing in untested dimensions.

So this file supports a limited claim:

> **The synthetic league reproduces the major aggregate scoring and chasing behaviours I deliberately chose to validate.**

It does not prove that the world is a complete model of real IPL cricket.

---

### Why the remaining score-spread mismatch is acceptable

The largest visible miss is:

```text
simulated first-innings SD ≈ 35.0
real first-innings SD      ≈ 37.4
```

The simulator therefore produces slightly less total-score variation than the archive.

I could increase day-to-day pitch variation or introduce another hidden effect to close that difference further.

I deliberately do not keep adding complexity merely to erase every residual.

Every new latent mechanism would also make the forecasting task more complicated and create another hidden quantity that needs justification.

At some point the gain in aggregate fit is not worth the loss in model simplicity and identifiability.

I therefore leave this difference documented.

---

### How this file fits into the pipeline

At this point the model-building path is:

```text
real IPL archive
      |
      v
measure statistical structure
      |
      v
build calibration
      |
      v
choose documented design assumptions
      |
      v
construct engine
      |
      v
generate synthetic league
      |
      v
dev/validate_world.py
      |
      +----------------------+
      |                      |
      v                      v
synthetic summaries      real targets
      |                      |
      +----------+-----------+
                 |
                 v
       operational validation
```

Only after this comparison looks reasonable do I trust the synthetic world enough to use it for the forecasting benchmark.

---

### How I think about this file

I think of `validate_world.py` as the point where I ask whether all the individually defensible pieces actually add up to a believable whole.

Calibration tells me what went into the simulator.

Validation tells me what came out.

Those are not the same question.

The central principle is:

> **I do not trust the world simply because every component has a rationale. I generate complete leagues and check whether their observable behaviour reproduces the major statistics of the real cricket system I intended to imitate.**

### References

Sargent, R. G. (2013). *Verification and validation of simulation models*. **Journal of Simulation, 7**(1), 12–24.

Davis, J., Perera, H., & Swartz, T. B. (2015). *A simulator for Twenty20 cricket*. **Australian & New Zealand Journal of Statistics, 57**(1), 55–71.

## 15. dev/run_ladder.py

### What I am trying to do

`dev/run_ladder.py` is where I stop looking at individual forecasting models in isolation and run the entire ladder on freshly generated worlds.

The purpose is to answer two questions before I evaluate any external model.

First, I want to know whether the task can actually be solved for the right statistical reasons.

Second, I want to know whether careless approaches fail by a large enough margin that the benchmark can distinguish good modelling from bad modelling.

A benchmark is not useful just because one strong reference model performs well. It needs a meaningful spread between approaches of different quality.

If the coin flip, team ratings, unregularized player model and careful reference all obtain almost the same score, then the task has very little discriminative power.

So I use the ladder as an experiment on the benchmark itself.

The world is the exam.

The forecasting tiers are the students I send through it before anyone else takes it.

---

### Why I need baselines

Forecasting research has repeatedly shown that sophisticated methods should not be judged in isolation.

Simple baselines are often surprisingly difficult to beat.

The Makridakis forecasting competitions are an important example of this discipline. The M4 competition compared 61 forecasting methods across 100,000 time series and again showed why new forecasting methods need to be evaluated against strong, understandable benchmarks rather than only against one another (Makridakis, Spiliotis & Assimakopoulos, 2020).

I apply the same idea on a smaller scale.

My ladder contains forecasters that fail in different ways.

The coin flip ignores everything.

The team model uses only team-level results.

The unshrunk player model uses the right player structure but trusts small samples too much.

The last-season-only model throws away older evidence.

The head-to-head model fits a large number of pair-specific effects that the earlier repeatability analysis says mostly do not exist.

The careful player model uses the full history with regularization.

The richer tiers then add the smaller matchup and venue-affinity structures.

This gives me a controlled spectrum from naive to careful.

---

### Reading the output

For each model I report the regret from `ExactScorer`, the skill relative to the coin flip, and the spread slope from `report()`.

The skill value is:

$$
1-\frac{R_{\text{model}}}{R_{\text{coin}}},
$$

so a positive value means the model removed some of the coin flip's regret.

A skill of:

$$
0
$$

means the model is exactly at the coin-flip baseline.

A negative value means it was worse.

A value around:

$$
0.6
$$

means it removed about 60 percent of the coin flip's avoidable regret.

I use the skill number mainly because it makes results across different worlds easier to read.

The actual proper quantity remains regret.

This is the same reference-forecast style of skill normalization discussed by Murphy (1988).

The slope is the spread diagnostic from `ExactScorer`.

A slope near one means the forecasts vary about as much as the true probabilities.

A slope below one indicates overconfidence because the forecasts spread too widely.

A slope above one indicates underconfidence because the forecasts remain too compressed toward `0.5`.

That interpretation follows the spread measure discussed by Cox (1958).

---

### Command-line configuration

The script can take both the world seeds and the number of future fixtures from the command line.

The seeds are parsed with:

```python
seeds = (
    [int(s) for s in sys.argv[1].split(",")]
    if len(sys.argv) > 1
    else [1]
)
```

So I can run something like:

```text
1,2,3
```

to evaluate three independently generated worlds.

The number of forecast fixtures is:

```python
fixtures_n = (
    int(sys.argv[2])
    if len(sys.argv) > 2
    else 30
)
```

This is useful because I can run a cheap smoke test with only a few fixtures or a larger experiment with many more.

---

### Building a fresh world

For every seed I create:

```python
league = League(seed)
```

This generates a new synthetic world using the same calibrated recipe but a different random realization.

I then generate the complete visible history:

```python
history = league.play_history()
```

and sample the future fixtures to be forecast:

```python
fixtures = league.draw_fixtures(fixtures_n)
```

At this point the forecasting models receive exactly the same type of information an external agent would receive.

The true hidden `SkillBook` remains inside the league.

---

### Computing the truth for the experiment

I calculate the future fixture probabilities using:

```python
truth = TruthEngine(
    league,
    copies=10_000
).probabilities(fixtures)
```

For the final benchmark truth I can afford a much larger Monte Carlo budget.

For this ladder experiment I use 10,000 copies because I need to evaluate many models across several worlds and want the experiment to remain practical.

The intention here is not to establish the final stored truth to maximum precision.

It is to obtain truth estimates accurate enough to rank the forecasting tiers and understand the broad separation between them.

I then construct:

```python
scorer = ExactScorer(truth)
```

so all tiers are evaluated against the same probability vector.

---

### Looking at how predictable the world is

Before fitting the models I print:

```python
truth.std()
truth.min()
truth.max()
```

This is useful because not every generated world has the same amount of predictive signal.

A world where almost every fixture has truth near:

```text
0.5
```

is fundamentally different from a world containing probabilities such as:

```text
0.25
0.40
0.65
0.78
```

In the first case there is little useful separation among teams and players.

In the second case there is much more structure for a forecaster to exploit.

Printing the standard deviation and range of the truth gives me a quick description of how much fixture-level signal exists in that particular seed.

This later becomes important when I discover that reference performance varies much more across worlds than the first three seeds suggested.

---

### Building the ladder

The ladder contains eight tiers in this script.

I begin with:

```python
CoinFlip()
```

and:

```python
TeamRatings()
```

as the two simplest baselines.

Then I create an unshrunk player model:

```python
BallModelForecaster(
    "players, no shrinkage",
    engine,
    shrink=False
)
```

This uses the public ball model but trusts noisy player estimates too strongly.

I also include:

```python
BallModelForecaster(
    "players, shrunk, last season only",
    engine,
    season_weights=[0, 0, 1]
)
```

which uses regularization but discards the first two seasons.

The main reference tier is:

```python
BallModelForecaster(
    "players, shrunk",
    engine
)
```

which uses the full visible history with the calibrated shrinkage procedure.

I then add the raw head-to-head tier:

```python
BallModelForecaster(
    "players, shrunk, raw head-to-head table",
    engine,
    head_to_head=True
)
```

and finally the two richer versions that include the lower-dimensional matchup structure and venue affinity.

All of them use the same public engine.

Only their statistical assumptions differ.

---

### Fitting and forecasting each tier

For every forecaster I call:

```python
f.fit(history)
```

and then:

```python
predict(fixtures)
```

The resulting probability vector is passed to:

```python
scorer.report(...)
```

which returns regret, skill, mean absolute probability error and slope.

The script mainly records and prints:

```text
skill
regret
slope
```

because these tell me how much useful information the model recovered and whether its probabilities were systematically too wide or too narrow.

For the `BallModelForecaster` tiers I also print the selected shrinkage scale when one exists.

That lets me see whether chronological validation preferred:

```text
0.3
1.0
3.0
```

for that particular world.

---

### Why I append results instead of overwriting them

After each forecaster finishes, I write one JSON line to:

```text
results/ladder_v2.jsonl
```

using append mode:

```python
with open(..., "a") as out:
```

This means experiments accumulate over time.

A result looks conceptually like:

```json
{
  "seed": 1,
  "name": "players, shrunk",
  "skill": 0.63,
  "regret": 0.0087
}
```

I prefer a JSON-lines file because each experiment is one independent record.

I do not have to rewrite one large JSON structure whenever I add another seed.

It also gives later analysis scripts a simple chronological experiment log.

This becomes important once I move from the first three worlds to the larger eleven-world analysis.

---

### Reporting performance across seeds

While the script runs, I keep a dictionary:

```python
table = {}
```

where every model name accumulates its skill values across worlds.

At the end I print the mean skill together with the minimum and maximum:

```text
mean skill over seeds (min to max)
```

This gives me an immediate view of both average performance and between-world variation.

A model whose average skill is strong but whose range is enormous is behaving differently from one whose performance is consistently moderate.

That distinction turned out to matter much more than I initially expected.

---

### What the first three worlds showed

The first serious experiment used three independent worlds.

The careful reference obtained skill values around:

```text
0.63
0.57
0.61
```

These were encouragingly consistent.

The unshrunk tier had roughly:

```text
1.16 to 1.88
```

times the reference regret.

The last-season-only tier was around:

```text
1.14 to 2.56
```

times reference regret.

The raw head-to-head model was dramatically worse, at approximately:

```text
2.7 to 7.6
```

times the reference regret.

The richer matchup and affinity models remained within roughly two percent of the ordinary reference.

At first glance, this was almost exactly the ladder shape I wanted.

---

### What those results told me about the task

The reference's success told me that the task is solvable.

A model using the public engine, all available history and sensible regularization can recover enough of the hidden world to forecast better than the naive baselines.

The unshrunk model told me that using the correct model family is not sufficient. A forecaster also has to treat noisy player estimates carefully.

The last-season-only tier showed that recent evidence matters, but throwing away older history loses useful information about persistent talent.

The head-to-head failure showed that adding large numbers of intuitive but weakly supported interactions can be disastrous.

The richer matchup models showed that there is no single hidden trick required to solve the task. The small matchup and venue structures help only marginally compared with simply doing the main regularized player estimation correctly.

That is exactly the sort of separation I wanted the benchmark to produce.

---

### My first conclusion about stability

From those first three seeds, I made an additional conclusion.

Because the reference skills were:

```text
0.63
0.57
0.61
```

I concluded that reference performance was fairly stable at around:

```text
0.6
```

That conclusion turned out to be wrong.

The error was not in the code.

The error was in how much I inferred from three worlds.

---

### What happened when I ran more worlds

Later, I accumulated eleven world seeds.

Across those worlds the reference skill ranged approximately from:

```text
-0.21
```

to:

```text
0.73
```

That is dramatically wider than the original three-world range.

Some synthetic worlds contain strong player and fixture differences that can be learned well from history.

Other worlds happen, by random construction, to contain much less useful predictive signal.

In those weak-signal worlds, estimating hundreds of latent parameters introduces estimation noise while there is relatively little real signal available to reward the effort.

A plug-in player model can therefore lose more from estimation error than it gains from the small underlying differences among fixtures.

In an extreme case it can perform worse than simply saying:

```text
0.5
```

for everything.

That is why the reference can have negative skill in some seeds.

---

### Why this was an important discovery

The benchmark generator is stochastic.

That means difficulty is not only determined by the code and design constants.

It is also determined by the realized hidden world.

One seed might happen to generate a league with several clearly different players, useful venue patterns and strongly separated future fixtures.

Another can generate a much flatter world.

Both follow exactly the same recipe.

The first three seeds happened to make the reference look much more stable than it really was across the population of possible worlds.

This matters enormously for grading.

If I set a universal pass threshold based on those three worlds, I could accidentally make some future worlds unfairly hard or easy.

The later bar analysis in File 17 is what finally exposes this problem systematically.

---

### The lesson from the three-world mistake

The lesson is simple:

> **A few successful pilot seeds are not enough to characterize a stochastic benchmark.**

I need to evaluate both models **and worlds**.

The forecasting algorithm is random only through its data.

The benchmark itself is also random because the hidden player and venue population changes with the seed.

So there are two sources of variation in observed benchmark performance:

```text
method quality
```

and:

```text
world difficulty.
```

The initial ladder experiment measured the first reasonably well but severely underestimated the second.

I keep this mistake documented because it directly changed the later grading design.

---

### Why a low-signal world can punish a good forecaster

Suppose almost every future fixture has true probability around:

```text
0.48 to 0.52
```

Then there is very little regret available for any model to remove relative to the coin flip.

A player-level forecaster still has to estimate batting style, quality, bowling ability, venue effects and other latent quantities from noisy historical outcomes.

Those estimates are imperfect.

If the true effects happen to cancel strongly in the future fixtures, the model can produce probabilities such as:

```text
0.42
0.58
```

when truth is actually much closer to:

```text
0.49
0.51.
```

The coin flip makes almost no error in that world.

The sophisticated model incurs regret because its estimated signal is larger than the real fixture-level signal.

So a negative reference skill is not automatically evidence that the forecaster implementation is broken.

It can be a genuine consequence of a weakly predictable realized world.

---

### Why this affects the pass bar

Originally I wanted the careful reference to provide a fairly stable performance landmark.

The wider seed experiment shows that a fixed absolute skill threshold is much harder to justify.

The same underlying forecasting method can have very different skill depending on how much signal the generated world happens to contain.

That means grading needs to account for world difficulty more carefully.

This is why the later files analyze the pass bar using many worlds rather than simply taking:

```text
reference skill ≈ 0.6
```

as a universal constant.

`run_ladder.py` is therefore not only a baseline runner.

It is also the experiment that reveals that **benchmark difficulty itself is a random variable**.

---

### Why I still keep the first three-world result

The fact that my stability conclusion was wrong does not make the first experiment useless.

The relative ordering of the careless tiers was still very informative.

The regularized full-history player model was consistently much stronger than the intended bad approaches.

The head-to-head tier was consistently poor.

The richer interaction models remained close to the reference.

So the initial experiment correctly characterized the **shape of the ladder**.

What it failed to characterize was the **population-level variability of the reference across world seeds**.

Those are different questions.

I keep both conclusions separate.

---

### The short-run check

I also use this script as a smoke test.

A small run with one world and around twelve fixtures should complete successfully.

It should print all eight tiers.

The careful reference should generally appear above the deliberately careless tiers.

I do not expect the exact numbers from such a tiny run to be stable.

With only twelve fixtures, the Monte Carlo truth itself is noisier as a summary of overall performance, and individual fixture composition matters a lot.

So the short run is checking:

```text
Does the experiment pipeline work?
```

rather than:

```text
Did I reproduce a particular benchmark score exactly?
```

That distinction prevents me from writing brittle tests around noisy small-sample numbers.

---

### Runtime is part of the experiment

For each world I record:

```python
began = time.time()
```

and print elapsed time after truth generation and again after the complete ladder.

This is useful because the reference models are computationally much heavier than the coin flip or team ratings.

The ball-model tiers repeatedly optimize many latent parameters and then perform Monte Carlo match simulation.

A benchmark can be statistically elegant and still be impractical if the baseline experiments require unreasonable resources.

So I keep runtime visible during development.

---

### Why the script uses the world's own engine

The script sets:

```python
engine = league.simulator.innings.model
```

and passes this same model into each `BallModelForecaster`.

This reinforces the fairness architecture from the earlier files.

The true league and reference models share the same public ball mechanics.

The forecaster is not given a separately reimplemented approximation of the simulator.

It uses the actual public `BallModel`.

The unknown part remains the hidden values that multiply the public directions.

That makes benchmark performance about inference rather than reverse engineering.

---

### How this file fits into the experiment pipeline

At this point the benchmark-development process looks like:

```text
League(seed)
    |
    v
generate public history
    |
    +-------------------+
    |                   |
    v                   v
future fixtures      hidden world
    |                   |
    |                   v
    |              TruthEngine
    |                   |
    |                   v
    |                true p
    |                   |
    v                   |
forecaster ladder       |
    |                   |
    v                   |
forecast q              |
    |                   |
    +---------+---------+
              |
              v
         ExactScorer
              |
              v
     regret / skill / slope
              |
              v
 results/ladder_v2.jsonl
```

This is the first place where the whole benchmark runs end to end repeatedly across independent worlds.

---

### What this script validates

`validate_world.py` asked:

> **Does the simulator look like cricket?**

`run_ladder.py` asks a different question:

> **Does the forecasting task behave like a useful benchmark?**

A realistic synthetic world is not automatically a good benchmark.

The world also needs enough learnable structure to reward careful modelling and enough statistical traps to punish careless modelling.

The ladder experiment checks exactly that.

---

### The main limitation

The largest limitation of the original ladder experiment was the number of world seeds.

Three seeds were enough to see large differences among forecasting strategies.

They were not enough to characterize the distribution of benchmark difficulty.

That became clear only after eleven worlds had been accumulated.

I therefore no longer treat the first three-world average as a stable estimate of reference performance.

The later bar analysis is the correct place to reason about pass thresholds across worlds.

---

### How I think about this file

I think of `run_ladder.py` as the **benchmark's pre-exam experiment**.

I generate fresh exams, send several known students through them and inspect both their scores and how those scores change from exam to exam.

Initially, this script convinced me that the task had the right ordering of methods.

Later, the accumulated runs taught me something more important: the difficulty of the exam itself changes materially with the generated world.

The central principle is:

> **Before judging an external model, I first verify that the benchmark rewards the modelling choices I intend it to reward, punishes the shortcuts I intend it to punish, and remains understandable across the random worlds produced by the generator.**

### References

Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2020). *The M4 Competition: 100,000 time series and 61 forecasting methods*. **International Journal of Forecasting, 36**(1), 54–74.

Murphy, A. H. (1988). *Skill scores based on the mean square error and their relationships to the correlation coefficient*. **Monthly Weather Review, 116**(12), 2417–2424.

Cox, D. R. (1958). *Two further applications of a model for binary regression*. **Biometrika, 45**, 562–565.

## 16. dev/make_task_data.py

### What I am trying to do

`dev/make_task_data.py` is the script that turns the simulator into the actual benchmark.

By this point I already know how to generate one synthetic league, expose its public history, hide its latent state, compute future fixture probabilities and run a reference forecaster. What I still need is a reproducible collection of worlds that can actually be used for grading.

This script builds those worlds.

I use eight league seeds:

```text
visible    -> 101
heldout_a  -> 202
heldout_b  -> 303
heldout_c  -> 404
heldout_d  -> 505
heldout_e  -> 606
heldout_f  -> 707
heldout_g  -> 808
```

The important idea is that only one of those worlds is visible during development.

The remaining seven are held out for grading.

For each world I create the public task folder that an agent is allowed to inspect, the high-precision true probabilities used by the grader, the reference forecaster's regret, the careless baseline regrets and the per-fixture forecasts produced by those tiers.

So this file is where the pieces from the earlier files finally become one complete task.

---

### The graded worlds

I define the graded worlds explicitly:

```python
LEAGUES = {
    "visible": 101,
    "heldout_a": 202,
    "heldout_b": 303,
    "heldout_c": 404,
    "heldout_d": 505,
    "heldout_e": 606,
    "heldout_f": 707,
    "heldout_g": 808,
}
```

I deliberately use named worlds rather than relying on an implicit sequence of seeds.

That makes the benchmark easier to inspect.

If the grader reports a problem on:

```text
heldout_e
```

I immediately know which generated world it refers to and which seed reproduces it.

The names also make the information boundary explicit.

`visible` is the world that may be inspected during development.

The `heldout_*` worlds are grading worlds.

---

### What one build produces

For every league I generate two broad classes of artifact.

The first is the public league folder produced by `save_league()`.

That folder contains the eight files from File 12:

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

These are the files a solver is allowed to use.

The second class contains private grading information.

That lives under:

```text
task_data/private/<world>/
```

and includes:

```text
truth.csv
tiers.csv
reference.json
```

The separation is intentional.

The public folder contains evidence.

The private folder contains the quantities needed to judge forecasts against hidden truth.

---

### Generating the world

For each seed I create:

```python
league = League(seed)
```

then generate the full historical record:

```python
history = league.play_history()
```

and draw the future fixtures:

```python
fixtures = league.draw_fixtures(args.fixtures)
```

The default number of fixtures is:

```text
24
```

so each world contributes 24 graded probability forecasts.

Across eight worlds, that gives:

$$
8\times24=192
$$

graded fixtures.

This is the 192-fixture evaluation set that appears in the scoring discussion.

---

### Writing the public world first

I immediately call:

```python
save_league(
    out / "leagues" / name,
    history,
    fixtures
)
```

This freezes the public representation of the world.

From that point onward I want the reference models to behave as if they were ordinary task solvers.

I therefore do something deliberately important later in the script: I load the world back from those public files instead of continuing to use the original in-memory `History`.

That avoids accidentally giving my own benchmark models information that the agent would never receive.

---

### Computing the truth

The private truth is calculated with:

```python
TruthEngine(
    league,
    copies=args.copies
).probabilities(fixtures)
```

The default is:

```text
100,000 copies per fixture
```

This means each future fixture is simulated many times using the true hidden `SkillBook`.

The resulting value is my estimate of:

$$
P(\text{home side wins}\mid\text{true hidden world}).
$$

I then write those probabilities to:

```text
truth.csv
```

with one row per fixture.

Conceptually the file contains:

```text
fixture      p_home
10000        ...
10001        ...
10002        ...
...
```

This file is private because it contains the answer the forecaster is trying to approximate.

---

### Why I use 100,000 Monte Carlo copies

The truth itself is produced by Monte Carlo simulation.

For a probability estimate based on $N$ independent draws, the standard error is:

$$
\sqrt{
\frac{p(1-p)}{N}
}.
$$

The maximum occurs at:

$$
p=0.5,
$$

so at:

$$
N=100000
$$

the worst-case standard error is:

$$
\sqrt{
\frac{0.25}{100000}
}
\approx
0.00158.
$$

So even in the hardest case, the uncertainty in a fixture probability is only around:

```text
0.0016
```

or sixteen basis points.

That is much smaller than the typical forecasting errors I am trying to distinguish.

---

### Why that amount of truth error is acceptable for regret

The regret for a fixture depends on the true probability $p$ and forecast $q$.

Its sensitivity to a small error in $p$ is related to:

$$
\operatorname{logit}(p)
-
\operatorname{logit}(q).
$$

For a reasonably good forecast this difference might be on the order of:

```text
0.3
```

so a truth-probability error around:

```text
0.0016
```

moves fixture regret by only around:

```text
0.0005
```

in a random direction.

Then I average across 192 fixtures.

Because the individual truth-simulation errors fluctuate rather than all pushing regret in the same direction, their effect on the final total is much smaller still.

The design estimate is that this contributes only around a few tenths of a percent of the reference's total regret.

That is why I call these probabilities "exact truth" for grading purposes even though they are technically high-precision Monte Carlo estimates.

The Monte Carlo principle itself goes back to Metropolis and Ulam (1949).

---

### Reloading the public data before fitting anything

After writing the public folder and the private truth, I intentionally do:

```python
history, fixtures = load_league(
    out / "leagues" / name
)
```

This line is one of the most important fairness checks in the script.

The world generator has access to hidden player values, venue values and current form.

The reference forecaster must not.

By discarding the original public objects and loading the files exactly as a solver would, I guarantee that the reference and baseline tiers are fitted on the serialized public representation.

They therefore see:

```text
the same balls
the same matches
the same players
the same venues
the same line-ups
the same fixtures
```

as an external solution.

They do not see the original league's private arrays.

---

### Building the reference

The reference tier is:

```python
BallModelForecaster(
    "reference",
    model,
    copies=REFERENCE_COPIES
)
```

with:

```text
REFERENCE_COPIES = 4000
```

The truth uses 100,000 copies because it establishes the grading target.

The reference only uses 4,000 because it is itself a practical forecasting method.

That distinction matters.

The grader should have much less Monte Carlo uncertainty than the model being benchmarked against it.

The reference is therefore deliberately computationally cheaper and noisier than the stored truth.

---

### Building the careless tiers

Unless I run the script with:

```text
--no-tiers
```

I also build several baseline forecasters.

These include the coin flip, team ratings, the unshrunk player model, the last-season-only player model and the raw head-to-head model.

These are the same conceptual tiers I examined in Files 13 and 15.

Their purpose here is different from the experimental ladder run.

At task-build time I want their forecasts stored permanently alongside the reference.

That lets the grader later compare an external submission not only with the pass threshold but with recognizable failure modes.

---

### `tiers.csv`

For every fixture I store the probability forecast from every tier in:

```text
tiers.csv
```

Conceptually it looks like:

```text
fixture   reference   coin flip   team ratings   no shrinkage   ...
10000       ...          0.5          ...             ...
10001       ...          0.5          ...             ...
...
```

This file is private.

It is not needed to calculate the candidate's regret.

Its purpose is diagnostic.

If a submission behaves very similarly to the raw head-to-head tier, the grader can potentially report that resemblance.

Likewise, if its forecasts look like team ratings or the no-shrinkage model, that can make a failure much easier to interpret.

So `tiers.csv` turns the benchmark from a single pass/fail number into something that can say more about *how* a method failed.

---

### `reference.json`

I also write:

```text
reference.json
```

which contains the quantities the pass rule needs.

It includes the reference regret, the coin-flip regret, the number of truth copies used and the regrets of all stored tiers.

Conceptually:

```json
{
  "regret": ...,
  "coin_flip_regret": ...,
  "truth_copies": 100000,
  "tiers": {
    "reference": ...,
    "coin flip": ...,
    "team ratings": ...,
    "no shrinkage": ...,
    "last season only": ...,
    "raw head-to-head": ...
  }
}
```

This means the grader does not have to rerun the reference model every time a candidate submission is evaluated.

The expensive baseline computation is performed once during task construction and committed as part of the private grading data.

---

### Why one visible world is not enough

The agent can inspect the visible world.

That creates a risk.

A method could accidentally or deliberately become specialized to the particular players, venues, fixture structure or statistical quirks of seed 101.

If I graded only on that same world, I would have difficulty separating a genuinely general forecasting method from one that had simply adapted itself to the visible instance.

The held-out worlds protect against that.

The same forecasting code must work when:

```text
the player skills are different
the venue values are different
the histories are different
the future fixtures are different
```

but the generative recipe is unchanged.

This is the ordinary logic of holdout evaluation.

Dwork and colleagues' reusable-holdout work studies the more difficult situation where a holdout is repeatedly queried and therefore gradually leaks information.

My setup is simpler.

The hidden worlds are intended to be used by the grader rather than repeatedly exposed for development.

The basic principle still applies: evaluation is more meaningful when it occurs on data that did not drive the solution.

---

### Why I use eight worlds

The number eight is not arbitrary.

The bar analysis in File 17 showed that grading one world at a time is noisy.

Reference regret itself contains Monte Carlo variation because its predictions are based on match simulation.

More importantly, the difficulty of individual generated worlds varies substantially.

Some worlds contain more learnable signal than others.

By summing regret across eight independent worlds, I average over both sources of instability.

The empirical analysis showed that the relative simulation noise of the combined score falls to roughly:

```text
1.1%
```

which is small enough to support a meaningful tolerance.

So the eight-world design is partly a statistical decision about grading stability.

---

### Idempotent task construction

The complete build is not cheap.

Before rebuilding a world I therefore look for:

```text
private/<world>/reference.json
```

and check whether it was already created using the requested truth precision.

If:

```python
truth_copies == args.copies
```

and the requested tier information is already available, I keep the existing world.

The script prints:

```text
already built ... kept
```

and continues to the next seed.

This makes the build idempotent in practical use.

If the first three worlds have already been generated and I later add five more, I do not have to spend time rebuilding the first three.

This is exactly how the later worlds could be added without recreating the earlier outputs.

---

### Why idempotence also helps reproducibility

Avoiding unnecessary rebuilds is not only an optimization.

Generated stochastic artifacts can be sensitive to code and numerical changes.

Once I have intentionally built and checked one benchmark world, preserving that artifact prevents an unrelated rerun from silently replacing it.

The seed makes regeneration possible, but keeping an already validated artifact is even safer when I want a fixed benchmark.

So the build script behaves more like a dataset builder than a temporary simulation command.

---

### Small-scale build check

For development I can run the script with a much smaller truth budget and fixture count.

For example:

```text
2,000 truth copies
5 fixtures
--no-tiers
```

This is not intended to produce grading-quality probabilities.

It is a smoke test for the complete build pipeline.

The check verifies that all eight public folders are created, the private directories exist, `truth.csv` and `reference.json` are written and the script can finish from beginning to end.

The small build completes in under a minute.

That means I can test changes to the pipeline without waiting for the full benchmark generation.

---

### Full build cost

The full configuration uses approximately:

```text
8 worlds
24 fixtures per world
100,000 truth copies per fixture
4,000 reference copies per fixture
plus the careless tiers
```

and takes roughly:

```text
25 minutes
```

in the recorded build environment.

That cost is acceptable because it is an offline operation.

I build the grading data once.

A candidate does not have to regenerate it.

---

### Why this repository's generated worlds differ slightly from the pilot

The calibration reconstructed in this repository differs from the original piloted calibration by up to approximately:

```text
0.0007
```

in some values.

As I saw in `world.py`, a tiny probability difference can eventually cause one categorical random draw to flip.

Once that happens, the match path can diverge.

So rebuilding seed 101 using this repository's calibration does not necessarily recreate every historical delivery from the pilot.

The worlds produced here are internally consistent with this repository's own calibration and truth.

They therefore form a complete benchmark in their own right.

But they are not automatically the exact same worlds on which the six original pilots ran.

That distinction matters when I talk about reproducibility.

---

### Reproducing the original pilot

The generator code itself can reproduce the piloted visible world when it is supplied the original calibration artifact.

File 12 checked this at the public-file level.

With the original constants, the seed-101 world serialized to files that were byte-identical to the visible pilot world.

So there are two separate claims.

This repository demonstrates that the generation pipeline can reproduce the original task when given the original constants.

Its default rebuilt calibration creates a slightly different, but self-consistent, benchmark.

I do not collapse those two claims into one.

---

### How I think about this file

I think of `make_task_data.py` as the point where the project stops being a simulator repository and becomes an actual evaluation dataset.

Before this file I have recipes.

After this file I have fixed worlds, fixed public evidence, fixed hidden truth, fixed reference scores and fixed diagnostic baselines.

The central idea is:

> **I generate the entire graded dataset ahead of time, expose only the public side of each world, compute its hidden truth at much higher precision than any ordinary forecaster, and fit every internal benchmark through exactly the same public loading path available to an external solver.**

### References

Metropolis, N., & Ulam, S. (1949). *The Monte Carlo method*. **Journal of the American Statistical Association, 44**(247), 335–341.

Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., & Roth, A. (2015). *The reusable holdout: Preserving validity in adaptive data analysis*. **Science, 349**(6248), 636–638.

## 17. dev/bar_analysis.py

### What I am trying to do

`dev/bar_analysis.py` is where I decide how much worse than the reference a submission is allowed to be before I call it a failure.

I do not want to invent that tolerance after seeing external model results.

I want to understand the sources of variation first, choose a rule using separate development worlds and then commit the rule before the pilots begin.

There are two quantities I need to understand.

The first is **noise**.

Even if I fit exactly the same reference model twice, its final fixture probabilities can differ slightly because `MatchSimulator` is Monte Carlo.

That means reference regret itself moves when I change only the simulation seed.

Any grading tolerance must be large enough that this harmless Monte Carlo fluctuation cannot make the reference fail against itself.

The second quantity is **separation**.

The tolerance must remain small enough that deliberately careless forecasting methods still fail.

If I make the threshold so generous that the no-shrinkage model passes, the task no longer tests the distinction I designed it to test.

So the basic problem is:

```text
tolerance must be large enough for noise
              but
tolerance must be small enough to reject careless tiers
```

This script measures both sides before I choose the pass rule.

---

### Why I use different worlds for bar design

The bar-analysis worlds begin at:

```text
1001
```

rather than using any of the graded seeds:

```text
101, 202, ..., 808
```

The default eight analysis worlds are therefore:

```text
1001
1002
1003
1004
1005
1006
1007
1008
```

These worlds are never used for candidate grading.

I want the tolerance to be chosen using development data that is separate from the eventual evaluation data.

Otherwise I could unconsciously tune the bar to peculiarities of the exact worlds on which candidates will be judged.

So even the benchmark threshold has its own holdout discipline.

---

### Generating one analysis world

For each seed I build the league normally:

```python
league = League(seed)
```

play its public history:

```python
history = league.play_history()
```

and draw the future fixtures:

```python
fixtures = league.draw_fixtures(
    args.fixtures
)
```

I then calculate a relatively high-precision truth using:

```python
TruthEngine(
    league,
    copies=args.copies
)
```

with a default of:

```text
40,000 truth copies
```

per fixture.

The goal here is not to build the final dataset.

It is to study the behaviour of the grading rule.

---

### Fitting the reference once

For each world I fit one reference forecaster:

```python
ref = BallModelForecaster(
    "reference",
    model,
    copies=4000
).fit(history)
```

The fitted parameters remain fixed for the noise experiment.

That is important.

I do not want to mix optimization variability, training-data variability and simulation variability.

I specifically want to ask:

> **If the fitted model is identical, how much does its reported regret change only because I used a different Monte Carlo seed for the fixture simulations?**

So I fit once and then predict repeatedly.

---

### Measuring simulation noise

I run the fitted reference four times.

Before each run I change:

```python
ref.seed
```

to:

```text
400000
410000
420000
430000
```

through:

```python
400_000 + 10_000 * k
```

Everything else remains the same.

The historical data are identical.

The fitted hidden-parameter estimates are identical.

The future fixtures are identical.

The truth is identical.

Only the Monte Carlo draws used by the reference predictor change.

I collect the four regrets in:

```python
repeats
```

and calculate:

```python
np.std(repeats) / repeats[0]
```

as a relative noise measure.

This tells me how large the ordinary prediction-simulation variation is compared with the reference's own regret.

---

### Why I express the noise relative to regret

An absolute regret fluctuation such as:

```text
0.0002
```

does not mean the same thing in every world.

If reference regret is:

```text
0.020
```

then that movement is tiny.

If reference regret is:

```text
0.002
```

the same movement is much more important.

So I divide the standard deviation of the repeated runs by the baseline reference regret.

This produces a percentage such as:

```text
5.9%
```

which tells me directly how much the reference score can move relative to itself.

That is the scale the tolerance also uses.

---

### Why I initially thought about three times the noise

If the repeated reference score behaved approximately like a stable random measurement, a tolerance around three standard deviations would make self-failure rare.

That is why the script prints:

```text
A tolerance should be at least three times that
```

after finding the largest observed relative noise across worlds.

This is a conservative heuristic rather than a formal theorem about the complete grading distribution.

Its purpose is practical.

I do not want a pass rule sitting so close to Monte Carlo noise that merely rerunning the same competent solution could cross it.

---

### Measuring the careless tiers

I next fit the two closest careless models.

The first is:

```python
BallModelForecaster(
    "x",
    model,
    shrink=False,
    copies=4000
)
```

which is the player model without proper regularization.

The second is:

```python
BallModelForecaster(
    "x",
    model,
    season_weights=[0, 0, 1],
    copies=4000
)
```

which keeps the shrinkage structure but uses only the final visible season.

I calculate their regrets and divide each by the baseline reference regret.

So if:

```text
no shrinkage ×1.30
```

that means:

$$
R_{\text{unshrunk}}
=
1.30R_{\text{reference}}.
$$

It has 30 percent more regret than the reference.

I also calculate:

```python
scorer.coin / repeats[0]
```

to see where the coin flip lies relative to reference regret.

---

### Why ratios are useful

The absolute regret scale differs from world to world.

A highly predictable world may give both the coin flip and the reference substantial regret separation.

A nearly flat world may give everyone very small absolute regret.

Expressing the careless tiers as multiples of the reference makes the question directly relevant to the intended grading rule.

I am asking:

> **How much worse than the reference is this failure mode in this particular world?**

That is exactly what a multiplicative tolerance needs to know.

---

### What I originally hoped to do

The first grading idea was to apply the tolerance independently on every world.

Conceptually the rule would have looked like:

$$
R_{\text{submission},w}
\le
(1+t)
R_{\text{reference},w}
$$

for every world $w$.

This initially seemed attractive.

It would require a candidate to perform reasonably well everywhere rather than compensating for one weak world with another strong one.

But the bar analysis showed that this rule was statistically unstable.

---

### The worst observed simulation noise

On one of the eight analysis worlds, repeated predictions from the exact same fitted reference produced relative regret variation of approximately:

```text
5.9%
```

That means a conservative three-noise tolerance would be about:

$$
3\times5.9\%
\approx
17.7\%
$$

or roughly:

```text
18%
```

If I wanted the reference to pass reliably on that world, a per-world tolerance substantially below this would be uncomfortable.

This is already larger than I originally expected.

---

### The problem with an 18 percent per-world tolerance

The nearest careless tier was sometimes only:

```text
6 to 7 percent
```

worse than the reference on an individual world.

That means the two requirements conflict.

To safely absorb the observed reference noise I might need something like:

```text
18%
```

but to reject the unshrunk tier on that world I would need the tolerance below roughly:

```text
6–7%
```

No single number can do both.

The problem is not solved by choosing a cleverer percentage.

The per-world grading formulation itself is wrong.

---

### The second problem: sometimes the coin flip beats the reference

The analysis exposed an even deeper issue.

In one of the eight worlds, the coin flip had lower regret than the reference.

This matches what I later observed in the larger ladder experiments.

Some generated worlds contain so little useful predictive variation that fitting many player parameters can cost more through estimation noise than it earns through signal.

So even a well-designed reference is not guaranteed to beat:

```text
q = 0.5
```

on every individual random world.

That makes a rule requiring reference-like performance **on every world** fundamentally brittle.

---

### Why the per-world rule was abandoned

At this point I had two independent arguments against grading world by world.

The first was Monte Carlo prediction noise.

The second was variation in intrinsic world predictability.

Together they meant that a candidate could fail one world for reasons that had little to do with the quality distinction I wanted to test.

So I changed the grading statistic.

Instead of comparing each world's regret separately, I sum regret across the eight graded worlds and apply one tolerance to the total.

---

### The total-regret rule

Conceptually I compare:

$$
\sum_{w=1}^{8}
R_{\text{submission},w}
$$

with:

$$
\sum_{w=1}^{8}
R_{\text{reference},w}.
$$

The pass rule can then take the form:

$$
\sum_wR_{\text{submission},w}
\le
1.10
\sum_wR_{\text{reference},w}.
$$

Now an unusually difficult or weak-signal world is only one component of the evaluation.

It cannot dominate the entire verdict.

Likewise, Monte Carlo noise from one world is averaged with independent noise from the others.

This is much closer to what I actually want to test:

> **Does the method perform at approximately reference quality across a population of generated worlds?**

rather than:

> **Did it happen to beat a noisy threshold on every individual seed?**

---

### Why summing independent worlds reduces noise

The graded worlds are generated independently.

Their Monte Carlo prediction errors are therefore largely independent as well.

When independent noisy quantities are summed, their variances add while the signal itself grows linearly with the number of worlds.

So relative noise falls approximately like:

$$
\frac{1}{\sqrt{W}},
$$

where $W$ is the number of worlds.

For:

$$
W=8,
$$

this gives a substantial reduction.

The empirical analysis estimated the relative noise of the combined eight-world score at about:

```text
1.1%
```

rather than the almost six percent worst-case value seen on a single world.

That changes the grading problem completely.

---

### Separation after summing the worlds

When regret is aggregated across the eight analysis worlds, the careless tiers separate much more cleanly.

The unshrunk tier has approximately:

```text
1.30 × reference regret
```

the last-season-only tier approximately:

```text
1.93 × reference regret
```

and the coin flip approximately:

```text
1.90 × reference regret.
```

Now I have a useful gap.

The closest careless tier is around 30 percent worse than the reference in total.

The stochastic noise of the sum is only around one percent.

That leaves enough room to choose a tolerance that is both safe and discriminative.

---

### Why I choose a ten-percent tolerance

The final design uses a tolerance of approximately:

```text
10%
```

on the total eight-world regret.

Compared with the estimated:

```text
1.1%
```

simulation noise of the combined score, ten percent is roughly nine times larger.

So ordinary Monte Carlo variation should not move a reference-quality method across the threshold.

At the same time, the nearest deliberately careless tier sits around:

```text
30%
```

above the reference.

So a ten-percent bar remains substantially below it.

It falls roughly a third of the way from the reference to that nearest known bad tier.

That gives the threshold both a noise justification and a behavioural justification.

---

### Why I do not tune the tolerance after model pilots

The most important procedural decision is that this analysis happens **before** the external model pilots.

If I ran several candidate models, saw that one scored 13 percent above the reference and then decided that the tolerance should be 15 percent, the benchmark would no longer be independently evaluating that model.

The threshold would have been influenced by the answer I wanted to classify.

That type of undisclosed analytical flexibility is exactly the problem discussed by Simmons, Nelson and Simonsohn (2011): when researchers can choose analyses, stopping rules or thresholds after seeing outcomes, apparently strong results can be manufactured surprisingly easily.

I want the opposite.

I want the grading rule fixed before the candidate results exist.

---

### Why I treat this like preregistration

Nosek, Ebersole, DeHaven and Mellor (2018) describe preregistration as committing important analytical decisions before observing the results those decisions will be used to judge.

That is the discipline I apply here.

I write down:

```text
which worlds determine the tolerance
how noise is measured
which careless tiers must remain outside the bar
whether grading is per-world or aggregated
what tolerance is used
```

before the pilot model results are available.

The goal is not bureaucratic documentation.

The goal is to remove my own ability to move the goalposts after seeing an inconvenient score.

---

### The original timing record

In the original repository, the final grading rule was committed at:

```text
16:39 on 19 September
```

and the first pilot began at:

```text
16:45
```

the same day.

The commit hash is recorded separately in `DECISIONS.md`.

The important point is chronological.

The rule existed in version control before the first external pilot produced a result.

That gives me evidence that the pass threshold was not retroactively chosen to make a particular pilot pass or fail.

---

### Why I preserve `DECISIONS.md`

The code tells me what the benchmark currently does.

It does not necessarily tell me why an earlier design was rejected.

For the grading rule, that history matters.

`DECISIONS.md` records that the initial per-world rule looked reasonable, that the bar analysis showed it was unsound, and that the rule was changed to total regret before the model pilots.

That decision trail is useful because otherwise the final aggregated rule could look arbitrary.

The analysis shows that it was a response to a concrete statistical problem discovered before evaluation.

---

### The command-line controls

The script accepts:

```text
--leagues
--copies
--fixtures
```

with defaults:

```text
8 analysis leagues
40,000 truth copies
24 fixtures per league
```

This lets me run a cheap development version without changing the code.

For example, I can use one world, fewer truth simulations and eight fixtures simply to check that the analysis executes correctly.

The full numbers are only meaningful at the larger configuration.

---

### The smoke test

A small one-world run at around:

```text
2,000 copies
8 fixtures
```

should print the main summary lines describing reference regret, simulation noise and the careless-tier ratios.

I do not expect those small-scale ratios to reproduce the final table.

With so few fixtures and such a small truth budget, sampling variation dominates.

The purpose of the smoke test is only to verify the analysis pipeline.

The full run is what supports the actual grading decision.

---

### What this file taught me about benchmark design

Initially I thought the main problem was choosing the right percentage tolerance.

The analysis showed that the deeper question was choosing the right **aggregation unit**.

No reasonable per-world tolerance could simultaneously absorb the reference's own noise and reject the nearest careless tier.

The correct fix was not to adjust 10 percent to 12 percent or 18 percent.

It was to stop grading each stochastic world independently.

This is an important benchmark-design lesson.

A threshold cannot repair a statistic whose variance is too high relative to the separation I care about.

Sometimes the evaluation statistic itself has to change.

---

### Why eight graded worlds now make sense

The eight-world design in `make_task_data.py` is therefore directly connected to this analysis.

Multiple worlds protect against overfitting to the visible seed.

They also average over random differences in how predictable individual worlds happen to be.

And they reduce Monte Carlo scoring noise enough that a reference-relative tolerance becomes useful.

So the number of worlds is not merely a security decision.

It is also part of the statistical design of the grader.

---

### How Files 16 and 17 fit together

`make_task_data.py` asks:

> **What exact worlds, truths and reference outputs will the grader use?**

`bar_analysis.py` asks:

> **How should those outputs be combined into a stable pass rule?**

The two files therefore sit on opposite sides of the same grading design.

Conceptually:

```text
fresh non-graded worlds
        |
        v
  bar_analysis.py
        |
        v
choose + commit grading rule
        |
        v
 make_task_data.py
        |
        v
eight fixed graded worlds
        |
        v
candidate evaluation
```

The tolerance is decided on worlds outside the graded set.

The graded worlds are then built under the already chosen rule.

That ordering is deliberate.

---

### How I think about this file

I think of `bar_analysis.py` as the place where I validate the **grader itself**.

`validate_world.py` validates the cricket world.

`run_ladder.py` validates the forecasting task.

`bar_analysis.py` validates the decision rule that turns forecasting performance into pass or fail.

The central principle is:

> **I choose the pass rule from independent synthetic worlds before seeing external model performance, and I aggregate enough worlds that Monte Carlo noise and random world difficulty are small compared with the performance gap between careful and deliberately careless forecasting methods.**

### References

Simmons, J. P., Nelson, L. D., & Simonsohn, U. (2011). *False-positive psychology: Undisclosed flexibility in data collection and analysis allows presenting anything as significant*. **Psychological Science, 22**(11), 1359–1366.

Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). *The preregistration revolution*. **Proceedings of the National Academy of Sciences, 115**(11), 2600–2606.