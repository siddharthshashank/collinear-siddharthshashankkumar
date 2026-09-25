"""The system as an architecture diagram: two columns (public, private), five rows (build, data, package, run, evidence).
Ten boxes, straight arrows with drawn heads, nothing crosses.

    python system.py  ->  system.svg, system.pdf
"""
from xml.sax.saxutils import escape

W, H = 1500, 1080
INK, MUTED, BAND = "#1b232b", "#59636d", "#f6f7f9"
BLUE, BLUE_F, RED, RED_F, GREY, GREY_F, GOLD, GOLD_F = "#2f6fb2", "#e9f1fb", "#b7423a", "#fcecea", "#6a737c", "#f0f2f4", "#a3823a", "#fbf5e6"
LX, RX, BW, BH = 405, 1095, 470, 100
SPAN_X, SPAN_W = 750, 1150
ROWS = {"build": 218, "gen": 350, "data": 500, "pack": 650, "run": 800, "evid": 950}

out = []
def add(s): out.append(s)
def text(x, y, s, size=13, weight="normal", fill=INK, anchor="middle"):
    add(f'<text x="{x}" y="{y}" font-family="Helvetica, Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')

def box(x, y, w, h, title, lines, fill, edge):
    add(f'<rect x="{x - w/2 + 2}" y="{y - h/2 + 3}" width="{w}" height="{h}" rx="9" fill="#dfe3e8"/>')          # soft drop shadow
    add(f'<rect x="{x - w/2}" y="{y - h/2}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{edge}" stroke-width="1.8"/>')
    n = len(lines); ty = y - (n * 18) / 2 - 3
    text(x, ty, title, 17, "bold", INK)
    for i, l in enumerate(lines): text(x, ty + 22 + 18 * i, l, 13.5, "normal", MUTED)

def head(x, y, direction, size=11):
    # a filled triangle pointing along direction: "down" or "right"
    if direction == "down": pts = f"{x - size/2},{y - size} {x + size/2},{y - size} {x},{y}"
    else: pts = f"{x - size},{y - size/2} {x - size},{y + size/2} {x},{y}"
    add(f'<polygon points="{pts}" fill="{INK}"/>')

def pill(x, y, s, size=12.5):
    tw = size * 0.55 * len(s) + 18
    add(f'<rect x="{x - tw/2}" y="{y - 11}" width="{tw}" height="20" rx="10" fill="#ffffff" stroke="#d5dadf" stroke-width="1"/>')
    text(x, y + 4, s, size, "normal", MUTED)

def down(x, y0, y1, label=None):
    add(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1 - 10}" stroke="{INK}" stroke-width="2.2"/>'); head(x, y1, "down")
    if label: pill(x, (y0 + y1) / 2, label)

def right(x0, x1, y, label=None):
    add(f'<line x1="{x0}" y1="{y}" x2="{x1 - 10}" y2="{y}" stroke="{INK}" stroke-width="2.2"/>'); head(x1, y, "right")
    if label:
        parts = label.split("|")
        for i, s in enumerate(parts): pill((x0 + x1) / 2, y - 16 - 22 * (len(parts) - 1 - i), s)

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Helvetica, Arial, sans-serif">')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(60, 52, "t20-exact-forecast", 26, "bold", INK, "start")
text(60, 80, "A forecasting task graded against the exact truth of a world it owns. The agent sees the left column; it never sees the right.", 14, "normal", MUTED, "start")

# row bands
for key, lab, y0, y1 in [("build", "BUILD", 160, 408), ("data", "DATA", 442, 558), ("pack", "PACKAGE", 592, 708), ("run", "RUN", 742, 858), ("evid", "EVIDENCE", 892, 1008)]:
    add(f'<rect x="60" y="{y0}" width="{W - 120}" height="{y1 - y0}" rx="12" fill="{BAND}"/>')
    text(78, y0 + 24, lab, 12, "bold", MUTED, "start")

# column headers
text(LX, 138, "PUBLIC", 14, "bold", BLUE); text(LX, 155, "what the agent sees", 12.5, "normal", MUTED)
text(RX, 138, "PRIVATE", 14, "bold", RED); text(RX, 155, "what only the generator and the verifier hold", 12.5, "normal", MUTED)

# build
box(SPAN_X, ROWS["build"], SPAN_W, BH, "Calibration from the real archive",
    ["295,557 Cricsheet IPL deliveries, parsed, measured and fitted by six scripts under dev/", "Only what repeats in independent halves is kept; the result is one constants file of aggregates"], GREY_F, GREY)
box(SPAN_X, ROWS["gen"], SPAN_W, BH, "World generator and shared engine",
    ["league/world.py builds a league from one seed: invented players, hidden skills, drifting form, transfers, three seasons", "league/engine.py plays every ball; the truth and every forecaster use this same engine with different skill books"], GREY_F, GREY)
down(SPAN_X, ROWS["build"] + BH/2, ROWS["gen"] - BH/2, "league/calibration.json and the chosen design constants")

# data
box(LX, ROWS["data"], BW, BH, "History and fixtures",
    ["Three seasons of balls, matches and line-ups", "24 fixtures with their elevens; 7 CSV files per world"], BLUE_F, BLUE)
box(RX, ROWS["data"], BW, BH, "Exact truth, reference, pass rule",
    ["TruthEngine: 100,000 copies per batting order per fixture", "Reference regret and tier forecasts; bar.json committed before any pilot"], RED_F, RED)
down(LX, ROWS["gen"] + BH/2, ROWS["data"] - BH/2, "make_task_data.py, 8 worlds")
down(RX, ROWS["gen"] + BH/2, ROWS["data"] - BH/2, "hidden SkillBook, never written out")

# package
box(LX, ROWS["pack"], BW, BH, "Agent image",
    ["Engine as code with public constants only", "The visible world, the handbook, a starter that says 0.5"], BLUE_F, BLUE)
box(RX, ROWS["pack"], BW, BH, "Verifier image and oracle",
    ["grader.py, a pristine engine, all 8 worlds, the private files", "solution/: the reference forecaster, installed for the oracle gate"], RED_F, RED)
down(LX, ROWS["data"] + BH/2, ROWS["pack"] - BH/2, "package_task.py, visible world only")
down(RX, ROWS["data"] + BH/2, ROWS["pack"] - BH/2, "package_task.py, all eight worlds")

# run
box(LX, ROWS["run"], BW, BH, "Agent container",
    ["Claude Code or Codex writes solution/forecast.py", "three hours; network for the model API only"], BLUE_F, BLUE)
box(RX, ROWS["run"], BW, BH, "Verifier container",
    ["Runs the program as an unprivileged user, 8 worlds x 12 minutes", "Regret against the truth; pooled rule twice; determinism; engine hash"], RED_F, RED)
down(LX, ROWS["pack"] + BH/2, ROWS["run"] - BH/2, "harbor run")
down(RX, ROWS["pack"] + BH/2, ROWS["run"] - BH/2, "separate container")
right(LX + BW/2, RX - BW/2, ROWS["run"], "artifacts|/app/solution|/app/engine")

# evidence
box(SPAN_X, ROWS["evid"], SPAN_W, BH, "Evidence and documents",
    ["jobs/: two gates, Harbor's linter, every pilot. Ten runs of the named pair, 0 of 10; the newer pair under test", "Ablations of the failed programs, figures drawn from the records, the design document, run report, decisions, notes"], GOLD_F, GOLD)
down(RX, ROWS["run"] + BH/2, ROWS["evid"] - BH/2, "reward.json, details.json")

# legend
ly = 1046
for i, (f, e, lab) in enumerate([(BLUE_F, BLUE, "public"), (RED_F, RED, "private"), (GREY_F, GREY, "build time, both sides"), (GOLD_F, GOLD, "records and documents")]):
    x = 60 + i * 230
    add(f'<rect x="{x}" y="{ly - 12}" width="26" height="16" rx="4" fill="{f}" stroke="{e}" stroke-width="1.6"/>'); text(x + 34, ly + 1, lab, 12.5, "normal", MUTED, "start")
add(f'<line x1="1000" y1="{ly - 4}" x2="1046" y2="{ly - 4}" stroke="{INK}" stroke-width="2.2"/>'); head(1056, ly - 4, "right")
text(1066, ly + 1, "data flow, labelled with the script or step that carries it", 12.5, "normal", MUTED, "start")
add("</svg>")

open("system.svg", "w").write("\n".join(out))
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
renderPDF.drawToFile(svg2rlg("system.svg"), "system.pdf")
print("written system.svg and system.pdf")
