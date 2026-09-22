import numpy as np

class ExactScorer:
	def __init__(self, truth, floor = 0.002):
	self.truth = np.asarray(truth, floor)
	self.floor = floor
	self.coin = self.regret(np.full(len(self.truth), 0.5))
	
	def regret(self, forecast):
	# p is the truth, q is the forecast after splitting
	p = self.truth
	q = np.clip(np.asarray(forecast, float), self.floor, 1 - self.floor)
	# expected log loss above the best possible, averaged over fixtures
	return float(np.mean(p