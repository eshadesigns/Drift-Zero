"""
backend/shield/probability.py

Computes collision probability using the Chan/Alfano 2D projection method.

Method summary
--------------
In the conjunction plane (perpendicular to the relative velocity vector at TCA),
the relative position uncertainty is modelled as a 2D Gaussian with a diagonal
covariance built from the combined 1-sigma uncertainties of both objects:

    C = diag(σ_r², σ_c²)

where σ_r is the combined radial uncertainty and σ_c is the combined
cross-track/along-track uncertainty.

The probability of collision is the integral of that Gaussian over the
hard-body disk (radius r_HBR) centred at the origin, when the *expected*
miss vector is (d, 0):

    Pc = (1 / (√(2π) σ_c)) *
         ∫_{-r}^{r} exp(−y²/(2σ_c²)) *
             [Φ((√(r²−y²) − d) / σ_r) − Φ((−√(r²−y²) − d) / σ_r)] dy

where Φ is the standard-normal CDF.  The inner integral over x has been
evaluated analytically; only a 1D numerical integral over y remains.

Defaults (combined 1-sigma for both objects combined)
------------------------------------------------------
  σ_r   = 1.0 km  (radial)
  σ_c   = 5.0 km  (cross-track / along-track)
  r_HBR = 0.01 km (10 m hard-body radius)

Input
-----
tca_result : dict returned by tca.find_tca, containing at minimum:
    miss_distance_km       : float
    relative_velocity_km_s : float

data_age_minutes : float  (age of the TLE data at the time of assessment)

Output
------
A copy of tca_result extended with:
    collision_probability  : float  (0 – 1)
    pc_method              : str    ('chan_alfano_2d')
    confidence             : str    ('nominal' | 'degraded' | 'low')
"""

from __future__ import annotations

import math
from typing import Optional

from scipy import integrate
from scipy.special import erf

# ── Default uncertainty model ─────────────────────────────────────────────────
SIGMA_RADIAL_KM:     float = 1.0     # combined 1-sigma, radial direction
SIGMA_CROSSTRACK_KM: float = 5.0     # combined 1-sigma, cross-track/along-track
HARD_BODY_RADIUS_KM: float = 0.01    # 10 m combined hard-body radius

# ── Confidence thresholds (data age in minutes) ───────────────────────────────
AGE_NOMINAL_MIN:  float = 60.0
AGE_DEGRADED_MIN: float = 360.0


def _phi(x: float) -> float:
    """Standard normal CDF evaluated at x."""
    return 0.5 * (1.0 + erf(x / math.sqrt(2.0)))


def _pc_integrand(
    y: float,
    d: float,
    sigma_r: float,
    sigma_c: float,
    r_hbr: float,
) -> float:
    """
    Single-variable integrand after analytically resolving the x-integral.

    Axis convention (standard for LEO conjunctions):
      x-axis — cross-track / along-track direction, uncertainty σ_c (larger).
               The scalar miss distance d is placed along this axis because
               conjunction miss vectors are dominated by the large-uncertainty
               direction in the conjunction plane.
      y-axis — radial direction, uncertainty σ_r (smaller); integrated over.

    Integral form:
      ∫_{-√(r²−y²)}^{√(r²−y²)} (1/(2π σ_c σ_r)) exp(−(x−d)²/(2σ_c²)) dx
          × exp(−y²/(2σ_r²))
      = (1/(√(2π) σ_r)) exp(−y²/(2σ_r²))
          × [Φ((√(r²−y²)−d)/σ_c) − Φ((−√(r²−y²)−d)/σ_c)]
    """
    y_sq = y * y
    r_sq = r_hbr * r_hbr
    if y_sq >= r_sq:
        return 0.0
    half_chord = math.sqrt(r_sq - y_sq)
    # y-axis uses sigma_r (radial, smaller)
    gauss_y = math.exp(-0.5 * (y / sigma_r) ** 2) / (math.sqrt(2.0 * math.pi) * sigma_r)
    # x-axis uses sigma_c (cross-track, larger); miss distance d lies along x
    p_x = _phi((half_chord - d) / sigma_c) - _phi((-half_chord - d) / sigma_c)
    return gauss_y * p_x


def _confidence(data_age_minutes: float) -> str:
    if data_age_minutes < AGE_NOMINAL_MIN:
        return "nominal"
    if data_age_minutes < AGE_DEGRADED_MIN:
        return "degraded"
    return "low"


def compute_probability(
    tca_result: dict,
    data_age_minutes: float = 0.0,
    sigma_radial_km: float = SIGMA_RADIAL_KM,
    sigma_crosstrack_km: float = SIGMA_CROSSTRACK_KM,
    hard_body_radius_km: float = HARD_BODY_RADIUS_KM,
) -> Optional[dict]:
    """
    Augment a TCA result dict with collision probability fields.

    Args:
        tca_result:          Output dict from tca.find_tca.
        data_age_minutes:    Age of the TLE data used.
        sigma_radial_km:     Combined 1-sigma radial uncertainty (km).
        sigma_crosstrack_km: Combined 1-sigma cross-track uncertainty (km).
        hard_body_radius_km: Combined hard-body radius (km).

    Returns:
        New dict = tca_result + {collision_probability, pc_method, confidence},
        or None if tca_result is None.
    """
    if tca_result is None:
        return None

    d = float(tca_result["miss_distance_km"])

    pc, _ = integrate.quad(
        _pc_integrand,
        -hard_body_radius_km,
        hard_body_radius_km,
        args=(d, sigma_radial_km, sigma_crosstrack_km, hard_body_radius_km),
        limit=100,
        epsabs=1e-15,
        epsrel=1e-10,
    )

    # Clamp to [0, 1] — numerical integration can produce tiny negatives
    pc = max(0.0, min(1.0, pc))

    return {
        **tca_result,
        "collision_probability": pc,
        "pc_method":             "chan_alfano_2d",
        "confidence":            _confidence(data_age_minutes),
    }
