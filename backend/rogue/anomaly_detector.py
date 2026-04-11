<<<<<<< Updated upstream
=======
import math
>>>>>>> Stashed changes
import numpy as np
from sklearn.ensemble import IsolationForest
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SatelliteBaseline:
    """
    Per-satellite running statistics using Welford's online algorithm.
    Used by AnomalyDetector for z-score computation.
    """
    norad_id: int
    cluster_id: int = 0
    means: dict = field(default_factory=dict)
    stds: dict = field(default_factory=dict)
    n: int = 0
    m2: dict = field(default_factory=dict, repr=False)  # sum of squared deviations

    def update(self, features: dict) -> None:
        self.n += 1
        for k, v in features.items():
            if not isinstance(v, (int, float)) or math.isnan(float(v)):
                continue
            v = float(v)
            if k not in self.means:
                self.means[k] = v
                self.m2[k] = 0.0
                self.stds[k] = 0.0
            else:
                delta = v - self.means[k]
                self.means[k] += delta / self.n
                delta2 = v - self.means[k]
                self.m2[k] += delta * delta2
                if self.n > 1:
                    self.stds[k] = math.sqrt(self.m2[k] / (self.n - 1))

    def zscore(self, key: str, value: float) -> float:
        std = self.stds.get(key, 0.0)
        if std < 1e-9:
            return 0.0
        return abs(float(value) - self.means.get(key, float(value))) / std


FEATURE_KEYS = [
    'delta_mean_motion', 'delta_eccentricity', 'delta_inclination',
    'delta_bstar', 'delta_v_proxy', 'time_gap_hours',
    'solar_f107', 'kp_index'
]

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

        if composite < 0.3:
            severity = "ROUTINE"
        elif composite < 0.65:
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
        # Structured text passed to Claude API for NL generation
        return (
            f"NORAD {norad_id} | {severity} | "
            f"delta_v_proxy={features.get('delta_v_proxy', 0):.2f} m/s | "
            f"anomalous_features={anomalous}"
        )