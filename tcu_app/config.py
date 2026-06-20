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
BS_NORMAL         = 0x400400   # Normal running state: b1=0x40, b2=0x04, b3=0x00
HEATER_SOFT_LIMIT_W    = settings.get('heater_soft_limit_w')

# ── AMAT0 stress test (live from settings) ────────────────────────────────────
STRESS_TEST_TOLERANCE      = settings.get('stress_test_tolerance')       # °C, ±band for "in tolerance"
STRESS_TEST_SETTLE_S       = settings.get('stress_test_settle_duration_s')  # consecutive in-tolerance seconds to call it settled
STRESS_TEST_DURATION_S     = settings.get('stress_test_duration_s')      # USER_CONFIGURED_DURATION — fixed total test runtime
STRESS_TEST_MIN_ENDURANCE_S = settings.get('stress_test_min_endurance_s')  # MIN_ENDURANCE_DURATION — (duration - test_end_time) must exceed this
STRESS_TEST_MIN_SEED_RUNS  = settings.get('stress_test_min_seed_runs')   # minimum pass-dataset size before the main AMAT0 test can run at all — below this, use the Reference subtab
STRESS_TEST_MAX_DURATION_S = 9000      # 2.5h hard ceiling on STRESS_TEST_DURATION_S itself — sanity backstop against misconfiguration
STRESS_TEST_DATA_DIR       = 'reference_data'
STRESS_TEST_HISTORY_MAX    = 100       # most-recent runs shown in the history dropdown

# ── In-app Documentation tab assets ───────────────────────────────────────────
MANUAL_DIR        = 'manual_pages'   # Haake ASM TCU manual, pre-extracted as page JPEGs
MANUAL_PAGE_COUNT = 50                # fixed — manual_pages/1.jpeg .. 50.jpeg
DOCS_ASSETS_DIR   = 'docs_assets'    # images used by the in-app Documentation tab

# ── 2kW heat load sequence test (live from settings) ─────────────────────────
SEQ_TEST_SETTLE_S        = settings.get('seq_test_settle_duration_s')
SEQ_TEST_TAIL_S          = settings.get('seq_test_tail_duration_s')
SEQ_TEST_Z_THRESHOLD     = settings.get('seq_test_z_threshold')
SEQ_TEST_BIN_WIDTH_W     = 10           # fixed — settle-time histogram bin width
SEQ_TEST_RANDOM_MIN_W    = settings.get('seq_test_random_min_w')
SEQ_TEST_RANDOM_MAX_W    = settings.get('seq_test_random_max_w')
SEQ_TEST_RANDOM_LEN_MIN  = settings.get('seq_test_random_len_min')
SEQ_TEST_RANDOM_LEN_MAX  = settings.get('seq_test_random_len_max')
SEQ_TEST_MAX_DURATION_S  = 9000         # 2.5h hard upper bound on any single stage (safety backstop)
SEQ_TEST_MAX_STAGES      = 100          # fixed upper bound — matches random length ceiling
SEQ_TEST_DATA_DIR        = 'sequence_test_data'


