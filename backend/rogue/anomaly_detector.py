import math
import numpy as np
from sklearn.ensemble import IsolationForest
from dataclasses import dataclass, field
from datetime import datetime

from backend.rogue.pol_model import SatelliteBaseline

FEATURE_KEYS = [
    'delta_mean_motion', 'delta_eccentricity', 'delta_inclination',
    'delta_bstar', 'delta_v_proxy', 'time_gap_hours',
    'solar_f107', 'kp_index'
]

# Satellites operated by known cooperative/civil agencies whose maneuvers
# are publicly tracked and operationally expected. Anomalies are still flagged
# (the maneuver is real) but intent cannot be classified as ADVERSARIAL.
_COOPERATIVE_NORADS: set[int] = {
    25544,   # ISS — NASA/Roscosmos/ESA/JAXA/CSA
    48274,   # CSS (Tiangong) — CMSA
    20580,   # HST (Hubble Space Telescope) — NASA
    43205,   # NOAA-20
    33591,   # NOAA-19
    28654,   # NOAA-18
    27424,   # Aqua — NASA
    25994,   # Terra — NASA
}

@dataclass
class AnomalyEvent:
    norad_id: int
    epoch: datetime
    severity: str          # ROUTINE | SUSPICIOUS | ADVERSARIAL
    composite_score: float
    z_score_max: float
    iso_score: float
    proximity_flag: bool
    anomalous_features: list[str]
    description: str       # for Claude API natural language layer

class AnomalyDetector:
    def __init__(self, baseline_store: dict, iso_models: dict):
        self.baselines = baseline_store   # norad_id -> SatelliteBaseline
        self.iso_models = iso_models      # cluster_id -> IsolationForest

    def score(self, norad_id: int, features: dict,
              cdm_events: list) -> AnomalyEvent:

        baseline = self.baselines.get(norad_id)
        cluster_id = baseline.cluster_id if baseline else 0

        # Layer 1: Z-score
        z_scores = {k: baseline.zscore(k, features[k])
                    for k in FEATURE_KEYS if baseline and k in features}
        z_max = max(z_scores.values(), default=0.0)
        anomalous = [k for k, z in z_scores.items() if z > 3.0]

        # Layer 2: Isolation Forest
        iso_model = self.iso_models.get(cluster_id)
        X = np.array([[features.get(k, 0.0) for k in FEATURE_KEYS]])
        iso_score = float(-iso_model.score_samples(X)[0]) if iso_model else 0.0

        # Layer 4: Proximity
        proximity_flag = any(
            e['sat_id'] == norad_id and e['miss_distance_km'] < 50
            for e in cdm_events
        )

        # Combine
        composite = (
            0.35 * min(z_max / 5.0, 1.0) +
            0.40 * min(iso_score / 0.5, 1.0) +
            0.25 * float(proximity_flag)
        )

        if composite < 0.5:
            severity = "ROUTINE"
        elif composite < 0.72:
            severity = "SUSPICIOUS"
        else:
            # Cooperative satellites can show large maneuvers for legitimate
            # operational reasons. Flag the anomaly but cap intent at SUSPICIOUS.
            if norad_id in _COOPERATIVE_NORADS:
                severity = "SUSPICIOUS"
            else:
                severity = "ADVERSARIAL"

        # Update baseline
        if baseline:
            baseline.update(features)

        return AnomalyEvent(
            norad_id=norad_id,
            epoch=features['epoch'],
            severity=severity,
            composite_score=composite,
            z_score_max=z_max,
            iso_score=iso_score,
            proximity_flag=proximity_flag,
            anomalous_features=anomalous,
            description=self._describe(norad_id, severity, features, anomalous)
        )

    def _describe(self, norad_id, severity, features, anomalous):
        return (
            f"NORAD {norad_id} | {severity} | "
            f"delta_v_proxy={features.get('delta_v_proxy', 0):.2f} m/s | "
            f"anomalous_features={anomalous}"
        )