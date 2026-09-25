"""Empirical Bayes inference for the public six-outcome ball model."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '2'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'
import sys, argparse, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scipy import sparse, optimize, linalg
from engine.model import load_public_model, SkillBook, MatchSimulator
from engine.league_io import load_league

class Fit:
    def __init__(self, history):
        self.h = history
        b, p, v = history.balls, history.players, history.venues
        self.np, self.nv = len(p.role), len(v.pitch)
        self.ns = int(b.season.max()) + 1
        self.nt = 2*self.ns
        self.times = np.array([s + k/3 for s in range(self.ns) for k in range(2)])
        self.model = m = load_public_model()
        self.dirs = np.array([m.bs,m.bq,m.wt,m.wq,m.c])
        self.n = len(b)
        self.y = b.outcome.to_numpy()
        chase = (b.innings.to_numpy() == 2).astype(float)
        pressure = np.where(chase, m.pressure(b.target.to_numpy(), b.runs_before.to_numpy(), b.over.to_numpy()*6+b.ball.to_numpy()), 0.)
        self.base = m.situation(b.over.to_numpy(), b.position.to_numpy(), b.wickets_before.to_numpy(), chase, pressure)
        bat, bowl, venue, season = [b[c].to_numpy() for c in ['batter','bowler','venue','season']]
        matches = history.matches.set_index('match')
        week = matches.loc[b.match,'week'].to_numpy()
        half = season*2 + (week > matches.week.max()/2).astype(int)
        bowl_ids = np.flatnonzero(p.role != 0)
        # Accommodate any player selected to bowl, regardless of role label.
        bowl_ids = np.union1d(bowl_ids,np.unique(bowl))
        self.bowl_ids = bowl_ids
        self.nb = len(bowl_ids)
        self.bowl_map = np.zeros(self.np,int); self.bowl_map[bowl_ids]=np.arange(self.nb)
        bi=self.bowl_map[bowl]
        _, match = np.unique(b.match,return_inverse=True)
        self.groups={}; self.k=0; entries=[[] for _ in range(5)]
        def group(name,size,sd,kind='iid'):
            idx=np.arange(self.k,self.k+size); self.k+=size
            self.groups[name]={'idx':idx,'sd':sd,'kind':kind}
            return idx
        def term(d,idx,value=1.): entries[d].append((idx,np.broadcast_to(value,(self.n,))))
        term(0,group('style_mean',3,1.)[p.role[bat]])
        term(0,group('style',self.np,.3)[bat])
        term(1,group('quality_mean',3,1.)[p.role[bat]])
        term(1,group('quality',self.np*self.nt,.3,'dynamic').reshape(self.np,self.nt)[bat,half])
        term(1,group('split',self.np,.2)[bat], np.where(p.style[bowl]==0,.5,-.5))
        term(2,group('kind_mean',2,1.)[p.style[bowl]])
        term(2,group('kind',self.nb,.25)[bi])
        term(3,group('bowl_mean',3,1.)[p.role[bowl]])
        term(3,group('bowl_quality',self.nb*self.nt,.3,'dynamic').reshape(self.nb,self.nt)[bi,half])
        term(4,group('era',self.ns,1.)[season])
        term(4,group('venue',self.nv,.25)[venue])
        term(4,group('dew_mean',1,.3)[np.zeros(self.n,int)],chase)
        term(4,group('dew',self.nv,.15)[venue],chase)
        term(4,group('day',match.max()+1,.2)[match])
        term(4,group('home',1,.3)[np.zeros(self.n,int)],(v.home_team[venue]==b.batting_team.to_numpy()).astype(float))
        term(4,group('affinity',self.np*self.nv,.12).reshape(self.np,self.nv)[bat,venue])
        term(4,group('type',4,.15).reshape(2,2)[p.hand[bat],p.style[bowl]])
        term(4,group('pitch',6,.15).reshape(2,3)[p.style[bowl],v.pitch[venue]],-1.)
        rows=np.arange(self.n)
        self.X=[]
        for ee in entries:
            xx=sparse.coo_matrix((np.concatenate([x[1] for x in ee]),(np.tile(rows,len(ee)),np.concatenate([x[0] for x in ee]))),shape=(self.n,self.k)).tocsr()
            xx.eliminate_zeros(); self.X.append(xx)
        self.x=np.zeros(self.k)
        for name in ('quality','bowl_quality'):
            self.groups[name]['hyper']=np.array([.30,.15])
        self.update_precision()

    def kernel(self,hyper):
        a,b=hyper
        return a*a + b*b * .5**np.abs(self.times[:,None]-self.times[None,:]) + np.eye(self.nt)*1e-7

    def update_precision(self):
        self.P=np.zeros((self.k,self.k))
        for g in self.groups.values():
            idx=g['idx']
            if g['kind']=='dynamic':
                ki=linalg.inv(self.kernel(g['hyper']))
                for block in idx.reshape(-1,self.nt): self.P[np.ix_(block,block)]=ki
            else: self.P[idx,idx]=1/g['sd']**2
        self.Ps=sparse.csr_matrix(self.P)

    def objective(self,x):
        scalar=np.column_stack([xx@x for xx in self.X])
        z=self.base+scalar@self.dirs
        mx=z.max(axis=1)
        pp=np.exp(z-mx[:,None]); ss=pp.sum(axis=1); pp/=ss[:,None]
        loss=np.sum(mx+np.log(ss)-z[np.arange(self.n),self.y])
        pp[np.arange(self.n),self.y]-=1
        residual=pp@self.dirs.T
        grad=sum(xx.T@residual[:,i] for i,xx in enumerate(self.X))
        px=self.Ps@x
        return loss+.5*x@px, grad+px

    def covariance(self):
        z=self.base+np.column_stack([xx@self.x for xx in self.X])@self.dirs
        pp=np.exp(z-z.max(axis=1)[:,None]); pp/=pp.sum(axis=1)[:,None]
        mean=pp@self.dirs.T
        H=self.P.copy()
        for i in range(5):
            for j in range(i+1):
                w=pp@(self.dirs[i]*self.dirs[j])-mean[:,i]*mean[:,j]
                h=(self.X[i].T@self.X[j].multiply(w[:,None])).toarray()
                H+=h
                if i!=j: H+=h.T
        cf=linalg.cho_factor(H,overwrite_a=True,check_finite=False)
        cov=linalg.cho_solve(cf,np.eye(self.k),overwrite_b=True,check_finite=False)
        return cov

    def train(self,iterations=7):
        start=time.time()
        for it in range(iterations):
            # Whiten correlated talent/form coefficients before optimization.
            L=np.zeros((self.k,self.k))
            for g in self.groups.values():
                idx=g['idx']
                if g['kind']=='dynamic':
                    ch=linalg.cholesky(self.kernel(g['hyper']),lower=True)
                    for block in idx.reshape(-1,self.nt): L[np.ix_(block,block)]=ch
                else: L[idx,idx]=g['sd']
            ls=sparse.csr_matrix(L)
            zz=[xx@ls for xx in self.X]
            z=self.base+np.column_stack([xx@self.x for xx in self.X])@self.dirs
            pp=np.exp(z-z.max(axis=1)[:,None]); pp/=pp.sum(axis=1)[:,None]
            dd=np.ones(self.k)
            for d in range(5):
                var=pp@(self.dirs[d]**2)-(pp@self.dirs[d])**2
                dd+=zz[d].power(2).T@var
            scale=1/np.sqrt(dd)
            def obj(u):
                w=u*scale
                z=self.base+np.column_stack([xx@w for xx in zz])@self.dirs
                mx=z.max(axis=1); prob=np.exp(z-mx[:,None]); ss=prob.sum(axis=1); prob/=ss[:,None]
                loss=np.sum(mx+np.log(ss)-z[np.arange(self.n),self.y])+.5*w@w
                prob[np.arange(self.n),self.y]-=1
                residual=prob@self.dirs.T
                grad=sum(xx.T@residual[:,i] for i,xx in enumerate(zz))+w
                return loss,grad*scale
            init=sparse.linalg.spsolve_triangular(ls,self.x,lower=True)/scale
            opt=optimize.minimize(obj,init,jac=True,method='L-BFGS-B',options={'maxiter':250,'ftol':2e-10,'gtol':.001,'maxcor':20})
            self.x=ls@(opt.x*scale)
            print('fit',it,round(time.time()-start,1),round(opt.fun,2),opt.nit,flush=True,file=sys.stderr)
            if it==iterations-1: break
            cov=self.covariance()
            for name,g in self.groups.items():
                idx=g['idx']
                if g['kind']=='dynamic':
                    blocks=idx.reshape(-1,self.nt)
                    # Integrate every other effect, then maximize the Gaussian
                    # marginal likelihood of the talent/form covariance.
                    cc=cov[np.ix_(idx,idx)].copy()
                    ci=linalg.cho_solve(linalg.cho_factor(cc,check_finite=False),np.eye(len(idx)),check_finite=False)
                    yy=ci@self.x[idx]
                    jj=ci-self.P[np.ix_(idx,idx)]
                    def hyper_obj(logsd):
                        K=self.kernel(np.exp(logsd))
                        ki=linalg.inv(K)
                        mat=jj.copy()
                        for ii in range(len(blocks)):
                            sl=slice(ii*self.nt,(ii+1)*self.nt)
                            mat[sl,sl]+=ki
                        cf=linalg.cho_factor(mat,overwrite_a=True,check_finite=False)
                        val=len(blocks)*np.linalg.slogdet(K)[1]+2*np.log(np.diag(cf[0])).sum()-yy@linalg.cho_solve(cf,yy,check_finite=False)
                        # A weak scale prior stabilizes poorly measured drift.
                        val+=((logsd[1]-np.log(.15))/.9)**2
                        return val
                    res=optimize.minimize(hyper_obj,np.log(g['hyper']),method='L-BFGS-B',bounds=[(np.log(.025),np.log(.8)),(np.log(.025),np.log(.6))],options={'ftol':1e-8,'maxiter':25})
                    g['hyper']=np.exp(res.x)
                elif name in ('style','split','kind','venue','dew','day','affinity'):
                    old=g['sd']**2
                    eig,vec=linalg.eigh(cov[np.ix_(idx,idx)],check_finite=False)
                    eig=np.minimum(eig,old)
                    proj=(vec.T@self.x[idx])**2
                    def variance_obj(logsd):
                        new=np.exp(2*logsd); d=1/new-1/old
                        den=1+eig*d
                        val=len(idx)*np.log(new/old)+np.log(den).sum()+np.sum(proj*d/den)
                        if name in ('split','venue','dew','affinity','kind'):
                            val+=((logsd-np.log(.15))/1.0)**2
                        return val
                    res=optimize.minimize_scalar(variance_obj,bounds=(np.log(.02),np.log(.8)),method='bounded',options={'xatol':.003})
                    g['sd']=np.exp(res.x)
            self.update_precision()
            print('scales', {n:np.round(g.get('hyper',g['sd']),3).tolist() for n,g in self.groups.items() if n in ('style','quality','split','kind','bowl_quality','venue','dew','day','affinity')},flush=True,file=sys.stderr)
        self.cov=None
        return self.book()

    def book(self):
        p,v=self.h.players,self.h.venues
        def values(name): return self.x[self.groups[name]['idx']]
        def future(name,n):
            g=self.groups[name]; a,b=g['hyper']
            cross=a*a+b*b*.5**(self.ns-self.times)
            weights=linalg.solve(self.kernel(g['hyper']),cross,assume_a='pos')
            return values(name).reshape(n,self.nt)@weights
        style=values('style')+values('style_mean')[p.role]
        quality=future('quality',self.np)+values('quality_mean')[p.role]
        kind=np.zeros(self.np); bowl_quality=np.zeros(self.np)
        kind[self.bowl_ids]=values('kind')+values('kind_mean')[p.style[self.bowl_ids]]
        bowl_quality[self.bowl_ids]=future('bowl_quality',self.nb)+values('bowl_mean')[p.role[self.bowl_ids]]
        return SkillBook(p,v,style,quality,values('split'),kind,bowl_quality,values('type').reshape(2,2),values('pitch').reshape(2,3),values('venue'),values('dew')+values('dew_mean')[0],values('affinity').reshape(self.np,self.nv),values('home')[0],values('era')[-1],self.groups['day']['sd'],0.)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--league',required=True); parser.add_argument('--out',required=True)
    parser.add_argument('--draws',type=int,default=49152); parser.add_argument('--iterations',type=int,default=6)
    args=parser.parse_args(); start=time.time()
    h,fixtures=load_league(args.league)
    fit=Fit(h); book=fit.train(args.iterations)
    from predict import sample_skills, win_probability
    skills=sample_skills(fit)
    gen=np.random.default_rng(726191)
    predictions=[]
    for i,f in enumerate(fixtures):
        q=win_probability(fit,skills,f,args.draws,gen)
        predictions.append(q)
        print('fixture',i,round(q,4),'elapsed',round(time.time()-start,1),file=sys.stderr,flush=True)
    pd.DataFrame({'fixture':[f.match for f in fixtures],'p_home':np.clip(predictions,.002,.998)}).to_csv(args.out,index=False)

if __name__=='__main__': main()
