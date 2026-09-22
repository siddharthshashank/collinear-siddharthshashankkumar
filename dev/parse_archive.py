import glob
import pandas as pd
import yaml

# C loader reads a match about 10x faster than pure Python one
Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

# dismissals that are not the bowler's doing
NOT_BOWLER = ("run out", "retired hurt", "obstructing the field")
COLUMNS = ["match", "date", "venue", "innings","team", "over_ball", "batter", "non_striker", "bowler",
           "runs_bat", "runs_total", "wide", "noball", "bowler_wicket", "wicket_any"]

def parse_match(path):
    doc = yaml.load(open(path), Loader=Loader)
    info = doc["info"]
    match_id = path.split("/")[-1][:-5]
    date = str(info["dates"][0])
    rows = []
    for number, innings in enumerate(doc["innings"], 1):
        # each innings is a one-entry dictionary, like {"1st innings": {...}}
        (label, body), = innings.items()
        # a super over is a tie-breaker, not part of the match proper
        if "super" in label.lower():
            continue
        for delivery in body["deliveries"]:
            # each delivery is a one-entry dictionary too, like {0.1: {...}}
            (over_ball, d), = delivery.items()
            extras = d.get("extras", {})
            wicket = d.get("wicket")
            # some files may list two wickets on one ball, most give a single block or none
            wickets = wicket if isinstance(wicket, list) else [wicket] if wicket else []
            kinds = [w["kind"] for w in wickets]
            rows.append((match_id, date, info.get("venue"), number, body["team"], float(over_ball),
                         d["batsman"], d["non_striker"], d["bowler"], d["runs"]["batsman"], d["runs"]["total"],
                         "wides" in extras, "noballs" in extras,
                         any(k not in NOT_BOWLER for k in kinds), any(k != "retired hurt" for k in kinds)))
    return rows