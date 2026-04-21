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
REPORTS_DIR = 'logs/reports'

# ── TCU serial (fixed protocol constants) ─────────────────────────────────────
TCU_BYTESIZE = 8
TCU_PARITY   = 'N'
TCU_STOPBITS = 1
TCU_TIMEOUT  = 2

# ── PZEM-004T (fixed protocol constants) ──────────────────────────────────────
PZEM_SLAVE = 0xF8

# ── Heater (fixed — hardware limit, never user-configurable) ──────────────────
HEATER_MAX_WATTS = 20000

# ── Live values from settings_manager ────────────────────────────────────────
# These are read at import — for hot reload, call settings.get() directly.

TCU_PORT          = settings.get('tcu_port')
TCU_BAUD          = settings.get('tcu_baud')
PZEM_PORT         = settings.get('pzem_port')
PZEM_BAUD         = settings.get('pzem_baud')
TEST_DURATION_MIN = settings.get('test_duration')
POLL_INTERVAL_SEC = settings.get('poll_interval')
TEMP_SETPOINT     = settings.get('temp_setpoint')
TEMP_TOLERANCE    = settings.get('temp_tolerance')
MIN_FLOW_RATE     = settings.get('min_flow_rate')

# Heater Modbus (user-configurable)
HEATER_PORT        = settings.get('heater_port')
HEATER_BAUD        = settings.get('heater_baud')
HEATER_SLAVE_ID    = settings.get('heater_slave_id')
HEATER_REG_SETPOINT = settings.get('heater_reg_setpoint')
HEATER_REG_ACTUAL   = settings.get('heater_reg_actual')
HEATER_WATTS_TOLERANCE = settings.get('heater_watts_tolerance')
HEATER_DISPLAY_MODE    = settings.get('heater_display_mode')

# Step response test (user-configurable)
HEATER_STEP_START_W       = settings.get('heater_step_start_w')
HEATER_STEP_END_W         = settings.get('heater_step_end_w')
HEATER_STEP_SIZE_W        = settings.get('heater_step_size_w')
HEATER_DWELL_TIME_MIN     = settings.get('heater_dwell_time_min')
STEP_TEST_DURATION_MIN    = settings.get('step_test_duration_min')

# Steady state detection (user-configurable)
STEADY_STATE_WINDOW_SEC  = settings.get('steady_state_window_sec')
STEADY_STATE_TOLERANCE   = settings.get('steady_state_tolerance')

# Thermal response detection (user-configurable)
THERMAL_RESPONSE_THRESHOLD   = settings.get('thermal_response_threshold')
THERMAL_RESPONSE_MIN_SAMPLES = settings.get('thermal_response_min_samples')
THERMAL_RESPONSE_SIGMA       = settings.get('thermal_response_sigma')
