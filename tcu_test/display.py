# =============================================================================
# display.py — Console Display Formatting
# =============================================================================
# All screen output handled here.
# Clears screen each poll cycle for clean fixed-position display.
# =============================================================================

import os
from config import TEST_DURATION_MIN, TEMP_SETPOINT, TEMP_TOLERANCE, TARGET_HEAT_LOAD


def clear_screen():
    """Clear terminal screen (Linux RPi compatible)."""
    os.system('clear')


def print_header(tcu_serial, log_filename):
    """Print test header on startup."""
    print("=" * 65)
    print("  TCU HEAT LOAD TEST JIG")
    print("=" * 65)
    print(f"  TCU Serial:    {tcu_serial}")
    print(f"  Setpoint:      {TEMP_SETPOINT}°C ± {TEMP_TOLERANCE}°C")
    print(f"  Duration:      {TEST_DURATION_MIN} minutes")
    print(f"  Target load:   {TARGET_HEAT_LOAD}W")
    print(f"  Log file:      {log_filename}")
    print("=" * 65)
    print()


def print_readings(elapsed, setpoint, inlet_temp,
                   pt100_inlet, outlet_temp,
                   delta_t, delta_t_pt100,
                   flow, heat_load, heat_load_pt100,
                   crosscheck_ok, crosscheck_msg,
                   alarms, status):
    """Refresh display with current readings — clears screen each cycle."""
    clear_screen()
    remaining = max(0, TEST_DURATION_MIN - elapsed)

    print("=" * 65)
    print("  TCU HEAT LOAD TEST — LIVE READINGS")
    print("=" * 65)
    print(f"  Elapsed:            {elapsed:.1f} min / {TEST_DURATION_MIN} min")
    print(f"  Remaining:          {remaining:.1f} min")
    print()

    # --- Temperature readings ---
    print(f"  Setpoint:           {_disp(setpoint, '°C')}")
    print(f"  Inlet temp (TCU):   {_disp(inlet_temp, '°C')}  (RS232 — authoritative)")
    print(f"  Inlet temp (PT100): {_disp(pt100_inlet, '°C')}  (independent sensor)")

    # Cross-check indicator
    if crosscheck_ok is None:
        print(f"  Cross-check:        N/A")
    elif crosscheck_ok:
        print(f"  Cross-check:        ✓ Sensors agree")
    else:
        print(f"  Cross-check:        ⚠ WARNING — {crosscheck_msg}")

    print()
    print(f"  Outlet temp (PT100):{_disp(outlet_temp, '°C')}  (independent sensor)")
    print()

    # --- Delta T ---
    print(f"  Delta T (TCU calc): {_disp(delta_t, '°C')}  (TCU inlet vs PT100 outlet)")
    print(f"  Delta T (PT100):    {_disp(delta_t_pt100, '°C')}  (both PT100 sensors)")
    print()

    # --- Flow and heat load ---
    print(f"  Flow rate:          {_disp(flow, ' ℓ/min')}  (TCU RS232)")
    print(f"  Heat load (TCU):    {_disp(heat_load, 'W')}  (target {TARGET_HEAT_LOAD}W)")
    print(f"  Heat load (PT100):  {_disp(heat_load_pt100, 'W')}  (independent calc)")
    print()

    # --- Alarms and status ---
    alarm_indicator = '✓' if alarms == ['No alarms'] else '✗'
    print(f"  Alarms:          {alarm_indicator} {'; '.join(alarms)}")
    print()
    print("-" * 65)
    print(f"  Status:             {status}")
    print("-" * 65)


def print_result(tcu_serial, result, reason):
    """Print final test result."""
    print()
    print("=" * 65)
    if result == "PASS":
        print("  RESULT:  PASS ✓")
        print(f"  TCU {tcu_serial} maintained {TEMP_SETPOINT}°C for {TEST_DURATION_MIN} min")
    elif result == "FAIL":
        print("  RESULT:  FAIL ✗")
        print(f"  Reason:  {reason}")
    else:
        print(f"  RESULT:  {result}")
        print(f"  Reason:  {reason}")
    print("=" * 65)
    print()


def _disp(value, unit=''):
    """Format reading for display — shows N/A if None."""
    return 'N/A' if value is None else f"{value}{unit}"
