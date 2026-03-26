# =============================================================================
# daq_thread.py — 1 Hz Data Acquisition Thread
# =============================================================================
# Reads all sensors every second and pushes samples to two queues:
#   ui_queue   (maxsize=1) — GUI gets latest sample only, never lags
#   log_queue  (unbounded) — Logger gets every sample, no drops
#
# This is the ONLY thread that touches the serial port.
# GUI and Logger never call TCUComms directly.
# =============================================================================

import time
import threading
from dataclasses import dataclass, field
from typing import Optional, List
from queue import Queue, Full


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
    pt100_inlet:    Optional[float] = None   # ESP32 node 1
    pt100_outlet:   Optional[float] = None   # ESP32 node 2
    # Derived
    delta_t:        Optional[float] = None
    heat_load:      Optional[float] = None
    delta_t_pt100:  Optional[float] = None
    heat_load_pt100: Optional[float] = None
    crosscheck_ok:  Optional[bool]  = None
    crosscheck_msg: str             = ''
    # RS232 raw log line for command log panel
    raw_log:        str             = ''


class DAQThread(threading.Thread):
    """
    1 Hz polling thread. Reads TCU + PT100 sensors, pushes Sample objects
    to ui_queue and log_queue.

    Usage:
        daq = DAQThread(tcu, sensors, ui_queue, log_queue)
        daq.start()
        ...
        daq.stop()
    """

    def __init__(self, tcu, sensors, ui_queue: Queue, log_queue: Queue,
                 parse_alarms_fn, calc_delta_t_fn, calc_heat_load_fn,
                 check_crosscheck_fn, interval: float = 1.0):
        super().__init__(daemon=True, name="DAQThread")
        self._tcu              = tcu
        self._sensors          = sensors
        self._ui_queue         = ui_queue
        self._log_queue        = log_queue
        self._parse_alarms     = parse_alarms_fn
        self._calc_delta_t     = calc_delta_t_fn
        self._calc_heat_load   = calc_heat_load_fn
        self._check_crosscheck = check_crosscheck_fn
        self._interval         = interval
        self._stop_event       = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            t0 = time.time()
            sample = self._read()
            self._push(sample)
            elapsed = time.time() - t0
            sleep_time = self._interval - elapsed
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)

    def _read(self) -> Sample:
        s = Sample(timestamp=time.time())
        log_lines = []

        # --- TCU RS232 ---
        if self._tcu and self._tcu.connected:
            s.inlet_temp = self._tcu.get_inlet_temp()
            if s.inlet_temp is not None:
                log_lines.append(f">M  <{s.inlet_temp:.2f} C$")

            s.flow_rate = self._tcu.get_flow_rate()
            if s.flow_rate is not None:
                log_lines.append(f">D  <{s.flow_rate} 1/min$")

            s.setpoint = self._tcu.get_setpoint()

            s.b1, s.b2, s.b3 = self._tcu.get_status_bytes()
            if s.b1 is not None:
                log_lines.append(f">BS <{s.b1:02X}{s.b2:02X}{s.b3:02X}$")

        s.alarms = self._parse_alarms(s.b1, s.b2, s.b3)

        # --- PT100 sensor nodes ---
        if self._sensors:
            s.pt100_inlet  = self._sensors.get_inlet_temp()
            s.pt100_outlet = self._sensors.get_outlet_temp()

        # --- Derived values ---
        s.delta_t        = self._calc_delta_t(s.inlet_temp, s.pt100_outlet)
        s.heat_load      = self._calc_heat_load(s.inlet_temp, s.pt100_outlet, s.flow_rate)
        s.delta_t_pt100  = self._calc_delta_t(s.pt100_inlet, s.pt100_outlet)
        s.heat_load_pt100 = self._calc_heat_load(s.pt100_inlet, s.pt100_outlet, s.flow_rate)
        s.crosscheck_ok, s.crosscheck_msg = self._check_crosscheck(s.inlet_temp, s.pt100_inlet)

        s.raw_log = '\n'.join(log_lines)
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
