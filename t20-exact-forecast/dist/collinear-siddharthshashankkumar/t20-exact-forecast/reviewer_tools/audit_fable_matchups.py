"""Reproduce Fable-r1's batting-card indexing error without running its forecast.

Only three reviewed method bodies are executed, after checking the complete
archived source hashes. Training, artifact imports, simulation and network are
not used. CSV counts describe reachable mismatches, not their scoring impact.

From source: .venv/bin/python dev/audit_fable_matchups.py
From an extracted task: python reviewer_tools/audit_fable_matchups.py
"""
import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace, MethodType

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TRIAL = Path("validation/jobs/replication-20260927-fable-r1/task__gZoWu3L")
APP = TRIAL / "artifacts/app"
SOURCES = {
    "solution/spec.py": "0f4e2503916a38341c7628776307f488ec90bf35231c32a888501fc3d8b5b05e",
    "solution/simulate.py": "566786d11e1613b3cdd8ec8a0d81934090c0f518f972649da18896d24479f180",
    "engine/model.py": "76d73fb1c749b3c6a5c37507eaefbf2f3e60bc892fa48f69f08b535202cd8c93",
}


def binding(path, disk_path=None):
    return {"path": str(path), "sha256": hashlib.sha256((disk_path or ROOT / path).read_bytes()).hexdigest()}


def reviewed_method(path, class_name, method_name, namespace):
    tree = ast.parse((ROOT / path).read_text(), filename=str(path))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
    # The full-file hashes were verified before extracting any executable code.
    module = ast.Module(body=[method], type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)
    location = {"path": str(path), "method": f"{class_name}.{method_name}",
                "start_line": method.lineno, "end_line": method.end_lineno}
    return namespace[method_name], location


def differential_cases(candidate_cards, candidate_block, public_cards):
    players = SimpleNamespace(role=np.zeros(22, int), hand=np.zeros(22, int),
                              style=np.r_[np.ones(11, int), np.zeros(11, int)])
    venues = SimpleNamespace(home_team=np.array([0]), pitch=np.array([0]))
    fixture = SimpleNamespace(home=0, away=1, venue=0, season=0,
                              home_xi=np.arange(11), away_xi=np.arange(11, 22),
                              home_bowlers=np.arange(5), away_bowlers=np.arange(11, 16))
    sizes = {"style_mean": 3, "style": 22, "tal_mean": 3, "q": 22, "split": 22,
             "kind_mean": 2, "kind": 10, "bq_mean": 3, "r": 10, "venue": 1,
             "era": 1, "chase_mean": 1, "chase": 1, "aff": 22, "home": 1,
             "type": 4, "pitch": 6}
    blocks, offset = {}, 0
    for name, size in sizes.items():
        blocks[name] = SimpleNamespace(start=offset, stop=offset + size)
        offset += size
    bowler_index = np.full(22, -1)
    bowler_index[np.r_[fixture.home_bowlers, fixture.away_bowlers]] = np.arange(10)
    spec = SimpleNamespace(L=SimpleNamespace(players=players, venues=venues, n_players=22),
                           K=0, n_seasons=0, des=SimpleNamespace(blocks=blocks),
                           bowlers=np.r_[fixture.home_bowlers, fixture.away_bowlers],
                           bowler_index=bowler_index, pair_index={(p, 0): p for p in range(22)})
    spec.block = MethodType(candidate_block, spec)
    results = []
    for equal_styles in (False, True):
        players.style[:] = 0 if equal_styles else np.r_[np.ones(11, int), np.zeros(11, int)]
        for effect, block in (("unit_split", "split"), ("unit_hand_by_pace", "type"),
                              ("unit_pace_pitch_help", "pitch")):
            theta = np.zeros((1, offset))
            if block == "split":
                theta[:, blocks[block].start:blocks[block].stop] = 1
            else:
                theta[:, blocks[block].start] = 1
            book = SimpleNamespace(players=players, venues=venues, style=np.zeros(22),
                                   quality=np.zeros(22), split=spec.block(theta, "split")[0],
                                   kind=np.zeros(22), bowl_quality=np.zeros(22),
                                   affinity=np.zeros((22, 1)), home_lift=0,
                                   type_table=spec.block(theta, "type")[0].reshape(2, 2),
                                   pitch_table=spec.block(theta, "pitch")[0].reshape(2, 3),
                                   pair_effect=lambda xi, bowlers: 0)
            sides, _, _ = candidate_cards(spec, theta, fixture)
            for side, team, xi, opposing in (
                ("home", 0, fixture.home_xi, fixture.away_bowlers),
                ("away", 1, fixture.away_xi, fixture.home_bowlers),
            ):
                expected, _ = public_cards(book, xi, team, opposing, 0)
                field = "quality" if block == "split" else "conditions"
                actual_array = sides[team][field][0]
                expected_array = getattr(expected, field)
                matches = bool(np.array_equal(actual_array, expected_array))
                if matches != equal_styles:
                    raise AssertionError(f"Unexpected differential result: {effect}, {side}, {equal_styles}")
                results.append({"case": effect, "batting_side": side,
                                "home_bowlers_style": "pace" if equal_styles else "spin",
                                "away_bowlers_style": "pace", "field": field,
                                "candidate_first_batter_by_bowling_slot": actual_array[0].tolist(),
                                "public_first_batter_by_bowling_slot": expected_array[0].tolist(),
                                "matches_public": matches, "equal_style_control": equal_styles})
    return results


def fixture_counts():
    # These are the submitted public inputs in both layouts. Record their
    # canonical task-relative paths so the report reproduces from the ZIP.
    candidates = [ROOT / "tests/leagues",
                  ROOT / "dist/collinear-siddharthshashankkumar/t20-exact-forecast/tests/leagues"]
    league_root = next((path for path in candidates if path.is_dir()), None)
    if league_root is None:
        raise FileNotFoundError("Packaged tests/leagues not found; package the source task first")
    results = []
    for name in ("visible", *(f"heldout_{letter}" for letter in "abcdefg")):
        folder = Path("tests/leagues") / name
        tables, sources = {}, []
        for filename in ("players.csv", "fixtures.csv", "fixture_lineups.csv"):
            path = folder / filename
            disk_path = league_root / name / filename
            with disk_path.open(newline="") as stream:
                tables[filename] = list(csv.DictReader(stream))
            sources.append(binding(path, disk_path))
        styles = {int(row["player"]): row["bowling_style"] for row in tables["players.csv"]}
        lineups = {}
        for row in tables["fixture_lineups.csv"]:
            if int(row["bowling_slot"]) >= 0:
                key = (int(row["fixture"]), int(row["team"]))
                lineups.setdefault(key, []).append((int(row["bowling_slot"]), int(row["player"])))
        differing = []
        for fixture in tables["fixtures.csv"]:
            fid = int(fixture["fixture"])
            home = sorted(lineups[fid, int(fixture["home"])])
            away = sorted(lineups[fid, int(fixture["away"])])
            if [slot for slot, _ in home] != list(range(5)) or [slot for slot, _ in away] != list(range(5)):
                raise ValueError(f"Unexpected bowling-slot schema in {name}/{fid}")
            slots = [i for i, ((_, h), (_, a)) in enumerate(zip(home, away)) if styles[h] != styles[a]]
            if slots:
                differing.append({"fixture": fid, "differing_slots": slots})
        results.append({"league": name, "total_fixtures": len(tables["fixtures.csv"]),
                        "fixtures_with_differing_style_vectors": len(differing),
                        "differing_bowling_slots": sum(len(item["differing_slots"]) for item in differing),
                        "differing_fixtures": differing, "source_files": sources})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/replication-20260927/fable-r1-matchup-audit.json")
    args = parser.parse_args()
    sources = []
    for filename, expected in SOURCES.items():
        source = binding(APP / filename)
        if source["sha256"] != expected:
            raise ValueError(f"Reviewed source hash changed; refusing execution: {source['path']}")
        sources.append(source)
    namespace = {"np": np, "PACE": 0,
                 "BattingCard": lambda style, quality, conditions: SimpleNamespace(
                     style=style, quality=quality, conditions=conditions),
                 "BowlingCard": lambda kind, quality: SimpleNamespace(kind=kind, quality=quality)}
    cards, loc1 = reviewed_method(APP / "solution/spec.py", "Spec", "cards", namespace)
    block, loc2 = reviewed_method(APP / "solution/spec.py", "Spec", "block", namespace)
    public, loc3 = reviewed_method(APP / "engine/model.py", "SkillBook", "cards", namespace)
    cases = differential_cases(cards, block, public)
    worlds = fixture_counts()
    report = {
        "schema_version": 1, "trial": str(TRIAL), "numpy_version": np.__version__,
        "commands": {"source": ".venv/bin/python dev/audit_fable_matchups.py",
                     "extracted_task": "python reviewer_tools/audit_fable_matchups.py"},
        "audit_script": binding(Path("reviewer_tools/audit_fable_matchups.py"), Path(__file__).resolve()),
        "scope": "Exact reviewed card-method differential probe plus static fixture CSV inspection. No forecast, training, simulation, network, or hidden truth probabilities are used.",
        "conclusion": "Delivered batting cards select split, hand/style and pitch/style effects using own-side bowling styles instead of the opponent's. Six constructed mismatches and six equal-style controls behave as expected. Opposing style vectors differ in 185/192 shipped fixtures (162/168 held-out).",
        "causal_limit": "This proves incorrect, reachable card feature selection. It does not measure its contribution to aggregate regret or explain the trial's final grading outcome.",
        "execution_boundary": "Only source-hash-bound Spec.cards, Spec.block and SkillBook.cards bodies were compiled; dataclass result containers were replaced with attribute-only SimpleNamespace containers. No archived module top-level code was imported.",
        "source_files": sources, "executed_methods": [loc1, loc2, loc3],
        "call_sites": [{"path": str(APP / "solution/simulate.py"), "lines": [55, 56]},
                       {"path": str(APP / "engine/model.py"), "lines": [200, 201]}],
        "differential_cases": cases, "fixture_audit": worlds,
        "totals": {"fixtures": sum(w["total_fixtures"] for w in worlds),
                   "fixtures_with_differing_style_vectors": sum(w["fixtures_with_differing_style_vectors"] for w in worlds),
                   "heldout_fixtures_with_differing_style_vectors": sum(w["fixtures_with_differing_style_vectors"] for w in worlds if w["league"] != "visible")},
    }
    if report["totals"] != {"fixtures": 192, "fixtures_with_differing_style_vectors": 185,
                           "heldout_fixtures_with_differing_style_vectors": 162}:
        raise AssertionError("Shipped fixture counts changed; review the conclusion before updating this audit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Confirmed 6 mismatch cases, 6 controls; 185/192 fixture style vectors differ. Report: {args.output}")


if __name__ == "__main__":
    main()
