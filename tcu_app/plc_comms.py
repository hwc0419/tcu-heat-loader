# =============================================================================
# plc_comms.py — FP0-C14CRS MEWTOCOL Communication
# =============================================================================
# Sends K value (0-4000) to PLC DT100 via MEWTOCOL over AFC8503 cable.
# PLC ST program reads DT100 and writes it directly to WY4 (W5 setpoint).
# Serial: /dev/plc, 9600 baud, 8O1 (odd parity — MEWTOCOL requirement).
# =============================================================================

import serial
import threading
import time
from settings_manager import settings

_MAX_RETRIES   = 3
_RETRY_DELAY_S = 0.1
_MEWTOCOL_BAUD = 19200
_MEWTOCOL_UNIT = '01'          # PLC unit number — default 01
_DT_REGISTER   = 100           # DT100 — W5 setpoint written by RPi
_K_MAX         = 4000
_K_MIN         = 0


def _checksum(body: str) -> str:
    """
    Compute MEWTOCOL BCC for FP0.
    XOR of characters from unit number to last text char (excluding % prefix).
    body should NOT include the % prefix.
    """
    result = 0
    for c in body:
        result ^= ord(c)
    return f'{result:02X}'


def _build_write_cmd(k_value: int) -> bytes:
    """
    Build MEWTOCOL WD (Write Data Register) command for DT100.
    Format: %<unit>#WD<start_addr><end_addr><value><BCC>\r
    DT address is 4-digit decimal: DT100 = '0100'.
    Start and end address are the same for single-word write.
    Value is 4-digit hex. BCC excludes % prefix.
    """
    addr  = f'{_DT_REGISTER:04d}'   # decimal: DT100 → '0100'
    value = f'{k_value:04X}'
    body  = f'{_MEWTOCOL_UNIT}#WD{addr}{addr}{value}'
    bcc   = _checksum(body)
    return f'%{body}{bcc}\r'.encode('ascii')


def _parse_response(resp: bytes) -> bool:
    """
    Parse MEWTOCOL write response.
    Success: %<unit>$WD<BCC>\r
    Error:   %<unit>!<code><BCC>\r
    """
    if not resp:
        return False
    text = resp.decode('ascii', errors='ignore').strip()
    if '$WD' in text:
        return True
    if '!' in text:
        print(f'PLC: MEWTOCOL error response: {text}')
        return False
    return False


class PlcComms:
    """
    MEWTOCOL interface to Panasonic FP0-C14CRS PLC.

    Usage:
        plc = PlcComms()
        plc.connect()
        plc.set_k(1325)    # 500W
        plc.set_k(0)       # heater off
        plc.disconnect()
    """

    def __init__(self):
        self._serial    = None
        self._lock      = threading.Lock()
        self._connected = False

    def connect(self) -> bool:
        """Open serial connection to PLC. Returns True on success."""
        port = settings.get('plc_port')
        if not port:
            print('PLC: plc_port not configured')
            return False
        try:
            self._serial = serial.Serial(
                port     = port,
                baudrate = _MEWTOCOL_BAUD,
                bytesize = 8,
                parity   = serial.PARITY_ODD,
                stopbits = 1,
                timeout  = 1.0
            )
            self._connected = True
            print(f'PLC: connected on {port}')
            return True
        except Exception as e:
            print(f'PLC: connect failed — {e}')
            self._connected = False
            return False

    def disconnect(self):
        """Close serial port."""
        with self._lock:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.close()
                except Exception:
                    pass
            self._serial    = None
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._serial is not None

    def set_k(self, k_value: int) -> bool:
        """
        Write K value (0-4000) to PLC DT100.
        Returns True on success.
        """
        if not isinstance(k_value, int):
            print(f'PLC.set_k: expected int, got {type(k_value)}')
            return False
        if not _K_MIN <= k_value <= _K_MAX:
            print(f'PLC.set_k: {k_value} out of range [{_K_MIN}, {_K_MAX}]')
            return False
        cmd = _build_write_cmd(k_value)
        for attempt in range(_MAX_RETRIES):
            try:
                with self._lock:
                    self._serial.reset_input_buffer()
                    self._serial.write(cmd)
                    resp = self._serial.read_until(b'\r')
                if _parse_response(resp):
                    return True
                print(f'PLC: set_k attempt {attempt + 1} bad response: {resp}')
            except Exception as e:
                print(f'PLC: set_k attempt {attempt + 1} failed — {e}')
            time.sleep(_RETRY_DELAY_S)
        return False

    def emergency_off(self) -> bool:
        """Write K0 to PLC immediately — W5 output goes to zero."""
        return self.set_k(0)

    def read_dt(self, addr: int):
        """
        Read one DT register. Returns int value or None on failure.
        Used for diagnostics and verifying DT100 setpoint.
        """
        if not self.is_connected():
            return None
        body = f'{_MEWTOCOL_UNIT}#RD{addr:04d}{addr:04d}'
        bcc  = _checksum(body)
        cmd  = f'%{body}{bcc}\r'.encode('ascii')
        print(f'PLC: sending: {repr(cmd)}')
        try:
            with self._lock:
                self._serial.reset_input_buffer()
                self._serial.write(cmd)
                time.sleep(0.1)
                raw = self._serial.read(32)
            print(f'PLC: read_dt({addr}) raw: {repr(raw)}')
            text = raw.decode('ascii', errors='ignore').strip()
            if '$RD' in text:
                idx = text.index('$RD') + 3
                return int(text[idx:idx+4], 16)
            if '!' in text:
                print(f'PLC: read_dt error response: {text}')
            return None
        except Exception as e:
            print(f'PLC: read_dt failed — {e}')
            return None
