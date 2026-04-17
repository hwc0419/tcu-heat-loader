# =============================================================================
# daq_thread.py — Configurable Rate Data Acquisition Thread
# =============================================================================
# Reads all sensors at a configurable interval and pushes samples to:
#   ui_queue   (maxsize=1) — GUI gets latest sample only, never lags
#   log_queue  (unbounded) — Logger gets every sample, no drops
#   ipc        (IPCWriter) — Web server gets latest sample for phone dashboard
#
# Poll interval is configurable at runtime via set_interval().
# This is the ONLY thread that touches the serial port.
# GUI and Logger never call TCUComms directly.
# =============================================================================

import time
import threading
from dataclasses import dataclass, field
from typing import Optional, List
from queue import Queue, Full

from test_logic import decode_status, is_abnormal
from ipc import IPCWriter


@dataclass
class Sample:
    """One complete sensor reading at a point in time."""
    timestamp:      float           # time.time()
    inlet_temp:     Optional[float] = None   # TCU RS232 M command
    flow_rate:      Optional[float] = None   # TCU RS232 D command
    setpoint:       Optional[float] = None   # TCU RS232 SOLL command
    b1:             Optional[int]   = None   # status byte 1
    b2:             Optional[int]   = None   # status byte 2
    b3:             Optional[int]   = None   # status byte 3
    alarms:         List[str]       = field(default_factory=lambda: ['No alarms'])
    # PZEM004T energy meter
    voltage:        Optional[float] = None   # V
    current:        Optional[float] = None   # A
    power:          Optional[float] = None   # W (true watts — handles SCR load)
    # RS232 raw log line for command log panel
    raw_log:        str             = ''
    # Human-readable decoded status for command log
    decoded_log:    list            = field(default_factory=list)
    # True if any condition is abnormal — used for log highlighting
    is_abnormal:    bool            = False


def _sample_to_dict(s: Sample) -> dict:
    """Convert Sample dataclass to JSON-serialisable dict for IPC."""
    return {
        'timestamp':    s.timestamp,
        'inlet_temp':   s.inlet_temp,
        'flow_rate':    s.flow_rate,
        'setpoint':     s.setpoint,
        'b1':           s.b1,
        'b2':           s.b2,
        'b3':           s.b3,
        'alarms':       s.alarms,
        'voltage':      s.voltage,
        'current':      s.current,
        'power':        s.power,
        'is_abnormal':  s.is_abnormal,
        'decoded_log':  s.decoded_log,
    }


class DAQThread(threading.Thread):
    """
    Configurable rate polling thread. Reads TCU + PZEM sensors, pushes
    Sample objects to ui_queue, log_queue and IPC (web server).

    Poll interval is set at construction from settings_manager and can be
    updated at runtime via set_interval() without restarting the thread.

    Usage:
        daq = DAQThread(tcu, pzem, ui_queue, log_queue, parse_alarms_fn)
        daq.start()
        daq.set_interval(2.0)   # change to 2 seconds on the fly
        daq.stop()
    """

    def __init__(self, tcu, pzem, ui_queue: Queue, log_queue: Queue,
                 parse_alarms_fn, interval: float = 1.0):
        super().__init__(daemon=True, name='DAQThread')
        self._tcu              = tcu
        self._pzem             = pzem
        self._ui_queue         = ui_queue
        self._log_queue        = log_queue
        self._parse_alarms     = parse_alarms_fn
        self._interval         = interval
        self._interval_lock    = threading.Lock()
        self._stop_event       = threading.Event()
        self._ipc              = IPCWriter()

    def stop(self):
        self._stop_event.set()
        self._ipc.close()

    def set_interval(self, seconds: float):
        """Update poll interval live — takes effect on next cycle."""
        with self._interval_lock:
            self._interval = max(0.5, float(seconds))

    def run(self):
        while not self._stop_event.is_set():
            t0 = time.time()
            sample = self._read()
            self._push(sample)
            with self._interval_lock:
                interval = self._interval
            elapsed = time.time() - t0
            sleep_time = interval - elapsed
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)

    def _read(self) -> Sample:
        s = Sample(timestamp=time.time())
        log_lines = []

        # --- TCU RS232 ---
        if self._tcu and self._tcu.connected:
            s.inlet_temp = self._tcu.get_inlet_temp()
            if s.inlet_temp is not None:
                log_lines.append(f'>M  <{s.inlet_temp:.2f} C$')

            s.flow_rate = self._tcu.get_flow_rate()
            if s.flow_rate is not None:
                log_lines.append(f'>D  <{s.flow_rate} 1/min$')

            s.setpoint = self._tcu.get_setpoint()

            s.b1, s.b2, s.b3 = self._tcu.get_status_bytes()
            if s.b1 is not None:
                log_lines.append(f'>BS <{s.b1:02X}{s.b2:02X}{s.b3:02X}$')

        s.alarms = self._parse_alarms(s.b1, s.b2, s.b3)

        # --- PZEM004T energy meter ---
        if self._pzem and self._pzem.connected:
            s.voltage, s.current, s.power = self._pzem.get_all()

        s.raw_log     = '\n'.join(log_lines)
        s.decoded_log = decode_status(
            s.b1, s.b2, s.b3,
            inlet_temp=s.inlet_temp,
            flow=s.flow_rate,
            setpoint=s.setpoint,
        )
        s.is_abnormal = is_abnormal(
            s.b1, s.b2, s.b3,
            inlet_temp=s.inlet_temp,
            setpoint=s.setpoint,
            flow=s.flow_rate,
        )
        return s

    def _push(self, sample: Sample):
        # GUI queue — drop oldest if full (always shows latest)
        try:
            self._ui_queue.put_nowait(sample)
        except Full:
            try:
                self._ui_queue.get_nowait()
            except Exception:
                pass
            try:
                self._ui_queue.put_nowait(sample)
            except Exception:
                pass

        # Log queue — never drop
        self._log_queue.put(sample)

        # IPC — web server gets latest sample (write errors are non-fatal)
        try:
            self._ipc.write(_sample_to_dict(sample))
        except Exception as e:
            print(f'IPC write error: {e}')
