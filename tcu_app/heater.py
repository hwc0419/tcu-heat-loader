# =============================================================================
# heater.py — Heater Control via PLC MEWTOCOL
# =============================================================================
# Converts watts setpoint to K constant via the empirical W5 model
# (3-parameter phase-angle fit, RMSE = 4.86W across 71-point sweep —
# see test_logic.py), then writes K value to PLC DT100 via MEWTOCOL.
# PLC ST program passes DT100 directly to WY4 → W5 SCR power regulator.
# =============================================================================

from plc_comms import PlcComms
from config import HEATER_MAX_WATTS, PLC_K_MIN, PLC_K_MAX
from test_logic import watts_to_k, k_to_watts

_WATTS_MIN = k_to_watts(PLC_K_MIN if PLC_K_MIN > 0 else 500)  # ~58.3W
_WATTS_MAX = k_to_watts(4000)                                  # ~1959.5W saturation


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
        Set heater power in watts. Converts to K via empirical W5 model.
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
