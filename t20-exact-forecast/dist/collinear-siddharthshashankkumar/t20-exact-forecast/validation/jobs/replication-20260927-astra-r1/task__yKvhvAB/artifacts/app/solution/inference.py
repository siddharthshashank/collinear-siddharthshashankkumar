"""Empirical Bayes inference for the public six-outcome delivery model."""
import time
import sys
import numpy as np
from scipy import sparse
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.linalg import cho_factor, cho_solve

class Fit:
    def __init__(self, history, model, periods=None):
        self.history, self.model = history, model
        b = history.balls
        self.n = len(b)
        self.y = b.outcome.to_numpy()
        self.d = np.array([model.bs,model.bq,model.wt,model.wq,model.c])
        chase = (b.innings.to_numpy() == 2).astype(float)
        ball = b.over.to_numpy()*6 + b.ball.to_numpy()
        pressure = model.pressure(b.target.to_numpy(),b.runs_before.to_numpy(),ball)*chase
        self.base=model.situation(b.over.to_numpy(),b.position.to_numpy(),b.wickets_before.to_numpy(),chase,pressure)
        self.groups={};self.parts=[[] for _ in range(5)];self.k=0
        p,v=history.players,history.venues
        np_,nv=len(p.role),len(v.pitch)
        self.np,self.nv=np_,nv
        bat=b.batter.to_numpy();bowl=b.bowler.to_numpy();venue=b.venue.to_numpy();season=b.season.to_numpy()
        self.ns=ns=history.seasons
        self.nt=nt=ns*2
        week=history.matches.set_index('match').week
        phase=(b.match.map(week).to_numpy()>=4).astype(int)
        period=season*2+phase
        self.bowling_ids=np.union1d(np.flatnonzero(p.role>0),np.unique(bowl)); nb=len(self.bowling_ids)
        self.bowl_index=np.zeros(np_,int);self.bowl_index[self.bowling_ids]=np.arange(nb)
        bi=self.bowl_index[bowl]
        hand=p.hand[bat];how=p.style[bowl]
        self.add('bat_mean_style',0,p.role[bat],3,.08,False)
        self.add('bat_style',0,bat,np_,.28)
        self.add('bat_mean_quality',1,p.role[bat],3,.06,False)
        self.add('bat_quality',1,bat,np_,.30)
        self.add('bat_form',1,period*np_+bat,nt*np_,.20)
        self.add('bat_split',1,bat,np_,.20,values=np.where(how==0,.5,-.5))
        self.add('bowl_mean_type',2,how,2,.8,False)
        self.add('bowl_type',2,bi,nb,.22)
        self.add('bowl_mean_quality',3,p.role[bowl],3,.07,False)
        self.add('bowl_quality',3,bi,nb,.25)
        self.add('bowl_form',3,period*nb+bi,nt*nb,.16)
        self.add('era',4,season,ns,.30,False)
        self.add('venue',4,venue,nv,.20)
        self.add('dew',4,venue,nv,.12,values=chase)
        self.add('wear',4,np.zeros(self.n,int),1,.3,False,values=chase)
        self.add('home',4,np.zeros(self.n,int),1,.25,False,values=(v.home_team[venue]==b.batting_team.to_numpy()).astype(float))
        self.add('hand_style',4,hand*2+how,4,.07,False)
        self.add('pitch_style',4,how*3+v.pitch[venue],6,.07,False)
        self.add('affinity',4,bat*nv+venue,np_*nv,.12)
        match_codes=np.unique(b.match.to_numpy(),return_inverse=True)[1]
        self.add('day',4,match_codes,match_codes.max()+1,.14)
        self.X=[]
        for parts in self.parts:
            rr=[];cc=[];vv=[]
            for rows,cols,vals in parts:
                rr.extend(rows);cc.extend(cols);vv.extend(vals)
            self.X.append(sparse.csr_matrix((vv,(rr,cc)),shape=(self.n,self.k)))
        self.sd=np.ones(self.k)
        for g in self.groups.values(): self.sd[g['slice']]=g['sd']
        self.beta=np.zeros(self.k)
        # AR(1) form, represented at half-season resolution.
        self.rho=.75
        corr=self.rho**np.abs(np.arange(nt)[:,None]-np.arange(nt)[None,:])
        self.Rinv=np.linalg.inv(corr)
        self.Q0=sparse.eye(self.k,format='lil')
        for name,size in [('bat_form',np_),('bowl_form',nb)]:
            sl=self.groups[name]['slice']
            self.Q0[sl,sl]=sparse.kron(self.Rinv,sparse.eye(size))
        self.Q0=self.Q0.tocsr()

    def add(self,name,axis,index,count,sd,learn=True,values=None):
        sl=slice(self.k,self.k+count)
        self.groups[name]=dict(slice=sl,sd=sd,learn=learn,count=count,axis=axis)
        values=np.ones(self.n) if values is None else values
        keep=values!=0
        self.parts[axis].append((np.nonzero(keep)[0],self.k+index[keep],values[keep]))
        self.k+=count

    def objective(self,u):
        beta=u*self.sd
        z=self.base.copy()
        for j in range(5): z+=(self.X[j]@beta)[:,None]*self.d[j]
        lse=logsumexp(z,axis=1)
        loss=np.sum(lse-z[np.arange(self.n),self.y])+.5*u@(self.Q0@u)
        prob=np.exp(z-lse[:,None]);prob[np.arange(self.n),self.y]-=1
        r=prob@self.d.T
        grad=self.Q0@u
        for j in range(5):grad+=self.sd*(self.X[j].T@r[:,j])
        return loss,grad

    def optimize(self,maxiter=100):
        start=time.time()
        opt=minimize(self.objective,self.beta/self.sd,jac=True,method='L-BFGS-B',options={'maxiter':maxiter,'ftol':1e-10,'gtol':1e-4,'maxcor':15})
        self.beta=opt.x*self.sd
        print('fit',self.k,opt.nit,round(time.time()-start,2),opt.fun,file=sys.stderr,flush=True)
        return opt

    def posterior(self):
        start=time.time()
        self.cov=None
        self.chol=None
        z=self.base.copy()
        for j in range(5):z+=(self.X[j]@self.beta)[:,None]*self.d[j]
        prob=np.exp(z-logsumexp(z,axis=1)[:,None])
        mean=prob@self.d.T
        H=self.Q0.toarray(order='F')
        H/=self.sd[:,None]
        H/=self.sd[None,:]
        for j in range(5):
            for k in range(j+1):
                w=prob@(self.d[j]*self.d[k])-mean[:,j]*mean[:,k]
                h=(self.X[j].T@self.X[k].multiply(w[:,None])).toarray()
                H+=h
                if j!=k:H+=h.T
        del h
        self.chol=cho_factor(H,lower=True,check_finite=False,overwrite_a=True)
        self.cov=cho_solve(self.chol,np.eye(self.k,order='F'),check_finite=False,overwrite_b=True)
        print('posterior',round(time.time()-start,2),file=sys.stderr,flush=True)
        return np.diag(self.cov)

    def train(self,iterations=5):
        for it in range(iterations):
            self.optimize()
            diag=self.posterior()
            for name,g in self.groups.items():
                sl=g['slice'];sd=g['sd']
                if g['learn']:
                    # Restricted moments: random effects are fitted with uncertain population means.
                    q=self.Q0[sl,sl]
                    posterior_trace=np.sum(q.multiply(self.cov[sl,sl]))
                    square=self.beta[sl]@(q@self.beta[sl])
                    count=g['count']
                    effective=max(1.,count-posterior_trace/sd**2)
                    # Weak hyperpriors stabilize variance estimates when little
                    # information is available for a component.
                    centers={'bat_style':(.32,4), 'bat_quality':(.22,5),
                             'bowl_type':(.18,4),'bowl_quality':(.20,5),
                             'bat_form':(.20,3),'bowl_form':(.16,3),
                             'bat_split':(.16,3),'affinity':(.12,3),
                             'venue':(.12,2),'dew':(.08,2),'day':(.22,3)}
                    center,strength=centers[name]
                    delta=(square+posterior_trace-count*sd**2+strength*(center**2-sd**2))/(effective+strength)
                    new=np.sqrt(max(.035**2,sd**2+.7*delta))
                    new=np.clip(new,sd*.70,sd*1.5)
                    self.sd[sl]=g['sd']=new
        self.optimize()

    def get(self,name):return self.beta[self.groups[name]['slice']]
