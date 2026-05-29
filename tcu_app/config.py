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
PLC_MAX_RETRIES = 3
PLC_RETRY_DELAY = 0.1   # seconds between retries

# ── Heater (fixed — W5 30A hardware limit, never user-configurable) ───────────
HEATER_MAX_WATTS = 6900   # 30A × 230V = 6900W (W5SP4V030-24J rated limit)

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
MIN_FLOW_RATE     = settings.get('min_flow_rate')
FLOW_FAIL_GRACE_SAMPLES = settings.get('flow_fail_grace')
HEATER_SOFT_LIMIT_W    = settings.get('heater_soft_limit_w')

# Step response test
HEATER_STEP_START_W       = settings.get('heater_step_start_w')
HEATER_STEP_END_W         = settings.get('heater_step_end_w')
HEATER_STEP_SIZE_W        = settings.get('heater_step_size_w')
HEATER_DWELL_TIME_MIN     = settings.get('heater_dwell_time_min')
STEP_TEST_DURATION_MIN    = settings.get('step_test_duration_min')

# Steady state detection
STEADY_STATE_WINDOW_SEC  = settings.get('steady_state_window_sec')
STEADY_STATE_TOLERANCE   = settings.get('steady_state_tolerance')

# Thermal response detection
THERMAL_RESPONSE_THRESHOLD   = settings.get('thermal_response_threshold')
THERMAL_RESPONSE_MIN_SAMPLES = settings.get('thermal_response_min_samples')
THERMAL_RESPONSE_SIGMA       = settings.get('thermal_response_sigma')


