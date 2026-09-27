#!/usr/bin/env python3
"""Forecast the supplied T20 fixtures from their league's public history.

Usage: python solution/forecast.py --league league --out forecasts.csv
"""
import os
# Bound numerical-library parallelism before importing numpy or scipy.
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
os.environ['MKL_NUM_THREADS']='2'
os.environ['NUMEXPR_NUM_THREADS']='2'

import argparse
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from engine.league_io import load_league
from engine.model import load_public_model
from inference import Fit
from simulation import Predictor


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    start=time.monotonic()
    history,fixtures=load_league(args.league)
    fit=Fit(history,load_public_model())
    fit.train(iterations=7)
    fit.posterior()
    predictor=Predictor(fit,draws=512)
    predictions=[]
    for fixture in fixtures:
        probability=predictor.predict(fixture,n=65536,seed=int(fixture.match))
        predictions.append((fixture.match,float(np.clip(probability,.002,.998))))
        print(f'fixture {fixture.match}: {probability:.6f}',file=sys.stderr,flush=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(predictions,columns=['fixture','p_home']).to_csv(args.out,index=False)
    print(f'Finished in {time.monotonic()-start:.1f}s',file=sys.stderr)


if __name__=='__main__':
    main()
