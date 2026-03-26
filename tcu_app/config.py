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
TCU_PORT        = '/dev/ttyUSB0'    # RPi USB-to-RS232 adapter (check with: ls /dev/ttyUSB*)
TCU_BAUD        = 4800              # baud rate per manual
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

# -----------------------------------------------------------------------------
# PT100 sensor node — INLET pipe (ESP32 Node 1)
# Independent inlet temperature — cross-checks TCU RS232 inlet reading.
# -----------------------------------------------------------------------------
PT100_INLET_ENABLED = False              # set False if inlet node not connected
PT100_INLET_HOST    = '192.168.1.100'   # ESP32 Node 1 IP on workshop WiFi
PT100_INLET_PORT    = 5000              # TCP port on ESP32 Node 1
PT100_INLET_TIMEOUT = 3                 # seconds to wait for response

# -----------------------------------------------------------------------------
# PT100 sensor node — OUTLET pipe (ESP32 Node 2)
# Outlet temperature — used with inlet PT100 for independent heat load calc.
# -----------------------------------------------------------------------------
PT100_OUTLET_ENABLED = False             # set False if outlet node not connected
PT100_OUTLET_HOST    = '192.168.1.101'  # ESP32 Node 2 IP on workshop WiFi
PT100_OUTLET_PORT    = 5000             # TCP port on ESP32 Node 2
PT100_OUTLET_TIMEOUT = 3               # seconds to wait for response

# -----------------------------------------------------------------------------
# Sensor cross-check threshold
# If PT100 inlet deviates from TCU RS232 inlet by more than this value,
# a WARNING is raised. Test continues but discrepancy is logged to CSV.
# -----------------------------------------------------------------------------
INLET_CROSSCHECK_TOLERANCE = 0.5       # °C
