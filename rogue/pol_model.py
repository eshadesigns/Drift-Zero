import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class SatelliteBaseline:
    norad_id: int
    cluster_id: Optional[int] = None
    n_obs: int = 0
    last_updated: Optional[datetime] = None
    # EWMA stats per feature
    means: dict = field(default_factory=dict)
    vars_: dict = field(default_factory=dict)
    # Maneuver cadence
    maneuver_count_30d: float = 0.0
    mean_maneuver_dv: float = 0.0
    # Orbital regime
    mean_motion_mean: float = 0.0
    mean_motion_var: float = 0.0

    ALPHA = 0.05  # EWMA decay

    def update(self, features: dict):
        for k, v in features.items():
            if k not in self.means:
                self.means[k] = v
                self.vars_[k] = 0.0
            else:
                old_mean = self.means[k]
                self.means[k] = self.ALPHA * v + (1 - self.ALPHA) * old_mean
                self.vars_[k] = (self.ALPHA * (v - self.means[k])**2
                                 + (1 - self.ALPHA) * self.vars_[k])
        self.n_obs += 1
        self.last_updated = datetime.utcnow()

    def zscore(self, feature: str, value: float) -> float:
        std = np.sqrt(self.vars_.get(feature, 1.0))
        if std < 1e-6:
            return 0.0
        return abs(value - self.means.get(feature, value)) / std