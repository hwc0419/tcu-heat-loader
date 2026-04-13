# =============================================================================
# config.py — TCU Heat Load Test Configuration
# =============================================================================
# Settings are now managed by settings_manager.py and persisted to
# settings.json. This file reads live values from settings_manager at import.
# To change settings at runtime, use the Settings tab in the GUI.
# =============================================================================

import sys
from settings_manager import settings

# ── Platform detection ────────────────────────────────────────────────────────
WINDOWS = sys.platform == 'win32'
LINUX   = not WINDOWS

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = 'logs'

# ── Live values from settings_manager ────────────────────────────────────────
# Read at import time — for hot reload, modules should call settings.get()
# directly rather than importing these constants.

TCU_PORT        = settings.get('tcu_port')
TCU_BAUD        = settings.get('tcu_baud')
TCU_BYTESIZE    = 8
TCU_PARITY      = 'N'
TCU_STOPBITS    = 1
TCU_TIMEOUT     = 2

TEST_DURATION_MIN   = settings.get('test_duration')
POLL_INTERVAL_SEC   = settings.get('poll_interval')

TEMP_SETPOINT       = settings.get('temp_setpoint')
TEMP_TOLERANCE      = settings.get('temp_tolerance')
MIN_FLOW_RATE       = 1

CP_WATER            = 4186
TARGET_HEAT_LOAD    = 1200

# ── PZEM-004T GPIO UART settings ─────────────────────────────────────────────
# RPi: GPIO UART /dev/ttyAMA0 (pins 14/15) — no USB port used
# Windows: USB-TTL adapter COM port
PZEM_PORT       = settings.get('pzem_port')
PZEM_SLAVE      = 0xF8
PZEM_BAUD       = settings.get('pzem_baud')
