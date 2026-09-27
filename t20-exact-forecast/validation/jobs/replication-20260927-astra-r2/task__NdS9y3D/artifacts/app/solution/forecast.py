"""Forecast a public simulated league; no fitted league data are bundled."""
import os

# Keep fitting within the two-core runtime budget, including BLAS operations.
os.environ['OPENBLAS_NUM_THREADS'] = '2'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.model import load_public_model
from engine.league_io import load_league
from fit import Fit
from simulate import Posterior, forecast


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    started = time.monotonic()
    history, fixtures = load_league(args.league)
    model = load_public_model()
    fitted = Fit(history, model, periods=2).fit(steps=55, verbose=False)
    posterior = Posterior(fitted, count=512)
    print(f'Fitted ball model in {time.monotonic() - started:.1f}s', file=sys.stderr, flush=True)
    rows = []
    for i, fixture in enumerate(fixtures):
        q = forecast(posterior, fixture, n=49152, seed=81237 + i)
        if not np.isfinite(q):
            raise RuntimeError('Simulation produced a nonfinite probability')
        rows.append((fixture.match, float(np.clip(q, 0.002, 0.998))))
        if (i + 1) % 6 == 0:
            print(f'Simulated {i + 1}/{len(fixtures)} fixtures', file=sys.stderr, flush=True)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=['fixture', 'p_home']).to_csv(output, index=False)
    print(f'Finished in {time.monotonic() - started:.1f}s', file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
