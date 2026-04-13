# =============================================================================
# main_window.py — Top-level application window
# =============================================================================

import threading
import time
from queue import Queue

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QLabel, QStatusBar, QMessageBox
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

from gui.monitor_tab import MonitorTab
from gui.test_tab    import TestTab
from gui.styles      import APP_STYLE, DARK, ACCENT, TEXT_DIM, RED, GREEN, AMBER

from daq_thread    import DAQThread, Sample
from logger_thread import LoggerThread

from tcu_comms  import TCUComms
from pzem004t   import SDM120
from test_logic import parse_alarms, check_pass_fail

from config import (
    TCU_PORT, TCU_BAUD, LOG_DIR,
    TEMP_SETPOINT, TEMP_TOLERANCE, TEST_DURATION_MIN
)


class _Signals(QObject):
    """Helper to emit signals from non-Qt threads into Qt GUI thread."""
    new_sample   = pyqtSignal(object)   # Sample
    fill_done    = pyqtSignal()
    fill_status  = pyqtSignal(str)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TCU Controller — SSMC")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(APP_STYLE)

        # ── Queues ──────────────────────────────────────────────────────────
        self._ui_queue  = Queue(maxsize=1)
        self._log_queue = Queue()

        # ── Hardware ────────────────────────────────────────────────────────
        self._tcu     = TCUComms()
        self._sdm     = SDM120()
        self._connected = False

        # ── Threads ─────────────────────────────────────────────────────────
        self._daq_thread    = None
        self._logger_thread = LoggerThread(self._log_queue)
        self._logger_thread.start()

        # ── Test state ──────────────────────────────────────────────────────
        self._test_active  = False
        self._test_start_t = None
        self._test_serial  = ''

        # ── Signals ─────────────────────────────────────────────────────────
        self._sig = _Signals()
        self._sig.new_sample.connect(self._on_sample)
        self._sig.fill_done.connect(self._on_fill_done)
        self._sig.fill_status.connect(self._on_fill_status)

        # ── Build UI ────────────────────────────────────────────────────────
        self._build_ui()

        # ── Poll UI queue via Qt timer (60Hz) ────────────────────────────────
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._drain_ui_queue)
        self._ui_timer.start(16)  # ~60 fps

        # ── Connect to TCU on startup ────────────────────────────────────────
        QTimer.singleShot(500, self._connect_tcu)

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet(f"background: #0A0A0A; border-bottom: 1px solid #2A2A2A;")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("HAAKE ASM  ·  TCU CONTROLLER")
        title.setStyleSheet(f"color: {ACCENT}; font-size: 14px; letter-spacing: 4px; font-family: 'Courier New';")
        hl.addWidget(title)
        layout.addWidget(header)

        # Tabs
        self._tabs = QTabWidget()
        self._monitor_tab = MonitorTab()
        self._test_tab    = TestTab()
        self._tabs.addTab(self._monitor_tab, "MONITOR")
        self._tabs.addTab(self._test_tab,    "HEAT LOAD TEST")
        layout.addWidget(self._tabs)

        # Status bar
        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet(
            f"background: #0A0A0A; color: {TEXT_DIM}; font-family: 'Courier New'; font-size: 11px;")
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(f"Port: {TCU_PORT}  |  Baud: {TCU_BAUD}  |  Connecting...")

        # Wire monitor tab signals
        self._monitor_tab.sig_start.connect(self._cmd_start)
        self._monitor_tab.sig_stop.connect(self._cmd_stop)
        self._monitor_tab.sig_fill.connect(self._cmd_fill)
        self._monitor_tab.sig_precond.connect(self._cmd_precond)
        self._monitor_tab.sig_clear_alarm.connect(self._cmd_clear_alarm)
        self._monitor_tab.sig_close_valve.connect(self._cmd_close_valve)
        self._monitor_tab.sig_set_setpoint.connect(self._cmd_set_setpoint)

        # Wire test tab signals
        self._test_tab.sig_test_start.connect(self._on_test_start)
        self._test_tab.sig_test_stop.connect(self._on_test_stop)

    # ── TCU connection ────────────────────────────────────────────────────────
    def _connect_tcu(self):
        self._tcu.connect()
        sdm_status = "SDM120 ✓" if self._sdm.connected else "SDM120 ✗"
        if self._tcu.connected:
            self._connected = True
            self._monitor_tab.set_connected(True)
            self._status_bar.showMessage(
                f"TCU: {TCU_PORT} {TCU_BAUD} baud ✓  |  {sdm_status}")
            self._start_daq()
        else:
            self._monitor_tab.set_connected(False)
            self._status_bar.showMessage(
                f"TCU: {TCU_PORT} CONNECTION FAILED  |  {sdm_status}")

    def _start_daq(self):
        self._daq_thread = DAQThread(
            tcu             = self._tcu,
            sdm             = self._sdm,
            ui_queue        = self._ui_queue,
            log_queue       = self._log_queue,
            parse_alarms_fn = parse_alarms,
        )
        self._daq_thread.start()

    # ── Qt timer: drain UI queue ──────────────────────────────────────────────
    def _drain_ui_queue(self):
        try:
            sample = self._ui_queue.get_nowait()
            self._sig.new_sample.emit(sample)
        except Exception:
            pass

    def _on_sample(self, sample: Sample):
        """Received in GUI thread — update both tabs."""
        self._monitor_tab.update(sample)

        if self._test_active:
            elapsed_min = (time.time() - self._test_start_t) / 60.0
            passed, msg = check_pass_fail(
                sample.inlet_temp, sample.flow_rate,
                sample.alarms, elapsed_min
            )
            self._logger_thread.set_status(msg)
            self._test_tab.update(sample, msg, passed)

            if passed is not None:
                self._end_test(passed, msg)

    # ── TCU commands ──────────────────────────────────────────────────────────
    def _cmd_start(self):
        if self._tcu.connected:
            self._tcu.start()
            self._monitor_tab.log_command('START', '$')

    def _cmd_stop(self):
        if self._tcu.connected:
            self._tcu.stop()
            self._monitor_tab.log_command('STOP', '$')

    def _cmd_clear_alarm(self):
        if self._tcu.connected:
            self._tcu.release_alarm()
            self._monitor_tab.log_command('ER', '$')

    def _cmd_close_valve(self):
        if self._tcu.connected:
            self._tcu._send('CVE')
            self._monitor_tab.log_command('CVE', '$')

    def _cmd_set_setpoint(self, temp: float):
        if self._tcu.connected:
            self._tcu.set_setpoint(temp)
            self._monitor_tab.log_command(f'SOLL  {temp:.2f}', '$')

    def _cmd_precond(self):
        """VT — pretemperature control only (no fill)."""
        if self._tcu.connected:
            threading.Thread(
                target=self._tcu._send, args=('VT',), daemon=True).start()
            self._monitor_tab.log_command('VT', '(running...)')

    def _cmd_fill(self):
        """AFV — blocking fill. Runs in background thread."""
        if not self._tcu.connected:
            return
        self._monitor_tab.log_command('AFV', '(filling — please wait...)')
        self._status_bar.showMessage("AFV: Filling and pretemperature control in progress...")

        def _fill_worker():
            self._tcu.fill(status_callback=lambda line: self._sig.fill_status.emit(line))
            self._sig.fill_done.emit()

        threading.Thread(target=_fill_worker, daemon=True).start()

    def _on_fill_status(self, line: str):
        self._monitor_tab.log_command('AFV', line)

    def _on_fill_done(self):
        self._monitor_tab.log_command('AFV', '$ — complete')
        self._status_bar.showMessage(
            f"Port: {TCU_PORT}  |  Fill complete — system ready")

    # ── Test management ───────────────────────────────────────────────────────
    def _on_test_start(self, serial: str):
        self._test_active  = True
        self._test_start_t = time.time()
        self._test_serial  = serial
        self._logger_thread.start_session(serial, mode='TEST')
        self._test_tab.set_logfile(self._logger_thread.filename)
        self._status_bar.showMessage(
            f"Heat load test running — TCU: {serial} — 30 min")

    def _on_test_stop(self):
        self._end_test(False, 'Aborted by operator')

    def _end_test(self, passed, msg: str):
        if not self._test_active:
            return
        self._test_active = False
        result = 'PASS' if passed is True else ('FAIL' if passed is False else 'ABORTED')
        self._logger_thread.end_session(result)
        self._status_bar.showMessage(
            f"Test complete — {result}: {msg}")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self._daq_thread:
            self._daq_thread.stop()
        self._logger_thread.stop()
        if self._tcu:
            self._tcu.disconnect()
        event.accept()
