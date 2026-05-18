# =============================================================================
# tcu.py — Haake ASM TCU RS232 Communication
# =============================================================================
# Handles all serial communication with the Haake TCU Controller.
# Commands and response formats from Haake ASM TCU manual pages 24-25.
#
# RS232 settings: 2400 baud, 8N1, no handshake
# All commands terminated with <CR>
# All responses terminated with $<CR><LF>
# =============================================================================

import serial
import time
from settings_manager import settings
from config import TCU_BYTESIZE, TCU_PARITY, TCU_STOPBITS, TCU_TIMEOUT

_SETPOINT_MIN = 17.0
_SETPOINT_MAX = 27.0
_FILL_TIMEOUT = 300    # seconds — 5 min max for AFV sequence


class TCU:
    """
    Manages RS232 communication with the Haake ASM TCU Controller.

    Usage:
        tcu = TCU()
        tcu.connect()
        temp = tcu.get_inlet_temp()
        tcu.start()
        tcu.disconnect()
    """

    def __init__(self):
        self.ser       = None
        self.connected = False

    def connect(self):
        """Open RS232 connection. Returns True on success."""
        port = settings.get('tcu_port')
        baud = settings.get('tcu_baud')
        if not port:
            print("TCU: tcu_port not configured")
            return False
        try:
            self.ser = serial.Serial(
                port     = port,
                baudrate = baud,
                bytesize = TCU_BYTESIZE,
                parity   = TCU_PARITY,
                stopbits = TCU_STOPBITS,
                timeout  = TCU_TIMEOUT,
            )
            self.connected = True
            print(f"TCU: connected on {port} at {baud} baud")
            return True
        except serial.SerialException as e:
            self.connected = False
            print(f"TCU: connection failed — {e}")
            return False

    def disconnect(self):
        """Close RS232 connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected and self.ser is not None and self.ser.is_open

    # ── Private ───────────────────────────────────────────────────────────────

    def _send(self, cmd: str) -> str:
        """Send command and return raw response. Returns empty string on failure."""
        if not self.is_connected():
            return ''
        try:
            self.ser.reset_input_buffer()
            self.ser.write((cmd + '\r').encode('ascii'))
            time.sleep(0.3)
            return self.ser.readline().decode('ascii').strip()
        except Exception as e:
            print(f"TCU: RS232 error on '{cmd}': {e}")
            return ''

    # ── Query commands ────────────────────────────────────────────────────────

    def get_inlet_temp(self):
        """M → XX.XX C$ — inlet fluid temperature in °C. Returns float or None."""
        raw = self._send('M')
        try:
            return float(raw.split()[0])
        except (ValueError, IndexError):
            return None

    def get_flow_rate(self):
        """D → XX.X l/min$ — flow rate in ℓ/min. Returns float or None."""
        raw = self._send('D')
        try:
            return float(raw.split()[0].replace('$', ''))
        except (ValueError, IndexError):
            return None

    def get_setpoint(self):
        """SOLL → XX.XX C$ — current temperature setpoint in °C. Returns float or None."""
        raw = self._send('SOLL')
        try:
            cleaned = raw.replace('$', '').replace('C', '').strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def get_heating_pct(self):
        """
        r YH → YH+XXX.XX$  — heating correcting variable (%)
        r YK → YK+XXX.XX YY.YY$  — cooling correcting variable (%)
        Only valid when TCU is actively running.
        Returns (heating_pct, cooling_pct) where both are floats 0-100.
        Returns (None, None) on failure.
        """
        heating_pct = self._read_yh()
        cooling_pct = self._read_yk()
        return heating_pct, cooling_pct

    def _read_yh(self):
        """Send 'r YH' and parse YH+XXX.XX$ → float heating %."""
        raw = self._send('r YH')
        if not raw or raw.strip() in ('F', '?', ''):
            return None
        try:
            # Format: YH+013.40$ or YH-000.00$
            cleaned = raw.replace('$', '').strip()
            if cleaned.startswith('YH'):
                val = float(cleaned[2:].strip())
                return max(0.0, min(100.0, val))
            return None
        except (ValueError, IndexError):
            return None

    def _read_yk(self):
        """Send 'r YK' and parse YK+XXX.XX YY.YY$ → float cooling %."""
        raw = self._send('r YK')
        if not raw or raw.strip() in ('F', '?', ''):
            return None
        try:
            # Format: YK+012.08 15.55$ — take second value as cooling %
            cleaned = raw.replace('$', '').strip()
            if cleaned.startswith('YK'):
                parts = cleaned[2:].strip().split()
                if len(parts) >= 2:
                    val = float(parts[1])
                    return max(0.0, min(100.0, val))
                elif len(parts) == 1:
                    val = float(parts[0])
                    return max(0.0, min(100.0, val))
            return None
        except (ValueError, IndexError):
            return None

    def get_status_bytes(self):
        """BS → XXXXXX$ — three status bytes as integers (b1, b2, b3).
        Normal healthy running state: 0x400400."""
        raw = self._send('BS')
        try:
            hex_str = raw.replace('$', '').strip()
            b1 = int(hex_str[0:2], 16)
            b2 = int(hex_str[2:4], 16)
            b3 = int(hex_str[4:6], 16)
            return b1, b2, b3
        except (ValueError, IndexError):
            return None, None, None

    # ── Control commands ──────────────────────────────────────────────────────

    def start(self):
        """START — start temperature control."""
        self._send('START')

    def stop(self):
        """STOP — stop temperature control."""
        self._send('STOP')

    def release_alarm(self):
        """ER — release safety circuit after fault is cleared."""
        self._send('ER')

    def close_valve(self):
        """CVE — close valve."""
        self._send('CVE')

    def precond(self):
        """VT — pretemperature control only (no fill)."""
        self._send('VT')

    def set_setpoint(self, temp: float):
        """SOLL XX.XX — set target temperature (17.00–27.00°C only)."""
        if not isinstance(temp, float) and not isinstance(temp, int):
            print(f"TCU.set_setpoint: expected float, got {type(temp)}")
            return
        if not (_SETPOINT_MIN <= temp <= _SETPOINT_MAX):
            print(f"TCU.set_setpoint: {temp}°C out of range [{_SETPOINT_MIN}, {_SETPOINT_MAX}]")
            return
        self._send(f'SOLL  {temp:.2f}')

    def fill(self, on_status=None):
        """AFV — fill system and pretemperature control to within ±0.2°C of setpoint.
        Blocking — can take several minutes. Calls on_status(line) with each
        status line received from TCU during the fill sequence."""
        if not self.is_connected():
            print("TCU.fill: not connected")
            return
        try:
            self.ser.reset_input_buffer()
            self.ser.write(b'AFV\r')
            old_timeout    = self.ser.timeout
            self.ser.timeout = _FILL_TIMEOUT
            MAX_LINES      = 1000   # upper bound — prevents infinite loop
            for _ in range(MAX_LINES):
                line = self.ser.readline().decode('ascii', errors='ignore').strip()
                if not line:
                    continue
                if on_status is not None:
                    on_status(line)
                else:
                    print(f"TCU AFV: {line}")
                if line.endswith('$'):
                    print("TCU.fill: AFV complete")
                    break
            self.ser.timeout = old_timeout
        except Exception as e:
            print(f"TCU.fill: error — {e}")
