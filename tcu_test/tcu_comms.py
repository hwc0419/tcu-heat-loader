# =============================================================================
# tcu_comms.py — Haake ASM TCU RS232 Communication
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
from config import (
    TCU_PORT, TCU_BAUD, TCU_BYTESIZE,
    TCU_PARITY, TCU_STOPBITS, TCU_TIMEOUT
)


class TCUComms:
    """
    Manages RS232 communication with the Haake ASM TCU Controller.
    Use as context manager:
        with TCUComms() as tcu:
            temp = tcu.get_inlet_temp()
    """

    def __init__(self):
        self.ser = None
        self.connected = False

    def connect(self):
        """Open RS232 connection to TCU Controller."""
        try:
            self.ser = serial.Serial(
                port        = TCU_PORT,
                baudrate    = TCU_BAUD,
                bytesize    = TCU_BYTESIZE,
                parity      = TCU_PARITY,
                stopbits    = TCU_STOPBITS,
                timeout     = TCU_TIMEOUT
            )
            self.connected = True
            print(f"TCU connected on {TCU_PORT} at {TCU_BAUD} baud")
        except serial.SerialException as e:
            self.connected = False
            print(f"TCU connection failed: {e}")

    def disconnect(self):
        """Close RS232 connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def _send(self, cmd):
        """Send command and return raw response. Returns empty string on failure."""
        if not self.connected:
            return ''
        try:
            self.ser.reset_input_buffer()
            self.ser.write((cmd + '\r').encode('ascii'))
            time.sleep(0.3)
            return self.ser.readline().decode('ascii').strip()
        except Exception as e:
            print(f"RS232 error on command '{cmd}': {e}")
            return ''

    # -------------------------------------------------------------------------
    # Query commands (Haake manual page 24-25)
    # -------------------------------------------------------------------------

    def get_inlet_temp(self):
        """M<CR> → XX.XX C$ — inlet fluid temperature in °C (0-28°C, ±0.02°C)"""
        raw = self._send('M')
        try:
            return float(raw.split()[0])
        except (ValueError, IndexError):
            return None

    def get_flow_rate(self):
        """D<CR> → XX 1/min$ — flow rate in ℓ/min (0-60 ℓ/min)"""
        raw = self._send('D')
        try:
            return int(raw.split()[0])
        except (ValueError, IndexError):
            return None

    def get_setpoint(self):
        """SOLL<CR> → XX.XX$ — current temperature setpoint in °C (17-27°C)"""
        raw = self._send('SOLL')
        try:
            return float(raw.replace('$', '').strip())
        except (ValueError, AttributeError):
            return None

    def get_status_bytes(self):
        """BS<CR> → XXXXXX$ — three status bytes as integers (b1, b2, b3).
        Normal healthy state: b1=0x40, b2=0x00, b3=0x00 (hex 400000)"""
        raw = self._send('BS')
        try:
            hex_str = raw.replace('$', '').strip()
            b1 = int(hex_str[0:2], 16)
            b2 = int(hex_str[2:4], 16)
            b3 = int(hex_str[4:6], 16)
            return b1, b2, b3
        except (ValueError, IndexError):
            return None, None, None

    # -------------------------------------------------------------------------
    # Control commands
    # -------------------------------------------------------------------------

    def start(self):
        """START<CR> — start temperature control."""
        self._send('START')

    def stop(self):
        """STOP<CR> — stop temperature control."""
        self._send('STOP')

    def release_alarm(self):
        """ER<CR> — release safety circuit after fault is cleared."""
        self._send('ER')

    def set_setpoint(self, temp):
        """SOLL  XX.XX<CR> — set target temperature (17.00-27.00°C only)."""
        if 17.0 <= temp <= 27.0:
            self._send(f'SOLL  {temp:.2f}')
        else:
            print(f"Setpoint {temp}°C out of allowed range (17-27°C)")
