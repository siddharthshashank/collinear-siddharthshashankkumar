"""Regression check against the supplied engine's innings simulator."""
import numpy as np
from forecast import load_league, load_public_model, SkillBook
from engine.model import InningsSimulator
from predict import tables, innings

def check(folder):
    h,ff=load_league(folder); f=ff[0]; gen=np.random.default_rng(14)
    p,v=h.players,h.venues; np_=len(p.role); nv=len(v.pitch)
    def draw(shape): return gen.normal(0,.2,shape)
    book=SkillBook(p,v,draw(np_),draw(np_),draw(np_),draw(np_),draw(np_),draw((2,2)),draw((2,3)),draw(nv),draw(nv),draw((np_,nv)),.15,.1,.2,.07)
    skills={k:np.asarray(getattr(book,k))[None,:] for k in ('style','quality','split','kind','bowl_quality','affinity')}
    skills.update(venue=book.venue_level[None,:],home=np.array([[book.home_lift]]),type=book.type_table.reshape(1,4),pitch=book.pitch_table.reshape(1,6),dew=(book.venue_dew-book.wear)[None,:],era=np.array([book.era]))
    model=load_public_model(); sim=InningsSimulator(model)
    table=tables(model,p,v,skills,f.home_xi,f.home,f.away_bowlers,f.venue)
    n=2048; day=gen.normal(0,book.day_sd,n)
    for target in (None,gen.integers(75,240,n)):
        chasing=target is not None
        ref=sim.play(*book.cards(f.home_xi,f.home,f.away_bowlers,f.venue),book.shift(f.venue,chasing)+day,n,np.random.default_rng(88),target=target)
        got=innings(model,table[int(chasing)],day,np.zeros(n,dtype=int),np.random.default_rng(88),target=target)
        np.testing.assert_array_equal(ref,got)
    print('Both innings modes exactly match the public simulator (2,048 trials each).')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--league',required=True)
    check(parser.parse_args().league)
