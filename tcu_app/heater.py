# =============================================================================
# heater.py — Heater Control via PLC MEWTOCOL
# =============================================================================
# Converts watts setpoint to K constant via empirical sweep lookup table,
# then writes K value to PLC DT100 via MEWTOCOL (plc_comms.py).
# PLC ST program passes DT100 directly to WY4 → W5 SCR power regulator.
# Sweep data: 71 points, K500–K4000, step K50 (20/05/2026).
# =============================================================================

import bisect
from plc_comms import PlcComms
from config import HEATER_MAX_WATTS, PLC_K_MIN, PLC_K_MAX

# Empirical K→watts lookup table from W5 sweep (20/05/2026).
# Format: (K_value, watts). Monotonically increasing in both columns.
# K values below 500 produce ~0W (BIAS threshold) — contactor handles true 0W.
_SWEEP_TABLE = [
    (500, 58.3),   (550, 71.3),   (600, 86.3),   (650, 102.7),
    (700, 121.2),  (750, 140.8),  (800, 161.3),  (850, 184.9),
    (900, 209.8),  (950, 237.2),  (1000, 267.2), (1050, 295.8),
    (1100, 329.4), (1150, 365.2), (1200, 400.0), (1250, 441.0),
    (1300, 478.9), (1350, 520.5), (1400, 564.2), (1450, 610.4),
    (1500, 661.5), (1550, 707.6), (1600, 756.8), (1650, 810.2),
    (1700, 861.2), (1750, 917.6), (1800, 966.0), (1850, 1017.5),
    (1900, 1068.4),(1950, 1120.5),(2000, 1172.1),(2050, 1213.1),
    (2100, 1263.4),(2150, 1309.3),(2200, 1356.0),(2250, 1401.5),
    (2300, 1442.1),(2350, 1485.4),(2400, 1527.2),(2450, 1564.4),
    (2500, 1601.4),(2550, 1637.2),(2600, 1672.0),(2650, 1700.4),
    (2700, 1731.9),(2750, 1762.2),(2800, 1785.8),(2850, 1812.7),
    (2900, 1828.8),(2950, 1845.8),(3000, 1857.4),(3050, 1879.9),
    (3100, 1895.5),(3150, 1908.0),(3200, 1918.2),(3250, 1925.9),
    (3300, 1935.4),(3350, 1941.7),(3400, 1947.1),(3450, 1949.4),
    (3500, 1951.7),(3550, 1954.9),(3600, 1954.0),(3650, 1957.2),
    (3700, 1959.5),(3750, 1958.6),(3800, 1958.6),(3850, 1958.6),
    (3900, 1958.6),(3950, 1958.6),(4000, 1958.6),
]

_K_LIST    = [row[0] for row in _SWEEP_TABLE]
_WATTS_LIST = [row[1] for row in _SWEEP_TABLE]
_WATTS_MIN  = _WATTS_LIST[0]   # 58.3W — minimum controllable output
_WATTS_MAX  = _WATTS_LIST[-1]  # 1958.6W — saturation point


def watts_to_k(watts: float) -> int:
    """
    Convert target watts to nearest K constant via linear interpolation
    of empirical sweep table. Returns 0 if watts < minimum threshold.
    Clamps to K4000 if watts >= saturation point.
    """
    if not isinstance(watts, (int, float)):
        return 0
    if watts <= 0:
        return 0
    if watts <= _WATTS_MIN:
        return _K_LIST[0]
    if watts >= _WATTS_MAX:
        return _K_LIST[-1]
    idx = bisect.bisect_left(_WATTS_LIST, watts)
    w_lo, w_hi = _WATTS_LIST[idx - 1], _WATTS_LIST[idx]
    k_lo, k_hi = _K_LIST[idx - 1],     _K_LIST[idx]
    frac = (watts - w_lo) / (w_hi - w_lo)
    return round(k_lo + frac * (k_hi - k_lo))


def k_to_watts(k: int) -> float:
    """
    Convert K constant to expected watts via linear interpolation.
    Returns 0.0 if k < K500 (below BIAS threshold).
    """
    if not isinstance(k, int):
        return 0.0
    if k <= 0:
        return 0.0
    if k <= _K_LIST[0]:
        return _WATTS_LIST[0]
    if k >= _K_LIST[-1]:
        return _WATTS_LIST[-1]
    idx = bisect.bisect_left(_K_LIST, k)
    k_lo, k_hi = _K_LIST[idx - 1], _K_LIST[idx]
    w_lo, w_hi = _WATTS_LIST[idx - 1], _WATTS_LIST[idx]
    frac = (k - k_lo) / (k_hi - k_lo)
    return w_lo + frac * (w_hi - w_lo)


class Heater:
    """
    Heater control via PLC MEWTOCOL.
    Converts watts to K constant via sweep lookup table,
    writes K to PLC DT100 via plc_comms.PlcComms.

    Usage:
        h = Heater()
        h.connect()
        h.set_watts(500)
        h.set_watts(0)     # off — PLC contactor stays on, W5 output = 0
        h.disconnect()
    """

    def __init__(self):
        self._plc       = PlcComms()
        self._current_k = 0

    def connect(self) -> bool:
        """Open PLC serial connection. Returns True on success."""
        return self._plc.connect()

    def disconnect(self):
        """Close PLC serial connection."""
        self._plc.disconnect()

    def is_connected(self) -> bool:
        return self._plc.is_connected()

    def set_watts(self, watts: int) -> bool:
        """
        Set heater power in watts. Converts to K via sweep table.
        Returns True on success. Rejects if watts > HEATER_MAX_WATTS.
        """
        if not isinstance(watts, int):
            print(f'Heater.set_watts: expected int, got {type(watts)}')
            return False
        if watts < 0 or watts > HEATER_MAX_WATTS:
            print(f'Heater.set_watts: {watts}W out of range [0, {HEATER_MAX_WATTS}]')
            return False
        k = watts_to_k(watts)
        ok = self._plc.set_k(k)
        if ok:
            self._current_k = k
        return ok

    def set_k(self, k: int) -> bool:
        """
        Write K constant directly to PLC DT100 (bypasses watts_to_k).
        Used by stepped heat load test, which precomputes K per step
        from the empirical sweep table.
        """
        if not isinstance(k, int):
            print(f'Heater.set_k: expected int, got {type(k)}')
            return False
        if not PLC_K_MIN <= k <= PLC_K_MAX:
            print(f'Heater.set_k: {k} out of range [{PLC_K_MIN}, {PLC_K_MAX}]')
            return False
        ok = self._plc.set_k(k)
        if ok:
            self._current_k = k
        return ok

    def emergency_off(self) -> bool:
        """Write K0 to PLC immediately."""
        ok = self._plc.emergency_off()
        if ok:
            self._current_k = 0
        return ok

    @property
    def current_k(self) -> int:
        """Last K value written to PLC."""
        return self._current_k

    @property
    def watts_min(self) -> float:
        """Minimum controllable output from sweep data."""
        return _WATTS_MIN

    @property
    def watts_max(self) -> float:
        """Maximum output at saturation from sweep data."""
        return _WATTS_MAX
