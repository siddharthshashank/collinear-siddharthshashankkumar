import os
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
import sys,time,pickle
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from engine.league_io import load_league
from engine.model import load_public_model
from fit import Fitter
h,fs=load_league(sys.argv[1] if len(sys.argv)>1 else '/app/league')
f=Fitter(h,load_public_model())
print('size',f.size,flush=True)
f.fit(iterations=30)
for name,g in f.groups.items():
 if g['fixed']:
  print(name,f.values(f.theta,name),flush=True)
# Only a development cache, never consumed by forecast.py.
with open('/app/solution/fit_debug.pkl','wb') as out: pickle.dump(f,out)
