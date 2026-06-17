# =============================================================================
# main_window.py — Top-level application window
# =============================================================================

import audit_logger
import threading
import time
from queue import Queue

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QLabel, QStatusBar, QMessageBox, QPushButton
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

from gui.monitor_tab       import MonitorTab
from gui.sequence_test_tab import SequenceTestTab
from gui.settings_tab      import SettingsTab
from gui.docs_tab          import DocsTab
from gui.heater_tab        import HeaterTab
from gui.stress_test_tab   import StressTestTab
from gui.styles            import get_app_style, ACCENT, RED, GREEN, AMBER

from settings_manager import settings
from translations     import tr

from daq_thread    import DAQThread, Sample
from logger_thread import LoggerThread

from tcu       import TCU
from pzem004t  import PZEM004T
from heater    import Heater
from test_logic   import parse_alarms

from config import (
    TCU_PORT, TCU_BAUD, LOG_DIR, WINDOWS
)


class _Signals(QObject):
    """Helper to emit signals from non-Qt threads into Qt GUI thread."""
    new_sample   = pyqtSignal(object)   # Sample
    fill_done    = pyqtSignal()
    fill_status  = pyqtSignal(str)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TCU++ — SSMC")

        # ── Dynamic scaling based on screen resolution ───────────────────────
        # Reference resolution: 1920px wide (full HD)
        # Scale clamped between 0.65 (small laptop) and 1.0 (full HD+)
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        scale  = max(0.65, min(1.0, screen.width() / 1920))
        self.setMinimumSize(int(800 * scale), int(550 * scale))
        self.setStyleSheet(get_app_style(scale))
        self._scale = scale

        # ── Queues ──────────────────────────────────────────────────────────
        self._ui_queue  = Queue(maxsize=1)
        self._log_queue = Queue()

        # ── Hardware ────────────────────────────────────────────────────────
        self._tcu      = TCU()
        self._pzem     = PZEM004T()
        self._heater   = Heater()
        self._connected = False
        # Attempt heater connection — non-fatal if hardware not present
        self._heater.connect()

        # ── Threads ─────────────────────────────────────────────────────────
        self._daq_thread    = None
        self._logger_thread = LoggerThread(self._log_queue)
        self._logger_thread.start()

        # ── Test state ──────────────────────────────────────────────────────
        self._test_active    = False
        self._test_start_t   = None
        self._test_serial    = ''

        # ── RPi priority / inactivity ────────────────────────────────────────
        self._rpi_active        = False
        self._last_interaction  = 0.0   # monotonic time of last interaction
        self._inactivity_timer  = QTimer(self)
        self._inactivity_timer.setInterval(1000)   # tick every second
        self._inactivity_timer.timeout.connect(self._on_inactivity_tick)
        self._inactivity_timer.start()

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

        # ── Register settings callback for live updates ───────────────────────
        settings.register_callback(self._on_settings_changed)

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
        header.setFixedHeight(int(44 * self._scale))
        self._header = header  # keep ref for theme reload
        self._update_header_style()
        hl = QVBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("HAAKE ASM  ·  TCU++")
        self._title_label = title
        self._update_title_style()
        hl.addWidget(title)
        layout.addWidget(header)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.tabBar().setExpanding(False)
        self._monitor_tab     = MonitorTab(scale=self._scale)
        self._seq_test_tab    = SequenceTestTab(scale=self._scale)
        self._heater_tab      = HeaterTab(scale=self._scale)
        self._stress_test_tab = StressTestTab(scale=self._scale)
        self._settings_tab    = SettingsTab(scale=self._scale)
        self._docs_tab        = DocsTab(scale=self._scale)
        self._tabs.addTab(self._monitor_tab,     tr('tab_monitor'))
        self._tabs.addTab(self._seq_test_tab,    tr('tab_test'))
        self._tabs.addTab(self._heater_tab,      tr('tab_heater'))
        self._tabs.addTab(self._stress_test_tab, tr('tab_response'))
        self._tabs.addTab(self._settings_tab,    tr('tab_settings'))
        self._tabs.addTab(self._docs_tab,        tr('tab_docs'))

        # Emergency stop button — fixed bottom-right, always visible
        self._estop_btn = QPushButton(tr('estop_btn'))
        self._estop_btn.setObjectName('btn_estop')
        self._estop_btn.setFixedSize(int(90 * self._scale), int(64 * self._scale))
        self._estop_btn.clicked.connect(self._on_estop)

        # Stack tabs and estop button in same area
        from PyQt5.QtWidgets import QStackedLayout
        tab_container = QWidget()
        tab_container.setLayout(QVBoxLayout())
        tab_container.layout().setContentsMargins(0, 0, 0, 0)
        tab_container.layout().addWidget(self._tabs)
        layout.addWidget(tab_container)

        # Position estop button over bottom-right corner
        self._estop_btn.setParent(central)
        self._estop_btn.raise_()
        self._tabs.resizeEvent = self._on_tabs_resize

        # Wire settings signals
        self._settings_tab.sig_theme_changed.connect(self._on_theme_changed)
        self._settings_tab.sig_language_changed.connect(self._on_language_changed)
        self._settings_tab.sig_ports_changed.connect(self._on_ports_changed)
        self._settings_tab.sig_user_removed.connect(self._on_user_removed)

        # Status bar
        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet(
            f"font-family: 'Courier New'; "
            f"font-size: {max(8, round(11 * self._scale))}px;")
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(f"Port: {TCU_PORT}  |  Baud: {TCU_BAUD}  |  Connecting...")

        # RPi priority countdown label (hidden until active)
        self._priority_lbl = QLabel('')
        self._priority_lbl.setStyleSheet('color: #F59E0B; font-weight: bold;')
        self._status_bar.addPermanentWidget(self._priority_lbl)

        # Release control button (hidden until RPi is active)
        self._release_btn = QPushButton('Release Control')
        self._release_btn.setObjectName('btn_fill')
        self._release_btn.setFixedHeight(22)
        self._release_btn.setVisible(False)
        self._release_btn.clicked.connect(self._on_release_control)
        self._status_bar.addPermanentWidget(self._release_btn)

        # Wire monitor tab signals
        self._monitor_tab.sig_start.connect(self._cmd_start)
        self._monitor_tab.sig_stop.connect(self._cmd_stop)
        self._monitor_tab.sig_fill.connect(self._cmd_fill)
        self._monitor_tab.sig_precond.connect(self._cmd_precond)
        self._monitor_tab.sig_clear_alarm.connect(self._cmd_clear_alarm)
        self._monitor_tab.sig_close_valve.connect(self._cmd_close_valve)
        self._monitor_tab.sig_set_setpoint.connect(self._cmd_set_setpoint)

        # Wire sequence test tab signals (2kW heat load sequence test)
        self._seq_test_tab.sig_test_start.connect(self._on_test_start)
        self._seq_test_tab.sig_test_stop.connect(self._on_test_stop)
        self._seq_test_tab.sig_set_k.connect(self._cmd_set_k)

        # Wire heater tab signals
        self._heater_tab.sig_set_watts.connect(self._cmd_set_heater_watts)

        # Wire stress test tab signals (AMAT0 burst-and-decay test)
        self._stress_test_tab.sig_test_start.connect(self._on_stress_test_start)
        self._stress_test_tab.sig_test_stop.connect(self._on_stress_test_stop)

    def _on_tabs_resize(self, event):
        """Reposition estop button on tab widget resize."""
        r   = self._tabs.rect()
        btn = self._estop_btn
        btn.move(r.width() - btn.width() - 12,
                 r.height() - btn.height() - 12)
        QTabWidget.resizeEvent(self._tabs, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_estop_btn') and hasattr(self, '_tabs'):
            r   = self._tabs.geometry()
            btn = self._estop_btn
            btn.move(r.right()  - btn.width()  - 12,
                     r.bottom() - btn.height() - 12)

    # ── Emergency stop ────────────────────────────────────────────────────────
    # ── RPi priority / inactivity ─────────────────────────────────────────────
    def record_interaction(self):
        """Call on any desktop user interaction to reset inactivity timer."""
        self._last_interaction = time.monotonic()
        if not self._rpi_active:
            self._rpi_active = True
            self._release_btn.setVisible(True)
            if self._daq_thread:
                self._daq_thread.set_rpi_active(True)

    def _on_inactivity_tick(self):
        """Called every second — checks inactivity timeout."""
        if not self._rpi_active:
            self._priority_lbl.setText('')
            return
        timeout_sec = settings.get('rpi_inactivity_timeout_min') * 60
        elapsed     = time.monotonic() - self._last_interaction
        remaining   = max(0.0, timeout_sec - elapsed)
        mm, ss      = divmod(int(remaining), 60)
        self._priority_lbl.setText(f'Control releases in {mm:02d}:{ss:02d}')
        if remaining <= 0:
            self._on_release_control()

    def _on_user_removed(self, username: str):
        """Notify web server to immediately invalidate removed user's session."""
        if not isinstance(username, str) or not username:
            return
        import urllib.request, json as _json
        try:
            payload = _json.dumps({'username': username}).encode()
            req     = urllib.request.Request(
                'http://127.0.0.1:5000/api/admin/invalidate_user',
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST')
            urllib.request.urlopen(req, timeout=2)
        except Exception as e:
            print(f"MainWindow: could not invalidate web session for {username}: {e}")

    def _on_release_control(self):
        self._rpi_active = False
        self._release_btn.setVisible(False)
        self._priority_lbl.setText('')
        if self._daq_thread:
            self._daq_thread.set_rpi_active(False)

    def _on_estop(self):
        reply = QMessageBox.question(
            self, tr('estop_title'), tr('estop_msg'),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'EMERGENCY STOP', '')
        # Heater off FIRST — always before TCU stop
        self._heater_tab.emergency_off()
        ok = self._heater.emergency_off()
        if not ok:
            print("MainWindow: heater emergency_off Modbus failed")
        # TCU stop
        self._cmd_stop()
        # Abort active tests
        if self._test_active:
            self._on_test_stop()
        self._seq_test_tab.on_tcu_abnormal()
        self._stress_test_tab.on_tcu_abnormal()

    # ── Heater command ────────────────────────────────────────────────────────
    def _cmd_set_k(self, k: int):
        """
        Set PLC K constant directly — used by the 2kW sequence test.
        Emits sig_k_confirmed back to seq_test_tab when PLC confirms receipt,
        so settle timing starts from actual confirmation, not command send.
        """
        if not isinstance(k, int):
            return
        if not self._heater.is_connected():
            print(f'Test: SET K={k} → NOT CONNECTED (check PLC port in settings)')
            return
        ok = self._heater.set_k(k)
        if ok:
            self._seq_test_tab.sig_k_confirmed.emit(k)
        else:
            print(f'Test: SET K={k} → FAILED')

    def _cmd_set_heater_watts(self, watts: int):
        """Send watt setpoint to heater via Modbus."""
        if not isinstance(watts, int):
            return
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'HEATER SETPOINT', f'{watts}W')
        if not self._heater.is_connected():
            self._heater_tab.log_modbus_response(
                f'SET {watts}W → NOT CONNECTED (check heater port in settings)')
            return
        ok  = self._heater.set_watts(watts)
        msg = f'SET {watts}W → {"OK" if ok else "FAILED"}'
        self._heater_tab.log_modbus_response(msg)
        if ok:
            self._heater_tab.update_setpoint_watts(watts)
    def _connect_tcu(self):
        self._tcu.connect()
        pzem_status = "PZEM004T ✓" if self._pzem.connected else "PZEM004T ✗"
        if self._tcu.connected:
            self._connected = True
            self._monitor_tab.set_connected(True)
            self._status_bar.showMessage(
                f"TCU: {TCU_PORT} {TCU_BAUD} baud ✓  |  {pzem_status}")
            self._start_daq()
        else:
            self._monitor_tab.set_connected(False)
            self._status_bar.showMessage(
                f"TCU: {TCU_PORT} CONNECTION FAILED  |  {pzem_status}")

    def _start_daq(self):
        self._daq_thread = DAQThread(
            tcu             = self._tcu,
            pzem            = self._pzem,
            ui_queue        = self._ui_queue,
            log_queue       = self._log_queue,
            parse_alarms_fn = parse_alarms,
            interval        = float(settings.get('poll_interval', 1)),
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
        """Received in GUI thread — update all tabs."""
        self._monitor_tab.update(sample)
        self._heater_tab.update_sample(sample)
        self._stress_test_tab.update_sample(sample)
        self._seq_test_tab.update_sample(sample)

        # Auto-off heater if BS != 0x400400 (TCU abnormal)
        if sample.b1 is not None:
            bs = (sample.b1 << 16) | ((sample.b2 or 0) << 8) | (sample.b3 or 0)
            if bs != 0x400400:
                ok = self._heater.emergency_off()
                if not ok:
                    print("MainWindow: heater auto-off on TCU abnormal failed")
                self._heater_tab.emergency_off()
                self._stress_test_tab.on_tcu_abnormal()
                self._seq_test_tab.on_tcu_abnormal()

    # ── TCU commands ──────────────────────────────────────────────────────────
    def _cmd_start(self):
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'TCU START', '')
        if self._tcu.connected:
            self._tcu.start()
            self._monitor_tab.log_command('START', '$')

    def _cmd_stop(self):
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'TCU STOP', '')
        if self._tcu.connected:
            self._tcu.stop()
            self._monitor_tab.log_command('STOP', '$')

    def _cmd_clear_alarm(self):
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'TCU CLEAR ALARM', '')
        if self._tcu.connected:
            self._tcu.release_alarm()
            self._monitor_tab.log_command('ER', '$')

    def _cmd_close_valve(self):
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'TCU CLOSE VALVE', '')
        if self._tcu.connected:
            self._tcu._send('CVE')
            self._monitor_tab.log_command('CVE', '$')

    def _cmd_set_setpoint(self, temp: float):
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'TCU SET SETPOINT', f'{temp:.2f}°C')
        if self._tcu.connected:
            self._tcu.set_setpoint(temp)
            self._monitor_tab.log_command(f'SOLL  {temp:.2f}', '$')

    def _cmd_precond(self):
        """VT — pretemperature control only (no fill)."""
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'TCU PRECOND', '')
        if self._tcu.connected:
            threading.Thread(
                target=self._tcu._send, args=('VT',), daemon=True).start()
            self._monitor_tab.log_command('VT', '(running...)')

    def _cmd_fill(self):
        """AFV — blocking fill. Runs in background thread."""
        self.record_interaction()
        audit_logger.log('Desktop', 'desktop', 'TCU FILL', '')
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
        self._status_bar.showMessage(f"Sequence test running — TCU: {serial}")

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

    def _on_stress_test_start(self):
        """AMAT0 stress test Start button — send TCU start command, then logging
        begins on the tab's own timer (update_sample feeds it per-second data)."""
        self._tcu.start()
        self._status_bar.showMessage("AMAT0 stress test running")

    def _on_stress_test_stop(self):
        self._status_bar.showMessage("AMAT0 stress test stopped")

    # ── Settings hot reload ───────────────────────────────────────────────────
    def _update_header_style(self):
        theme = settings.get('theme', 'light')
        if theme == 'dark':
            self._header.setStyleSheet("background: #0A0A0A; border-bottom: 1px solid #2A2A2A;")
        else:
            self._header.setStyleSheet("background: #E0E0E0; border-bottom: 1px solid #CCCCCC;")

    def _update_title_style(self):
        self._title_label.setStyleSheet(
            f"color: {ACCENT}; font-size: {max(10, round(14 * self._scale))}px; "
            f"letter-spacing: {max(1, round(4 * self._scale))}px; font-family: 'Courier New';")

    def _on_theme_changed(self, theme: str):
        """Hot reload stylesheet when theme changes."""
        self.setStyleSheet(get_app_style(self._scale, theme=theme))
        self._update_header_style()

    def _on_language_changed(self, lang: str):
        """Hot reload all tab labels and UI strings when language changes."""
        self._monitor_tab.retranslate()
        self._seq_test_tab.retranslate()
        self._settings_tab.retranslate()
        self._heater_tab.retranslate()
        self._stress_test_tab.retranslate()
        # Update tab bar labels
        self._tabs.setTabText(0, tr('tab_monitor'))
        self._tabs.setTabText(1, tr('tab_test'))
        self._tabs.setTabText(2, tr('tab_heater'))
        self._tabs.setTabText(3, tr('tab_response'))
        self._tabs.setTabText(4, tr('tab_settings'))
        self._tabs.setTabText(5, tr('tab_docs'))
        self._estop_btn.setText(tr('estop_btn'))

    def _on_ports_changed(self):
        """Notify user that port changes take effect on next connection."""
        self._status_bar.showMessage(
            "Port settings updated — reconnect TCU to apply")

    def _on_settings_changed(self, key, value):
        """Called by settings_manager for any setting change — update live."""
        audit_logger.log('Desktop', 'desktop', f'SETTING CHANGED: {key}', str(value))
        # Update DAQ poll interval immediately
        if key == 'poll_interval' and self._daq_thread is not None:
            self._daq_thread.set_interval(float(value))
        # Refresh both tabs on any test parameter change
        if key in ('temp_setpoint', 'temp_tolerance', 'test_duration', 'poll_interval'):
            self._monitor_tab.refresh_settings()
            self._seq_test_tab.refresh_settings()

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self._daq_thread:
            self._daq_thread.stop()
        self._logger_thread.stop()
        if self._tcu:
            self._tcu.disconnect()
        event.accept()
