# =============================================================================
# heater.py — Heater Modbus RTU Communication
# =============================================================================
# Controls the vendor thyristor heater controller via Modbus RTU over
# UART3 + MAX485 (RPi) or USB RS485 adapter (Windows testing).
# All register addresses are placeholder until vendor confirms register map.
# =============================================================================

import minimalmodbus
import threading
import time
from settings_manager import settings
from config import HEATER_MAX_WATTS

_MAX_RETRIES   = 3
_RETRY_DELAY_S = 0.1


class Heater:
    """
    Modbus RTU interface to thyristor heater controller.

    Usage:
        h = Heater()
        h.connect()
        h.set_watts(5000)
        w = h.read_actual_watts()
        h.disconnect()
    """

    def __init__(self):
        self._inst      = None
        self._lock      = threading.Lock()
        self._connected = False

    def connect(self) -> bool:
        """Open Modbus connection. Returns True on success."""
        port     = settings.get('heater_port')
        baud     = settings.get('heater_baud')
        slave_id = settings.get('heater_slave_id')
        if not port:
            print("Heater: heater_port not configured")
            return False
        try:
            inst = minimalmodbus.Instrument(port, slave_id)
            inst.serial.baudrate = baud
            inst.serial.timeout  = 1.0
            inst.mode            = minimalmodbus.MODE_RTU
            self._inst      = inst
            self._connected = True
            print(f"Heater: connected on {port} baud={baud} slave={slave_id}")
            return True
        except Exception as e:
            print(f"Heater: connect failed — {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Close Modbus serial port."""
        with self._lock:
            if self._inst and self._inst.serial.is_open:
                try:
                    self._inst.serial.close()
                except Exception:
                    pass
            self._inst      = None
            self._connected = False

    def is_connected(self) -> bool:
        """Return True if port is open."""
        return self._connected and self._inst is not None

    def set_watts(self, watts: int) -> bool:
        """
        Send power setpoint in watts via Modbus.
        Returns True on success. Rejects if watts > HEATER_MAX_WATTS.
        """
        if not isinstance(watts, int):
            print(f"Heater.set_watts: expected int, got {type(watts)}")
            return False
        if watts < 0 or watts > HEATER_MAX_WATTS:
            print(f"Heater.set_watts: {watts}W out of range [0, {HEATER_MAX_WATTS}]")
            return False
        reg = settings.get('heater_reg_setpoint')
        return self._write_register(reg, watts)

    def read_actual_watts(self):
        """Read actual delivered power from controller.
        Returns int watts or None on failure."""
        reg = settings.get('heater_reg_actual')
        return self._read_register(reg)

    def emergency_off(self) -> bool:
        """Set heater to 0W immediately. Returns True on success."""
        reg = settings.get('heater_reg_setpoint')
        return self._write_register(reg, 0)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _write_register(self, reg: int, value: int) -> bool:
        """Write integer value to Modbus register with retries."""
        if not self.is_connected():
            print("Heater: not connected")
            return False
        if not isinstance(reg, int) or not isinstance(value, int):
            print(f"Heater._write_register: invalid args reg={reg} value={value}")
            return False
        for attempt in range(_MAX_RETRIES):
            try:
                with self._lock:
                    self._inst.write_register(reg, value, functioncode=6)
                return True
            except Exception as e:
                print(f"Heater: write reg {reg:#04x} attempt {attempt+1} failed — {e}")
                time.sleep(_RETRY_DELAY_S)
        return False

    def _read_register(self, reg: int):
        """Read integer value from Modbus register with retries.
        Returns int or None on failure."""
        if not self.is_connected():
            return None
        if not isinstance(reg, int):
            print(f"Heater._read_register: invalid reg={reg}")
            return None
        for attempt in range(_MAX_RETRIES):
            try:
                with self._lock:
                    value = self._inst.read_register(reg, functioncode=3)
                return int(value)
            except Exception as e:
                print(f"Heater: read reg {reg:#04x} attempt {attempt+1} failed — {e}")
                time.sleep(_RETRY_DELAY_S)
        return None
