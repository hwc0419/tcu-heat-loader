# =============================================================================
# config.py — TCU Heat Load Test Configuration
# =============================================================================
# All settings are centralised here.
# Change values here only — do not hardcode values in other files.
#
# Platform: Raspberry Pi running Raspberry Pi OS
# =============================================================================

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
LOG_DIR = 'logs'                        # folder for CSV output files

# -----------------------------------------------------------------------------
# TCU RS232 connection settings
# (from Haake ASM TCU manual page 34 — dip switch defaults)
# -----------------------------------------------------------------------------
TCU_PORT        = 'COM5'    # RPi USB-to-RS232 adapter (check with: ls /dev/ttyUSB*)
TCU_BAUD        = 2400              # baud rate per manual
TCU_BYTESIZE    = 8                 # data bits
TCU_PARITY      = 'N'               # no parity
TCU_STOPBITS    = 1                 # stop bits
TCU_TIMEOUT     = 2                 # seconds to wait for response

# -----------------------------------------------------------------------------
# Test parameters
# -----------------------------------------------------------------------------
TEST_DURATION_MIN   = 30    # total test duration in minutes
POLL_INTERVAL_SEC   = 5     # how often to read TCU (seconds)

# -----------------------------------------------------------------------------
# Pass / fail thresholds
# -----------------------------------------------------------------------------
TEMP_SETPOINT       = 22.0  # °C — TCU target temperature
TEMP_TOLERANCE      = 0.1   # °C — max allowed deviation from setpoint
MIN_FLOW_RATE       = 1     # ℓ/min — minimum acceptable flow rate

# -----------------------------------------------------------------------------
# Physics constants
# -----------------------------------------------------------------------------
CP_WATER            = 4186  # J/kg·K — specific heat of water at ~22°C
TARGET_HEAT_LOAD    = 1200  # W — rated cooling capacity of Haake TCU
