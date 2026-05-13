# =============================================================================
# test_logic.py — Pass/Fail Logic, Alarm Parsing, Heat Load Calculation
# =============================================================================
# Contains:
#   - BS status byte parsing       (Haake manual page 33-34)
#   - Heat load calculation        Q = m_dot * Cp * delta_T
#   - Delta T calculation
#   - Inlet sensor cross-check     PT100 inlet vs TCU RS232 inlet
#   - Pass/fail evaluation against configured thresholds
# =============================================================================

from settings_manager import settings

# Number of consecutive low-flow samples before triggering a FAIL.
# DAQ runs at ~1 Hz so this is approximately 5 seconds.
FLOW_FAIL_GRACE_SAMPLES = 5


# =============================================================================
# BS status byte parsing
# =============================================================================

def parse_alarms(b1, b2, b3):
    """
    Parse three status bytes returned by BS command.
    Returns list of alarm strings, or ['No alarms'] if healthy.

    Normal operation: b1=0x40 (FULL mark exceeded — expected and normal)
                      b2=0x00, b3=0x00

    Bit definitions from Haake ASM TCU manual page 33-34.
    """
    if b1 is None:
        return ['Cannot read TCU status']

    alarms = []

    # Byte 1 — water level and temperature limits
    if b1 & (1 << 5): alarms.append('Water level ASM not reached')
    if b1 & (1 << 4): alarms.append('Water level MIN not reached')
    if b1 & (1 << 3): alarms.append('Pump 2 operating temp exceeded')
    if b1 & (1 << 2): alarms.append('Pump 1 operating temp exceeded')
    if b1 & (1 << 1): alarms.append('Temperature exceeded 27C limit')
    if b1 & (1 << 0): alarms.append('Temperature below 17C limit')

    # Byte 2 — operational faults
    if b2 & (1 << 7): alarms.append('Unit auto shutdown')
    if b2 & (1 << 6): alarms.append('START/STOP commands blocked')
    if b2 & (1 << 5): alarms.append('Temperature out of 3-40C range')
    if b2 & (1 << 4): alarms.append('Temperature sensor fault')
    if b2 & (1 << 3): alarms.append('Calibration fault')
    if b2 & (1 << 1): alarms.append('Heating circuit fault')
    if b2 & (1 << 0): alarms.append('Operating pressure not reached')

    # Byte 3 — hardware faults
    if b3 & (1 << 7): alarms.append('Supply voltage not present')
    if b3 & (1 << 4): alarms.append('Hardware fault: main contactor')
    if b3 & (1 << 3): alarms.append('Hardware fault: watchdog')
    if b3 & (1 << 2): alarms.append('Hardware fault: alarm triggering')
    if b3 & (1 << 1): alarms.append('Hardware fault: unlocking switch')
    if b3 & (1 << 0): alarms.append('Hardware fault: start test')

    return alarms if alarms else ['No alarms']


# =============================================================================
# Pass / fail evaluation
# =============================================================================

def check_pass_fail(inlet_temp, flow, alarms, elapsed_min, low_flow_count):
    """
    Evaluate current test state against pass/fail criteria.

    Args:
        inlet_temp      : float | None — current inlet temperature
        flow            : float | None — current flow rate
        alarms          : list[str]    — parsed alarm list
        elapsed_min     : float        — elapsed test time in minutes
        low_flow_count  : int          — consecutive low-flow sample count
                          managed by caller; reset to 0 on test start

    Returns:
        (True,  message, new_count) — test passed
        (False, message, new_count) — test failed — reason in message
        (None,  message, new_count) — test still running

    Pass conditions (ALL must hold for full test duration):
        1. Inlet temp within TEMP_SETPOINT +/- TEMP_TOLERANCE
        2. Flow rate >= MIN_FLOW_RATE (grace: FLOW_FAIL_GRACE_SAMPLES
           consecutive low readings before FAIL)
        3. No TCU alarms
        4. Test duration reached
    """
    if inlet_temp is None:
        return None, 'Cannot read inlet temperature', low_flow_count
    if flow is None:
        return None, 'Cannot read flow rate', low_flow_count

    temp_setpoint  = settings.get('temp_setpoint')
    temp_tolerance = settings.get('temp_tolerance')
    min_flow       = settings.get('min_flow_rate')
    test_duration  = settings.get('test_duration')

    deviation = abs(inlet_temp - temp_setpoint)
    if deviation > temp_tolerance:
        return False, (
            f'Temp {inlet_temp:.2f}°C outside '
            f'{temp_setpoint}±{temp_tolerance}°C'
        ), low_flow_count

    # Flow rate — grace period before failing
    if flow < min_flow:
        new_count = low_flow_count + 1
        if new_count >= FLOW_FAIL_GRACE_SAMPLES:
            return False, (
                f'Flow rate too low for {FLOW_FAIL_GRACE_SAMPLES}s: '
                f'{flow:.1f} l/min (min {min_flow})'
            ), new_count
        return None, f'Flow low — warning {new_count}/{FLOW_FAIL_GRACE_SAMPLES}', new_count

    new_count = 0

    if alarms != ['No alarms']:
        return False, f'TCU alarm: {alarms[0]}', new_count

    if elapsed_min >= test_duration:
        return True, f'PASS — {test_duration} min completed successfully', new_count

    remaining = test_duration - elapsed_min
    return None, f'RUNNING — {remaining:.1f} min remaining', new_count


# =============================================================================
# BS status decode — human-readable log string
# =============================================================================

def decode_status(b1, b2, b3, inlet_temp=None, flow=None, setpoint=None):
    """
    Return a human-readable status string from BS bytes and live readings.
    Used by DAQ thread to populate the command log in the monitor tab.
    """
    if b1 is None:
        return 'BS: no data'

    bs = (b1 << 16) | ((b2 or 0) << 8) | (b3 or 0)
    alarms = parse_alarms(b1, b2, b3)
    alarm_str = '; '.join(alarms)

    temp_str = f'{inlet_temp:.2f}°C' if inlet_temp is not None else 'N/A'
    flow_str = f'{flow:.2f} l/min'   if flow       is not None else 'N/A'
    sp_str   = f'{setpoint:.2f}°C'   if setpoint   is not None else 'N/A'

    return (
        f'BS={bs:#08x} | '
        f'Inlet={temp_str} SP={sp_str} Flow={flow_str} | '
        f'{alarm_str}'
    )


# =============================================================================
# BS abnormal check
# =============================================================================

def is_abnormal(b1, b2, b3, inlet_temp=None, setpoint=None, flow=None):
    """
    Return True if TCU is in an abnormal state requiring heater auto-off.

    Normal running state: BS = 0x400400 (b2 bit 2 = main contactor ON).
    Any deviation from this — including alarms, sensor faults, or low flow —
    is treated as abnormal.

    Returns bool. Returns True (abnormal) if b1 is None (no data).
    """
    if b1 is None:
        return True

    bs = (b1 << 16) | ((b2 or 0) << 8) | (b3 or 0)
    if bs != 0x400400:
        return True

    alarms = parse_alarms(b1, b2, b3)
    if alarms != ['No alarms']:
        return True

    if flow is not None and flow < settings.get('min_flow_rate'):
        return True

    return False
