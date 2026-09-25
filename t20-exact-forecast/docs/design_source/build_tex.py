"""Builds the design document as a LaTeX paper from the same content.py the report builder uses.

    python build_tex.py        ->  tex/DESIGN.tex     then: cd tex && latexmk -pdf DESIGN.tex
"""
import re
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from content import BLOCKS, TITLE

HERE = Path(__file__).resolve().parent
TEX = HERE / "tex"
TEXT_WIDTH = 468.0        # points, letter paper with one-inch margins
MAX_SCALE = 1.3           # a drawing is never enlarged beyond 1.3 times its natural size

# How each drawing is cut into parts: (label, x0, y0, x1, y1) in the drawing's own viewBox units (1400 wide).
# The cuts follow the zones the drawings already have, so no box or arrow is severed.
CROPS = {
    "dependencies": [("The archive, the parser, the two fits and the merge, with their files", 20, 130, 720, 760),
                     ("The constants file read at import, validation, the ladder runner and the bar analysis with their import taps", 600, 130, 1330, 760),
                     ("The library modules and their own imports, above the scripts that tap them", 660, 76, 2140, 330),
                     ("The task-data build and the packager: what each reads, what each writes", 1180, 130, 1960, 760),
                     ("The Harbor run, the ablations, the figures and the documents", 1780, 130, 2720, 760)],
    "architecture": [("Calibration and the synthetic world", 20, 76, 660, 716),
                     ("Task data and packaging", 660, 76, 1300, 716),
                     ("The Harbor runtime", 1300, 76, 1740, 716),
                     ("Evidence and documents, left half", 20, 728, 900, 890),
                     ("Evidence and documents, right half", 900, 728, 1740, 890)],
    "system_overview": [("Calibration from the real archive, and the synthetic world that holds the hidden state", 8, 8, 544, 464),
                        ("Task build and packaging", 544, 8, 830, 464),
                        ("The Harbor runtime: the agent container and the separate verifier container", 830, 8, 1392, 464),
                        ("Research evidence and the pass bar, left half", 8, 468, 705, 604),
                        ("Research evidence and the pass bar, right half", 705, 468, 1392, 604)],
    "calibration_pipeline": [("From the archive to the two fitted files", 8, 8, 709, 444),
                             ("From the fitted files to the constants file, and the validation loop", 709, 8, 1392, 444)],
    "task_build_and_packaging": [("make\\_task\\_data.py, repeated for each of the eight worlds", 8, 8, 664, 524),
                                 ("package\\_task.py: the four source trees and the two sides of the task", 668, 8, 1392, 524)],
    "harbor_runtime": [("The agent container", 8, 8, 494, 584),
                       ("The verifier container and the grader's checks", 572, 8, 1392, 584)],
    "grading_rule": [("Each world's mean regret, left half", 8, 8, 700, 160),
                     ("Each world's mean regret, right half", 700, 8, 1392, 160),
                     ("The rule on all eight worlds and the key it sets", 8, 160, 460, 380),
                     ("The same rule on the seven held-out worlds and the key it sets", 460, 160, 880, 380),
                     ("The constraint checks and the artifact check, and their keys", 880, 160, 1392, 380)],
    "research_ladder": [("The ladder runner: worlds, truth and the eight tiers", 8, 8, 672, 228),
                        ("The ladder runner: scoring and the results log", 672, 8, 1104, 228),
                        ("The bar analysis: eight worlds that are never graded", 8, 236, 672, 448),
                        ("The bar analysis: the ratios and what they showed", 672, 236, 1104, 448),
                        ("The pass bar as committed, and what was not measured", 1104, 8, 1392, 448)],
}
PANELS = {"pilot_results": [("pilot_a", "All ten runs and the ladder tiers, pooled over the graded worlds. Filled markers are all eight worlds, hollow the seven held out; run 8 is the session cut short by a usage limit."),
                            ("pilot_b", "Regret on each world as a multiple of the reference's. Bold values are at or under the bar."),
                            ("pilot_c", "The ablations of Section 6.3: each first-round program as submitted (hollow) and after its one constant was changed (filled), on held-out world c.")]}


def esc(text):
    text = text.replace("\\", r"\textbackslash{}")
    for a, b in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        text = text.replace(a, b)
    return text.replace('"', "''")


def rich(text):
    out, i = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*|`(.+?)`", text):
        out.append(esc(text[i:m.start()]))
        out.append((r"\textbf{" + esc(m.group(1)) + "}") if m.group(1) is not None else (r"\texttt{" + esc(m.group(2)) + "}"))
        i = m.end()
    out.append(esc(text[i:]))
    return "".join(out).replace(" -> ", r" $\to$ ")


def table(header, rows, widths):
    usable = 1.0 - (len(widths) * 6.0) / TEXT_WIDTH - 0.01          # each column carries 2 x 3pt of padding
    cols = "".join(">{\\raggedright\\arraybackslash}p{%.3f\\textwidth}" % (w * usable) for w in widths)
    head = " & ".join(r"\textbf{" + rich(h) + "}" for h in header) + r" \\ \midrule"
    body = "\n".join(" & ".join(rich(str(c)) for c in row) + r" \\ \addlinespace[2pt]" for row in rows)
    return "\n".join([r"\begin{small}", r"\begin{longtable}{" + cols + "}", r"\toprule", head, r"\endfirsthead", r"\toprule", head, r"\endhead",
                      r"\midrule \multicolumn{%d}{r}{\footnotesize continued on the next page} \\ \endfoot" % len(header),
                      r"\bottomrule \endlastfoot", body, r"\end{longtable}", r"\end{small}"])


def figure(name, caption):
    return "\n".join([r"\begin{figure}[htbp]", r"\centering", r"\includegraphics[width=\textwidth]{figs/%s.pdf}" % name, r"\caption{" + rich(caption) + "}", r"\end{figure}"])


def cropped_figures(name, title, caption):
    """One drawing cut into parts, each a figure at readable scale; the parts share one figure number."""
    page = PdfReader(TEX / "figs" / f"{name}.pdf").pages[0]
    W, H = float(page.mediabox.width), float(page.mediabox.height)
    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', (HERE / "figures" / f"{name}.svg").read_text())
    k = W / float(vb.group(1))
    out = []
    for n, (label, x0, y0, x1, y1) in enumerate(CROPS[name]):
        natural = k * (x1 - x0)
        width = min(TEXT_WIDTH, MAX_SCALE * natural) / TEXT_WIDTH
        vp = "%.1f %.1f %.1f %.1f" % (k * x0, H - k * y1, k * x1, H - k * y0)
        part = "(%s) %s" % ("abcdefg"[n], label)
        cap = (r"\textbf{" + rich(title) + "} " + rich(caption) + " " + part + ".") if n == 0 else (rich(title) + ", continued. " + part + ".")
        out.append("\n".join([r"\begin{figure}[htbp]" + (r"\ContinuedFloat" if n else ""), r"\centering",
                              r"\includegraphics[viewport=%s, clip, width=%.3f\textwidth]{figs/%s.pdf}" % (vp, width, name),
                              r"\caption{" + cap + "}", r"\end{figure}"]))
    return "\n\n".join(out)


FULL = {"system"}
def full_page(name, title, caption):
    return "\n".join([r"\begin{landscape}", r"\begin{figure}[p]", r"\centering",
                      r"\includegraphics[width=\linewidth,height=0.86\textheight,keepaspectratio]{figs/%s.pdf}" % name,
                      r"\caption{\textbf{" + rich(title) + "} " + rich(caption) + "}", r"\end{figure}", r"\end{landscape}"])


def panel_figures(name, title, caption):
    out = []
    for n, (file, label) in enumerate(PANELS[name]):
        cap = (r"\textbf{" + rich(title) + "} " + rich(caption) + " (%s) %s" % ("abc"[n], rich(label))) if n == 0 else (rich(title) + ", continued. (%s) %s" % ("abc"[n], rich(label)))
        out.append("\n".join([r"\begin{figure}[htbp]" + (r"\ContinuedFloat" if n else ""), r"\centering",
                              r"\includegraphics[width=0.86\textwidth]{figs/%s.pdf}" % file, r"\caption{" + cap + "}", r"\end{figure}"]))
    return "\n\n".join(out)


RENAME = {"Summary": "Introduction", "The chosen design, part by part": "The design, part by part", "What comes next": "Future work"}


def body():
    out, appendix = [], False
    for block in BLOCKS:
        kind = block[0]
        if kind == "h1":
            title = re.sub(r"^\d+\.\s*", "", block[1])
            if title.startswith("Appendix"):
                out.append(r"\appendix" + "\n" + r"\section{Repository map and the bugs the checks caught}"); appendix = True
            elif title == "Plates":
                out.append(r"\section{Drawings of the system}")
            else:
                out.append(r"\section{" + rich(RENAME.get(title, title)) + "}")
        elif kind == "h2":
            out.append(r"\subsection{" + rich(re.sub(r"^\d+\.\d+\s*", "", block[1])) + "}")
        elif kind == "p":
            if block[1].startswith("**Sources.**"):
                continue                                     # the paper carries a reference list instead
            if block[1].startswith("Seven drawings of the system"):
                out.append("Eight drawings of the system, each cut along its own zones into parts that read at text size. They are generated from the repository by the scripts under \\texttt{figures/}, so they change when the code does.\n")
                continue
            out.append(rich(block[1]) + "\n")
        elif kind == "bullets":
            out.append(r"\begin{itemize}[leftmargin=1.4em, itemsep=2pt]" + "\n" + "\n".join(r"\item " + rich(b) for b in block[1]) + "\n" + r"\end{itemize}")
        elif kind == "table":
            out.append(table(block[1], block[2], block[3]))
        elif kind == "code":
            out.append(r"\begin{lstlisting}" + "\n" + block[1] + "\n" + r"\end{lstlisting}")
        elif kind == "figure":
            out.append(figure(block[1], block[2]))
        elif kind == "plate":
            title = re.sub(r"^Plate \d+\.\s*", "", block[2])
            out.append(full_page(block[1], title, block[3]) if block[1] in FULL else panel_figures(block[1], title, block[3]) if block[1] in PANELS else cropped_figures(block[1], title, block[3]))
    return "\n\n".join(out)


ABSTRACT = (
    "Every forecasting benchmark I know grades against outcomes, and an outcome is one noisy draw. This paper describes a task for coding agents in which the luck is "
    "taken out of the grade. An agent receives three seasons of ball-by-ball history from a simulated Twenty20 cricket league, together with the match engine stripped of "
    "its hidden values, and must deliver a program that forecasts the home side's win probability for the coming fixtures. Because I generate the league, the true "
    "probability of every fixture is known, and a forecast is scored by its expected logarithmic loss against that truth, the Kullback-Leibler regret. The simulator is "
    "calibrated to 295,557 real deliveries from the Cricsheet IPL archive, models only effects that repeat in independent halves of that archive, and ships only aggregate "
    "constants. The pass rule, a bar on regret summed over eight worlds at 1.10 times a reference forecaster built from ordinary regularised statistics, was chosen on "
    "worlds that are never graded and committed before any model ran. Under that rule Claude Opus 4.7 and GPT-5.5, each run five times in its native harness at high "
    "reasoning effort, failed ten times out of ten, at 1.11 to 1.70 times the reference's regret, with every run producing a valid, deterministic forecast. Reading the "
    "programs found the same cause in each: prior scales set three to forty-four times too weak, with no check that could see it; changing that one constant moved each "
    "program most of the way to the reference, and made the near miss beat it. The next generation, Claude Fable 5.1 and GPT-6-astra, passed four of five completed runs on the "
    "same frozen task by the route the design predicted, learning the prior scales from the data and checking themselves against leagues they built; the bar sits between the two "
    "generations. The task, its verifier, its records and this paper are in one repository."
)

REFERENCES = [
    "Amodei, D., Olah, C., Steinhardt, J., Christiano, P., Schulman, J., and Man\\'e, D. (2016). Concrete problems in AI safety. arXiv:1606.06565.",
    "Anscombe, F. J. (1956). On estimating binomial response relations. \\emph{Biometrika}, 43, 461--464.",
    "Bernardo, J. M. (1979). Expected information as expected utility. \\emph{Annals of Statistics}, 7, 686--690.",
    "Bishop, C. M. (2006). \\emph{Pattern Recognition and Machine Learning}. Springer.",
    "Blanchard, P., Higham, D. J., and Higham, N. J. (2021). Accurately computing the log-sum-exp and softmax functions. \\emph{IMA Journal of Numerical Analysis}, 41, 2311--2330.",
    "Bradley, R. A. and Terry, M. E. (1952). Rank analysis of incomplete block designs: I. The method of paired comparisons. \\emph{Biometrika}, 39, 324--345.",
    "Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. \\emph{Monthly Weather Review}, 78, 1--3.",
    "Brown, W. (1910). Some experimental results in the correlation of mental abilities. \\emph{British Journal of Psychology}, 3, 296--322.",
    "Byrd, R. H., Lu, P., Nocedal, J., and Zhu, C. (1995). A limited memory algorithm for bound constrained optimization. \\emph{SIAM Journal on Scientific Computing}, 16, 1190--1208.",
    "Cover, T. M. and Thomas, J. A. (2006). \\emph{Elements of Information Theory}, 2nd edition. Wiley.",
    "Cox, D. R. (1958). Two further applications of a model for binary regression. \\emph{Biometrika}, 45, 562--565.",
    "Cricsheet. Ball-by-ball cricket data, maintained by Stephen Rushe. cricsheet.org. Open Data Commons Attribution License 1.0.",
    "Davis, J., Perera, H., and Swartz, T. B. (2015). A simulator for Twenty20 cricket. \\emph{Australian \\& New Zealand Journal of Statistics}, 57, 55--71.",
    "Devroye, L. (1986). \\emph{Non-Uniform Random Variate Generation}. Springer.",
    "Duckworth, F. C. and Lewis, A. J. (1998). A fair method for resetting the target in interrupted one-day cricket matches. \\emph{Journal of the Operational Research Society}, 49, 220--227.",
    "Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., and Roth, A. (2015). The reusable holdout: preserving validity in adaptive data analysis. \\emph{Science}, 349, 636--638.",
    "Efron, B. and Morris, C. (1977). Stein's paradox in statistics. \\emph{Scientific American}, 236(5), 119--127.",
    "Fuller, W. A. (1987). \\emph{Measurement Error Models}. Wiley.",
    "Galton, F. (1886). Regression towards mediocrity in hereditary stature. \\emph{Journal of the Anthropological Institute}, 15, 246--263.",
    "Glickman, M. E. (1999). Parameter estimation in large dynamic paired comparison experiments. \\emph{Journal of the Royal Statistical Society: Series C}, 48, 377--394.",
    "Gneiting, T. and Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. \\emph{Journal of the American Statistical Association}, 102, 359--378.",
    "Good, I. J. (1952). Rational decisions. \\emph{Journal of the Royal Statistical Society: Series B}, 14, 107--114.",
    "Harbor Framework Team (2026). Harbor: a framework for evaluating and optimizing agents and models in container environments. Laude Institute. github.com/laude-institute/harbor.",
    "Hoerl, A. E. and Kennard, R. W. (1970). Ridge regression: biased estimation for nonorthogonal problems. \\emph{Technometrics}, 12, 55--67.",
    "James, W. and Stein, C. (1961). Estimation with quadratic loss. \\emph{Proceedings of the Fourth Berkeley Symposium on Mathematical Statistics and Probability}, 1, 361--379.",
    "Jolliffe, I. T. (2002). \\emph{Principal Component Analysis}, 2nd edition. Springer.",
    "Kelly, J. L. (1956). A new interpretation of information rate. \\emph{Bell System Technical Journal}, 35, 917--926.",
    "Kullback, S. and Leibler, R. A. (1951). On information and sufficiency. \\emph{Annals of Mathematical Statistics}, 22, 79--86.",
    "Law, A. M. (2015). \\emph{Simulation Modeling and Analysis}, 5th edition. McGraw-Hill.",
    "Liu, D. C. and Nocedal, J. (1989). On the limited memory BFGS method for large scale optimization. \\emph{Mathematical Programming}, 45, 503--528.",
    "Lord, F. M. and Novick, M. R. (1968). \\emph{Statistical Theories of Mental Test Scores}. Addison-Wesley.",
    "Makridakis, S., Spiliotis, E., and Assimakopoulos, V. (2020). The M4 Competition: 100,000 time series and 61 forecasting methods. \\emph{International Journal of Forecasting}, 36, 54--74.",
    "Marylebone Cricket Club (2017). \\emph{The Laws of Cricket}, 2017 Code. Laws 17, 21, 22 and 23.",
    "McFadden, D. (1974). Conditional logit analysis of qualitative choice behavior. In P. Zarembka (ed.), \\emph{Frontiers in Econometrics}, 105--142. Academic Press.",
    "McKinney, W. (2010). Data structures for statistical computing in Python. \\emph{Proceedings of the 9th Python in Science Conference}, 56--61.",
    "Metropolis, N. and Ulam, S. (1949). The Monte Carlo method. \\emph{Journal of the American Statistical Association}, 44, 335--341.",
    "Morris, T. P., White, I. R., and Crowther, M. J. (2019). Using simulation studies to evaluate statistical methods. \\emph{Statistics in Medicine}, 38, 2074--2102.",
    "Murphy, A. H. (1973). Hedging and skill scores for probability forecasts. \\emph{Journal of Applied Meteorology}, 12, 215--223.",
    "Murphy, A. H. (1988). Skill scores based on the mean square error and their relationships to the correlation coefficient. \\emph{Monthly Weather Review}, 116, 2417--2424.",
    "Nosek, B. A., Ebersole, C. R., DeHaven, A. C., and Mellor, D. T. (2018). The preregistration revolution. \\emph{Proceedings of the National Academy of Sciences}, 115, 2600--2606.",
    "Peng, R. D. (2011). Reproducible research in computational science. \\emph{Science}, 334, 1226--1227.",
    "Saltzer, J. H. and Schroeder, M. D. (1975). The protection of information in computer systems. \\emph{Proceedings of the IEEE}, 63, 1278--1308.",
    "Sargent, R. G. (2013). Verification and validation of simulation models. \\emph{Journal of Simulation}, 7, 12--24.",
    "Selten, R. (1998). Axiomatic characterization of the quadratic scoring rule. \\emph{Experimental Economics}, 1, 43--61.",
    "Shafranovich, Y. (2005). Common format and MIME type for comma-separated values (CSV) files. RFC 4180, IETF.",
    "Simmons, J. P., Nelson, L. D., and Simonsohn, U. (2011). False-positive psychology: undisclosed flexibility in data collection and analysis allows presenting anything as significant. \\emph{Psychological Science}, 22, 1359--1366.",
    "Skalse, J., Howe, N. H. R., Krasheninnikov, D., and Krueger, D. (2022). Defining and characterizing reward hacking. arXiv:2209.13085.",
    "Spearman, C. (1904). The proof and measurement of association between two things. \\emph{American Journal of Psychology}, 15, 72--101.",
    "Spearman, C. (1910). Correlation calculated from faulty data. \\emph{British Journal of Psychology}, 3, 271--295.",
    "Stone, M. (1974). Cross-validatory choice and assessment of statistical predictions. \\emph{Journal of the Royal Statistical Society: Series B}, 36, 111--147.",
    "Swartz, T. B., Gill, P. S., and Muthukumarana, S. (2009). Modelling and simulation for one-day cricket. \\emph{Canadian Journal of Statistics}, 37, 143--160.",
    "Tango, T., Lichtman, M., and Dolphin, A. (2007). \\emph{The Book: Playing the Percentages in Baseball}. Potomac Books.",
    "Tipping, M. E. and Bishop, C. M. (1999). Probabilistic principal component analysis. \\emph{Journal of the Royal Statistical Society: Series B}, 61, 611--622.",
    "Tukey, J. W. (1977). \\emph{Exploratory Data Analysis}. Addison-Wesley.",
    "Uhlenbeck, G. E. and Ornstein, L. S. (1930). On the theory of the Brownian motion. \\emph{Physical Review}, 36, 823--841.",
    "Wickham, H. (2014). Tidy data. \\emph{Journal of Statistical Software}, 59(10), 1--23.",
]

PREAMBLE = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{mathptmx}
\usepackage{microtype}
\usepackage{graphicx}
\usepackage{array}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{pdflscape}
\usepackage{enumitem}
\usepackage{listings}
\usepackage{caption}
\usepackage{fancyhdr}
\usepackage{amsmath}
\usepackage{xcolor}
\usepackage[hidelinks]{hyperref}
\color{black}
\pagecolor{white}
\captionsetup{font=small, labelfont=bf, width=0.95\textwidth}
\setlength{\parskip}{4pt plus 1pt}
\setlength{\parindent}{0pt}
\setlength{\tabcolsep}{3pt}
\lstset{basicstyle=\ttfamily\footnotesize, breaklines=true, frame=single, framerule=0.3pt, rulecolor=\color{black}, xleftmargin=4pt, columns=fullflexible, keepspaces=true}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small Grading forecasts against the exact truth}
\fancyhead[R]{\small S. S. Kumar}
\fancyfoot[C]{\small\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\title{\LARGE\bfseries %(title)s\\[6pt]\large Design of a Harbor task that grades probabilistic forecasts against a planted truth}
\author{Siddharth Shashank Kumar\\ \small thesidshashank@gmail.com\\ \small github.com/siddharthshashank/collinear-siddharthshashankkumar}
\date{24 September 2026}
\begin{document}
\maketitle
\begin{abstract}
%(abstract)s
\end{abstract}
\tableofcontents
\clearpage
"""


def references():
    return r"\section*{References}" + "\n" + r"\addcontentsline{toc}{section}{References}" + "\n" + r"\begin{footnotesize}" + "\n" + r"\begin{enumerate}[leftmargin=1.6em, itemsep=1pt, label={[\arabic*]}]" + "\n" + "\n".join(r"\item " + r for r in REFERENCES) + "\n" + r"\end{enumerate}" + "\n" + r"\end{footnotesize}"


if __name__ == "__main__":
    TEX.mkdir(exist_ok=True)
    doc = PREAMBLE % {"title": rich(TITLE), "abstract": ABSTRACT} + body() + "\n\n" + references() + "\n\\end{document}\n"
    (TEX / "DESIGN.tex").write_text(doc)
    print("wrote", TEX / "DESIGN.tex", len(doc), "characters")
