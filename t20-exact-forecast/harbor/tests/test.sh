#!/bin/bash
# A verifier retry must never reuse an earlier success after a startup failure.
mkdir -p /logs/verifier || exit 1
rm -f /logs/verifier/reward.json /logs/verifier/reward.txt /logs/verifier/details.json || exit 1
grader_status=0
python /tests/grader.py > /logs/verifier/grader_stdout.txt 2> /logs/verifier/grader_stderr.txt || grader_status=$?
if [ ! -s /logs/verifier/reward.json ]; then
  echo '{"overall": 0.0, "functional_correctness": 0.0, "constraint_satisfaction": 0.0, "robustness": 0.0, "artifact_quality": 0.0}' > /logs/verifier/reward.json
fi
if [ ! -s /logs/verifier/details.json ]; then
  printf '{"grader_error":"grader exited before writing details (status %s); see grader_stderr.txt"}\n' "$grader_status" > /logs/verifier/details.json
fi
cat /logs/verifier/reward.json
