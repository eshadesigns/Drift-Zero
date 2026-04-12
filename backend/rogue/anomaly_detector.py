import numpy as np
from sklearn.ensemble import IsolationForest
from dataclasses import dataclass
from datetime import datetime

from backend.rogue.pol_model import SatelliteBaseline

FEATURE_KEYS = [
    'delta_mean_motion', 'delta_eccentricity', 'delta_inclination',
    'delta_raan', 'delta_bstar', 'delta_v_proxy', 'time_gap_hours',
    'solar_f107', 'kp_index',
]

# Rule-based intent labels (Rogue pattern-of-life / threat heuristics)
INTENT_AGGRESSIVE_PROXIMITY = 'AGGRESSIVE_PROXIMITY'
INTENT_INSPECTION = 'INSPECTION'
INTENT_EVASIVE = 'EVASIVE'
INTENT_SHADOWING = 'SHADOWING'
INTENT_STATION_KEEPING = 'STATION_KEEPING'


def infer_intent_label(
    *,
    anomalous_features: list[str],
    composite_score: float,
    proximity_flag: bool,
    features: dict,
) -> str:
    """
    Classify intent from feature anomalies, composite score, and CDM proximity.
    Rules are evaluated in priority order (first match wins).
    """
    af = set(anomalous_features)
    dv = float(features.get('delta_v_proxy', 0.0) or 0.0)

    if proximity_flag and dv > 50.0:
        return INTENT_AGGRESSIVE_PROXIMITY
    if proximity_flag and 'delta_raan' in af:
        return INTENT_INSPECTION
    if (
        proximity_flag
        and composite_score >= 0.52
        and ('delta_v_proxy' in af or dv > 15.0)
    ):
        return INTENT_EVASIVE
    if proximity_flag and composite_score >= 0.60:
        return INTENT_SHADOWING
    if proximity_flag:
        return INTENT_SHADOWING
    if af & {'delta_mean_motion', 'delta_eccentricity', 'delta_inclination',
              'delta_raan', 'delta_bstar', 'delta_v_proxy'}:
        return INTENT_STATION_KEEPING
    return INTENT_STATION_KEEPING

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
    intent_label: str      # STATION_KEEPING | EVASIVE | INSPECTION | SHADOWING | AGGRESSIVE_PROXIMITY
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
            severity = "ADVERSARIAL"

        # Update baseline
        if baseline:
            baseline.update(features)

        intent = infer_intent_label(
            anomalous_features=anomalous,
            composite_score=composite,
            proximity_flag=proximity_flag,
            features=features,
        )

        return AnomalyEvent(
            norad_id=norad_id,
            epoch=features['epoch'],
            severity=severity,
            composite_score=composite,
            z_score_max=z_max,
            iso_score=iso_score,
            proximity_flag=proximity_flag,
            anomalous_features=anomalous,
            intent_label=intent,
            description=self._describe(norad_id, severity, features, anomalous, intent)
        )

    def _describe(self, norad_id, severity, features, anomalous, intent_label):
        return (
            f"NORAD {norad_id} | {severity} | intent={intent_label} | "
            f"delta_v_proxy={features.get('delta_v_proxy', 0):.2f} m/s | "
            f"anomalous_features={anomalous}"
        )