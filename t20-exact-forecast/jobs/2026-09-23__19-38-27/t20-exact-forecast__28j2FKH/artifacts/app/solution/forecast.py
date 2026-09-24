import argparse
import sys
from pathlib import Path

# the solution folder first, so `reference_forecaster` is found; then /app, so `engine` is found
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import pandas as pd
from engine.league_io import load_league
from engine.model import load_public_model
from reference_forecaster import BallModelForecaster

parser = argparse.ArgumentParser()
parser.add_argument("--league", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
history, fixtures = load_league(args.league)
# the same settings the task data were built with: the public model, 4,000 copies per fixture
forecaster = BallModelForecaster("reference", load_public_model(), copies=4000).fit(history)
pd.DataFrame({"fixture": [f.match for f in fixtures], "p_home": forecaster.predict(fixtures)}).to_csv(args.out, index=False)