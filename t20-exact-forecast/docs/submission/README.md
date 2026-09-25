# Collinear take-home submission

## Learning what to trust

This folder is the design submission for `t20-exact-forecast`. The primary deliverable is [DESIGN_DOCUMENT.md](DESIGN_DOCUMENT.md): the benchmark's purpose, the IPL-inspired setting, the architecture, the grading rule, the verifier, the evidence and the fairness limits. The runnable Harbor task is at `dist/collinear-siddharthshashankkumar/t20-exact-forecast/` in this repository, built and gated, with every run recorded under `jobs/`.

## Reading order

1. [DESIGN_DOCUMENT.md](DESIGN_DOCUMENT.md), the design argument.
2. [DECISIONS.md](DECISIONS.md), the alternatives, evidence, changes of mind and accepted trade-offs.
3. [RUN_REPORT.md](RUN_REPORT.md), controls, ten runs of the named pair, five completed runs of the newer pair, exclusions, and reproduction commands.
4. [PROVENANCE.md](PROVENANCE.md), originality, external data, licences, methods, AI assistance and where the evidence is.
5. [instruction.md](instruction.md), the solver-facing task, verbatim from the package.

The extended version of the design document, with the seven system drawings, is `docs/DESIGN.pdf`; it says the same things at greater length.

## How this addresses the evaluation areas

| Evaluation area | Where to look | What is demonstrated |
|---|---|---|
| Problem novelty | Design §§1–2; Provenance | A new combination of calibrated synthetic worlds, public mechanics, hidden quantities, executable forecasting and truth-based scoring |
| Task validity | Design §§3–5, 9; Decisions D02–D06 | A realistic but controlled problem, four linked subgoals, an executable oracle, a do-nothing control and stated limitations |
| Evaluation design | Design §§6–8; Decisions D07–D10; Run Report | Proper probabilistic regret, held-out worlds, a pooled rule committed before any pilot, a separate verifier, reward fields and failure attribution |
| Clarity | Design summary, tables and diagram; instruction | Plain-language purpose, concrete deliverable, constraints, success rule and evidence status |

## The central argument

The benchmark's difficulty is not a hidden file-format trick. The agent receives a working simulator and a clear interface. It must infer how much to trust limited observations, test whether its assumptions fit the history it was given, and turn the result into a deterministic program that generalises to seven unseen worlds.

I own the synthetic world, so I know the probability that each fixture is won. Expected logarithmic regret against that probability separates forecast quality from the luck of one realised match. The verifier applies the 10% reference-relative rule to all eight worlds and to the seven held-out worlds separately; the rule was committed before any model ran and has not moved.

The most informative failure is a verification failure: a submitted program created synthetic validation leagues using the same broad ability assumptions it needed to question, and passed a careful test in a world that already agreed with its premise. The passing programs of the next generation built the same kind of check with spreads taken from the real league's estimates. This is why the benchmark evaluates not only whether an agent can fit a model, but whether it can build a check capable of disagreeing with that model.

## Results

The pair named in the brief's goal line, GPT-5.5 and Claude Opus 4.7, failed all ten runs at 1.11 to 1.70 times the reference's regret, nine with the fingerprint of a forecaster that believes small samples; reading the programs found prior scales set 3 to 44 times too weak, and changing that one constant moved each program most of the way to the reference. The newer pair, GPT-6-astra and Claude Fable 5.1, passed four of five completed runs at 1.008 to 1.072, with one Fable miss at 1.104 that passed on the held-out worlds. The bar sits between the two generations. The task is an evidenced, discriminating benchmark; it is not one that fails the newest pair, and the levers that would change that are documented as future work, each needing a fresh committed rule.

## The Harbor package

```text
dist/collinear-siddharthshashankkumar/t20-exact-forecast/
├── instruction.md
├── task.toml
├── environment/          # agent image and public task files
├── tests/                # verifier image, grader, private truth and fixtures
└── solution/solve.sh     # executable oracle entry point
```

From the repository root:

```sh
make venv
make package
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a oracle
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a nop
harbor check ./dist/collinear-siddharthshashankkumar/t20-exact-forecast
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-opus-4-7 --ak reasoning_effort=high
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-5.5 --ak reasoning_effort=high
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a claude-code -m anthropic/claude-fable-5-1 --ak reasoning_effort=high
harbor run -p ./dist/collinear-siddharthshashankkumar/t20-exact-forecast -a codex -m openai/gpt-6-astra --ak reasoning_effort=high
harbor view ./jobs
```

Model runs need the corresponding provider access; the oracle, the control and the linter need none.

## Checklist

- [x] One primary design document, with an extended version.
- [x] Problem novelty and provenance note.
- [x] Four linked subgoals with hypotheses, checks and a durable program deliverable.
- [x] Exact scoring definition and held-out evaluation rule, committed before any pilot.
- [x] Verifier architecture and false-positive/false-negative audit.
- [x] Oracle, control, linter and model evidence for both generations, with job identities.
- [x] Fairness rationale, limitations and next-version changes.
- [x] Reproduction commands and explicit resource and network assumptions.
- [x] External data attribution and licence.
