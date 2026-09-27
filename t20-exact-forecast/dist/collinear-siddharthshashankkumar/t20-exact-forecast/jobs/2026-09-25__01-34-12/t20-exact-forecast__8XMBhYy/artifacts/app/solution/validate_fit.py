"""Forward validation on the final historical season (development diagnostic)."""
import sys
import numpy as np
from forecast import Fit,load_league
from engine.model import History

def main(folder):
    h,_=load_league(folder)
    last=int(h.balls.season.max())
    train=History(h.balls[h.balls.season<last].copy(),h.matches[h.matches.season<last].copy(),h.players,h.venues,seasons=last)
    fit=Fit(train); book=fit.train(4)
    b=h.balls[h.balls.season==last]; m=fit.model; p=h.players; v=h.venues
    bat=b.batter.to_numpy(); bowl=b.bowler.to_numpy(); venue=b.venue.to_numpy()
    chasing=(b.innings.to_numpy()==2).astype(float)
    pressure=np.where(chasing,m.pressure(b.target.to_numpy(),b.runs_before.to_numpy(),b.over.to_numpy()*6+b.ball.to_numpy()),0)
    base=m.situation(b.over.to_numpy(),b.position.to_numpy(),b.wickets_before.to_numpy(),chasing,pressure)
    effects=[np.outer(book.style[bat],m.bs),np.outer(book.quality[bat]+np.where(p.style[bowl]==0,.5,-.5)*book.split[bat],m.bq),np.outer(book.kind[bowl],m.wt),np.outer(book.bowl_quality[bowl],m.wq)]
    conditions=book.affinity[bat,venue]+book.home_lift*(v.home_team[venue]==b.batting_team.to_numpy())+book.type_table[p.hand[bat],p.style[bowl]]-book.pitch_table[p.style[bowl],v.pitch[venue]]+book.venue_level[venue]+book.era+chasing*book.venue_dew[venue]
    effects.append(np.outer(conditions,m.c))
    for variant in ('full','role_means_only','no_recent_form','public'):
        z=base+sum(effects)
        if variant=='role_means_only':
            bm=fit.x[fit.groups['quality_mean']['idx']][p.role[bat]]
            wm=fit.x[fit.groups['bowl_mean']['idx']][p.role[bowl]]
            sm=fit.x[fit.groups['style_mean']['idx']][p.role[bat]]
            km=fit.x[fit.groups['kind_mean']['idx']][p.style[bowl]]
            z=base+effects[-1]+np.outer(sm,m.bs)+np.outer(bm,m.bq)+np.outer(km,m.wt)+np.outer(wm,m.wq)
        if variant=='no_recent_form':
            for name,n,indices,d in [('quality',fit.np,bat,m.bq),('bowl_quality',fit.nb,fit.bowl_map[bowl],m.wq)]:
                gg=fit.groups[name]; aa,bb=gg['hyper']; xx=fit.x[gg['idx']].reshape(n,fit.nt)
                from scipy import linalg
                kt=fit.kernel(gg['hyper'])
                past=xx@linalg.solve(kt,np.full(fit.nt,aa*aa),assume_a='pos')
                future=xx@linalg.solve(kt,aa*aa+bb*bb*.5**(fit.ns-fit.times),assume_a='pos')
                z+=np.outer((past-future)[indices],d)
        if variant=='public': z=base
        probs=m.shares(z)
        loss=-np.log(probs[np.arange(len(b)),b.outcome.to_numpy()])
        print(variant,loss.mean(),loss.sum())
    print('fitted means', {name: fit.x[fit.groups[name]['idx']] for name in ('style_mean','quality_mean','kind_mean','bowl_mean','home','era')})

if __name__=='__main__':main(sys.argv[1])
