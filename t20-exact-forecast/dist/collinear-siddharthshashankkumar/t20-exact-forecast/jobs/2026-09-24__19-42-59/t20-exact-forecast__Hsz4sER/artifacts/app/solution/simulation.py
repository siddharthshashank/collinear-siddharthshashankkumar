"""Vectorized posterior predictive simulation of the documented engine."""
import numpy as np

class PredictiveSimulator:
    def __init__(self,fit,draws):
        self.fit,self.s,self.m=fit,draws,fit.model
        self.count=len(draws['style'])

    def logits(self,xi,team,bowlers,venue):
        p,v=self.fit.h.players,self.fit.h.venues
        s=self.s; how=p.style[bowlers]; bi=self.fit.bowlmap[bowlers]
        quality=s['quality'][:,xi,None]+s['split'][:,xi,None]*np.where(how==0,.5,-.5)[None,None,:]
        conditions=s['affinity'][:,xi,venue,None]+s['home'][:,None,None]*(v.home_team[venue]==team)
        conditions=conditions+s['hand'][:,p.hand[xi,None],how[None,:]]+s['pitch'][:,how,v.pitch[venue]][:,None,:]
        z=(s['style'][:,xi,None,None]*self.m.bs+quality[:,:,:,None]*self.m.bq+
           s['kind'][:,bi][:,None,:,None]*self.m.wt+s['bowling'][:,bi][:,None,:,None]*self.m.wq+conditions[:,:,:,None]*self.m.c)
        # Each over uses the next bowler; the public position term is fixed.
        z=z[:,:,np.arange(20)%5,:].transpose(0,2,1,3)
        z=z+self.m.cal.over_logits[None,:,None,:]+self.m.cal.position_vectors[None,None,:,:]-self.m.cal.typical_wickets[None,:,None,None]*self.m.cal.wickets_vector
        return z

    def innings(self,z,conditions,n,gen,target=None):
        m=self.m;groups=np.arange(n)%self.count
        striker=np.zeros(n,dtype=np.int64);partner=np.ones(n,dtype=np.int64);next_in=np.full(n,2,dtype=np.int64)
        runs=np.zeros(n,dtype=np.int64); wickets=np.zeros(n,dtype=np.int64);live=np.ones(n,dtype=bool)
        base=conditions[:,None]*m.c
        if target is not None:base=base+m.cal.second_innings_vector
        for ball in range(120):
            over=ball//6
            logit=z[groups,over,striker]+base+wickets[:,None]*m.cal.wickets_vector
            if target is not None:
                pressure=np.clip(np.log(np.maximum(target-runs,1)*6/((120-ball)*m.cal.par_rate[over])),-1.,1.2)
                logit+=pressure[:,None]*m.cal.pressure_vector
            prob=np.exp(logit)
            cumulative=np.cumsum(prob,axis=1)
            uniform=gen.random(n)*cumulative[:,-1]
            kind=(uniform[:,None]>cumulative[:,:5]).sum(axis=1)
            extra=(gen.random(n)<m.cal.extras_per_ball)&live
            out=(kind==0)&live
            scored=np.where(live,np.array([0,0,1,2,4,6])[kind],0)
            runs+=scored+extra;wickets+=out
            striker=np.where(out,next_in,striker);next_in+=out
            swap=(scored%2==1)^(ball%6==5)
            striker,partner=np.where(swap,partner,striker),np.where(swap,striker,partner)
            np.minimum(striker,10,out=striker);np.minimum(partner,10,out=partner)
            live&=wickets<10
            if target is not None:live&=runs<target
        return runs

    def probability(self,f,n=32768,seed=19041):
        s=self.s;groups=np.arange(n)%self.count
        zh=self.logits(f.home_xi,f.home,f.away_bowlers,f.venue)
        za=self.logits(f.away_xi,f.away,f.home_bowlers,f.venue)
        level=s['venue'][groups,f.venue]+s['era'][groups]
        dew=s['dew'][groups,f.venue]
        estimates=[]
        # Common random numbers couple the two toss outcomes and reduce noise.
        for home_first in (True,False):
            gen=np.random.default_rng(seed)
            day=gen.normal(0.,s['day_sd'],n)
            first=self.innings(zh if home_first else za,level+day,n,gen)
            second=self.innings(za if home_first else zh,level+day+dew,n,gen,target=first+1)
            wins=(second>first)+.5*(second==first)
            estimates.append(1-wins if home_first else wins)
        return float(np.mean((estimates[0]+estimates[1])*.5))
