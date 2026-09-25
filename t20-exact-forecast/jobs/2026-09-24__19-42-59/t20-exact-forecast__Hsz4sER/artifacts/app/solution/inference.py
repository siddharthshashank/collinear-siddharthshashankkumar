"""Laplace marginal likelihood and posterior predictive parameter draws."""
import time
import sys
import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_triangular
from scipy.optimize import minimize
from scipy.special import ndtr
from scipy.stats import truncnorm


def posterior(fit, correction=True):
    H = fit.hessian().toarray()
    ch = cho_factor(H, lower=True, check_finite=False)
    V = cho_solve(ch, np.eye(fit.pdim), check_finite=False)
    delta = np.zeros(fit.pdim)
    if correction:
        # Variances of the five linear predictors, including their correlations.
        C = np.zeros((fit.n,5,5))
        entries=[]
        for j in range(5):
            dense=[]
            for rows,cols,values in zip(fit.rows[j],fit.cols[j],fit.values[j]):
                ix=np.zeros(fit.n,dtype=int);val=np.zeros(fit.n)
                ix[rows]=cols;val[rows]=values
                dense.append((ix,val))
            entries.append(dense)
        for j in range(5):
            for k in range(j+1):
                for ix,a in entries[j]:
                    for iy,b in entries[k]:
                        C[:,j,k] += V[ix,iy]*a*b
                C[:,k,j]=C[:,j,k]
        prob,_=fit.probabilities(fit.theta)
        dm=prob@fit.d.T
        cz=np.einsum('nij,nj->ni',C,dm)
        var=np.einsum('ja,njk,ka->na',fit.d,C,fit.d)-2*cz@fit.d
        dp=.5*prob*(var-(prob*var).sum(axis=1)[:,None])
        score=fit.Z.T @ (dp@fit.d.T).T.ravel()
        delta=-cho_solve(ch,score,check_finite=False)
    return V,delta,ch


def marginal_fit(fit, maxiter=26):
    params=[];start=[];bounds=[]
    for name,g in fit.groups.items():
        if not g['learn']:continue
        keys=['talent','form','length'] if g['temporal'] else ['sd']
        for key in keys:
            params.append((name,key));start.append(np.log(g[key]))
            bounds.append((np.log(2),np.log(40)) if key=='length' else (np.log(.025),np.log(.8)))
    dt=np.abs(fit.times[:,None]-fit.times[None,:])
    calls=0
    def objective(logs):
        nonlocal calls
        tick=time.time();calls+=1
        for (name,key),value in zip(params,logs):fit.groups[name][key]=np.exp(value)
        fit.update_prior();loss,nit=fit.optimize()
        V,delta,ch=posterior(fit)
        logdetprior=0.
        for g in fit.groups.values():
            if g['temporal']:logdetprior-=g['size']/fit.nt*np.linalg.slogdet(g['cov'])[1]
            else:logdetprior-=2*g['size']*np.log(g['sd'])
        value=loss+np.log(np.diag(ch[0])).sum()-.5*logdetprior
        derivatives={}
        for name,g in fit.groups.items():
            if not g['learn']:continue
            mu=fit.theta[g['sl']]; shift=delta[g['sl']]
            if g['temporal']:
                count=g['size']//fit.nt
                mu=mu.reshape(count,fit.nt);shift=shift.reshape(count,fit.nt)
                ix=np.arange(g['start'],g['start']+g['size']).reshape(count,fit.nt)
                moment=(mu.T@mu+mu.T@shift+shift.T@mu)/count+V[ix[:,:,None],ix[:,None,:]].mean(axis=0)
                P=g['prec'];score=.5*count*(P-P@moment@P)
                K=np.exp(-dt/g['length'])
                derivatives[name,'talent']=np.sum(score)*2*g['talent']**2
                derivatives[name,'form']=np.sum(score*K)*2*g['form']**2
                derivatives[name,'length']=np.sum(score*K*dt/g['length'])*g['form']**2
                # A weak prior resolves talent/form ambiguity in short careers.
                for key,center,spread in [('form',.14,.65),('length',8.,.7)]:
                    dev=np.log(g[key]/center)
                    value+=.5*(dev/spread)**2
                    derivatives[name,key]+=dev/spread**2
            else:
                moment=np.sum(mu**2+2*mu*shift+V.diagonal()[g['sl']])
                derivative=g['size']-moment/g['sd']**2
                weight=2 if g['size']<30 else 1
                init={'style':.28,'split':.16,'kind':.22,'venue':.2,'dew':.12,'affinity':.1,'day':.14}[name]
                value+=weight*(np.log(g['sd'])+.5*init**2/g['sd']**2)
                derivative+=weight*(1-init**2/g['sd']**2)
                derivatives[name,'sd']=derivative
        grad=np.array([derivatives[p] for p in params])
        fit.V,fit.mean_delta,fit.ch=V,delta,ch
        print('marginal',calls,'loss',round(value,3),'grad',round(np.linalg.norm(grad),3),'seconds',round(time.time()-tick,2),file=sys.stderr,flush=True)
        return value,grad
    result=minimize(objective,np.array(start),method='L-BFGS-B',jac=True,bounds=bounds,options={'maxiter':maxiter,'ftol':1.e-10,'gtol':.02,'maxls':8})
    if np.max(np.abs(result.x-np.array([np.log(fit.groups[n][k]) for n,k in params])))>1e-7:objective(result.x)
    print('hyperparameters',[(name,key,round(fit.groups[name][key],4)) for name,key in params],file=sys.stderr,flush=True)
    return result


def predictive_draws(fit, count=512):
    if not hasattr(fit,'V'):
        fit.V,fit.mean_delta,fit.ch=posterior(fit)
    gen=np.random.default_rng(82561)
    z=gen.normal(size=(fit.pdim,count//2));z=np.concatenate((z,-z),axis=1)
    draw=(solve_triangular(fit.ch[0].T,z,lower=False,check_finite=False).T+fit.theta+fit.mean_delta)
    # The handbook identifies the home effect as a lift. Condition the joint
    # Gaussian on its being nonnegative, retaining all parameter correlations.
    home=fit.groups['home']['start']
    mean=fit.theta[home]+fit.mean_delta[home]
    sd=np.sqrt(fit.V[home,home])
    quantile=np.clip(ndtr((draw[:,home]-mean)/sd),1e-12,1-1e-12)
    positive=truncnorm.ppf(quantile,-mean/sd,np.inf,loc=mean,scale=sd)
    draw+=(positive-draw[:,home])[:,None]*(fit.V[:,home]/sd**2)[None,:]
    def get(name):return draw[:,fit.groups[name]['sl']]
    def quality(name):
        g=fit.groups[name]
        cross=g['talent']**2+g['form']**2*np.exp(-np.abs(fit.future-fit.times)/g['length'])
        w=np.linalg.solve(g['cov'],cross)
        result=get(name).reshape(count,-1,fit.nt)@w
        variance=max(0,g['talent']**2+g['form']**2-cross@w)
        noise=gen.normal(size=(count//2,result.shape[1]));noise=np.concatenate((noise,-noise))
        return result+np.sqrt(variance)*noise
    p=fit.h.players
    return dict(style=get('style')+get('style_mean')[:,p.role],quality=quality('quality')+get('quality_mean')[:,p.role],
                split=get('split'),kind=get('kind')+get('kind_mean')[:,p.style[fit.bowlers]],
                bowling=quality('bowling')+get('bowling_mean')[:,p.role[fit.bowlers]-1],
                venue=get('venue'),era=get('era')[:,-1],dew=get('dew')+get('chase'),home=get('home')[:,0],
                affinity=get('affinity').reshape(count,fit.np,fit.nv),hand=get('hand_type').reshape(count,2,2),
                pitch=get('pitch_type').reshape(count,2,3),day_sd=fit.groups['day']['sd'])
