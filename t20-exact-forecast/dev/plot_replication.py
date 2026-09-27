"""Draw the fixed eight-slot replication without hiding incomplete runs.

Uses the Python standard library to write an accessible SVG. Optional PNG export
uses the same Node/Sharp renderer dependency as the architecture figures; neither
dependency is installed in the evaluated task environment.

    python dev/plot_replication.py
    python dev/plot_replication.py --png --node /path/to/node

Input: validation/replication-20260927/results.json. Required top-level fields are
task_version, relative_tolerance, planned_trials, and trials. Each trial supplies
trial_id, model, harness, reasoning_effort, replicate, status, all_world_ratio,
held_out_ratio, overall_reward, note, and job_path. Extra audit fields are allowed.
The separate optional attempts list is retained as evidence, not treated as new
trial slots. One recorded disposition per slot is plotted. Missing ratios remain
missing, and no scores are inferred from a process exit or status string.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import textwrap
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "validation" / "replication-20260927" / "results.json"
STATUSES = {"completed", "interrupted", "infrastructure_error", "running", "pending"}
W = 1600
INK, MUTED, GRID, BG = "#172A3A", "#516477", "#D9E1E9", "#FFFFFF"
ALL_COLOR, HELD_COLOR, LIMIT_COLOR = "#2164A6", "#735395", "#A34435"
CHART_LEFT, CHART_RIGHT = 390, 1050
TOP, ROW_GAP, GROUP_GAP = 310, 76, 16


def number(value, field, nullable=True):
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number" + (" or null" if nullable else ""))
    return float(value)


def load_results(path):
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("planned_trials") != 8 or len(data.get("trials", [])) != 8:
        raise ValueError("Keep all eight preregistered trial slots, including pending and failed attempts.")
    if not isinstance(data.get("task_version"), str) or not data["task_version"]:
        raise ValueError("task_version must identify the evaluated task version")
    tolerance = number(data.get("relative_tolerance"), "relative_tolerance", nullable=False)
    if tolerance < 0:
        raise ValueError("relative_tolerance cannot be negative")
    groups, seen_ids, seen_slots = {}, set(), set()
    for trial in data["trials"]:
        for key in ("trial_id", "model", "harness", "reasoning_effort", "status"):
            if not isinstance(trial.get(key), str) or not trial[key].strip():
                raise ValueError(f"Each trial needs a nonempty {key}")
        if trial["trial_id"] in seen_ids:
            raise ValueError(f"Duplicate trial_id: {trial['trial_id']}")
        seen_ids.add(trial["trial_id"])
        if trial["status"] not in STATUSES:
            raise ValueError(f"Unrecognized status for {trial['trial_id']}: {trial['status']}")
        if trial.get("replicate") not in (1, 2) or isinstance(trial.get("replicate"), bool):
            raise ValueError(f"Replicate must be 1 or 2: {trial['trial_id']}")
        slot = (trial["model"], trial["replicate"])
        if slot in seen_slots:
            raise ValueError(f"Duplicate model/replicate slot: {slot}")
        seen_slots.add(slot)
        for key in ("all_world_ratio", "held_out_ratio", "overall_reward"):
            if key not in trial:
                raise ValueError(f"{trial['trial_id']} needs {key}; use null for an unavailable result")
            trial[key] = number(trial[key], f"{trial['trial_id']}.{key}")
            if trial[key] is not None and trial[key] < 0:
                raise ValueError(f"{trial['trial_id']}.{key} cannot be negative")
        reward = trial["overall_reward"]
        if reward is not None and reward > 1:
            raise ValueError(f"overall_reward is outside [0, 1]: {trial['trial_id']}")
        if trial["status"] == "completed" and reward is None:
            raise ValueError(f"A completed trial needs its verifier reward: {trial['trial_id']}")
        if reward == 1.0 and any(trial[key] is None for key in ("all_world_ratio", "held_out_ratio")):
            raise ValueError(f"A full pass needs both recorded ratios: {trial['trial_id']}")
        # Grader summaries may round ratios to three decimals. Beyond that
        # rounding allowance, inconsistent evidence should be investigated.
        if reward == 1.0 and max(trial["all_world_ratio"], trial["held_out_ratio"]) > 1 + tolerance + 0.0005:
            raise ValueError(f"A full-pass reward conflicts with a recorded accuracy ratio: {trial['trial_id']}")
        for key in ("note", "job_path"):
            if trial.get(key) is not None and not isinstance(trial[key], str):
                raise ValueError(f"{trial['trial_id']}.{key} must be text")
        groups.setdefault(trial["model"], []).append(trial)
    if len(groups) != 4 or any(len(trials) != 2 for trials in groups.values()):
        raise ValueError("The fixed batch must retain two trial slots for each of four models.")
    if "attempts" in data and not isinstance(data["attempts"], list):
        raise ValueError("attempts must be a list of retained attempt records")
    rows = [trial for trials in groups.values() for trial in sorted(trials, key=lambda t: t["replicate"])]
    return data, rows, hashlib.sha256(raw).hexdigest()


def disposition(trial):
    status = trial["status"]
    if status == "completed":
        if trial["overall_reward"] == 1.0:
            return "PASS", "#16766F"
        return "NO FULL PASS", "#895610"
    return {
        "interrupted": ("INTERRUPTED", "#895610"),
        "infrastructure_error": ("INFRA ERROR", "#A34435"),
        "running": ("RUNNING", MUTED),
        "pending": ("PENDING", MUTED),
    }[status]


def nice_ticks(lo, hi):
    step = (hi - lo) / 5
    power = 10 ** math.floor(math.log10(step))
    step = next(v * power for v in (1, 2, 2.5, 5, 10) if v * power >= step)
    first, last = math.ceil(lo / step), math.floor(hi / step)
    return [i * step for i in range(first, last + 1)]


def draw(data, rows, source_hash, source_label):
    limit = 1 + data["relative_tolerance"]
    observed = [trial[key] for trial in rows for key in ("all_world_ratio", "held_out_ratio") if trial[key] is not None]
    lo = max(0, min([1.0, *observed]) - 0.08)
    hi = max([limit + 0.1, *observed])
    hi += max(0.05, (hi - lo) * 0.06)
    axis = lambda value: CHART_LEFT + (value - lo) / (hi - lo) * (CHART_RIGHT - CHART_LEFT)
    ys = [TOP + index * ROW_GAP + (index // 2) * GROUP_GAP for index in range(8)]
    axis_y = ys[-1] + 45
    notes = []
    for trial in rows:
        if trial.get("note"):
            notes.extend(textwrap.wrap(f"{trial['trial_id']}: {trial['note']}", width=122, break_long_words=False, break_on_hyphens=False))
    footer_y = axis_y + 88
    height = footer_y + 130 + (len(notes) * 29 + 42 if notes else 0)
    if data.get("test_fixture"):
        height += 36
    description = (
        f"Eight declared trial slots for task v{data['task_version']}, two per model. "
        f"Filled blue dots show the all-eight-world regret ratio; hollow purple dots show the held-out-seven ratio. "
        f"Both accuracy gates require ratios at most {limit:.2f}. A full pass also requires the other verifier checks. "
        "Missing scores are not plotted. Interrupted and infrastructure outcomes remain explicitly labeled. "
        + " ".join(f"{trial['trial_id']}: {trial['status']}; all-world ratio {trial['all_world_ratio']}; held-out ratio {trial['held_out_ratio']}; reward {trial['overall_reward']}." for trial in rows)
    )
    items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img" aria-labelledby="title description">',
             '<title id="title">Eight fresh model trials, shown individually</title>',
             f'<desc id="description">{escape(description)}</desc>',
             f'<rect width="{W}" height="{height}" fill="{BG}"/>']

    def text(x, y, value, size=24, color=INK, weight=400, anchor="start"):
        items.append(f'<text x="{x:.2f}" y="{y:.2f}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(str(value))}</text>')

    def line(x1, y1, x2, y2, color=GRID, width=1.4, dashed=False):
        dash = ' stroke-dasharray="8 7"' if dashed else ""
        items.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}"{dash}/>')

    def dot(x, y, held=False):
        color = HELD_COLOR if held else ALL_COLOR
        fill = "white" if held else color
        items.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="8" fill="{fill}" stroke="{color}" stroke-width="3"/>')

    text(56, 64, "Eight fresh trials, shown individually", 40, weight=700)
    text(56, 104, "Each row is one declared trial slot. Lower regret relative to the reference is better.", 25, MUTED)
    text(56, 146, f"Task v{data['task_version']}  ·  Two trials per model  ·  Fixed accuracy limit: {limit:.2f}×", 24, MUTED)
    dot(65, 198); text(86, 206, "All 8 worlds", 23)
    dot(304, 198, held=True); text(325, 206, "Held-out 7", 23)
    line(546, 198, 597, 198, LIMIT_COLOR, 3, True); text(610, 206, f"{limit:.2f}× limit", 23)
    text(980, 206, "Missing scores stay unplotted", 23, MUTED)
    text(56, 261, "MODEL / TRIAL", 20, MUTED, 700)
    text(CHART_LEFT, 261, "REGRET / REFERENCE", 20, MUTED, 700)
    text(1092, 261, "ALL 8 / HELD 7", 20, MUTED, 700)
    text(1358, 261, "DISPOSITION", 20, MUTED, 700)
    for group in range(4):
        y = ys[group * 2] - 27
        fill = "#F7F9FC" if group % 2 == 0 else "white"
        items.append(f'<rect x="40" y="{y}" width="1520" height="{ROW_GAP + 66}" rx="10" fill="{fill}"/>')
    items.append(f'<rect x="{CHART_LEFT}" y="280" width="{axis(limit)-CHART_LEFT:.2f}" height="{axis_y-280}" fill="#EAF5F2" fill-opacity="0.65"/>')
    for tick in nice_ticks(lo, hi):
        line(axis(tick), 280, axis(tick), axis_y)
        text(axis(tick), axis_y + 34, f"{tick:.2f}", 21, MUTED, anchor="middle")
    line(axis(1.0), 280, axis(1.0), axis_y, "#95A3B1", 1.6, True)
    line(axis(limit), 280, axis(limit), axis_y, LIMIT_COLOR, 3, True)
    line(CHART_LEFT, axis_y, CHART_RIGHT, axis_y, "#A8B5C1")
    for index, (trial, y) in enumerate(zip(rows, ys)):
        label, status_color = disposition(trial)
        text(56, y, f"{trial['model']} · {trial['replicate']}", 25, weight=700)
        text(56, y + 28, f"{trial['harness']} · {trial['reasoning_effort']}", 21, MUTED)
        all_ratio, held_ratio = trial["all_world_ratio"], trial["held_out_ratio"]
        if all_ratio is not None and held_ratio is not None:
            line(axis(all_ratio), y - 8, axis(held_ratio), y + 8, "#9AA8B5", 2)
        if all_ratio is not None:
            dot(axis(all_ratio), y - 8)
        if held_ratio is not None:
            dot(axis(held_ratio), y + 8, held=True)
        if all_ratio is None and held_ratio is None:
            fill = "#F7F9FC" if (index // 2) % 2 == 0 else "white"
            items.append(f'<rect x="{CHART_LEFT}" y="{y-23}" width="{CHART_RIGHT-CHART_LEFT}" height="49" fill="{fill}"/>')
            messages = {"pending": "Not started", "running": "No scored forecast yet", "interrupted": "Interrupted; no scored forecast", "infrastructure_error": "Infrastructure error; no scored forecast", "completed": "No valid scored forecast"}
            text(CHART_LEFT + 18, y + 7, messages[trial["status"]], 22, MUTED)
        ratio_label = " / ".join("—" if value is None else f"{value:.3f}" for value in (all_ratio, held_ratio))
        text(1092, y + 7, ratio_label, 25)
        text(1358, y + 2, label, 20, status_color, 700)
        reward = trial["overall_reward"]
        if reward is not None:
            text(1358, y + 28, f"reward {reward:.3f}", 20, MUTED)
    text(56, footer_y, "Shading marks the accuracy limit. A complete pass also requires all constraint and output checks.", 23, MUTED)
    text(56, footer_y + 34, "These eight rows describe this batch; they are not a population pass-rate estimate.", 23, MUTED)
    attempt_note = f" · {len(data['attempts'])} attempt records retained" if "attempts" in data else ""
    text(56, footer_y + 68, f"Source: {source_label}{attempt_note}", 19, MUTED)
    text(56, footer_y + 96, f"Input SHA-256: {source_hash[:20]}…  ·  Recorded slot dispositions; source JSON and linked jobs retain attempt-level evidence.", 19, MUTED)
    if notes:
        text(56, footer_y + 137, "Recorded trial notes", 23, weight=700)
        for index, note in enumerate(notes):
            text(56, footer_y + 169 + index * 29, note, 20, MUTED)
    if data.get("test_fixture"):
        text(1544, height - 20, "LAYOUT TEST FIXTURE — NOT MODEL EVIDENCE", 23, LIMIT_COLOR, 700, anchor="end")
    items.append("</svg>")
    return "\n".join(items) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="SVG path; default: replication-results.svg beside input JSON")
    parser.add_argument("--png", action="store_true", help="Also render a PNG through the existing Node/Sharp dependency")
    parser.add_argument("--node", default="node", help="Node executable used only with --png; NODE_PATH may locate Sharp")
    args = parser.parse_args()
    data, rows, source_hash = load_results(args.input)
    output = args.output or args.input.with_name("replication-results.svg")
    try:
        source_label = str(args.input.resolve().relative_to(ROOT))
    except ValueError:
        source_label = args.input.name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(draw(data, rows, source_hash, source_label))
    print(f"Wrote {output}")
    if args.png:
        code = "const sharp=require('sharp'); sharp(process.argv[1],{density:144}).png().toFile(process.argv[2]).catch(e=>{console.error(e.message);process.exit(1)});"
        subprocess.run([args.node, "-e", code, str(output), str(output.with_suffix('.png'))], check=True)
        print(f"Wrote {output.with_suffix('.png')}")


if __name__ == "__main__":
    main()
