#!/bin/bash
# Verifier entry point. The grader always writes /logs/verifier/reward.json, even if it crashes.
mkdir -p /logs/verifier
python /tests/grader.py > /logs/verifier/grader_stdout.txt 2> /logs/verifier/grader_stderr.txt
if [ ! -s /logs/verifier/reward.json ]; then
  echo '{"overall": 0.0, "functional_correctness": 0.0, "constraint_satisfaction": 0.0, "robustness": 0.0, "artifact_quality": 0.0}' > /logs/verifier/reward.json
fi
cat /logs/verifier/reward.json