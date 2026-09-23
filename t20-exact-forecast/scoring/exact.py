import numpy as np

class ExactScorer:
    def __init__(self, truth, floor = 0.002):
        self.truth = np.asarray(truth, float)
        self.floor = floor
        self.coin = self.regret(np.full(len(self.truth), 0.5))
    
    def regret(self, forecast):
        # p is the truth, q is the forecast after splitting
        p = self.truth
        q = np.clip(np.asarray(forecast, float), self.floor, 1 - self.floor)
        # expected log loss above the best possible, averaged over fixtures
        return float(np.mean(p * np.log(p / q) + (1 - p) * np.log((1 - p) / (1 - q))))

    def skill(self, forecast):
        # share of the coin flip's regret that this forecast removes
        return 1.0 - self.regret(forecast) / self.coin

    def report(self, forecast):
        # regret and skill, plus two descriptions: mean absolute error in probability, and the calibration slope.
        # The slope regresses logit(truth) on logit(forecast): 1 means the forecast spreads exactly as much as the truth,
        # below 1 means overconfident (forecasts vary more than the truth), above 1 under-confident.
        q = np.clip(np.asarray(forecast, float), self.floor, 1 - self.floor)
        logit = lambda x: np.log(x / (1 - x))
        slope = float(np.polyfit(logit(q), logit(self.truth), 1)[0]) if np.ptp(q) > 1e-9 else float("nan")
        return {"regret": self.regret(q), "skill": self.skill(q), "mean_abs_error": float(np.abs(q - self.truth).mean()), "slope": slope}