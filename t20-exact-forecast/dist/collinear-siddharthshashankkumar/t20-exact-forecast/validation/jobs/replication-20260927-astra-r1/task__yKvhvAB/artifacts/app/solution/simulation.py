"""Posterior predictive simulation, using exactly the public innings rules."""
import numpy as np
from scipy.linalg import solve_triangular

class Predictor:
    def __init__(self, fit, draws=256, seed=20260927, uncertainty=True):
        self.fit=fit
        self.model=fit.model
        self.rng=np.random.default_rng(seed)
        self.draws=draws
        rng=self.rng
        if uncertainty:
            normal=rng.standard_normal((fit.k,draws//2))
            normal=np.concatenate([normal,-normal],axis=1)
            self.samples=fit.beta[:,None]+solve_triangular(fit.chol[0],normal,lower=True,trans='T',check_finite=False)
        else:self.samples=np.broadcast_to(fit.beta[:,None],(fit.k,draws)).copy()
        def get(name):return self.samples[fit.groups[name]['slice']].T
        self.get=get
        p,v=fit.history.players,fit.history.venues
        self.style=get('bat_style')+get('bat_mean_style')[:,p.role]
        # Last fitted form state is near the middle of the last half-season.
        # Carry it through the remainder of that season and the off-season.
        carry=.80
        self.quality=get('bat_quality')+get('bat_mean_quality')[:,p.role]+carry*get('bat_form')[:,-fit.np:]
        self.bquality=get('bowl_quality')+get('bowl_mean_quality')[:,p.role[fit.bowling_ids]]+carry*get('bowl_form')[:,-len(fit.bowling_ids):]
        if uncertainty:
            for quality,name in [(self.quality,'bat_form'),(self.bquality,'bowl_form')]:
                z=rng.standard_normal((draws//2,quality.shape[1]))
                z=np.concatenate([z,-z],axis=0)
                quality+=np.sqrt(1-carry**2)*fit.groups[name]['sd']*z
        self.kind=get('bowl_type')+get('bowl_mean_type')[:,p.style[fit.bowling_ids]]
        self.affinity=get('affinity').reshape(draws,fit.np,fit.nv)
        self.era=get('era')[:,-1]
        if uncertainty:
            z=rng.standard_normal(draws//2)
            self.era+=.10*np.r_[z,-z]

    def logits(self,xi,team,bowlers,venue):
        fit=self.fit;p,v=fit.history.players,fit.history.venues
        how=p.style[bowlers]
        sign=np.where(how==0,.5,-.5)
        bi=fit.bowl_index[bowlers]
        get=self.get
        quality=self.quality[:,xi,None]+get('bat_split')[:,xi,None]*sign[None,None,:]
        conditions=self.affinity[:,xi,venue,None].copy()
        if v.home_team[venue]==team:conditions+=get('home')[:,:,None]
        conditions=conditions+get('hand_style')[:,p.hand[xi,None]*2+how[None,:]]
        conditions=conditions+get('pitch_style')[:,how*3+v.pitch[venue]][:,None,:]
        d=fit.d
        return (self.style[:,xi,None,None]*d[0]+quality[:,:,:,None]*d[1]
                +self.kind[:,bi][:,None,:,None]*d[2]+self.bquality[:,bi][:,None,:,None]*d[3]
                +conditions[:,:,:,None]*d[4])

    def innings(self,logits,conditions,which,n,rng,target=None):
        cal=self.model.cal
        striker=np.zeros(n,dtype=np.int32);partner=np.ones(n,dtype=np.int32);next_in=np.full(n,2,dtype=np.int32)
        wickets=np.zeros(n,dtype=np.int32);runs=np.zeros(n,dtype=np.int32);live=np.ones(n,bool)
        chasing=target is not None
        run_values=np.array([0,0,1,2,4,6],dtype=np.int32)
        fixed=cal.over_logits-cal.typical_wickets[:,None]*cal.wickets_vector+int(chasing)*cal.second_innings_vector
        for ball in range(120):
            over=ball//6
            z=logits[which,striker,over%5]+fixed[over]+cal.position_vectors[striker]
            z+=wickets[:,None]*cal.wickets_vector+conditions[:,None]*self.model.c
            if chasing:
                pressure=np.clip(np.log(np.maximum(target-runs,1)*6/((120-ball)*cal.par_rate[over])),-1.,1.2)
                z+=pressure[:,None]*cal.pressure_vector
            # The six logits are moderate; avoiding the max subtraction is exact
            # to floating point precision for this model's range.
            p=np.exp(z)
            cdf=np.cumsum(p,axis=1)
            u=rng.random(n)*cdf[:,-1]
            kind=np.minimum(np.sum(u[:,None]>cdf,axis=1),5)
            extra=(rng.random(n)<cal.extras_per_ball)&live
            out=(kind==0)&live
            scored=np.where(live&~out,run_values[kind],0)
            runs+=scored+extra
            wickets+=out
            striker=np.where(out,next_in,striker)
            next_in+=out
            swap=(scored%2==1)^(ball%6==5)
            striker,partner=np.minimum(np.where(swap,partner,striker),10),np.minimum(np.where(swap,striker,partner),10)
            live&=wickets<10
            if chasing:live&=runs<target
        return runs

    def predict(self,fixture,n=16384,seed=0):
        rng=np.random.default_rng(831729+seed)
        f=fixture
        which=np.arange(n)%self.draws
        home=self.logits(f.home_xi,f.home,f.away_bowlers,f.venue)
        away=self.logits(f.away_xi,f.away,f.home_bowlers,f.venue)
        base=self.get('venue')[:,f.venue]+self.era
        dew=self.get('dew')[:,f.venue]+self.get('wear')[:,0]
        total=0.
        for first,second,home_chasing in [(home,away,False),(away,home,True)]:
            day=rng.normal(0,self.fit.groups['day']['sd'],n)
            common=base[which]+day
            set_=self.innings(first,common,which,n,rng)
            chase=self.innings(second,common+dew[which],which,n,rng,target=set_+1)
            win=np.mean(chase>set_)+.5*np.mean(chase==set_)
            total+=.5*(win if home_chasing else 1-win)
        return float(total)
