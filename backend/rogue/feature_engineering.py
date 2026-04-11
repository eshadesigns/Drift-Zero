import numpy as np


def normalize_tle_row(row: dict) -> dict:
    """
    Maps Space-Track uppercase column names to lowercase keys
    expected by extract_delta_features. Handles both already-typed
    values (from a pandas row) and raw strings (from the REST API).
    """
    return {
        'epoch':        row['EPOCH'],
        'mean_motion':  float(row['MEAN_MOTION']),
        'eccentricity': float(row['ECCENTRICITY']),
        'inclination':  float(row['INCLINATION']),
        'raan':         float(row['RA_OF_ASC_NODE']),
        'bstar':        float(row['BSTAR']),
    }


def extract_delta_features(tle_prev: dict, tle_curr: dict,
                            solar_f107: float, kp: float) -> dict:
    """
    Compute delta features between two consecutive TLEs.
    TLE dicts contain: epoch, mean_motion, eccentricity,
                       inclination, raan, bstar
    """
    time_gap_hours = (tle_curr['epoch'] - tle_prev['epoch']).total_seconds() / 3600

    delta_mm    = tle_curr['mean_motion']  - tle_prev['mean_motion']
    delta_ecc   = tle_curr['eccentricity'] - tle_prev['eccentricity']
    delta_inc   = tle_curr['inclination']  - tle_prev['inclination']
    delta_bstar = tle_curr['bstar']        - tle_prev['bstar']

    curr_raan = tle_curr['raan']
    prev_raan = tle_prev['raan']
    delta_raan = (curr_raan - prev_raan + 180) % 360 - 180

    # Rough delta-v proxy from mean motion change
    # dv ≈ 0.5 * v_orb * (delta_mm / mm) for small changes
    v_orb_km_s = 7.784 * (tle_prev['mean_motion'] / 15.0) ** (1/3)  # approx LEO
    delta_v_proxy = abs(delta_mm / tle_prev['mean_motion']) * v_orb_km_s * 1000  # m/s

    return {
        'epoch': tle_curr['epoch'],
        'time_gap_hours': time_gap_hours,
        'delta_mean_motion': delta_mm,
        'delta_eccentricity': delta_ecc,
        'delta_inclination': delta_inc,
        'delta_raan': delta_raan,
        'delta_bstar': delta_bstar,
        'delta_v_proxy': delta_v_proxy,
        'solar_f107': solar_f107,
        'kp_index': kp,
    }