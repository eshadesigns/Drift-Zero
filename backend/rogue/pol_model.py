import math
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class SatelliteBaseline:
    norad_id: int
    cluster_id: int = 0
    means: dict = field(default_factory=dict)
    stds: dict = field(default_factory=dict)
    n: int = 0
    m2: dict = field(default_factory=dict, repr=False)

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