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

from config import (
    TEMP_SETPOINT, TEMP_TOLERANCE,
    MIN_FLOW_RATE, CP_WATER, TEST_DURATION_MIN
)


# =============================================================================
# BS status byte parsing
# =============================================================================

def parse_alarms(b1, b2, b3):
    """
    Parse three status bytes returned by BS command.
    Returns list of alarm strings, or ['No alarms'] if healthy.

    Reference: Haake ASM TCU manual section 6.5.
    Normal running state: b1=0x40, b2=0x04, b3=0x00
      b1 bit 6 = water level FULL (always set — normal)
      b2 bit 2 = main contactor ON (set at START, cleared at STOP/ALARM)
    (A) = Alarm source
    (S) = START and ER cannot be carried out, unit must be switched off
    """
    if b1 is None:
        return ['Cannot read TCU status']

    alarms = []

    # Byte 1 — water level and temperature limits
    # bit 7: no meaning
    # bit 6: FULL mark exceeded — normal, not an alarm
    if b1 & (1 << 5): alarms.append('Liquid level mark ASM not reached')
    if b1 & (1 << 4): alarms.append('(A) Liquid level mark MIN not reached')
    if b1 & (1 << 3): alarms.append('(A) Pump 2 (ext.) operating temperature exceeded')
    if b1 & (1 << 2): alarms.append('(A) Pump 1 (int.) operating temperature exceeded')
    if b1 & (1 << 1): alarms.append('(A) Temperature exceeded 27°C upper limit')
    if b1 & (1 << 0): alarms.append('(A) Temperature below 17°C lower limit')

    # Byte 2 — operational status
    # bit 2: main contactor activated — normal at START, cleared at STOP/ALARM
    if b2 & (1 << 7): alarms.append('ALARM — unit switches off automatically')
    if b2 & (1 << 6): alarms.append('START/STOP commands and internal monitoring blocked')
    if b2 & (1 << 5): alarms.append('(A) Temperature below 3°C or above 40°C')
    if b2 & (1 << 4): alarms.append('(A) Temperature sensor breakage or short-circuit')
    if b2 & (1 << 3): alarms.append('(A) Calibration fault')
    # bit 2: main contactor — not an alarm
    if b2 & (1 << 1): alarms.append('(A) Fault in heating circuit')
    if b2 & (1 << 0): alarms.append('(A) Operating pressure not reached')

    # Byte 3 — hardware faults
    # bits 6, 5: no meaning
    if b3 & (1 << 7): alarms.append('Supply voltage not present in safety circuit')
    if b3 & (1 << 4): alarms.append('(S) Hardware fault: main contactor — switch unit off')
    if b3 & (1 << 3): alarms.append('(S) Hardware fault: watchdog switching — switch unit off')
    if b3 & (1 << 2): alarms.append('(S) Hardware fault: alarm triggering — switch unit off')
    if b3 & (1 << 1): alarms.append('(S) Hardware fault: unlocking switching — switch unit off')
    if b3 & (1 << 0): alarms.append('(S) Hardware fault: start test — switch unit off')

    return alarms if alarms else ['No alarms']



def check_pass_fail(inlet_temp, flow, alarms, elapsed_min):
    """
    Evaluate current test state against pass/fail criteria.

    Returns:
        (True,  message) — test passed — 30 min completed
        (False, message) — test failed — reason in message
        (None,  message) — test still running

    Pass conditions (ALL must hold for full test duration):
        1. Inlet temp within TEMP_SETPOINT ± TEMP_TOLERANCE
        2. Flow rate >= MIN_FLOW_RATE
        3. No TCU alarms
        4. Test duration reached

    Note: inlet sensor cross-check is advisory only — does not cause FAIL.
    """
    if inlet_temp is None:
        return None, 'Cannot read inlet temperature'
    if flow is None:
        return None, 'Cannot read flow rate'

    deviation = abs(inlet_temp - TEMP_SETPOINT)
    if deviation > TEMP_TOLERANCE:
        return False, (
            f'Temp {inlet_temp:.2f}°C outside '
            f'{TEMP_SETPOINT}±{TEMP_TOLERANCE}°C'
        )

    if flow < MIN_FLOW_RATE:
        return False, f'Flow rate too low: {flow} ℓ/min (min {MIN_FLOW_RATE})'

    if alarms != ['No alarms']:
        return False, f'TCU alarm: {alarms[0]}'

    if elapsed_min >= TEST_DURATION_MIN:
        return True, f'PASS — {TEST_DURATION_MIN} min completed successfully'

    remaining = TEST_DURATION_MIN - elapsed_min
    return None, f'RUNNING — {remaining:.1f} min remaining'


# =============================================================================
# Human-readable status decoding
# =============================================================================

# =============================================================================
# Human-readable status decoding
# =============================================================================

def decode_status(b1, b2, b3, inlet_temp=None, flow=None, setpoint=None):
    """
    Produce a full human-readable description of the TCU state for the
    command log. Called every poll cycle.

    Reference: Haake ASM TCU manual section 6.5.
    Normal running state: b1=0x40, b2=0x04, b3=0x00
    """
    if b1 is None:
        return ['STATUS: Cannot read TCU — check RS232 connection']

    lines = []

    # ── Water level (byte 1) ──────────────────────────────────────────────────
    if b1 & (1 << 6):
        lines.append('Water level: FULL ✓')
    if b1 & (1 << 5):
        lines.append('⚠ Water level ASM mark not reached — check water supply')
    if b1 & (1 << 4):
        lines.append('⚠ (A) Water level MIN not reached — risk of dry run')

    # ── Main contactor state (byte 2 bit 2) ───────────────────────────────────
    if b2 is not None:
        if b2 & (1 << 2):
            lines.append('Main contactor: ON — TCU running ✓')
        else:
            lines.append('Main contactor: OFF — TCU stopped or alarm active')

    # ── Temperature ───────────────────────────────────────────────────────────
    if inlet_temp is not None and setpoint is not None:
        deviation = inlet_temp - setpoint
        if abs(deviation) <= 0.5:
            lines.append(
                f'Temperature: {inlet_temp:.2f}°C  '
                f'(setpoint {setpoint:.1f}°C, deviation {deviation:+.2f}°C) ✓')
        else:
            lines.append(
                f'⚠ Temperature: {inlet_temp:.2f}°C  '
                f'(setpoint {setpoint:.1f}°C, deviation {deviation:+.2f}°C) — outside tolerance')

    if b1 & (1 << 1):
        lines.append('⚠ (A) Temperature exceeded 27°C upper limit — shutdown imminent')
    if b1 & (1 << 0):
        lines.append('⚠ (A) Temperature below 17°C lower limit — check coolant')
    if b2 is not None and b2 & (1 << 5):
        lines.append('⚠ (A) Temperature below 3°C or above 40°C operating range')
    if b2 is not None and b2 & (1 << 4):
        lines.append('✕ (A) Temperature sensor breakage or short-circuit')

    # ── Flow rate ─────────────────────────────────────────────────────────────
    if flow is not None:
        if flow >= 1.0:
            lines.append(f'Flow rate: {flow:.1f} ℓ/min ✓')
        elif flow > 0:
            lines.append(f'⚠ Flow rate: {flow:.1f} ℓ/min — below 1 ℓ/min minimum')
        else:
            lines.append('⚠ Flow rate: ZERO — pump failure or valve closed')

    # ── Pump faults (byte 1) ──────────────────────────────────────────────────
    if b1 & (1 << 3):
        lines.append('⚠ (A) Pump 2 (ext.) operating temperature exceeded')
    if b1 & (1 << 2):
        lines.append('⚠ (A) Pump 1 (int.) operating temperature exceeded')

    # ── Operational faults (byte 2) ───────────────────────────────────────────
    if b2 is not None:
        if b2 & (1 << 7):
            lines.append('✕ ALARM — unit switches off automatically')
        if b2 & (1 << 6):
            lines.append('✕ START/STOP commands and internal monitoring blocked')
        if b2 & (1 << 3):
            lines.append('✕ (A) Calibration fault — unit requires service')
        if b2 & (1 << 1):
            lines.append('✕ (A) Fault in heating circuit — check heater continuity')
        if b2 & (1 << 0):
            lines.append('✕ (A) Operating pressure not reached — check pump and valves')

    # ── Hardware faults (byte 3) ──────────────────────────────────────────────
    if b3 is not None:
        if b3 & (1 << 7):
            lines.append('✕ Supply voltage not present in safety circuit')
        if b3 & (1 << 4):
            lines.append('✕ (S) Hardware fault: main contactor — switch unit OFF')
        if b3 & (1 << 3):
            lines.append('✕ (S) Hardware fault: watchdog switching — switch unit OFF')
        if b3 & (1 << 2):
            lines.append('✕ (S) Hardware fault: alarm triggering — switch unit OFF')
        if b3 & (1 << 1):
            lines.append('✕ (S) Hardware fault: unlocking switching — switch unit OFF')
        if b3 & (1 << 0):
            lines.append('✕ (S) Hardware fault: start test — switch unit OFF')

    return lines if lines else ['STATUS: All systems normal']


def is_abnormal(b1, b2, b3, inlet_temp=None, setpoint=None,
                tolerance=None, flow=None):
    """
    Returns True if ANY condition requires operator attention.

    Correctly excludes normal operating bits:
      b1 bit 6 — water level FULL (always set in normal operation)
      b2 bit 2 — main contactor ON (set at START, cleared at STOP/ALARM)
    """
    from config import TEMP_TOLERANCE, MIN_FLOW_RATE
    tol      = tolerance if tolerance is not None else TEMP_TOLERANCE
    min_flow = MIN_FLOW_RATE

    if b1 is None:
        return True

    # b1: alarm bits are 0-5. Bit 6 is normal FULL mark — mask it out
    if b1 & 0b00111111:
        return True

    # b2: bit 2 is normal contactor ON — mask it out, check everything else
    if b2 is not None and (b2 & 0b11111011):
        return True

    # b3: all set bits are hardware faults
    if b3 is not None and b3 != 0:
        return True

    if inlet_temp is not None and setpoint is not None:
        if abs(inlet_temp - setpoint) > tol:
            return True

    if flow is not None and flow < min_flow:
        return True

    return False
