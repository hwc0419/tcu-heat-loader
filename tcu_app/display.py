# =============================================================================
# display.py — Console Display Formatting
# =============================================================================
# All screen output handled here.
# Clears screen each poll cycle for clean fixed-position display.
# =============================================================================

import os
from config import TEST_DURATION_MIN, TEMP_SETPOINT, TEMP_TOLERANCE, TARGET_HEAT_LOAD


def clear_screen():
    """Clear terminal screen (Windows and Unix compatible)."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(tcu_serial, log_filename):
    """Print test header on startup."""
    print("=" * 60)
    print("  TCU HEAT LOAD TEST JIG")
    print("=" * 60)
    print(f"  TCU Serial:    {tcu_serial}")
    print(f"  Setpoint:      {TEMP_SETPOINT}°C ± {TEMP_TOLERANCE}°C")
    print(f"  Duration:      {TEST_DURATION_MIN} minutes")
    print(f"  Target load:   {TARGET_HEAT_LOAD}W")
    print(f"  Log file:      {log_filename}")
    print("=" * 60)
    print()


def print_readings(elapsed, setpoint, inlet_temp,
                   outlet_temp, delta_t, flow,
                   heat_load, alarms, status):
    """Refresh display with current readings — clears screen each cycle."""
    clear_screen()
    remaining = max(0, TEST_DURATION_MIN - elapsed)

    print("=" * 60)
    print("  TCU HEAT LOAD TEST — LIVE READINGS")
    print("=" * 60)
    print(f"  Elapsed:       {elapsed:.1f} min / {TEST_DURATION_MIN} min")
    print(f"  Remaining:     {remaining:.1f} min")
    print()
    print(f"  Setpoint:      {_disp(setpoint, '°C')}")
    print(f"  Inlet temp:    {_disp(inlet_temp, '°C')}  (TCU RS232)")
    print(f"  Outlet temp:   {_disp(outlet_temp, '°C')}  (PT100 sensor)")
    print(f"  Delta T:       {_disp(delta_t, '°C')}")
    print()
    print(f"  Flow rate:     {_disp(flow, ' ℓ/min')}  (TCU RS232)")
    print(f"  Heat load:     {_disp(heat_load, 'W')}  (target {TARGET_HEAT_LOAD}W)")
    print()
    alarm_indicator = '✓' if alarms == ['No alarms'] else '✗'
    print(f"  Alarms:     {alarm_indicator} {'; '.join(alarms)}")
    print()
    print("-" * 60)
    print(f"  Status:        {status}")
    print("-" * 60)


def print_result(tcu_serial, result, reason):
    """Print final test result."""
    print()
    print("=" * 60)
    if result == "PASS":
        print("  RESULT:  PASS ✓")
        print(f"  TCU {tcu_serial} maintained {TEMP_SETPOINT}°C for {TEST_DURATION_MIN} min")
    elif result == "FAIL":
        print("  RESULT:  FAIL ✗")
        print(f"  Reason:  {reason}")
    else:
        print(f"  RESULT:  {result}")
        print(f"  Reason:  {reason}")
    print("=" * 60)
    print()


def _disp(value, unit=''):
    """Format reading for display — shows N/A if None."""
    return 'N/A' if value is None else f"{value}{unit}"
