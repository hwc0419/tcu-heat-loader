# =============================================================================
# logger.py — CSV Test Data Logger
# =============================================================================
# Creates a timestamped CSV file per test run.
# Logs one row every POLL_INTERVAL_SEC seconds.
# Final row records the overall pass/fail result.
#
# File naming: TCU_test_<serial>_<YYYYMMDD_HHMMSS>.csv
# =============================================================================

import csv
import os
from datetime import datetime


class TestLogger:
    """
    Handles CSV logging for a single TCU test run.
    Use as context manager:
        with TestLogger(tcu_serial) as log:
            log.write_row(...)
    """

    HEADERS = [
        'Timestamp',
        'Elapsed (min)',
        'Setpoint (C)',
        'Inlet Temp (C)',
        'Outlet Temp (C)',
        'Delta T (C)',
        'Flow (L/min)',
        'Heat Load (W)',
        'Target Heat Load (W)',
        'Alarms',
        'Status'
    ]

    def __init__(self, tcu_serial, output_dir='.'):
        self.tcu_serial = tcu_serial
        timestamp       = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename   = os.path.join(
            output_dir,
            f"TCU_test_{tcu_serial}_{timestamp}.csv"
        )
        self._file   = None
        self._writer = None

    def open(self):
        """Open CSV file and write header row."""
        self._file   = open(self.filename, 'w', newline='')
        self._writer = csv.writer(self._file)
        self._writer.writerow(self.HEADERS)
        self._file.flush()
        print(f"Logging to: {self.filename}")

    def close(self):
        """Flush and close CSV file."""
        if self._file:
            self._file.flush()
            self._file.close()
            print(f"Log saved: {self.filename}")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def write_row(self, elapsed, setpoint, inlet_temp,
                  outlet_temp, delta_t, flow,
                  heat_load, target_heat_load,
                  alarms, status):
        """Write one data row to CSV and flush immediately."""
        if not self._writer:
            return
        self._writer.writerow([
            datetime.now().strftime('%H:%M:%S'),
            f"{elapsed:.1f}",
            _fmt(setpoint),
            _fmt(inlet_temp),
            _fmt(outlet_temp),
            _fmt(delta_t),
            _fmt(flow),
            _fmt(heat_load),
            target_heat_load,
            '; '.join(alarms),
            status
        ])
        self._file.flush()

    def write_final(self, elapsed, result):
        """Write final result row as last entry in CSV."""
        if not self._writer:
            return
        self._writer.writerow([
            datetime.now().strftime('%H:%M:%S'),
            f"{elapsed:.1f}",
            '', '', '', '', '', '', '', '',
            f"FINAL RESULT: {result}"
        ])
        self._file.flush()


def _fmt(value):
    """Format value for CSV — returns empty string if None."""
    return '' if value is None else value
