# =============================================================================
# logger_thread.py — CSV Logger Thread
# =============================================================================
# Consumes samples from log_queue and writes to CSV.
# Decoupled from DAQ — slow SD card writes never block 1Hz sampling.
# =============================================================================

import csv
import os
import threading
from datetime import datetime
from queue import Queue, Empty

LOG_DIR = 'logs'

HEADERS = [
    'Timestamp', 'Elapsed (min)',
    'Setpoint (C)', 'Inlet Temp TCU (C)',
    'Flow (L/min)',
    'Voltage (V)', 'Current (A)', 'Power (W)',
    'Alarms', 'Mode', 'Status'
]


class LoggerThread(threading.Thread):
    """
    Consumes Sample objects from log_queue, writes one CSV row per sample.
    Start with start_session() to open a new CSV file.
    Stop session with end_session().
    """

    def __init__(self, log_queue: Queue):
        super().__init__(daemon=True, name="LoggerThread")
        self._queue       = log_queue
        self._stop_event  = threading.Event()
        self._file        = None
        self._writer      = None
        self._start_time  = None
        self._mode        = 'MONITOR'
        self._status      = ''
        self.filename     = ''
        self._session_active = False

    def start_session(self, tcu_serial: str, mode: str = 'MONITOR'):
        """Open a new CSV file for a logging session."""
        os.makedirs(LOG_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = os.path.join(LOG_DIR, f"TCU_{mode}_{tcu_serial}_{ts}.csv")
        self._file = open(self.filename, 'w', newline='')
        self._writer = csv.writer(self._file)
        self._writer.writerow(HEADERS)
        self._file.flush()
        self._start_time = None
        self._mode = mode
        self._session_active = True

    def end_session(self, result: str = ''):
        """Flush, write final row and close CSV."""
        if self._writer and result:
            self._writer.writerow(['', '', '', '', '', '', '', '', '', '', f'FINAL: {result}'])
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
            self._writer = None
        self._session_active = False

    def set_status(self, status: str):
        self._status = status

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                sample = self._queue.get(timeout=0.5)
                if self._session_active and self._writer:
                    self._write(sample)
            except Empty:
                continue

    def _write(self, sample):
        if self._start_time is None:
            self._start_time = sample.timestamp
        elapsed = (sample.timestamp - self._start_time) / 60.0
        ts = datetime.fromtimestamp(sample.timestamp).strftime('%H:%M:%S')

        def fmt(v):
            return '' if v is None else v

        self._writer.writerow([
            ts,
            f'{elapsed:.2f}',
            fmt(sample.setpoint),
            fmt(sample.inlet_temp),
            fmt(sample.flow_rate),
            fmt(sample.voltage),
            fmt(sample.current),
            fmt(sample.power),
            '; '.join(sample.alarms),
            self._mode,
            self._status,
        ])
        self._file.flush()
