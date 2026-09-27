# Architecture figures

Seven diagrams share a common type scale, spacing system and color scheme. Each answers one question, with detailed reasoning kept in the linked documents.

| Figure | Question |
|---|---|
| [System overview](system_overview.svg) | Which inputs reach the submitted forecaster, and which reach only the grader? |
| [Calibration](calibration_pipeline.svg) | Which inputs are measured, and which are design choices? |
| [Packaging](task_build_and_packaging.svg) | What is included in the one-task submission, and what reaches each image? |
| [Runtime](harbor_runtime.svg) | How do artifacts, league inputs and returned forecasts cross the process boundaries? |
| [Grading](grading_rule.svg) | How do both accuracy gates and the other checks produce the reward? |
| [Research design](research_ladder.svg) | Why was the rule pooled and committed before the archived trial series? |
| [Task selection](decision_path.svg) | Why was forecasting selected over the earlier candidates? |

The SVGs are editable vector assets; the PNGs are high-resolution copies for Markdown and document embedding. Teal indicates authoring/build work, blue public inputs or candidate execution, purple private evaluation, and amber scoring or cautions. Labels carry the meaning as well as color.

The overview follows the actual data flow: the simulator produces public-schema league files and private scoring data; the submitted program receives league files and returns CSV forecasts; the grader combines those forecasts with private probability estimates and reference scores. “Public schema” does not mean every league is visible during development: one is visible then, and seven are held out until grading.

The runtime diagram separates workspace preparation, execution as `runner`, and privileged scoring. Its arrows route private scores only into the scoring process. Each SVG includes a full text description for assistive readers, and the overview uses larger core labels for legibility when embedded in the README.

## Rebuild

From the source project's `t20-exact-forecast/` directory:

```sh
python3 figures/src/architecture.py
npm ci --prefix figures
npm run --prefix figures render
```

SVG generation needs only Python's standard library. PNG rendering uses `sharp` 0.35.4 with a committed npm lockfile for its dependency graph. Fonts and platform rasterization can affect exact PNG bytes; the editable SVG is the canonical drawing. These are reviewer-tooling dependencies and do not change the task environment. The committed SVGs and PNGs are sufficient to read the submission without installing anything.

## Attribution and scope

The six original architecture drawings were by Rutvikk Kharod, used with permission. These replacements were redrawn from the repository and their existing organization with Codex assistance; the earlier drawings remain in Git history and the historical PDF. The task-selection diagram is new.

The diagrams describe submission **v0.1.1**, which hardens artifact handling and verification and declares a verifier with no network. The forecasting rule, data, engine and oracle are unchanged. The archived model trials used **v0.1.0**; those results are not relabeled as fresh trials of the hardened version. Stored probability estimates still have Monte Carlo uncertainty.

The result charts and the older system.svg/system.png overview are historical artifacts and were not regenerated. The seven files listed above are the current architecture set.

See [provenance](../PROVENANCE.md) and [decisions](../DECISIONS.md).
