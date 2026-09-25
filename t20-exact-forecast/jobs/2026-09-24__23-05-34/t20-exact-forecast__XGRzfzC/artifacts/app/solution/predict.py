"""Posterior predictive match simulation with paired toss orders."""
import numpy as np
from scipy import linalg


class Predictive:
    def __init__(self,fit,draws=1024,seed=761023):
        self.fit = fit
        self.m = fit.m
        self.K = draws
        rng = np.random.default_rng(seed)
        def normal(shape):
            z = rng.standard_normal((draws//2,)+shape)
            return np.concatenate((z,-z),axis=0)
        # Joint samples preserve the important posterior correlations between
        # player, venue, match, and population effects.
        z = normal((fit.npar,))
        x = fit.x-fit.mean_correction+linalg.solve_triangular(fit.L[0].T,z.T,lower=False,check_finite=False).T
        def v(name):
            g=fit.groups[name]
            return x[:,g['start']:g['end']]
        def future(name):
            g = fit.groups[name]
            a,b = g['variance']
            cross = a+b*.55**(fit.S-np.arange(fit.S))
            weights = linalg.solve(fit.covariance(g),cross,assume_a='pos')
            residual = max(a+b-cross@weights,0.)
            return v(name).reshape(draws,-1,fit.S)@weights + np.sqrt(residual)*normal((g['size']//fit.S,))
        p = fit.h.players
        self.style = v('style')+v('bat_mean')[:,p.role]+v('bat_global')
        self.quality = future('quality')+v('quality_mean')[:,p.role]+v('quality_global')
        self.split = v('split')
        self.kind = v('kind_mean')[:,p.style].copy()
        self.kind[:,fit.bowlers] += v('kind')
        self.bowl_quality = v('bowl_mean')[:,p.role].copy()+v('bowl_global')
        self.bowl_quality[:,fit.bowlers] += future('bowl_quality')
        self.affinity = v('affinity').reshape(draws,fit.P,fit.V)
        self.type = v('type').reshape(draws,2,2)
        self.pitch = v('pitch').reshape(draws,2,3)
        self.venue = v('venue')
        self.dew = v('dew')+v('chase_mean')
        self.home = v('home')
        self.era = v('era')[:,-1:]+.10*normal((1,))
        self.day_sd = np.sqrt(fit.groups['day']['variance'])

    def base(self,xi,team,bowlers,venue,chasing):
        fit,m = self.fit,self.m
        p = fit.h.players
        how = p.style[bowlers]
        sign = np.where(how==0,.5,-.5)
        quality = self.quality[:,xi,None]+self.split[:,xi,None]*sign[None,None,:]
        conditions = (self.affinity[:,xi,venue]+self.era+self.venue[:,venue,None])[:,:,None]
        conditions = conditions+self.type[:,p.hand[xi]][:,:,how]-self.pitch[:,how,fit.h.venues.pitch[venue]][:,None,:]
        if fit.h.venues.home_team[venue]==team:
            conditions += self.home[:,:,None]
        if chasing:
            conditions += self.dew[:,venue,None,None]
        z = (self.style[:,xi,None,None]*m.bs + quality[:,:,:,None]*m.bq
             + self.kind[:,None,bowlers,None]*m.wt + self.bowl_quality[:,None,bowlers,None]*m.wq
             + conditions[:,:,:,None]*m.c)
        # shape: over, posterior draw, batting position, outcome
        z = z[:,:,np.arange(20)%5,:].transpose(2,0,1,3).copy()
        z += m.cal.over_logits[:,None,None,:]+m.cal.position_vectors[None,None,:,:]
        z -= m.cal.typical_wickets[:,None,None,None]*m.cal.wickets_vector
        if chasing:
            z += m.cal.second_innings_vector
        return z

    def play(self,base,day,n,rng,target=None):
        m = self.m
        draw = np.arange(n)%self.K
        striker,partner,next_in = np.zeros(n,int),np.ones(n,int),np.full(n,2)
        wickets,runs = np.zeros(n,int),np.zeros(n,int)
        live = np.ones(n,bool)
        day_logits = day[:,None]*m.c
        run_values = np.array([0,0,1,2,4,6])
        for ball in range(120):
            z = base[ball//6,draw,striker]+day_logits+wickets[:,None]*m.cal.wickets_vector
            if target is not None:
                pressure = m.pressure(target,runs,ball)
                z += pressure[:,None]*m.cal.pressure_vector
            p = np.exp(z-z.max(axis=1,keepdims=True))
            p /= p.sum(axis=1,keepdims=True)
            kind = np.minimum((rng.random(n)[:,None]>p.cumsum(axis=1)).sum(axis=1),5)
            extra = (rng.random(n)<m.cal.extras_per_ball)&live
            out = (kind==0)&live
            scored = np.where(live & ~out,run_values[kind],0)
            runs += scored+extra
            wickets += out
            striker = np.where(out,next_in,striker)
            next_in += out
            swap = (scored%2==1)^(ball%6==5)
            striker,partner = np.where(swap,partner,striker),np.where(swap,striker,partner)
            striker,partner = np.minimum(striker,10),np.minimum(partner,10)
            live &= wickets<10
            if target is not None:
                live &= runs<target
        return runs

    def probability(self,f,n=16384,seed=913):
        total=0.
        for first,second,xi1,xi2,bowl1,bowl2 in (
            (f.home,f.away,f.home_xi,f.away_xi,f.home_bowlers,f.away_bowlers),
            (f.away,f.home,f.away_xi,f.home_xi,f.away_bowlers,f.home_bowlers)):
            # Common random numbers for the two possible batting orders greatly
            # reduce error in the toss-averaged home probability.
            rng = np.random.default_rng(seed)
            day = rng.normal(0,self.day_sd,n)
            first_total = self.play(self.base(xi1,first,bowl2,f.venue,False),day,n,rng)
            chase = self.play(self.base(xi2,second,bowl1,f.venue,True),day,n,rng,first_total+1)
            q = np.mean((chase>first_total)+.5*(chase==first_total))
            total += .5*(q if second==f.home else 1-q)
        return float(total)
