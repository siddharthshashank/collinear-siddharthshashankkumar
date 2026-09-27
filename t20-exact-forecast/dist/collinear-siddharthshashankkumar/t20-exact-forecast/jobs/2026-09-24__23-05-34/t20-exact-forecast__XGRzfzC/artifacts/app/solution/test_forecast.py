"""Run with: python solution/test_forecast.py"""
import unittest
from types import SimpleNamespace
from forecast import Estimator, np, pd, linalg
from predict import Predictive
from engine.model import (PlayerTable, VenueTable, History, Fixture, SkillBook,
                          InningsSimulator, load_public_model)


class ForecastChecks(unittest.TestCase):
    def test_likelihood_derivatives(self):
        rng = np.random.default_rng(441)
        n,p = 240,22
        players = PlayerTable(np.arange(p)%3,np.arange(p)%2,np.arange(p)%2)
        venues = VenueTable(np.array([0,1]),np.array([1,2]))
        balls = pd.DataFrame(dict(season=rng.integers(0,3,n),
            match=rng.integers(0,9,n),innings=rng.integers(1,3,n),
            over=rng.integers(0,20,n),ball=rng.integers(0,6,n),
            batting_team=rng.integers(0,2,n),venue=rng.integers(0,2,n),
            batter=rng.integers(0,p,n),bowler=rng.integers(11,p,n),
            outcome=rng.integers(0,6,n),position=rng.integers(0,11,n),
            wickets_before=rng.integers(0,10,n),runs_before=rng.integers(0,150,n),
            target=np.full(n,171)))
        fit = Estimator(History(balls,pd.DataFrame(),players,venues,seasons=3))
        fit.Q = fit.precision()
        fit.x = rng.normal(0,.03,fit.npar)
        direction = rng.normal(size=fit.npar)
        direction /= np.linalg.norm(direction)
        eps = 1e-4
        f,g = fit.objective(fit.x)
        plus,gplus = fit.objective(fit.x+eps*direction)
        minus,gminus = fit.objective(fit.x-eps*direction)
        self.assertAlmostEqual((plus-minus)/(2*eps),g@direction,places=6)
        H = fit.hessian().toarray()
        np.testing.assert_allclose((gplus-gminus)/(2*eps),H@direction,atol=1e-7)
        correction = fit.curvature_correction(linalg.inv(H),fit.probabilities(fit.x)[1])
        x = fit.x.copy()
        fit.x = x+eps*direction
        lp = np.linalg.slogdet(fit.hessian().toarray())[1]/2
        fit.x = x-eps*direction
        lm = np.linalg.slogdet(fit.hessian().toarray())[1]/2
        self.assertAlmostEqual((lp-lm)/(2*eps),direction@H@correction,places=6)

    def test_simulator_matches_engine(self):
        rng = np.random.default_rng(18)
        P,V = 22,2
        players = PlayerTable(np.arange(P)%3,np.arange(P)%2,np.arange(P)%2)
        venues = VenueTable(np.array([99,1]),np.array([1,2]))
        book = SkillBook(players,venues,rng.normal(0,.3,P),rng.normal(0,.2,P),
            rng.normal(0,.1,P),rng.normal(0,.2,P),rng.normal(0,.2,P),
            rng.normal(0,.08,(2,2)),rng.normal(0,.08,(2,3)),rng.normal(0,.1,V),
            rng.normal(0,.1,V),rng.normal(0,.1,(P,V)),.1,.1,.25,.04)
        model = load_public_model()
        pred = object.__new__(Predictive)
        pred.m = model
        pred.fit = SimpleNamespace(h=SimpleNamespace(players=players,venues=venues),m=model)
        pred.K = 1
        for name in ['style','quality','split','kind','bowl_quality','affinity']:
            setattr(pred,name,getattr(book,name)[None])
        pred.type = book.type_table[None]
        pred.pitch = book.pitch_table[None]
        pred.venue = book.venue_level[None]
        pred.dew = (book.venue_dew-book.wear)[None]
        pred.home = np.array([[book.home_lift]])
        pred.era = np.array([[book.era]])
        pred.day_sd = book.day_sd
        xi,five = np.arange(11),np.arange(17,22)
        sim = InningsSimulator(model)
        n = 1000
        day = rng.normal(0,.25,n)
        for venue in [0,1]:
            for chasing in [False,True]:
                target = np.full(n,177) if chasing else None
                expected = sim.play(*book.cards(xi,1,five,venue),
                    book.shift(venue,chasing)+day,n,np.random.default_rng(328),target)
                actual = pred.play(pred.base(xi,1,five,venue,chasing),day,n,
                    np.random.default_rng(328),target)
                np.testing.assert_array_equal(expected,actual)
        fixture = Fixture(1,3,0,1,0,xi,five,xi,five)
        self.assertEqual(pred.probability(fixture,1024),.5)


if __name__ == '__main__':
    unittest.main()
