# =============================================================================
# config.py — TCU++ Configuration
# =============================================================================
# All runtime-configurable settings are read from settings_manager.
# Hard constants (non-user-configurable) are defined here directly.
# =============================================================================

import sys
from settings_manager import settings

# ── Platform detection ────────────────────────────────────────────────────────
WINDOWS = sys.platform == 'win32'
LINUX   = not WINDOWS

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR     = 'logs'
REPORTS_DIR = 'reports'

# ── TCU serial (fixed protocol constants) ─────────────────────────────────────
TCU_BYTESIZE = 8
TCU_PARITY   = 'N'
TCU_STOPBITS = 1
TCU_TIMEOUT  = 2

# ── PZEM-004T (fixed protocol constants) ──────────────────────────────────────
PZEM_SLAVE = 0xF8

import serial as _serial

# ── PLC (fixed protocol constants) ────────────────────────────────────────────
PLC_BAUD        = 9600
PLC_BYTESIZE    = 8
PLC_PARITY      = _serial.PARITY_ODD
PLC_STOPBITS    = 1
PLC_TIMEOUT     = 1.0
PLC_DT_SETPOINT = 100   # DT100 — RPi writes K value here
PLC_UNIT        = '01'  # MEWTOCOL unit number — FP0 default
PLC_K_MIN       = 0
PLC_K_MAX       = 4000
PLC_MAX_RETRIES = 100
PLC_RETRY_DELAY = 0.1   # seconds between retries

# ── Heater (fixed — W5 30A hardware limit, never user-configurable) ───────────
HEATER_MAX_WATTS = 2000

# Live values from settings_manager
PLC_PORT          = settings.get('plc_port')
TCU_PORT          = settings.get('tcu_port')
TCU_BAUD          = settings.get('tcu_baud')
PZEM_PORT         = settings.get('pzem_port')
PZEM_BAUD         = settings.get('pzem_baud')
TEST_DURATION_MIN = settings.get('test_duration')
POLL_INTERVAL_SEC = settings.get('poll_interval')
TEMP_SETPOINT     = settings.get('temp_setpoint')
TEMP_TOLERANCE    = settings.get('temp_tolerance')
FLOW_SETPOINT     = settings.get('flow_setpoint')
FLOW_TOLERANCE    = settings.get('flow_tolerance')
MIN_FLOW_RATE     = settings.get('min_flow_rate')
FLOW_FAIL_GRACE_SAMPLES = settings.get('flow_fail_grace')
BS_NORMAL         = 0x400400   # Normal running state: b1=0x40, b2=0x04, b3=0x00
HEATER_SOFT_LIMIT_W    = settings.get('heater_soft_limit_w')

# ── Stepped heat load test (fixed — not user-configurable) ───────────────────
STEPPED_TEST_NUM_STEPS       = 80       # 0W, 100W, 200W … 8000W
STEPPED_TEST_STEP_WATTS      = 100      # W per step
STEPPED_TEST_STEP_DURATION_S = 300      # 5 minutes per step
STEPPED_TEST_AVG_WINDOW_S    = 180      # last 3 minutes used for averaging
STEPPED_TEST_SETPOINT_TOL    = 0.1      # °C — exclude samples outside setpoint ± this
STEPPED_TEST_TARGET_WATTS    = 28604    # W — extrapolation target (29°C at 50 L/min)
STEPPED_TEST_MAX_DURATION_S  = 32400   # 9 hours hard limit


