import json
from dataclasses import dataclass
from pathlib import Path
import numpy as np

@dataclass(frozen = True)
class Calibration:
    over_logits: np.ndarray
    position_vectors: np.ndarray
    wickets_vector: np.ndarray
    pressure_vector: np.ndarray
    second_innings_vector: np.ndarray
    typical_wickets: np.ndarray
    par_rate: np.ndarray
    directions: dict
    spreads: dict
    era_step: float
    runs_per_condition_unit: float
    extras_per_ball: float
    venue_sd_runs: float
    batter_venue_sd_runs: float
    real_targets: dict

    @classmethod
    def load(cls, path = None):
        raw = json.loads(Path(path or Path(__file__).with_name("calibration.json")).read_text())
        groups = [0, 0, 0, 1, 1, 2, 2, 3, 3, 3, 3]                        # positions 1-3, 4-5, 6-7, 8-11
        return cls(np.array(raw["over_logits"]), np.array(raw["position_vectors"])[groups], np.array(raw["wickets_in_hand_vector"]),
                   np.array(raw["chase_pressure_vector"]), np.array(raw["second_innings_vector"]), np.array(raw["typical_wickets_by_over"]),
                   np.array(raw["par_rate_from_over"]), {k: np.array(v) for k, v in raw["directions"].items()}, raw["spreads"], raw["era_step"],
                   raw["runs_per_unit"]["conditions"], raw["extras_per_legal_ball"], raw["venue_level_sd_runs"], raw["batter_venue_sd_runs"], raw["real_targets"])

@dataclass(frozen = True)
class Design:
    teams: int = 10
    squad_roles: tuple = (7, 4, 7)                 # batters, allrounders, bowlers in every squad
    xi_roles: tuple = (5, 2, 4)
    seasons: int = 3
    weeks_per_season: int = 8
    talent_share: float = 0.7                   # with form_memory this gives the archive's 0.8 year-to-year stability of batting skill
    form_memory_years: float = 0.75
    type_gap: float = 0.28                     # spinners concede sixes, pace concedes fours: the public bowling style explains about half the type spread
    split_sd: float = 0.10                     # a batter's pace-versus-spin gap in quality; small, as the archive's head-to-head repeat implies
    type_table_runs: tuple = ((0.0, -0.008), (0.0, 0.019))      # [right, left hand][vs pace, vs spin], runs per ball
    pitch_table_runs: tuple = ((0.0, 0.019, -0.010), (0.0, -0.010, 0.019))   # [pace, spin][neutral, pacey, turning] help to the bowler
    home_runs: float = 0.025
    affinity_share: float = 0.8                # part of the measured batter-at-venue spread that is personal, not just playing at home
    dew_share: float = 0.4
    dew_runs: float = 0.044
    level_runs: float = -0.058                 # players differ, and that alone lifts the average total; this recentres it on the archive
    day_sd_runs: float = 0.17                  # the pitch on the day; set so the spread of totals matches the archive
    wear_runs: float = 0.053                    # second innings are a little harder; set so identical sides chase at the archive's rate
    left_handed: float = 0.3
    transfer_share: float = 0.25 