import argparse
from pathlib import Path

import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--league", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
fixtures = pd.read_csv(Path(args.league) / "fixtures.csv")
pd.DataFrame({"fixture": fixtures.fixture, "p_home": 0.5}).to_csv(args.out, index=False)