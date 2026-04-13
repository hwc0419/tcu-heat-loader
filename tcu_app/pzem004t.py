# =============================================================================
# sdm120.py — PZEM-004T Energy Meter via Modbus RTU (GPIO UART)
# =============================================================================
# Reads voltage, current and active power from PZEM-004T v3.0 via GPIO UART.
#
# Hardware connection (RPi GPIO — saves USB ports):
#   PZEM-004T TX → RPi GPIO 15 (RX, pin 10)
#   PZEM-004T RX → RPi GPIO 14 (TX, pin 8)
#   PZEM-004T 5V → RPi pin 2 (5V)
#   PZEM-004T GND → RPi pin 6 (GND)
#
# RPi UART setup required (run once):
#   sudo raspi-config → Interface Options → Serial Port
#     "Login shell over serial?" → No
#     "Serial port hardware enabled?" → Yes
#   Add to /boot/firmware/config.txt: dtoverlay=disable-bt
#   sudo reboot
#
# PZEM-004T v3.0 Modbus RTU settings (from datasheet):
#   Baud rate    : 9600
#   Data bits    : 8
#   Parity       : None
#   Stop bits    : 1
#   Default addr : 0xF8 (broadcast — works for single device on bus)
#
# Register map (function code 04) — integer scaled, NOT IEEE 754 floats:
#   0x0000 — Voltage       (uint16, ÷10    → V)
#   0x0001 — Current Lo    (uint16, combined with 0x0002, ÷1000 → A)
#   0x0002 — Current Hi    (uint16)
#   0x0003 — Power Lo      (uint16, combined with 0x0004, ÷10   → W)
#   0x0004 — Power Hi      (uint16)
#
# Requires: pip3 install minimalmodbus --break-system-packages
# =============================================================================

import minimalmodbus
from config import PZEM_PORT, PZEM_SLAVE, PZEM_BAUD


class SDM120:
    """
    PZEM-004T v3.0 energy meter interface via Modbus RTU over GPIO UART.
    Class kept as SDM120 for drop-in compatibility with rest of codebase.

    Usage:
        sdm = SDM120()
        if sdm.connected:
            v, i, w = sdm.get_all()
    """

    def __init__(self):
        self.connected = False
        self._meter    = None
        self._connect()

    def _connect(self):
        """Initialise Modbus RTU connection to PZEM-004T via GPIO UART."""
        try:
            self._meter = minimalmodbus.Instrument(PZEM_PORT, PZEM_SLAVE)
            self._meter.serial.baudrate = PZEM_BAUD
            self._meter.serial.bytesize = 8
            self._meter.serial.parity   = 'N'
            self._meter.serial.stopbits = 1
            self._meter.serial.timeout  = 1
            self._meter.mode = minimalmodbus.MODE_RTU
            self.connected = True
            print(f"PZEM-004T connected on {PZEM_PORT} (slave 0x{PZEM_SLAVE:02X}) at {PZEM_BAUD} baud")
        except Exception as e:
            self.connected = False
            print(f"PZEM-004T connection failed: {e}")
            print(f"  Check GPIO UART enabled — see setup notes in sdm120.py")

    def get_voltage(self):
        """
        Returns voltage in V (1dp), or None on failure.
        Register 0x0000 — uint16, divide by 10.
        """
        try:
            raw = self._meter.read_register(0x0000, functioncode=4)
            return round(raw / 10.0, 1)
        except Exception:
            return None

    def get_current(self):
        """
        Returns current in A (3dp), or None on failure.
        Registers 0x0001 (lo) + 0x0002 (hi) — uint32, divide by 1000.
        """
        try:
            regs = self._meter.read_registers(0x0001, 2, functioncode=4)
            raw = (regs[1] << 16) | regs[0]   # hi word | lo word
            return round(raw / 1000.0, 3)
        except Exception:
            return None

    def get_power(self):
        """
        Returns active power in W (1dp), or None on failure.
        Registers 0x0003 (lo) + 0x0004 (hi) — uint32, divide by 10.
        Handles phase angle SCR load correctly — true watts measurement.
        """
        try:
            regs = self._meter.read_registers(0x0003, 2, functioncode=4)
            raw = (regs[1] << 16) | regs[0]   # hi word | lo word
            return round(raw / 10.0, 1)
        except Exception:
            return None

    def get_all(self):
        """
        Returns (voltage, current, power) tuple.
        Reads all 5 registers in a single Modbus transaction — faster than
        three separate reads (~100ms vs ~300ms).
        """
        try:
            regs = self._meter.read_registers(0x0000, 5, functioncode=4)
            voltage = round(regs[0] / 10.0, 1)
            current = round(((regs[2] << 16) | regs[1]) / 1000.0, 3)
            power   = round(((regs[4] << 16) | regs[3]) / 10.0, 1)
            return voltage, current, power
        except Exception:
            return None, None, None
