# =============================================================================
# test_logic.py — Stepped Heat Load Test Logic
# =============================================================================
# Contains:
#   - BS status byte parsing         (Haake manual page 33-34)
#   - K constant interpolation       from 71-point W5 sweep table
#   - Stepped test averaging         last 3 min, exclude outliers
#   - Linear fit + extrapolation     cooling_pct = m*W + b → 28604W
#   - Pass/fail evaluation
# =============================================================================

import numpy as np
from config import (
    STEPPED_TEST_NUM_STEPS,
    STEPPED_TEST_STEP_WATTS,
    STEPPED_TEST_AVG_WINDOW_S,
    STEPPED_TEST_SETPOINT_TOL,
    STEPPED_TEST_TARGET_WATTS,
    FLOW_FAIL_GRACE_SAMPLES,
)
from settings_manager import settings

# =============================================================================
# W5 71-point sweep lookup table  (K value → measured watts)
# Source: W5_Sweep_Data.xlsx — sheet "W5 Sweep Data"
# =============================================================================
_K_TABLE = [
    (500,  58.300),  (550,  71.340),  (600,  86.310),  (650,  102.680),
    (700,  121.180), (750,  140.818), (800,  161.308),  (850,  184.864),
    (900,  209.760), (950,  237.160), (1000, 267.240),  (1050, 295.792),
    (1100, 329.448), (1150, 365.182), (1200, 399.960),  (1250, 441.000),
    (1300, 478.935), (1350, 520.520), (1400, 564.200),  (1450, 610.450),
    (1500, 661.500), (1550, 707.610), (1600, 756.840),  (1650, 810.160),
    (1700, 861.184), (1750, 917.568), (1800, 966.002),  (1850, 1017.456),
    (1900, 1068.360),(1950, 1120.480),(2000, 1172.056), (2050, 1213.125),
    (2100, 1263.360),(2150, 1309.308),(2200, 1356.040), (2250, 1401.498),
    (2300, 1442.133),(2350, 1485.424),(2400, 1527.186), (2450, 1564.434),
    (2500, 1601.360),(2550, 1637.250),(2600, 1672.000), (2650, 1700.352),
    (2700, 1731.933),(2750, 1762.212),(2800, 1785.836), (2850, 1812.663),
    (2900, 1828.814),(2950, 1845.836),(3000, 1857.385), (3050, 1879.914),
    (3100, 1895.484),(3150, 1907.976),(3200, 1918.200), (3250, 1925.937),
    (3300, 1935.360),(3350, 1941.652),(3400, 1947.108), (3450, 1949.415),
    (3500, 1951.722),(3550, 1954.876),(3600, 1954.029), (3650, 1957.184),
    (3700, 1959.492),(3750, 1958.643),(3800, 1958.643), (3850, 1958.643),
    (3900, 1958.643),(3950, 1958.643),(4000, 1958.643),
]
_K_VALS   = [row[0] for row in _K_TABLE]
_W_VALS   = [row[1] for row in _K_TABLE]

# =============================================================================
# K constant interpolation
# =============================================================================

def watts_to_k(target_watts: float) -> int:
    """
    Interpolate K constant from 71-point sweep table.
    Returns K as int (0-4000). Returns 0 for target <= 0.
    Returns K_MAX (4000) for target above table maximum.
    Fixed loop bound: at most len(_K_TABLE) = 71 iterations.
    """
    if target_watts <= 0:
        return 0
    if target_watts >= _W_VALS[-1]:
        return _K_VALS[-1]
    for i in range(len(_K_TABLE) - 1):   # bound: 70 iterations
        if _W_VALS[i] <= target_watts <= _W_VALS[i + 1]:
            frac = (target_watts - _W_VALS[i]) / (_W_VALS[i + 1] - _W_VALS[i])
            return int(round(_K_VALS[i] + frac * (_K_VALS[i + 1] - _K_VALS[i])))
    return _K_VALS[-1]


def build_step_table() -> list:
    """
    Build list of (step_index, target_watts, k_constant).
    Step 0 = 0W, steps increment by stepped_step_size_w up to stepped_max_watts.
    Fixed bound: at most MAX_STEPS = 32400 // 1 iterations (9h / 1s min step).
    In practice bounded by max_watts / step_size_w + 1.
    """
    max_watts = settings.get('stepped_max_watts')
    step_size = settings.get('stepped_step_size_w')
    if not isinstance(step_size, int) or step_size < 1:
        step_size = 100
    MAX_STEPS = 540   # hard upper bound: 9h / 1min minimum step = 540 steps
    steps     = []
    i         = 0
    w         = 0
    while w <= max_watts and i <= MAX_STEPS:   # bound: MAX_STEPS iterations
        steps.append((i, w, watts_to_k(w)))
        i += 1
        w  = i * step_size
    return steps


# =============================================================================
# Step averaging
# =============================================================================

def compute_step_avg(samples: list, setpoint: float) -> float | None:
    """
    Average cooling_pct over last STEPPED_TEST_AVG_WINDOW_S seconds,
    excluding samples outside setpoint ± STEPPED_TEST_SETPOINT_TOL.
    Returns None if no valid samples remain.
    Fixed bound: at most len(samples) iterations.
    """
    if not samples:
        return None
    avg_window = STEPPED_TEST_AVG_WINDOW_S
    t_end      = samples[-1][0]
    t_start    = t_end - avg_window
    valid      = []
    for ts, cooling, temp in samples:   # bound: caller limits buffer to step window
        if ts < t_start:
            continue
        if temp is None or cooling is None:
            continue
        if abs(temp - setpoint) > STEPPED_TEST_SETPOINT_TOL:
            continue
        valid.append(cooling)
    if not valid:
        return None
    return float(np.mean(valid))


# =============================================================================
# Linear fit + extrapolation
# =============================================================================

def fit_and_extrapolate(results: list) -> dict:
    """
    Fit linear model cooling_pct = m * watts + b from completed step results.
    results: list of (watts, avg_cooling_pct) — NaN entries excluded.

    Returns dict:
        slope        : float
        intercept    : float
        r_squared    : float
        extrap_pct   : float  — predicted cooling % at TARGET_WATTS
        passed       : bool   — True if extrap_pct < 100
        n_points     : int    — number of valid points used
    """
    valid = [(w, c) for w, c in results if c is not None]
    if len(valid) < 2:
        return {
            'slope': None, 'intercept': None, 'r_squared': None,
            'extrap_pct': None, 'passed': None, 'n_points': len(valid),
        }
    watts_arr   = np.array([v[0] for v in valid], dtype=float)
    cooling_arr = np.array([v[1] for v in valid], dtype=float)
    m, b        = np.polyfit(watts_arr, cooling_arr, 1)
    rmse        = float(np.sqrt(np.mean((cooling_arr - y_pred) ** 2)))
    ss_res      = float(np.sum((cooling_arr - y_pred) ** 2))
    ss_tot      = float(np.sum((cooling_arr - np.mean(cooling_arr)) ** 2))
    r2          = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    extrap      = float(m * STEPPED_TEST_TARGET_WATTS + b)
    return {
        'slope':       float(m),
        'intercept':   float(b),
        'r_squared':   r2,
        'rmse':        rmse,
        'extrap_pct':  extrap,
        'passed':      extrap < 100.0,
        'n_points':    len(valid),
    }


# =============================================================================
# BS status byte parsing
# =============================================================================

def parse_alarms(b1, b2, b3):
    """
    Parse three status bytes returned by BS command.
    Returns list of alarm strings, or ['No alarms'] if healthy.
    Normal operation: b1=0x40, b2=0x00, b3=0x00.
    """
    if b1 is None:
        return ['Cannot read TCU status']
    alarms = []
    if b1 & (1 << 5): alarms.append('Water level ASM not reached')
    if b1 & (1 << 4): alarms.append('Water level MIN not reached')
    if b1 & (1 << 3): alarms.append('Pump 2 operating temp exceeded')
    if b1 & (1 << 2): alarms.append('Pump 1 operating temp exceeded')
    if b1 & (1 << 1): alarms.append('Temperature exceeded 27C limit')
    if b1 & (1 << 0): alarms.append('Temperature below 17C limit')
    if b2 & (1 << 7): alarms.append('Unit auto shutdown')
    if b2 & (1 << 6): alarms.append('START/STOP commands blocked')
    if b2 & (1 << 5): alarms.append('Temperature out of 3-40C range')
    if b2 & (1 << 4): alarms.append('Temperature sensor fault')
    if b2 & (1 << 3): alarms.append('Calibration fault')
    if b2 & (1 << 1): alarms.append('Heating circuit fault')
    if b2 & (1 << 0): alarms.append('Operating pressure not reached')
    if b3 & (1 << 7): alarms.append('Supply voltage not present')
    if b3 & (1 << 4): alarms.append('Hardware fault: main contactor')
    if b3 & (1 << 3): alarms.append('Hardware fault: watchdog')
    if b3 & (1 << 2): alarms.append('Hardware fault: alarm triggering')
    if b3 & (1 << 1): alarms.append('Hardware fault: unlocking switch')
    if b3 & (1 << 0): alarms.append('Hardware fault: start test')
    return alarms if alarms else ['No alarms']


# =============================================================================
# BS status decode — human-readable log string
# =============================================================================

def decode_status(b1, b2, b3, inlet_temp=None, flow=None, setpoint=None):
    """Return a human-readable status string from BS bytes and live readings."""
    if b1 is None:
        return 'BS: no data'
    bs        = (b1 << 16) | ((b2 or 0) << 8) | (b3 or 0)
    alarms    = parse_alarms(b1, b2, b3)
    alarm_str = '; '.join(alarms)
    temp_str  = f'{inlet_temp:.2f}°C' if inlet_temp is not None else 'N/A'
    flow_str  = f'{flow:.2f} l/min'   if flow       is not None else 'N/A'
    sp_str    = f'{setpoint:.2f}°C'   if setpoint   is not None else 'N/A'
    return (
        f'BS={bs:#08x} | '
        f'Inlet={temp_str} SP={sp_str} Flow={flow_str} | '
        f'{alarm_str}'
    )


# =============================================================================
# Abnormal state check
# =============================================================================

def is_abnormal(b1, b2, b3, inlet_temp=None, setpoint=None, flow=None):
    """
    Return True if TCU is in an abnormal state requiring heater auto-off.
    Normal running state: BS = 0x400400.
    """
    if b1 is None:
        return True
    bs = (b1 << 16) | ((b2 or 0) << 8) | (b3 or 0)
    if bs != 0x400400:
        return True
    if parse_alarms(b1, b2, b3) != ['No alarms']:
        return True
    if flow is not None and flow < settings.get('min_flow_rate'):
        return True
    return False
