"""The whole project on one grid: six lanes, nodes aligned to rows, arrows horizontal or vertical with at most one bend.

    python architecture.py  ->  architecture.svg, architecture.pdf
"""
from xml.sax.saxutils import escape

W, H = 1760, 950
INK, MUTED, LINE = "#1b232b", "#5a646e", "#8b949c"
FILL = {"process": "#ffffff", "public": "#e8f1fa", "private": "#fbe9e7", "doc": "#fbf5e6", "raw": "#f1f1f1"}
EDGE = {"process": "#2c3640", "public": "#3d76b3", "private": "#b8483d", "doc": "#a3823a", "raw": "#8b949c"}
NW, NH = 224, 66
ROW = {1: 176, 2: 270, 3: 364, 4: 458, 5: 552, 6: 646}
COL = {"A": 180, "B": 500, "C": 820, "D": 1140, "E": 1520}
LANE = {"A": (30, 330), "B": (350, 650), "C": (670, 970), "D": (990, 1290), "E": (1310, 1730)}
BOTTOM = 816

out = []
def add(s): out.append(s)

def text(x, y, s, size=12, weight="normal", fill=INK, anchor="middle", family="Helvetica, Arial, sans-serif"):
    add(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')

def lane(x0, y0, x1, y1, title, subtitle):
    add(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="10" fill="#f7f8f9" stroke="#d5dadf" stroke-width="1"/>')
    text(x0 + 14, y0 + 24, title, 14, "bold", INK, "start")
    text(x0 + 14, y0 + 42, subtitle, 11, "normal", MUTED, "start")

NODES = {}
def node(key, kind, title, sub, x, y, w=NW, mono=False):
    NODES[key] = (x, y, w, NH)
    add(f'<rect x="{x - w/2}" y="{y - NH/2}" width="{w}" height="{NH}" rx="6" fill="{FILL[kind]}" stroke="{EDGE[kind]}" stroke-width="1.4"/>')
    fam = "Menlo, Consolas, monospace" if mono else "Helvetica, Arial, sans-serif"
    lines = [sub] if isinstance(sub, str) else list(sub)
    ty = y - 9 if len(lines) == 1 else y - 16
    text(x, ty, title, 10.5 if w < 150 else (12.5 if len(title) < 28 else 11), "bold", INK, "middle", fam)
    for i, line in enumerate(lines):
        text(x, ty + 17 + 13 * i, line, 10.5, "normal", MUTED)

def pt(key, side, off=0):
    x, y, w, h = NODES[key]
    return {"l": (x - w/2, y + off), "r": (x + w/2, y + off), "t": (x + off, y - h/2), "b": (x + off, y + h/2)}[side]

def path(points, dashed=False, color=INK, head=True):
    d = "M " + " L ".join(f"{x},{y}" for x, y in points)
    dash = ' stroke-dasharray="6,4"' if dashed else ""
    marker = ' marker-end="url(#head)"' if head else ""
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.5"{dash}{marker}/>')

def label(x, y, s, anchor="middle"):
    tw = 6.0 * len(s) + 10
    lx = x - tw/2 if anchor == "middle" else x - 4
    add(f'<rect x="{lx}" y="{y - 10}" width="{tw}" height="15" fill="#ffffff"/>')
    text(x, y + 2, s, 10, "normal", MUTED, anchor)

def straight(a, sa, b, sb, **kw): path([pt(a, sa), pt(b, sb)], **kw)

def fork(src, targets):
    """src's bottom splits to the tops of the targets through one horizontal rail."""
    x0, y0 = pt(src, "b"); rail = y0 + (pt(targets[0], "t")[1] - y0) / 2
    path([(x0, y0), (x0, rail)], head=False)
    xs = [pt(t, "t")[0] for t in targets]
    path([(min(xs), rail), (max(xs), rail)], head=False)
    for t in targets: path([(pt(t, "t")[0], rail), pt(t, "t")])

def join(sources, dst):
    """the bottoms of the sources merge on one rail into dst's top."""
    x1, y1 = pt(dst, "t"); rail = pt(sources[0], "b")[1] + (y1 - pt(sources[0], "b")[1]) / 2
    xs = [pt(s, "b")[0] for s in sources]
    for s in sources: path([pt(s, "b"), (pt(s, "b")[0], rail)], head=False)
    path([(min(xs), rail), (max(xs), rail)], head=False)
    path([(x1, rail), (x1, y1)])

def bus(sources, target, x):
    ys = [pt(s, "r")[1] for s in sources]; tx, ty = pt(target, "l")
    for s in sources: path([pt(s, "r"), (x, pt(s, "r")[1])], head=False)
    path([(x, min(ys + [ty])), (x, max(ys + [ty]))], head=False)
    path([(x, ty), (tx, ty)])

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Helvetica, Arial, sans-serif">')
add('<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="' + INK + '"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(30, 40, "t20-exact-forecast: how the task is built, packaged, run and evidenced", 20, "bold", INK, "start")
text(30, 62, "Six stages, left to right. Blue is what the agent sees; red is what only the generator and the verifier hold.", 12, "normal", MUTED, "start")

lane(LANE["A"][0], 84, LANE["A"][1], 706, "1  Calibration", "dev/, from the real archive")
lane(LANE["B"][0], 84, LANE["B"][1], 706, "2  Synthetic world", "league/, holds the hidden state")
lane(LANE["C"][0], 84, LANE["C"][1], 706, "3  Task data", "dev/make_task_data.py, dev/bar_analysis.py")
lane(LANE["D"][0], 84, LANE["D"][1], 706, "4  Packaging", "package_task.py, one Harbor task directory")
lane(LANE["E"][0], 84, LANE["E"][1], 706, "5  Harbor runtime", "two containers; only two artifacts cross")
lane(30, 736, 1730, 880, "6  Evidence and documents", "everything a reviewer reads is generated from the records")

A, B, C, D, E = (COL[k] for k in "ABCDE")
# lane 1
node("archive", "raw", "Cricsheet IPL archive", "raw YAML, ODC-BY 1.0, not tracked", A, ROW[1])
node("parse", "process", "parse_archive.py", "data/balls.pkl, one row per delivery", A, ROW[2], mono=True)
node("fit_state", "process", "fit_state.py", ("situation model,", "player directions"), A - 58, ROW[3], w=108, mono=True)
node("fit_const", "process", "fit_constants.py", ("extras, venues,", "interactions, targets"), A + 58, ROW[3], w=108, mono=True)
node("build", "process", "build_calibration.py", "league/calibration.json, aggregates only", A, ROW[4], mono=True)
node("design", "process", "calibration.py", ("Calibration: measured constants", "Design: chosen constants, with reasons"), A, ROW[5], mono=True)
node("validate", "process", "validate_world.py", ("three leagues against the real targets;", "three Design constants tuned to them"), A, ROW[6], mono=True)
straight("archive", "b", "parse", "t")
fork("parse", ["fit_state", "fit_const"])
join(["fit_state", "fit_const"], "build")
straight("build", "b", "design", "t")
straight("design", "b", "validate", "t")
x = A + NW/2 + 18
path([pt("validate", "r"), (x, ROW[6]), (x, ROW[5]), pt("design", "r")], dashed=True, color=LINE)

# lane 2
node("truth_engine", "private", "TruthEngine", ("100,000 copies per batting order", "the true p for every fixture"), B, ROW[3])
node("skillbook", "private", "Hidden SkillBook", ("skills, form, venues, dew, affinities", "never leaves this lane"), B, ROW[4])
node("league", "process", "League(seed)", ("one random stream per world", "8 graded seeds; 8 more for the bar"), B, ROW[5], mono=True)
node("history", "public", "History and fixtures", ("3 seasons of balls, matches, line-ups", "24 fixtures with announced elevens"), B, ROW[6])
straight("design", "r", "league", "l")
straight("league", "t", "skillbook", "b")
straight("skillbook", "t", "truth_engine", "b")
straight("league", "b", "history", "t")

# lane 3
node("bar_json", "private", "harbor/bar.json", ("total regret at most 1.10 x reference", "committed before any pilot"), C, ROW[1], mono=True)
node("bar_analysis", "process", "bar_analysis.py", ("noise and separation on worlds", "1001 to 1008, never graded"), C, ROW[2], mono=True)
node("truth_csv", "private", "truth.csv", "one per world: the exact answers", C, ROW[3], mono=True)
node("reference", "private", "reference.json, tiers.csv", ("the bar's denominator;", "tier forecasts for attribution"), C, ROW[4], mono=True)
node("ladder", "process", "forecasters/ladder.py", ("reference and 5 careless tiers,", "fitted from the reloaded public files"), C, ROW[5], mono=True)
node("public_folders", "public", "task_data/leagues/WORLD/", ("8 public folders:", "7 CSV files and meta.json"), C, ROW[6], mono=True)
straight("truth_engine", "r", "truth_csv", "l")
straight("history", "r", "public_folders", "l"); label((B + C) / 2, ROW[6] - 16, "save_league")
straight("public_folders", "t", "ladder", "b"); label(C + 58, (ROW[5] + ROW[6]) / 2, "load_league")
straight("ladder", "t", "reference", "b")
straight("truth_csv", "b", "reference", "t")
straight("bar_analysis", "t", "bar_json", "b")

# lane 4
node("oracle", "process", "solution/ (oracle)", ("solve.sh installs the reference", "forecaster as the submission"), D, ROW[2], mono=True)
node("env", "public", "environment/app/", ("engine with public constants, visible world,", "handbook, starter"), D, ROW[3], mono=True)
node("package", "process", "package_task.py", ("four source trees in,", "one task directory out"), D, ROW[4], mono=True)
node("tests", "private", "tests/", ("grader, pristine engine, all 8 worlds,", "truth, reference, tiers, bar"), D, ROW[5], mono=True)
bus(["bar_json", "truth_csv", "reference", "public_folders"], "package", 980)
straight("package", "t", "env", "b")
straight("package", "b", "tests", "t")

# lane 5
node("agent", "public", "Agent container", ("public inputs only, network for the model API;", "the agent replaces solution/forecast.py"), E, ROW[3], w=320)
node("verifier", "private", "Verifier container", ("runs the submission as user runner, /tests unreadable;", "8 worlds x 720 s, beside a pristine engine"), E, ROW[5], w=320)
node("reward", "doc", "reward.json, details.json", ("pooled rule on all 8 and on the held-out 7;", "determinism, engine hash, time, validity"), E, ROW[6], w=320, mono=True)
straight("env", "r", "agent", "l")
straight("tests", "r", "verifier", "l")
straight("agent", "b", "verifier", "t"); label(E + 8, ROW[4], "artifacts: /app/solution and /app/engine", "start")
straight("verifier", "b", "reward", "t")
path([pt("oracle", "r"), (E, ROW[2]), pt("agent", "t")], dashed=True, color=LINE); label((D + NW/2 + E) / 2, ROW[2] - 16, "oracle gate only")

# lane 6
node("jobs", "doc", "jobs/", ("two gates, the linter, every pilot;", "agent session directories excluded"), E, BOTTOM, w=320, mono=True)
node("ablate", "process", "dev/ablate_pilots.py", ("one constant changed per program;", "ablations.log"), D, BOTTOM, mono=True)
node("figures", "process", "figures/src/pilot_results.py", ("the pilot figure, drawn from", "the job records and the logs"), C, BOTTOM, mono=True)
node("docs", "doc", "docs/DESIGN.pdf", ("with RUN_REPORT.md, DECISIONS.md,", "NOTES.md and docs/ARCHITECTURE.md"), B, BOTTOM, mono=True)
node("readme", "doc", "README.md", "the entry point", A, BOTTOM, mono=True)
straight("reward", "b", "jobs", "t")
straight("jobs", "l", "ablate", "r")
straight("ablate", "l", "figures", "r")
straight("figures", "l", "docs", "r")
straight("docs", "l", "readme", "r")

# legend
ly = 918
for i, (kind, lab) in enumerate([("process", "script or step"), ("public", "public: the agent sees it"), ("private", "private: generator and verifier only"), ("doc", "record or document"), ("raw", "external, not tracked")]):
    x = 30 + i * 240
    add(f'<rect x="{x}" y="{ly - 11}" width="22" height="14" rx="3" fill="{FILL[kind]}" stroke="{EDGE[kind]}" stroke-width="1.2"/>')
    text(x + 30, ly, lab, 11, "normal", MUTED, "start")
add(f'<path d="M 1250,{ly - 4} L 1290,{ly - 4}" stroke="{INK}" stroke-width="1.5" marker-end="url(#head)"/>'); text(1298, ly, "data flow", 11, "normal", MUTED, "start")
add(f'<path d="M 1390,{ly - 4} L 1430,{ly - 4}" stroke="{LINE}" stroke-width="1.5" stroke-dasharray="6,4" marker-end="url(#head)"/>'); text(1438, ly, "oracle install, or a tuning loop", 11, "normal", MUTED, "start")
add("</svg>")

open("architecture.svg", "w").write("\n".join(out))
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
renderPDF.drawToFile(svg2rlg("architecture.svg"), "architecture.pdf")
print("written architecture.svg and architecture.pdf")
