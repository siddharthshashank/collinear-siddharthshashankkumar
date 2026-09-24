"""Builds DESIGN.pdf and DESIGN.md (with SVG figures) from one list of content blocks."""
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import landscape

OUT = Path(__file__).resolve().parent / "out"
INK, MUTED, LINE = colors.HexColor("#1f2328"), colors.HexColor("#57606a"), colors.HexColor("#8c959f")
FILLS = {"grey": colors.HexColor("#f1efe8"), "teal": colors.HexColor("#e1f5ee"), "purple": colors.HexColor("#eeedfe"), "coral": colors.HexColor("#faece7"), "white": colors.white}
WIDTH = 468


# ---------------------------------------------------------------- diagrams
def wrap(text, font, size, width):
    lines, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if stringWidth(trial, font, size) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    return lines + [current] if current else lines


class Diagram:
    def __init__(self, height):
        self.d = Drawing(WIDTH, height)

    def box(self, x, y, w, h, title, body="", fill="grey"):
        self.d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=FILLS[fill], strokeColor=LINE, strokeWidth=0.6))
        title_lines = wrap(title, "Helvetica-Bold", 8.5, w - 12)
        body_lines = wrap(body, "Helvetica", 7.5, w - 12) if body else []
        total = len(title_lines) * 10.5 + len(body_lines) * 9.5 + (3 if body_lines else 0)
        cursor = y + h / 2 + total / 2 - 8
        for line in title_lines:
            self.d.add(String(x + w / 2, cursor, line, textAnchor="middle", fontName="Helvetica-Bold", fontSize=8.5, fillColor=INK))
            cursor -= 10.5
        cursor -= 3 if body_lines else 0
        for line in body_lines:
            self.d.add(String(x + w / 2, cursor, line, textAnchor="middle", fontName="Helvetica", fontSize=7.5, fillColor=MUTED))
            cursor -= 9.5

    def arrow(self, *points):
        for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
            self.d.add(Line(x1, y1, x2, y2, strokeColor=MUTED, strokeWidth=0.9))
        (x1, y1), (x2, y2) = points[-2], points[-1]
        if x1 == x2:
            s = 1 if y2 > y1 else -1
            head = [x2, y2, x2 - 3.2, y2 - 6 * s, x2 + 3.2, y2 - 6 * s]
        else:
            s = 1 if x2 > x1 else -1
            head = [x2, y2, x2 - 6 * s, y2 - 3.2, x2 - 6 * s, y2 + 3.2]
        self.d.add(Polygon(head, fillColor=MUTED, strokeColor=MUTED, strokeWidth=0.5))


def fig_decision_map():
    g = Diagram(236)
    cols = [(0, "A. Backtest audit", "A repository of forecast backtests silently uses revised data. One written rule. The agent repairs every script.", "teal"),
            (161, "B. Exactly-once ingest", "An ingest service on an object store must stay correct under every crash, redelivery and zombie-writer schedule.", "teal"),
            (322, "C. Exact-truth forecasting", "Forecast a simulated league from ball-by-ball history. Forecasts are graded against the true probabilities.", "purple")]
    status = ["Built and piloted. Opus 4.7 and GPT-5.5 solve it at 8, 24 and 48 scripts. Sonnet 5 and Haiku 4.5 fail.",
              "Built and verified on 27,710 schedules. Judged likely to be solved by the top models. Parked.",
              "Chosen, built, gated and piloted. Opus 4.7 0 of 5, GPT-5.5 0 of 5 under a rule committed first."]
    for (x, title, body, fill), note in zip(cols, status):
        g.box(x, 156, 146, 76, title, body, fill)
        g.box(x, 64, 146, 70, "Outcome", note, "white")
        g.arrow((x + 73, 156), (x + 73, 134))
    g.box(0, 4, 468, 42, "Rejected on paper", "A port of a live Kaggle competition. Stock and candlestick prediction. Live sports forecasting. Recovery of a sealed binary format. "
          "A query cost budget. Machine-checked proofs.", "grey")
    return g.d


def fig_audit():
    g = Diagram(168)
    boxes = [("World generator", "Seeded surveillance counts with revisions and withdrawn numbers", "grey"),
             ("Repository for the agent", "N backtest scripts, shared helpers, decoy analyses, one written rule", "teal"),
             ("Agent", "Repairs every violation without changing what a script computes. Writes findings.", "coral"),
             ("Verifier", "Reruns every script against an honest twin. Every forecast row must match.", "purple")]
    for i, (title, body, fill) in enumerate(boxes):
        g.box(i * 122, 78, 102, 86, title, body, fill)
        if i:
            g.arrow((i * 122 - 20, 121), (i * 122, 121))
    g.box(0, 6, 468, 48, "Three worlds", "The visible world, a held-out world from another seed, and the visible world with its future hidden. "
          "A script that still reads settled data changes its forecasts when the future is removed.", "white")
    g.arrow((417, 78), (417, 54))
    return g.d


def fig_ingest():
    g = Diagram(220)
    boxes = [("Upload queue", "Delivers a batch again until it is acknowledged", "grey"), ("Consumers", "The owner and, after a handover, a zombie that is still running", "coral"),
             ("Object store", "Whole-object writes and put-if-absent. No transactions.", "grey"), ("Readers", "Take the highest commit and read the day tables it names", "grey")]
    for i, (title, body, fill) in enumerate(boxes):
        g.box(i * 122, 142, 102, 74, title, body, fill)
        if i:
            g.arrow((i * 122 - 20, 179), (i * 122, 179))
    g.box(61, 74, 346, 46, "Scheduler", "Before every storage or queue call it chooses the next move: step a consumer, kill one, or hand the queue over.", "purple")
    g.box(61, 6, 346, 46, "Explorer", "Tries every schedule inside the declared bounds. The reader guarantee is checked before every step.", "purple")
    g.arrow((173, 120), (173, 142))
    g.arrow((234, 52), (234, 74))
    return g.d


def fig_pipeline():
    g = Diagram(300)
    rows = [256, 206, 156, 106, 56, 6]
    left = [("Cricsheet IPL archive", "1,243 matches, 295,557 balls", "grey"), ("Measurements", "Form, interactions, situation responses, directions of player differences", "teal"),
            ("calibration.json", "Aggregate constants only, with attribution", "teal"), ("Engine", "BallModel, InningsSimulator, MatchSimulator", "purple"),
            ("League", "Hidden skills and conditions. Public history and fixtures.", "purple"), ("Truth engine", "Exact home-win probability of every fixture. Hidden.", "purple")]
    for (title, body, fill), y in zip(left, rows):
        g.box(0, y, 200, 38, title, body, fill)
    for a, b in zip(rows[:-1], rows[1:]):
        g.arrow((100, a), (100, b + 38))
    g.box(268, 206, 200, 88, "What is public and what is hidden", "Public. How a ball works, the match rules, the history, the line-ups. "
          "Hidden. Every player's values, venue levels, dew, the season level, the pitch on the day.", "white")
    g.box(268, 106, 200, 38, "Public history and fixtures", "Seven CSV files per league", "grey")
    g.box(268, 56, 200, 38, "Agent's forecaster", "Sees only public files and the engine", "coral")
    g.box(268, 6, 200, 38, "Exact scorer and pass bar", "Expected log loss against the truth, relative to a reference", "purple")
    g.arrow((200, 85), (234, 85), (234, 125), (268, 125))
    g.arrow((368, 106), (368, 94))
    g.arrow((368, 56), (368, 44))
    g.arrow((200, 25), (268, 25))
    return g.d


def fig_verifier():
    g = Diagram(250)
    g.box(0, 150, 130, 92, "Agent container", "/app/solution holds the forecaster. /app/engine is the public engine. /app/league is the visible league.", "coral")
    g.box(0, 50, 130, 64, "Artifacts", "Harbor copies /app/solution and /app/engine to the verifier", "grey")
    g.arrow((65, 150), (65, 114))
    g.box(168, 4, 300, 242, "", "", "white")
    g.d.add(String(318, 231, "Verifier container, never seen by the agent", textAnchor="middle", fontName="Helvetica-Bold", fontSize=8.5, fillColor=INK))
    inner = [("Run the forecaster", "As an unprivileged user, on the visible league and on seven held-out leagues, under a time limit"),
             ("Grade against stored truth", "Regret per league from truth computed at 100,000 copies per fixture"),
             ("Apply the bar and the checks", "Total regret within 1.10 times the stored reference total. Same output twice. Engine untouched."),
             ("Report", "reward.json, and details.json naming the ladder tier the forecast most resembles")]
    for i, (title, body) in enumerate(inner):
        y = 178 - i * 56
        g.box(180, y, 276, 42, title, body, "purple")
        if i:
            g.arrow((318, y + 56), (318, y + 42))
    g.arrow((130, 82), (150, 82), (150, 199), (180, 199))
    return g.d


FIGURES = {"decision_map": fig_decision_map, "audit": fig_audit, "ingest": fig_ingest, "pipeline": fig_pipeline, "verifier": fig_verifier}

# ---------------------------------------------------------------- content
from content import BLOCKS, TITLE, SUBTITLE  # noqa: E402

# ---------------------------------------------------------------- renderers
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=6)
STYLES = {"h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK, spaceBefore=14, spaceAfter=7),
          "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4),
          "p": BODY, "bullet": ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=3, spaceAfter=3),
          "caption": ParagraphStyle("caption", fontName="Helvetica-Oblique", fontSize=8.3, leading=11, textColor=MUTED, spaceBefore=4, spaceAfter=10),
          "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.2, leading=10.6, textColor=INK),
          "head": ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=8.2, leading=10.6, textColor=INK),
          "code": ParagraphStyle("code", fontName="Courier", fontSize=7.7, leading=10, textColor=INK, backColor=colors.HexColor("#f6f8fa"), borderPadding=6, spaceAfter=10, spaceBefore=4)}


def rich(text):
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`(.+?)`", r'<font face="Courier" size="8.6">\1</font>', text)


PLATES = Path(__file__).resolve().parents[2] / "figures"         # the repository's figures/ folder
if not PLATES.is_dir():
    PLATES = Path(__file__).resolve().parent / "figures"


def plate(name, max_w, max_h):
    svg = PLATES / f"{name}.svg"
    try:
        from svglib.svglib import svg2rlg
        d = svg2rlg(str(svg))
        k = min(max_w / d.width, max_h / d.height)
        d.width, d.height = d.width * k, d.height * k
        d.scale(k, k)
        return d
    except Exception:
        img = Image(str(PLATES / f"{name}.png"))
        k = min(max_w / img.imageWidth, max_h / img.imageHeight)
        img.drawWidth, img.drawHeight = img.imageWidth * k, img.imageHeight * k
        return img


def pdf_flowables():
    flow = [Paragraph(rich(TITLE), ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=20, leading=25, textColor=INK, spaceAfter=4)),
            Paragraph(rich(SUBTITLE), ParagraphStyle("s", fontName="Helvetica", fontSize=10, leading=14, textColor=MUTED, spaceAfter=14))]
    held = None
    for i, block in enumerate(BLOCKS):
        kind = block[0]
        nxt = BLOCKS[i + 1][0] if i + 1 < len(BLOCKS) else None
        if kind in ("h1", "h2") and nxt == "figure":
            held = Paragraph(rich(block[1]), STYLES[kind])            # keep a heading on the same page as the figure under it
        elif kind in ("h1", "h2", "p"):
            flow.append(Paragraph(rich(block[1]), STYLES[kind]))
        elif kind == "bullets":
            flow += [Paragraph(rich(item), STYLES["bullet"], bulletText="\u2022") for item in block[1]]
            flow.append(Spacer(1, 4))
        elif kind == "table":
            _, header, rows, widths = block
            data = [[Paragraph(rich(c), STYLES["head"]) for c in header]] + [[Paragraph(rich(str(c)), STYLES["cell"]) for c in row] for row in rows]
            table = Table(data, colWidths=[w * WIDTH for w in widths], repeatRows=1)
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f4")), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
                                       ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                                       ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
            flow += [table, Spacer(1, 9)]
        elif kind == "code":
            flow.append(Preformatted(block[1], STYLES["code"]))
        elif kind == "figure":
            flow.append(KeepTogether(([held] if held else []) + [FIGURES[block[1]](), Paragraph(rich(block[2]), STYLES["caption"])]))
            held = None
        elif kind == "break":
            flow.append(PageBreak())
        elif kind == "plate":
            flow += [NextPageTemplate("landscape"), PageBreak(), Paragraph(rich(block[2]), STYLES["h2"]),
                     plate(block[1], landscape(letter)[0] - 1.2 * inch, landscape(letter)[1] - 2.6 * inch), Paragraph(rich(block[3]), STYLES["caption"])]
        elif kind == "portrait":
            flow += [NextPageTemplate("portrait"), PageBreak()]
    return flow


def footer(canvas, doc):
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(inch, 0.55 * inch, "Design document. t20-exact-forecast. Siddharth Shashank Kumar.")
    canvas.drawRightString(letter[0] - inch, 0.55 * inch, str(doc.page))


def footer_landscape(canvas, doc):
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.6 * inch, 0.5 * inch, "Design document. t20-exact-forecast. Siddharth Shashank Kumar.")
    canvas.drawRightString(landscape(letter)[0] - 0.6 * inch, 0.5 * inch, str(doc.page))


def markdown():
    out = [f"# {TITLE}", "", SUBTITLE, ""]
    for block in BLOCKS:
        kind = block[0]
        if kind == "h1":
            out += [f"## {block[1]}", ""]
        elif kind == "h2":
            out += [f"### {block[1]}", ""]
        elif kind == "p":
            out += [block[1], ""]
        elif kind == "bullets":
            out += [f"- {item}" for item in block[1]] + [""]
        elif kind == "table":
            _, header, rows, _ = block
            out += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows] + [""]
        elif kind == "code":
            out += ["```", block[1], "```", ""]
        elif kind == "figure":
            out += [f"![{block[2]}](figures/{block[1]}.svg)", "", f"*{block[2]}*", ""]
        elif kind == "plate":
            out += [f"### {block[2]}", "", f"![{block[3]}](../../figures/{block[1]}.svg)", "", f"*{block[3]}*", ""]
    return "\n".join(out)


if __name__ == "__main__":
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT / "DESIGN.pdf"), pagesize=letter, title=TITLE, author="Siddharth Shashank Kumar")
    W, H = letter
    doc.addPageTemplates([PageTemplate("portrait", [Frame(inch, 0.9 * inch, W - 2 * inch, H - 1.8 * inch, id="p")], onPage=footer),
                          PageTemplate("landscape", [Frame(0.6 * inch, 0.8 * inch, H - 1.2 * inch, W - 1.6 * inch, id="l")], pagesize=landscape(letter), onPage=footer_landscape)])
    doc.build(pdf_flowables())
    for name, make in FIGURES.items():
        renderSVG.drawToFile(make(), str(OUT / "figures" / f"{name}.svg"))
    (OUT / "DESIGN.md").write_text(markdown())
    print("built", sorted(p.name for p in OUT.iterdir()))
