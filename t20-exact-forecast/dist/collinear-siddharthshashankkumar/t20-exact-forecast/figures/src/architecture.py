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
    "check": ("#895610", "#FFF6E5"),
    "neutral": ("#516477", "#F1F4F7"),
}
NAMES = ["system_overview", "calibration_pipeline", "task_build_and_packaging", "harbor_runtime", "grading_rule", "research_ladder", "decision_path"]
DESCRIPTIONS = {
    1: "Cricsheet aggregates and explicit design assumptions inform a simulator that generates eight synthetic worlds. One world's public files are visible during agent development; seven more are held out until grading. The submitted forecaster receives each world's public-schema files and returns a forecast CSV. Separately stored probability estimates and reference regrets reach the trusted grader, which validates forecasts and writes reward and detail files. Private scoring data do not enter the submitted program.",
    2: "The calibration pipeline reconstructs match state from 1,243 IPL matches and 295,557 deliveries, measures repeatable aggregate structure, and exports calibration constants. Measured profiles and variation are distinguished from chosen or tuned transfer rates, form drift and simplified rules. Agreement with a tuning target is calibration, not independent validation.",
    3: "The packaging script combines Harbor templates, public engine and starter files, eight worlds, and reviewer documents into one task directory. The environment build context contains only the visible world and public tools. The tests context contains all worlds and private scoring data. The oracle and reviewer evidence are outside both build contexts.",
    4: "Harbor copies solution and engine artifacts from the agent container into a separate verifier with network disabled. The privileged grader rejects symlinked artifacts before preparing the submitted solution, a pristine engine and eight public-schema league folders. The submitted program runs as user runner and returns CSV forecasts. Those forecasts return to the privileged grader, which alone reads root-only private truth and reference scores. It checks validity, timing, regret, engine integrity and repeatability aligned by fixture identity, then writes reward.json and details.json. No private-score arrow enters the runner. This shows the hardened v0.1.1 submission; historical model trials used v0.1.0.",
    5: "For each fixture the verifier computes Bernoulli logarithmic regret from a stored probability estimate and a submitted forecast clipped to 0.002 through 0.998, then averages by world. Functional correctness requires the sum across all eight worlds to be at most 1.10 times the reference sum. Robustness applies the same limit to the seven held-out worlds. Overall reward is functional correctness times one half robustness plus one quarter constraint satisfaction plus one quarter artifact quality. Artifact quality is the fraction of worlds with valid forecasts. Only an overall reward of one is a complete pass.",
    6: "Development comparisons on separate worlds informed a pooled-regret rule and a held-out-only gate. A ten percent tolerance was committed before the archived model trials. Later oracle and no-op controls, model trials and interventions were evaluated under that rule. The decision to pool addressed observed per-world reference variation of up to 5.8 percent, but uncertainty still limits interpretation near the threshold.",
    7: "Three task ideas are compared. Earlier backtest-audit attempts were set aside after reported model repairs; ingest under faults was rejected by design judgment without a pilot. Forecasting was selected because a mechanically correct program can still over-trust uneven histories, providing a measurable statistical failure mode. The accepted cost is a more difficult fairness argument and Monte Carlo uncertainty. Separate trial records for the earlier ideas are not included.",
}

class Figure:
    def __init__(self, number, title, subtitle):
        self.items = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(DESCRIPTIONS[number])}</desc>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#708497"/></marker></defs>',
            f'<rect width="{W}" height="{H}" fill="{BG}"/>'
        ]
        self.text(64, 43, f"COLLINEAR TAKE-HOME  /  ARCHITECTURE {number:02}", 13, "#16766F", 700, tracking=1.8)
        self.text(64, 100, title, 43, INK, 700)
        self.text(64, 138, subtitle, 21, MUTED)
        self.line(64, 166, 1536, 166)
        self.line(64, 902, 1536, 902)
        self.text(64, 931, "submission v0.1.1  ·  historical trials v0.1.0", 15, MUTED)
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

    def node(self, x, y, w, h, label, title, lines=(), role="neutral"):
        """Larger labels for the two diagrams embedded as architectural overviews."""
        edge, _ = COLORS[role]
        self.rect(x, y, w, h)
        self.rect(x, y+18, 4, h-36, edge, edge, 2)
        self.text(x+22, y+32, label, 21, edge, 700)
        self.text(x+22, y+71, title, 28, INK, 700)
        for i, line in enumerate(lines):
            self.text(x+22, y+110+i*32, line, 24, MUTED)

    def save(self, name):
        (OUT / f"{name}.svg").write_text("\n".join(self.items + ["</svg>"]))

def overview():
    f=Figure(1,"From synthetic history to a scored forecast.","The program receives league files. The trusted grader also receives private scoring data.")
    f.node(64,214,430,172,"Authoring inputs","Calibrated simulator",[
        "Cricsheet aggregates","Explicit design assumptions"],"build")
    f.node(588,214,430,172,"Offline generation","Eight synthetic worlds",[
        "Invented teams and players","Public history + hidden state"],"build")
    f.node(1112,214,424,172,"Verifier only","Stored scoring data",[
        "Probability estimates","Reference regrets"],"private")
    f.arrow([(494,300),(580,300)])
    f.arrow([(1018,300),(1104,300)])
    f.arrow([(803,386),(803,430),(279,430),(279,478)])
    f.arrow([(1324,386),(1324,478)])
    f.node(64,486,430,232,"Public file schema","League folders",[
        "1 visible during development","7 held out until grading","Engine + handbook supplied"],"public")
    f.node(588,486,430,232,"Agent-written artifact","solution/forecast.py",[
        "Learn on the visible league","Run on each league folder","Return one forecast CSV"],"public")
    f.node(1112,486,424,232,"Trusted grader","Validate and score",[
        "Compare forecasts to truth","Apply both accuracy gates","Write reward + details"],"private")
    f.arrow([(494,606),(580,606)])
    f.text(541,586,"files",23,MUTED,anchor="middle")
    f.arrow([(1018,606),(1104,606)])
    f.text(1065,586,"CSV",23,MUTED,anchor="middle")
    f.rect(64,778,1472,91,"#EDF4FC","#CFD9E2",12)
    f.text(88,812,"The access boundary",25,INK,700)
    f.text(88,851,"League folders reach the runner. Stored probabilities and reference scores reach only the grader.",24,MUTED)
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
    f.text(88,488,"task_data/",25,INK,700);f.text(88,522,"One visible + seven held-out worlds",19,MUTED)
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
    f=Figure(4,"Forecasts return to the privileged grader.","Public-schema inputs go to the runner; private scoring inputs stay on the grader's side.")
    f.panel(64,214,392,572,"","public")
    f.text(88,251,"AGENT · PUBLIC NETWORK",21,COLORS["public"][0],700)
    f.panel(512,214,1024,572,"","private")
    f.text(536,251,"SEPARATE VERIFIER · NO NETWORK",21,COLORS["private"][0],700)
    f.node(88,283,344,177,"Public inputs","Inspect and iterate",[
        "Visible league","Engine + handbook"],"public")
    f.arrow([(260,460),(260,518)])
    f.node(88,526,344,177,"Submitted artifacts","forecast.py",[
        "solution/ + engine/","copied by Harbor"],"public")
    f.text(88,742,"3-hour session · API access",21,MUTED)
    f.text(88,773,"Oracle: installs the reference",21,MUTED)
    f.node(536,286,466,173,"Artifact checks + setup","Validate and prepare",[
        "Reject symlinked artifacts","Pristine engine + league inputs"],"public")
    f.arrow([(456,614),(486,614),(486,372),(528,372)])
    f.arrow([(769,459),(769,493)])
    f.node(536,501,466,206,"Unprivileged submitted program","Run as user runner",[
        "8 worlds · 720 s per world","Visible world run twice","CSV with fixture + p_home"],"public")
    f.node(1072,286,440,173,"Root-only /tests","Private score data",[
        "Probability estimates","Reference regrets"],"private")
    f.arrow([(1292,459),(1292,493)])
    f.node(1072,501,440,206,"Privileged grader","Score returned CSVs",[
        "Validity, timing and regret","Engine-integrity check","Fixture-aligned repeat check"],"private")
    f.arrow([(1002,606),(1064,606)])
    f.text(1037,586,"CSV",23,MUTED,anchor="middle")
    f.arrow([(1292,707),(1292,729)])
    f.rect(1072,737,440,43)
    f.text(1292,766,"reward.json + details.json",24,INK,700,anchor="middle")
    f.rect(64,808,1472,74,"#FFF6E5","#F0D5A7",12)
    f.text(88,838,"Separate the versions when reading the evidence",23,"#895610",700)
    f.text(88,868,"This is the hardened v0.1.1 verifier. Archived model trials used v0.1.0; the forecasting rule is unchanged.",23,MUTED)
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
    f.text(88,809,"C: engine, repeatability, runtime   |   A: fraction of worlds with valid output",21,MUTED)
    f.text(1512,839,"Solved only when overall = 1.0",20,"#16766F",700,anchor="end")
    f.save("grading_rule")

def research():
    f=Figure(6,"Choose the rule before reading model results.","Development experiments informed the threshold; later trials and interventions test the result under that fixed rule.")
    xs=[64,578,1092]
    cards=[
      ("01 / DEVELOPMENT","Compare candidate methods",["Reference + simpler alternatives","Separate development worlds","Measure score variation"],"build"),
      ("02 / COMMITMENT","Fix the evaluation rule",["Pool regret across worlds","Add the held-out-only gate","Commit 10% before archived trials"],"check"),
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
    (OUT / "architecture-manifest.json").write_text(json.dumps({"figures":NAMES,"canvas":[W,H],"source":"src/architecture.py","runtime_changed":True,"runtime_scope":"Verifier hardening in submission v0.1.1; historical model trials remain v0.1.0. Forecasting rule, data, engine and oracle are unchanged."},indent=2)+"\n")
    print(f"Wrote {len(NAMES)} editable SVG diagrams.")
