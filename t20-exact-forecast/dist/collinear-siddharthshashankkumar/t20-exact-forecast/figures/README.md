# Architecture figures

Seven diagrams share a common type scale, spacing system and color scheme. Each answers one question, with detailed reasoning kept in the linked documents.

| Figure | Question |
|---|---|
| [System overview](system_overview.svg) | How does calibration become a task with public inputs and private evaluation? |
| [Calibration](calibration_pipeline.svg) | Which inputs are measured, and which are design choices? |
| [Packaging](task_build_and_packaging.svg) | What is included in the one-task submission, and what reaches each image? |
| [Runtime](harbor_runtime.svg) | Which artifacts cross into the separate verifier? |
| [Grading](grading_rule.svg) | How do both accuracy gates and the other checks produce the reward? |
| [Research design](research_ladder.svg) | Why was the rule pooled and committed before model trials? |
| [Task selection](decision_path.svg) | Why was forecasting selected over the earlier candidates? |

The SVGs are editable vector assets; the PNGs are high-resolution copies for Markdown and document embedding. Teal indicates authoring/build work, blue public inputs or candidate execution, purple private evaluation, and amber scoring or cautions. Labels carry the meaning as well as color.

## Rebuild

From the source project's `t20-exact-forecast/` directory:

```sh
python3 figures/src/architecture.py
npm install --prefix figures
npm run --prefix figures render
```

SVG generation needs only Python's standard library. PNG rendering uses the pinned `sharp` version in `figures/package.json`. These are reviewer-tooling dependencies and do not change the evaluated task environment. The committed SVGs and PNGs are sufficient to read the submission without installing anything.

## Attribution and scope

The six original architecture drawings were by Rutvikk Kharod, used with permission. These replacements were redrawn from the repository and their existing organization with Codex assistance; the earlier drawings remain in Git history and the historical PDF. The task-selection diagram is new.

The diagrams describe the evaluated runtime. They do not imply that the frozen verifier enforces network isolation or that Monte Carlo estimates are exact probabilities. The result charts and the older system.svg/system.png overview are historical artifacts and were not regenerated. The seven files listed above are the current architecture set.

See [provenance](../PROVENANCE.md) and [decisions](../DECISIONS.md).
