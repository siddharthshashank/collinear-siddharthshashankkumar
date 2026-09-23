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