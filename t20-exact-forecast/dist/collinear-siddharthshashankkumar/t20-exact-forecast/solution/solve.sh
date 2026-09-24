#!/bin/bash
# Oracle: install the reference forecaster as the solution
set -euo pipefail
HERE = "$(cd "$(dirname "$0")" && pwd)"
cp "$HERE/forecast.py" "$HERE/reference_forecaster.py" /app/solution/