"""Posterior predictive matches with coupled random draws for the two toss results."""
import numpy as np
from scipy.linalg import cholesky
from scipy.special import ndtr, ndtri

class Posterior:
    def __init__(self, fit, count=256):
        self.fit=fit
        self.count=count
        self.model=fit.m
        gen=np.random.default_rng(763901)
        z=gen.standard_normal((count//2,fit.size))
        z=np.concatenate([z,-z])
        root=cholesky(fit.last_cov,lower=True,check_finite=False)
        mean=fit.posterior_mean()
        theta=mean[None,:]+z@root.T
        # Home advantage is a lift in the generative model. Condition the
        # Gaussian approximation on this coefficient being nonnegative.
        home_index=fit.groups['home']['start']
        home_sd=np.sqrt(fit.last_cov[home_index,home_index])
        home_z=(theta[:,home_index]-mean[home_index])/home_sd
        lower=ndtr(-mean[home_index]/home_sd)
        quantile=np.clip(lower+(1-lower)*ndtr(home_z),1e-12,1-1e-12)
        positive_home=mean[home_index]+home_sd*ndtri(quantile)
        theta+=(positive_home-theta[:,home_index])[:,None]*(fit.last_cov[:,home_index]/home_sd**2)[None,:]
        def get(name):
            g=fit.groups[name]
            return theta[:,g['start']:g['stop']]
        self.get=get
        p=fit.h.players
        self.style=get('style')+get('style_mean')[:,p.role]
        def quality(name):
            K=fit.kernel(name)
            # The next season starts before its midpoint, the point represented
            # by a season-average skill in the observation model.
            future=fit.future
            cross=fit.groups[name]['sd']**2+fit.form[name]**2*fit.rho**(future-fit.times)
            w=np.linalg.solve(K,cross)
            residual=max(0,fit.groups[name]['sd']**2+fit.form[name]**2-cross@w)
            xx=get(name).reshape(count,-1,fit.S)@w
            noise=gen.normal(size=(count//2,xx.shape[1]))
            return xx+np.sqrt(residual)*np.concatenate([noise,-noise])
        self.quality=quality('quality')+get('quality_mean')[:,p.role]
        self.split=get('split')
        self.kind=np.zeros((count,fit.P));self.bowling=np.zeros((count,fit.P))
        ids=fit.bowling_ids
        self.kind[:,ids]=get('kind')+get('kind_mean')[:,p.style[ids]]
        self.bowling[:,ids]=quality('bowling')+get('bowl_mean')[:,p.role[ids]]
        # Players who did not bowl in the history retain their population prior.
        absent=np.setdiff1d(np.arange(fit.P),ids)
        self.kind[:,absent]=get('kind_mean')[:,p.style[absent]]
        self.bowling[:,absent]=get('bowl_mean')[:,p.role[absent]]
        self.affinity=get('affinity').reshape(count,fit.P,fit.V)
        self.hand=get('hand').reshape(count,2,2)
        self.pitch=get('pitch').reshape(count,2,3)
        self.venue=get('venue')
        self.era=get('era')[:,-1]
        e=gen.normal(0,.08,count//2);self.era+=np.r_[e,-e]
        self.dew=get('dew')+get('dew_mean')
        self.home=get('home')[:,0]
        self.day_sd=fit.groups['day']['sd']

    def cards(self, fixture, home_bats):
        f=fixture;fit=self.fit;p=fit.h.players;v=fit.h.venues;m=self.model
        xi=f.home_xi if home_bats else f.away_xi
        bowl=f.away_bowlers if home_bats else f.home_bowlers
        team=f.home if home_bats else f.away
        how=p.style[bowl];hand=p.hand[xi]
        sign=np.where(how==0,.5,-.5)
        cond=self.affinity[:,xi,f.venue][:,:,None]+self.hand[:,hand[:,None],how[None,:]]+self.pitch[:,how,v.pitch[f.venue]][:,None,:]
        cond+=self.venue[:,f.venue,None,None]+self.era[:,None,None]
        if v.home_team[f.venue]==team:cond+=self.home[:,None,None]
        quality=self.quality[:,xi,None]+self.split[:,xi,None]*sign[None,None,:]
        logits=(self.style[:,xi,None,None]*m.bs+quality[:,:,:,None]*m.bq+
                self.kind[:,bowl][:,None,:,None]*m.wt+
                self.bowling[:,bowl][:,None,:,None]*m.wq+cond[:,:,:,None]*m.c)
        return logits


def innings(model, card, condition, n, gen, sample, target=None):
    cal=model.cal
    striker=np.zeros(n,dtype=np.int32);partner=np.ones(n,dtype=np.int32)
    wickets=np.zeros(n,dtype=np.int32);runs=np.zeros(n,dtype=np.int32)
    live=np.ones(n,dtype=bool)
    # Static public terms and every sampled player's coefficients are reused.
    base=cal.over_logits[:,None,None,:]+cal.position_vectors[None,:,None,:]+(np.arange(11)[None,None,:,None]-cal.typical_wickets[:,None,None,None])*cal.wickets_vector
    for ball in range(120):
        over=ball//6
        z=base[over,striker,wickets]+card[sample,striker,over%5]+condition[:,None]*model.c
        if target is not None:
            pressure=np.clip(np.log(np.maximum(target-runs,1)*6/((120-ball)*cal.par_rate[over])),-1.,1.2)
            z+=cal.second_innings_vector+pressure[:,None]*cal.pressure_vector
        z-=z.max(axis=1,keepdims=True)
        prob=np.exp(z);prob/=prob.sum(axis=1,keepdims=True)
        u=gen.random(n)
        kind=(u[:,None]>np.cumsum(prob,axis=1)).sum(axis=1)
        kind=np.minimum(kind,5)
        extra=(gen.random(n)<cal.extras_per_ball)&live
        out=(kind==0)&live
        scored=np.where(live,np.array([0,0,1,2,4,6])[kind],0)
        runs+=scored+extra
        wickets+=out
        striker=np.where(out,wickets+1,striker)
        swap=((scored%2)==1)^(ball%6==5)
        striker,partner=np.where(swap,partner,striker),np.where(swap,striker,partner)
        striker=np.minimum(striker,10);partner=np.minimum(partner,10)
        live &= wickets<10
        if target is not None:live &= runs<target
    return runs


def forecast(posterior,fixture,n=24576,seed=19):
    model=posterior.model
    home=posterior.cards(fixture,True);away=posterior.cards(fixture,False)
    sample=np.arange(n)%posterior.count
    total=0.
    for first_home in (True,False):
        # Coupling the two equally likely batting orders removes much simulation
        # variance: identical sides produce exactly one half.
        gen=np.random.default_rng(seed)
        day=gen.normal(0.,posterior.day_sd,n)
        first=home if first_home else away
        second=away if first_home else home
        set_=innings(model,first,day,n,gen,sample)
        chase=innings(model,second,day+posterior.dew[sample,fixture.venue],n,gen,sample,target=set_+1)
        win=np.mean((chase>set_)+.5*(chase==set_))
        total+=.5*(1.-win if first_home else win)
    return float(total)
