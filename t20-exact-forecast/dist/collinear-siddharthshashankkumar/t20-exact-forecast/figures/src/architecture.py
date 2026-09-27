"""Editable architecture diagrams; SVG output uses only the Python standard library.

Run from any directory: python3 figures/src/architecture.py
Render PNGs separately with: node figures/src/render.cjs
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json

OUT = Path(__file__).resolve().parents[1]
W, H = 1600, 960
INK, MUTED, LINE, BG = "#172A3A", "#516477", "#CFD9E2", "#F7F9FC"
COLORS = {
    "build": ("#16766F", "#EAF5F2"),
    "public": ("#2164A6", "#EDF4FC"),
    "private": ("#735395", "#F3EFF8"),
    "check": ("#A36916", "#FFF6E5"),
    "neutral": ("#516477", "#F1F4F7"),
}
NAMES = ["system_overview", "calibration_pipeline", "task_build_and_packaging", "harbor_runtime", "grading_rule", "research_ladder", "decision_path"]

class Figure:
    def __init__(self, number, title, subtitle):
        self.items = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#708497"/></marker></defs>',
            f'<rect width="{W}" height="{H}" fill="{BG}"/>'
        ]
        self.text(64, 43, f"COLLINEAR TAKE-HOME  /  ARCHITECTURE {number:02}", 13, "#16766F", 700, tracking=1.8)
        self.text(64, 100, title, 43, INK, 700)
        self.text(64, 138, subtitle, 21, MUTED)
        self.line(64, 166, 1536, 166)
        self.line(64, 902, 1536, 902)
        self.text(64, 931, "t20-exact-forecast  ·  evaluated runtime v0.1.0", 15, MUTED)
        self.text(1536, 931, "Design rationale and evidence in DECISIONS.md", 15, MUTED, anchor="end")

    def text(self, x, y, value, size=20, fill=INK, weight=400, anchor="start", tracking=0):
        self.items.append(f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" letter-spacing="{tracking}">{escape(str(value))}</text>')

    def rect(self, x, y, w, h, fill="white", stroke=LINE, radius=14):
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')

    def line(self, x1, y1, x2, y2, color=LINE):
        self.items.append(f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{color}" stroke-width="1.5"/>')

    def arrow(self, points, dashed=False):
        d = "M" + " L".join(f"{x} {y}" for x, y in points)
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.items.append(f'<path d="{d}" fill="none" stroke="#708497" stroke-width="2.2" stroke-linejoin="round"{dash} marker-end="url(#arrow)"/>')

    def panel(self, x, y, w, h, label, role="neutral"):
        edge, fill = COLORS[role]
        self.rect(x, y, w, h, fill, fill, 18)
        self.text(x+24, y+34, label, 15, edge, 700, tracking=1.1)

    def card(self, x, y, w, h, eyebrow, title, lines=(), role="neutral", size=19):
        edge, fill = COLORS[role]
        self.rect(x, y, w, h)
        self.rect(x, y+18, 4, h-36, edge, edge, 2)
        self.text(x+24, y+32, eyebrow.upper(), 12, edge, 700, tracking=1)
        self.text(x+24, y+68, title, 25, INK, 700)
        for i, text in enumerate(lines):
            self.text(x+24, y+103+i*27, text, size, MUTED)
        assert 103 + (len(lines)-1)*27 < h - 10 if lines else True, (title, "card too short")

    def note(self, y, title, body):
        self.rect(64, y, 1472, 78, "#FFF6E5", "#F0D5A7", 12)
        self.text(88, y+29, title, 17, "#895610", 700)
        self.text(88, y+56, body, 18, MUTED)

    def save(self, name):
        (OUT / f"{name}.svg").write_text("\n".join(self.items + ["</svg>"]))

def overview():
    f=Figure(1,"One task. Two execution environments.","Real data inform the simulation; public inputs reach the agent; scoring evidence stays with the verifier.")
    xs=[64,440,816,1192]
    data=[
        ("01 / CALIBRATE","Ground the scenario",["Cricsheet IPL aggregates","Measured + chosen constants"],"build"),
        ("02 / GENERATE","Create eight worlds",["Invented players and teams","History + future fixtures"],"build"),
        ("03 / PACKAGE","Assemble one task",["Public and private contexts","Oracle + reviewer evidence"],"neutral"),
        ("04 / EVALUATE","Run in Harbor",["Native agent harness","Separate programmatic grader"],"check")]
    for i,(step,title,lines,role) in enumerate(data):
        f.card(xs[i],214,344,175,step,title,lines,role,18)
        if i<3:f.arrow([(xs[i]+344,300),(xs[i+1]-8,300)])
    f.text(64,446,"VISIBILITY IS A DESIGN CHOICE",14,MUTED,700,tracking=1)
    f.panel(64,470,708,304,"AGENT-VISIBLE / environment/app", "public")
    f.card(88,530,660,204,"Inputs → durable deliverable","Learn from the public history",[
        "7 CSVs · handbook · public engine · starter",
        "Agent writes solution/forecast.py and supporting files",
        "The program must work on unseen league folders"],"public",20)
    f.panel(828,470,708,304,"VERIFIER-ONLY / tests", "private")
    f.card(852,530,660,204,"Private evidence → reward","Score the submitted program",[
        "8 worlds · stored probabilities · reference regrets",
        "Pristine engine · output, timing and repeat checks",
        "reward.json + per-world details + retained job records"],"private",20)
    f.text(64,832,"Why this split?",21,INK,700)
    f.text(230,832,"Test inference from the supplied evidence while keeping evaluation data out of the agent image.",20,MUTED)
    f.save("system_overview")

def calibration():
    f=Figure(2,"Calibrate the setting; expose the assumptions.","Keep observations, design choices and validation separate so a good fit is not mistaken for independent evidence.")
    cards=[
      (64,"01 / SOURCE","Cricsheet archive",["1,243 IPL matches","295,557 deliveries","Raw archive not shipped"]),
      (440,"02 / PREPARE","Reconstruct the state",["Legal balls and dismissals","Score, wickets and chase state","One consistent tabular history"]),
      (816,"03 / ESTIMATE","Measure repeatability",["Over and situation effects","Player / venue variation","Retain supported structure"]),
      (1192,"04 / EXPORT","Calibration constants",["Aggregate values only","Attribution retained","No real player identities"])]
    for i,(x,step,title,lines) in enumerate(cards):
        f.card(x,214,344,206,step,title,lines,"build",18)
        if i<3:f.arrow([(x+344,318),(x+368,318)])
    f.panel(64,477,708,243,"MEASURED INPUTS","build")
    f.text(88,552,"Profiles, directions and aggregate variation",25,INK,700)
    f.text(88,601,"Derived from the archive and the recorded analysis.",21,MUTED)
    f.text(88,642,"Source: league/calibration.json",19,MUTED)
    f.panel(828,477,708,243,"EXPLICIT DESIGN CHOICES","check")
    f.text(852,552,"Transfers, form drift and simplified rules",25,INK,700)
    f.text(852,601,"Chosen or tuned; not all are independently estimated.",21,MUTED)
    f.text(852,642,"Source: Design in league/calibration.py",19,MUTED)
    f.note(785,"Interpretation matters","Matching a target used for tuning is calibration. The league remains a simplified model of cricket.")
    f.save("calibration_pipeline")

def packaging():
    f=Figure(3,"Package one task with a deliberate boundary.","The submission is self-contained; Docker build contexts decide what reaches the agent and verifier.")
    f.panel(64,222,400,520,"SOURCE MATERIAL","build")
    f.text(88,306,"harbor/",25,INK,700);f.text(88,340,"Prompt, metadata, grader, oracle",19,MUTED)
    f.text(88,397,"task_src/ + league/",25,INK,700);f.text(88,431,"Starter, handbook, public engine",19,MUTED)
    f.text(88,488,"task_data/",25,INK,700);f.text(88,522,"Eight public worlds + private scores",19,MUTED)
    f.text(88,579,"Documents + jobs + figures",25,INK,700);f.text(88,613,"Rationale, evidence and provenance",19,MUTED)
    f.card(516,395,270,176,"Build step","package_task.py",["Check required inputs","Preserve runtime hashes"],"neutral",18)
    f.arrow([(464,480),(508,480)]);f.arrow([(786,480),(830,480)])
    f.panel(840,222,696,520,"ONE HARBOR TASK DIRECTORY","neutral")
    rows=[
      (282,"environment/","Public image: visible world, engine, handbook, starter","public"),
      (388,"tests/","Private image: eight worlds, grading data and checks","private"),
      (494,"solution/","Oracle installer and reference forecaster","check"),
      (600,"Reviewer material","DECISIONS · ASSUMPTIONS · reports · jobs · figures","neutral")]
    for y,title,body,role in rows:
        edge,_=COLORS[role];f.rect(864,y,648,86);f.text(884,y+32,title,23,edge,700);f.text(884,y+61,body,18,MUTED)
    f.note(787,"Reviewer material stays outside both Docker build contexts","The zip contains one task.toml. Reports, oracle code and archived solutions are not copied into the agent workspace.")
    f.save("task_build_and_packaging")

def runtime():
    f=Figure(4,"A submitted program crosses the boundary.","The agent produces an artifact; the trusted grader prepares a clean run and evaluates its forecasts.")
    f.panel(64,211,584,561,"AGENT CONTAINER / public network for harness + API","public")
    f.card(88,271,536,177,"Public inputs","Read, inspect and iterate",["Visible league · public engine · handbook","3-hour session budget"],"public",20)
    f.arrow([(356,448),(356,482)])
    f.card(88,493,536,177,"Artifact","solution/forecast.py",["Supports arbitrary --league and --out paths","Only solution/ and engine/ are transferred"],"public",19)
    f.text(88,729,"Oracle run: solve.sh installs the reference instead.",18,MUTED)
    f.panel(840,211,696,561,"VERIFIER CONTAINER / network mode not declared","private")
    f.card(864,271,314,153,"Root-only /tests","Private score data",["Probabilities + reference"],"private",18)
    f.card(1200,271,312,153,"Trusted process","grader.py",["Prepare pristine engine"],"private",18)
    f.arrow([(1178,348),(1192,348)])
    f.arrow([(1356,424),(1356,474)])
    f.card(864,484,648,135,"Unprivileged runner in the intended image","Execute on eight league folders",["720 s per world · visible world repeated"],"public",19)
    f.arrow([(648,552),(856,552)])
    f.text(744,500,"Harbor copies",16,MUTED,anchor="middle")
    f.text(744,524,"the artifacts",16,MUTED,anchor="middle")
    f.arrow([(1188,619),(1188,648)])
    f.rect(864,659,648,81);f.text(888,692,"Check integrity, validity and regret",24,INK,700);f.text(888,721,"Write reward.json and details.json",19,MUTED)
    f.note(795,"A boundary, not a security guarantee","No-network is a program rule, not enforced isolation here. Privilege and timeout limitations remain in RUN_REPORT.md.")
    f.save("harbor_runtime")

def grading():
    f=Figure(5,"A forecast must pass both accuracy gates.","Expected logarithmic regret is computed against fixed Monte Carlo probability estimates; lower is better.")
    f.panel(64,210,1472,170,"01 / SCORE EACH FIXTURE, THEN AVERAGE WITHIN EACH WORLD","neutral")
    f.text(88,292,"regret = p · ln(p / q) + (1 − p) · ln((1 − p) / (1 − q))",33,INK,700)
    f.text(88,343,"p = stored probability estimate   |   q = submitted forecast, clipped to [0.002, 0.998]",21,MUTED)
    f.arrow([(800,380),(800,410),(417,410),(417,440)])
    f.arrow([(800,410),(1183,410),(1183,440)])
    f.card(64,450,706,170,"02A / Functional correctness · F","All eight worlds",["Sum of candidate regret ≤ 1.10 × reference sum","The visible world is included."],"check",20)
    f.card(830,450,706,170,"02B / Robustness · R","Seven held-out worlds",["Same limit, computed without the visible world","Visible-world tuning cannot carry a weak method."],"check",20)
    f.panel(64,678,1472,180,"03 / COMBINE WITH CONSTRAINTS AND ARTIFACT QUALITY","build")
    f.text(88,760,"overall = F × (0.50 R + 0.25 C + 0.25 A)",35,INK,700)
    f.text(88,809,"C: engine, repeatability, runtime   |   A: valid forecast share",21,MUTED)
    f.text(1512,839,"Solved only when overall = 1.0",20,"#16766F",700,anchor="end")
    f.save("grading_rule")

def research():
    f=Figure(6,"Choose the rule before reading model results.","Development experiments informed the threshold; later trials and interventions test the result under that fixed rule.")
    xs=[64,578,1092]
    cards=[
      ("01 / DEVELOPMENT","Compare candidate methods",["Reference + simpler alternatives","Separate development worlds","Measure score variation"],"build"),
      ("02 / COMMITMENT","Fix the evaluation rule",["Pool regret across worlds","Add the held-out-only gate","Commit 10% tolerance before pilots"],"check"),
      ("03 / OBSERVATION","Evaluate and diagnose",["Oracle + no-op controls","Native-harness model trials","Read programs; test interventions"],"private")]
    for i,(step,title,lines,role) in enumerate(cards):
        f.card(xs[i],234,444,222,step,title,lines,role,21)
        if i<2:f.arrow([(xs[i]+444,345),(xs[i+1]-8,345)])
    f.panel(64,528,1472,263,"WHY THE DESIGN CHANGED","neutral")
    f.text(88,599,"A per-world threshold was unstable.",29,INK,700)
    f.text(88,648,"Observed reference variation reached 5.8% on one development world.",23,MUTED)
    f.text(88,687,"Some weak methods were only 6–8% worse on others. Pooling made the comparison more useful.",23,MUTED)
    f.text(88,743,"Later qualification: a fixed rule still needs uncertainty disclosure near its threshold.",21,"#895610",700)
    f.text(64,852,"Evidence: bar.log · harbor/bar.json · jobs/ · ablations.log",20,MUTED)
    f.save("research_ladder")

def decisions():
    f=Figure(7,"The task choice was an experiment too.","I compared what each candidate would measure, how I could verify it, and whether its difficulty was substantive.")
    xs=[64,578,1092]
    cards=[
      ("SET ASIDE / reported earlier trials","Backtest audit",["Repair time-availability violations","More files increased workload","The recorded models repaired them"],"neutral"),
      ("SET ASIDE / design judgment","Ingest under faults",["Check crash and retry correctness","Strong deterministic verifier","Not piloted; expected a short repair loop"],"neutral"),
      ("SELECTED / evaluated here","Forecasting under uncertainty",["Estimate from uneven histories","Validate confidence, not just execution","Reusable program on unseen worlds"],"build")]
    for x,(step,title,lines,role) in zip(xs,cards):
        f.card(x,229,444,241,step,title,lines,role,20)
    f.panel(64,537,1472,259,"WHAT MADE THE SELECTED TASK DIFFERENT","build")
    f.text(88,610,"A program can be mechanically correct and still over-trust its data.",30,INK,700)
    f.text(88,666,"That gives the verifier a meaningful quantity to measure and the agent a hypothesis to challenge.",23,MUTED)
    f.text(88,721,"The accepted cost: a harder calibration and fairness argument, with Monte Carlo uncertainty.",23,MUTED)
    f.text(64,855,"Earlier candidate histories are described in the notes; their separate trial records are not included here.",19,MUTED)
    f.save("decision_path")

if __name__ == "__main__":
    for build in (overview,calibration,packaging,runtime,grading,research,decisions): build()
    (OUT / "architecture-manifest.json").write_text(json.dumps({"figures":NAMES,"canvas":[W,H],"source":"src/architecture.py","runtime_changed":False},indent=2)+"\n")
    print(f"Wrote {len(NAMES)} editable SVG diagrams.")
