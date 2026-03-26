# =============================================================================
# main.py — TCU Heat Load Test — Main Entry Point
# =============================================================================
# Orchestrates full test sequence:
#   1. Connect to TCU via RS232
#   2. Connect to two PT100 wireless sensor nodes via WiFi TCP
#      - Node 1: inlet pipe  (cross-check against TCU RS232 inlet)
#      - Node 2: outlet pipe (independent outlet temperature)
#   3. Run 30-minute heat load test at 1200W
#   4. Log all readings to CSV every 5 seconds
#   5. Display live readings on RPi touchscreen terminal
#   6. Declare PASS or FAIL automatically
#
# Usage:
#   python3 main.py
#   or: ./start.sh
#
# Dependencies:
#   pip3 install pyserial --break-system-packages
# =============================================================================

import time
import sys

import os
from config      import POLL_INTERVAL_SEC, TARGET_HEAT_LOAD, LOG_DIR
from tcu_comms   import TCUComms
from pt100       import PT100Sensors
from test_logic  import (
    parse_alarms,
    calculate_delta_t,
    calculate_heat_load,
    check_pass_fail,
    check_inlet_crosscheck
)
from logger      import TestLogger
from display     import (
    print_header,
    print_readings,
    print_result
)


def get_tcu_serial():
    """Prompt operator for TCU serial number before test starts."""
    print()
    serial_no = input("  Enter TCU serial number: ").strip()
    if not serial_no:
        print("  Serial number cannot be empty.")
        sys.exit(1)
    return serial_no


def run_test():
    """Main test sequence."""

    tcu_serial = get_tcu_serial()
    tcu        = TCUComms()
    sensors    = PT100Sensors()

    tcu.connect()
    if not tcu.connected:
        print("Cannot connect to TCU — check RS232 cable and TCU_PORT in config.py")
        sys.exit(1)

    with TestLogger(tcu_serial, output_dir=LOG_DIR) as log:

        print_header(tcu_serial, log.filename)

        # --- Fill sequence ---
        print("  Is the TCU water circuit already filled and READY light on?")
        fill_resp = input("  Enter Y if already filled, or press ENTER to send AFV fill command: ").strip().upper()
        if fill_resp != 'Y':
            print("  Sending AFV fill command to TCU...")
            tcu.fill()
            print("  Fill command sent. Waiting for TCU to fill and reach temperature.")
            input("  Press ENTER when READY light is on and flow is confirmed...")
        else:
            print("  Skipping fill — TCU already ready.")

        input("  Press ENTER when heater is active and flow is confirmed...")

        start_time   = time.time()
        final_result = 'ABORTED'
        final_reason = 'Test stopped by operator'
        elapsed      = 0.0

        try:
            while True:
                elapsed = (time.time() - start_time) / 60.0

                # --- Read all data sources ---
                inlet_temp  = tcu.get_inlet_temp()
                flow        = tcu.get_flow_rate()
                setpoint    = tcu.get_setpoint()
                b1, b2, b3  = tcu.get_status_bytes()
                pt100_inlet = sensors.get_inlet_temp()
                outlet_temp = sensors.get_outlet_temp()

                # --- Derived values ---
                alarms           = parse_alarms(b1, b2, b3)

                # Delta T: TCU inlet vs PT100 outlet (primary)
                delta_t          = calculate_delta_t(inlet_temp, outlet_temp)

                # Delta T: both PT100 sensors (independent cross-check)
                delta_t_pt100    = calculate_delta_t(pt100_inlet, outlet_temp)

                # Heat load using TCU inlet + PT100 outlet (primary)
                heat_load        = calculate_heat_load(inlet_temp, outlet_temp, flow)

                # Heat load using both PT100 sensors (fully independent)
                heat_load_pt100  = calculate_heat_load(pt100_inlet, outlet_temp, flow)

                # Inlet sensor cross-check (advisory warning only)
                crosscheck_ok, crosscheck_msg = check_inlet_crosscheck(
                    inlet_temp, pt100_inlet
                )

                # Pass/fail uses TCU RS232 inlet as authoritative source
                passed, status_msg = check_pass_fail(
                    inlet_temp, flow, alarms, elapsed
                )

                # --- Refresh display ---
                print_readings(
                    elapsed, setpoint, inlet_temp,
                    pt100_inlet, outlet_temp,
                    delta_t, delta_t_pt100,
                    flow, heat_load, heat_load_pt100,
                    crosscheck_ok, crosscheck_msg,
                    alarms, status_msg
                )

                # --- Log to CSV ---
                log.write_row(
                    elapsed, setpoint, inlet_temp,
                    pt100_inlet, outlet_temp,
                    delta_t, delta_t_pt100,
                    flow, heat_load, heat_load_pt100,
                    TARGET_HEAT_LOAD,
                    crosscheck_msg,
                    alarms, status_msg
                )

                # --- Check for completion ---
                if passed is True:
                    final_result = 'PASS'
                    final_reason = status_msg
                    break
                if passed is False:
                    final_result = 'FAIL'
                    final_reason = status_msg
                    break

                time.sleep(POLL_INTERVAL_SEC)

        except KeyboardInterrupt:
            final_result = 'ABORTED'
            final_reason = 'Stopped by operator (Ctrl+C)'

        finally:
            log.write_final(elapsed, final_result)
            print_result(tcu_serial, final_result, final_reason)
            sensors.close()
            tcu.disconnect()


if __name__ == '__main__':
    run_test()
