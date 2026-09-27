# Canonical assignment requirements

The user confirmed that the supplied sections 4–9 below are canonical for this submission. They take precedence over earlier brief interpretations in historical notes or the PDF. Formatting has been normalized; the required models and artifacts have not been changed.

**Complete and submit all required artifacts, runnable components, validation, and evidence specified in the canonical assignment brief. The canonical brief is the source of truth if anything elsewhere differs.**

## 4. Harbor submission requirements

Submit a zip file or repository containing exactly one task directory unless otherwise approved. Use a stable slug such as `collinear-candidate/<task-name>`.

Required contents:

- `instruction.md`: clear task prompt, constraints, files to inspect, and expected deliverable.
- `task.toml`: Harbor metadata, timeouts, resource requirements, network policy, authorship, and category.
- `environment/Dockerfile` or `environment/docker-compose.yaml`: pinned, reproducible environment.
- `tests/test.sh`: verifier entrypoint that writes `/logs/verifier/reward.txt` or `/logs/verifier/reward.json`.
- `tests/test_*.py` or grader files: functional checks, fixtures, metrics, or judge logic.
- `solution/solve.sh`: oracle solution that passes the verifier.
- Seed files: codebase, logs, datasets, configs, mock services, docs, schemas, or databases as needed.
- `README.md` or `RUN_REPORT.md`: task idea, fairness rationale, why this is an economically viable/real task, model runs, verifier design, limitations, and reproduction commands.

Minimum commands to include:

```sh
harbor run -p ./<task-dir> -a oracle
harbor run -p ./<task-dir> -a <agent> -m <gpt-5.5-high-or-opus-4.7>
harbor view ./jobs
```

## 5. Verifier requirements

The verifier must check the core success criteria. You can use programmatic verifiers or agentic judges. Please avoid LLM as a Judge judging a trajectory.

For multi-criterion grading, prefer `reward.json`, for example:

```json
{
  "overall": 0.0,
  "functional_correctness": 0.0,
  "constraint_satisfaction": 0.0,
  "robustness": 0.0,
  "artifact_quality": 0.0
}
```

Make sure that your failure is not a false positive or negative.

## 6. Net-new requirement

The task must be newly created for this exercise.

No direct ports of SWE-bench, Terminal-Bench, public CTFs, Kaggle notebooks, coding challenges, public benchmark tasks, public issues, or previous Collinear tasks. Open-source libraries and small public datasets are allowed when properly licensed and transformed into a genuinely new task scenario.

Include a short provenance note explaining what was created from scratch and what external sources were used.

Feel free to take any domain of your choice: Coding, Finance, MCP Tool Calling, <Literally anything>.

## 7. Evidence of target-model failure

Run GPT-5.5-high or Claude Opus 4.7 (you can use harbor on prem) using the codex or claude code harness. Feel free to contact adit@collinear.ai for API credits.

A strong submission includes 1 model trials or clear pass/fail logs with the model failing on at least one critical thing. Include a short failure analysis: wrong hypothesis, incomplete inspection, bad state tracking, brittle patch, skipped verification, report hallucination, or other substantive failure.

## 8. Scoring rubric

| Criterion | Points |
|---|---:|
| Harbor compliance and reproducibility | 20 |
| Fairness and solvability | 20 |
| Verifier quality | 20 |
| Long-horizon difficulty | 15 |
| Evidence of frontier-model failure | 15 |
| Originality and realism | 10 |

## 9. Final checklist

- I submitted exactly one net-new Harbor task directory.
- `instruction.md` is clear and does not leak the solution.
- `task.toml` has accurate metadata, timeouts, resources, and network policy.
- The environment builds from a clean machine or documented container provider.
- `solution/solve.sh` is executable and oracle passes.
- `tests/test.sh` writes `/logs/verifier/reward.txt` or `reward.json`.
- The verifier checks meaningful success criteria and rejects shallow solutions.
- `RUN_REPORT.md` includes oracle result, target-model result or run command, failure analysis, realism/economic viability of task, and fairness audit.
- External sources and licenses are documented.
- The task is not copied from an existing benchmark, issue, CTF, tutorial, or prior internal task.
