"""Posterior predictive matches, using the exact public innings rules."""
import numpy as np
from scipy import linalg, special
from scipy.stats import qmc


def sample_skills(fit, count=1024):
    # Scrambled Sobol draws reduce integration error; all seeds are fixed.
    cov=fit.covariance()
    ch=linalg.cholesky(cov,lower=True,check_finite=False)
    extra=fit.np+fit.nb+1
    normal=special.ndtri(qmc.Sobol(fit.k+extra,scramble=True,seed=70913).random_base2(int(np.log2(count))))
    draws=fit.x[None,:]+normal[:,:fit.k]@ch.T
    def get(name): return draws[:,fit.groups[name]['idx']]
    def future(name,n,offset):
        g=fit.groups[name]; a,b=g['hyper']
        cross=a*a+b*b*.5**(fit.ns-fit.times)
        weights=linalg.solve(fit.kernel(g['hyper']),cross,assume_a='pos')
        variance=max(0.,a*a+b*b-cross@weights)
        return get(name).reshape(count,n,fit.nt)@weights+np.sqrt(variance)*normal[:,fit.k+offset:fit.k+offset+n]
    p=fit.h.players
    out={}
    out['style']=get('style')+get('style_mean')[:,p.role]
    out['quality']=future('quality',fit.np,0)+get('quality_mean')[:,p.role]
    out['split']=get('split')
    out['kind']=np.zeros((count,fit.np)); out['bowl_quality']=np.zeros((count,fit.np))
    out['kind'][:,fit.bowl_ids]=get('kind')+get('kind_mean')[:,p.style[fit.bowl_ids]]
    out['bowl_quality'][:,fit.bowl_ids]=future('bowl_quality',fit.nb,fit.np)+get('bowl_mean')[:,p.role[fit.bowl_ids]]
    for name in ('venue','home','type','pitch'): out[name]=get(name)
    out['dew']=get('dew')+get('dew_mean')
    out['affinity']=get('affinity').reshape(count,fit.np,fit.nv)
    out['era']=get('era')[:,-1] + .12*normal[:,-1]
    out['day_sd']=fit.groups['day']['sd']
    return out


def tables(model,players,venues,skills,xi,team,bowlers,venue):
    s=skills; how=players.style[bowlers]; hand=players.hand[xi]
    count=len(s['era'])
    quality=s['quality'][:,xi,None]+s['split'][:,xi,None]*np.where(how==0,.5,-.5)[None,None,:]
    conditions=s['affinity'][:,xi,venue,None]
    if venues.home_team[venue]==team: conditions=conditions+s['home'][:,:,None]
    conditions=conditions+s['type'].reshape(count,2,2)[:,hand[:,None],how[None,:]]
    conditions=conditions-s['pitch'].reshape(count,2,3)[:,how,venues.pitch[venue]][:,None,:]
    conditions=conditions+(s['era']+s['venue'][:,venue])[:,None,None]
    z=s['style'][:,xi,None,None]*model.bs+quality[:,:,:,None]*model.bq
    z=z+s['kind'][:,None,bowlers,None]*model.wt+s['bowl_quality'][:,None,bowlers,None]*model.wq
    z=z+conditions[:,:,:,None]*model.c
    return z,z+s['dew'][:,venue,None,None,None]*model.c


def innings(model,table,day,draw_idx,gen,target=None):
    n=len(day); cal=model.cal
    striker=np.zeros(n,dtype=int); partner=np.ones(n,dtype=int); next_in=np.full(n,2,dtype=int)
    wickets=np.zeros(n,dtype=int); runs=np.zeros(n,dtype=int); live=np.ones(n,dtype=bool)
    chasing=float(target is not None)
    scores=np.array([0,0,1,2,4,6])
    shared=day[:,None]*model.c
    for ball in range(120):
        over=ball//6; who=over%5
        z=table[draw_idx,striker,who]+cal.over_logits[over]+cal.position_vectors[striker]
        z=z+(wickets-cal.typical_wickets[over])[:,None]*cal.wickets_vector+shared
        if target is not None:
            z=z+cal.second_innings_vector+model.pressure(target,runs,ball)[:,None]*cal.pressure_vector
        p=model.shares(z)
        kind=np.minimum((gen.random(n)[:,None]>p.cumsum(axis=1)).sum(axis=1),5)
        extra=(gen.random(n)<cal.extras_per_ball)&live
        out=(kind==0)&live
        scored=np.where(live&~out,scores[kind],0)
        runs+=scored+extra; wickets+=out
        striker=np.where(out,next_in,striker); next_in+=out
        swap=(scored%2==1)^(ball%6==5)
        striker,partner=np.where(swap,partner,striker),np.where(swap,striker,partner)
        striker=np.minimum(striker,10); partner=np.minimum(partner,10)
        live&=wickets<10
        if target is not None: live&=runs<target
    return runs


def win_probability(fit,skills,f,n,gen):
    model=fit.model
    home=tables(model,fit.h.players,fit.h.venues,skills,f.home_xi,f.home,f.away_bowlers,f.venue)
    away=tables(model,fit.h.players,fit.h.venues,skills,f.away_xi,f.away,f.home_bowlers,f.venue)
    idx=np.arange(n)%len(skills['era'])
    total=0.
    for first,second,home_chases in ((home,away,False),(away,home,True)):
        day=gen.normal(0,skills['day_sd'],n)
        a=innings(model,first[0],day,idx,gen)
        b=innings(model,second[1],day,idx,gen,target=a+1)
        q=np.mean(b>a)+.5*np.mean(b==a)
        total+=.5*(q if home_chases else 1-q)
    return float(total)
