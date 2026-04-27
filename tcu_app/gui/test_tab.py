# =============================================================================
# test_tab.py — Mode 2: Heat Load Test
# =============================================================================

import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QTextEdit,
    QLineEdit, QProgressBar, QSizePolicy, QDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg
from collections import deque
from datetime import datetime

from gui.styles import PANEL, SURFACE, BORDER, ACCENT, GREEN, RED, AMBER, TEXT, TEXT_DIM
from gui.graph_utils import make_graph_panel
from settings_manager import settings
from translations import tr

def _get_window():
    """Return graph window size in samples based on current test duration."""
    return settings.get('test_duration') * 60

class TestTab(QWidget):
    """
    Heat load test panel — pass/fail test.
    Operator enters TCU serial, starts test, monitors progress.
    """

    sig_test_start = pyqtSignal(str)   # emits tcu_serial
    sig_test_stop  = pyqtSignal()

    def __init__(self, scale: float = 1.0, parent=None):
        self._scale = scale
        super().__init__(parent)
        self._test_active  = False
        self._start_time   = None
        self._t0_graph     = None
        self._result       = None
        self._banner_state = 'ready'
        self._banner_msg   = ''

        self._times      = deque(maxlen=_get_window())
        self._temps      = deque(maxlen=_get_window())
        self._heat_loads = deque(maxlen=_get_window())
        self._heat_times = deque(maxlen=_get_window())
        self._flow_times = deque(maxlen=_get_window())
        self._flow_vals  = deque(maxlen=_get_window())

        self._build_ui()
        self._setup_graph()
        self._build_popup_graphs()

        # Timer updates elapsed display every second
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Left: graph + readings ─────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(8)

        # Test status banner
        self.banner = QLabel(tr("ready_msg"))
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setObjectName("status_warn")
        self.banner.setMinimumHeight(int(36 * self._scale))
        self.banner.setStyleSheet(f"""
            background: {SURFACE};
            border: 1px solid {BORDER};
            font-size: 13px;
            letter-spacing: 2px;
            padding: 6px;
        """)
        left.addWidget(self.banner)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, settings.get('test_duration') * 60)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        left.addWidget(self.progress)

        # Live readings grid
        self._grp_readings = QGroupBox(tr("live_readings"))
        readings_box = self._grp_readings
        rg = QGridLayout(readings_box)
        rg.setSpacing(10)

        def reading(label):
            l = QLabel(label)
            l.setObjectName("label_dim")
            v = QLabel("---")
            v.setObjectName("val_medium")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return l, v

        self.lbl_elapsed,   self.val_elapsed   = reading(tr("elapsed"))
        self.lbl_remaining, self.val_remaining = reading(tr("remaining"))
        self.lbl_temp,      self.val_temp      = reading(tr("inlet_temp"))
        self.lbl_sp,        self.val_sp        = reading(tr("setpoint"))
        self.lbl_flow,      self.val_flow      = reading(tr("flow_rate"))
        self.lbl_voltage,   self.val_voltage   = reading(tr("voltage"))
        self.lbl_current,   self.val_current   = reading(tr("current"))
        self.lbl_power,     self.val_power     = reading(tr("power"))
        self.lbl_alarm,     self.val_alarm     = reading(tr("alarms"))

        rows = [
            (self.lbl_elapsed,   self.val_elapsed),
            (self.lbl_remaining, self.val_remaining),
            (self.lbl_temp,      self.val_temp),
            (self.lbl_sp,        self.val_sp),
            (self.lbl_flow,      self.val_flow),
            (self.lbl_voltage,   self.val_voltage),
            (self.lbl_current,   self.val_current),
            (self.lbl_power,     self.val_power),
            (self.lbl_alarm,     self.val_alarm),
        ]
        for i, (l, v) in enumerate(rows):
            rg.addWidget(l, i, 0)
            rg.addWidget(v, i, 1)

        left.addWidget(readings_box)

        # Graph popup button (replaces inline graph)
        self._btn_graphs = QPushButton("📈 Show Graphs")
        self._btn_graphs.setObjectName('btn_fill')
        self._btn_graphs.clicked.connect(self._on_show_graphs)
        left.addWidget(self._btn_graphs)
        left.addWidget(graph_box, stretch=1)

        root.addLayout(left, stretch=3)

        # ── Right: controls ────────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        # Serial number input
        self._grp_serial = QGroupBox(tr("tcu_serial"))
        serial_box = self._grp_serial
        sg = QVBoxLayout(serial_box)
        self.edit_serial = QLineEdit()
        self.edit_serial.setPlaceholderText(tr("serial_ph"))
        sg.addWidget(self.edit_serial)
        right.addWidget(serial_box)

        # Test controls
        self._grp_ctrl = QGroupBox(tr("test_controls"))
        ctrl_box = self._grp_ctrl
        cg = QVBoxLayout(ctrl_box)
        cg.setSpacing(10)

        self.btn_test_start = QPushButton(tr("btn_test_start"))
        self.btn_test_start.setObjectName("btn_test_start")
        self.btn_test_stop  = QPushButton(tr("btn_test_stop"))
        self.btn_test_stop.setObjectName("btn_test_stop")
        self.btn_test_stop.setEnabled(False)

        cg.addWidget(self.btn_test_start)
        cg.addWidget(self.btn_test_stop)
        right.addWidget(ctrl_box)

        # Pass/fail criteria reminder
        self._grp_criteria = QGroupBox(tr("pass_criteria"))
        criteria_box = self._grp_criteria
        cr = QVBoxLayout(criteria_box)
        from settings_manager import settings as _s
        self.lbl_crit = QLabel()
        self.lbl_crit.setObjectName("label_dim")
        self.lbl_crit.setWordWrap(True)
        self._refresh_criteria()
        cr.addWidget(self.lbl_crit)
        right.addWidget(criteria_box)

        # Result display
        self._grp_result = QGroupBox(tr("test_result"))
        result_box = self._grp_result
        rr = QVBoxLayout(result_box)
        self.lbl_result = QLabel("—")
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setObjectName("val_large")
        self.lbl_result.setMinimumHeight(int(60 * self._scale))
        rr.addWidget(self.lbl_result)
        self.lbl_result_reason = QLabel("")
        self.lbl_result_reason.setAlignment(Qt.AlignCenter)
        self.lbl_result_reason.setWordWrap(True)
        self.lbl_result_reason.setObjectName("label_dim")
        rr.addWidget(self.lbl_result_reason)
        right.addWidget(result_box)

        # Log file path
        self._grp_log = QGroupBox(tr("log_file"))
        log_box = self._grp_log
        ll = QVBoxLayout(log_box)
        self.lbl_logfile = QLabel(tr("not_started"))
        self.lbl_logfile.setObjectName("label_dim")
        self.lbl_logfile.setWordWrap(True)
        ll.addWidget(self.lbl_logfile)
        right.addWidget(log_box)

        right.addStretch()
        root.addLayout(right, stretch=1)

        # Wire buttons
        self.btn_test_start.clicked.connect(self._on_start)
        self.btn_test_stop.clicked.connect(self._on_stop)

    def _setup_graph(self):
        """No-op — graph lives in popup dialog."""
        pass

    def _build_popup_graphs(self):
        """Build popup dialog with temperature + flow rate graphs."""
        self._popup = QDialog(self)
        self._popup.setWindowTitle('Test Graphs')
        self._popup.setMinimumSize(700, 500)
        v = QVBoxLayout(self._popup)

        temp_panel, self._popup_plot_temp, _ = make_graph_panel(
            'TCU Inlet Temperature', self._scale)
        self._popup_plot_temp.setLabel('left',   'Temperature', units='°C')
        self._popup_plot_temp.setLabel('bottom', 'Elapsed',     units='min')
        self._popup_plot_temp.showGrid(x=True, y=True, alpha=0.2)
        self._popup_plot_temp.addLegend()
        self._curve_tcu = self._popup_plot_temp.plot(
            pen=pg.mkPen(color=ACCENT, width=2), name='TCU Inlet')

        # Threshold lines
        sp  = settings.get('temp_setpoint')
        tol = settings.get('temp_tolerance')
        self._sp_hi = pg.InfiniteLine(
            angle=0, pos=sp + tol,
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine))
        self._sp_lo = pg.InfiniteLine(
            angle=0, pos=sp - tol,
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine))
        self._popup_plot_temp.addItem(self._sp_hi)
        self._popup_plot_temp.addItem(self._sp_lo)
        v.addWidget(temp_panel)

        flow_panel, self._popup_plot_flow, _ = make_graph_panel(
            'Flow Rate', self._scale)
        self._popup_plot_flow.setLabel('left',   'Flow rate', units='ℓ/min')
        self._popup_plot_flow.setLabel('bottom', 'Elapsed',   units='min')
        self._popup_plot_flow.showGrid(x=True, y=True, alpha=0.2)
        self._curve_flow = self._popup_plot_flow.plot(
            pen=pg.mkPen(color='#2196F3', width=2), name='Flow rate')
        v.addWidget(flow_panel)

    def _on_show_graphs(self):
        """Show popup with live test graphs."""
        self._popup.show()
        self._popup.raise_()

    # ── Button handlers ───────────────────────────────────────────────────────
    def _on_start(self):
        serial = self.edit_serial.text().strip()
        if not serial:
            self.banner.setText(tr("enter_serial"))
            return
        self._test_active = True
        self._start_time  = time.time()
        self._t0_graph    = None
        self._result      = None
        self._times.clear(); self._temps.clear()
        self.btn_test_start.setEnabled(False)
        self.btn_test_stop.setEnabled(True)
        self.edit_serial.setEnabled(False)
        self.lbl_result.setText("—")
        self.lbl_result_reason.setText("")
        self.progress.setValue(0)
        self._timer.start(1000)
        self.sig_test_start.emit(serial)
        self._update_banner('running', '')

    def _on_stop(self):
        self.sig_test_stop.emit()
        self._end_test('ABORTED', 'Stopped by operator')

    def retranslate(self):
        """Update all labels and group box titles to current language."""
        # Group box titles
        self._grp_readings.setTitle(tr('live_readings'))
        self._grp_serial.setTitle(tr('tcu_serial'))
        self._grp_ctrl.setTitle(tr('test_controls'))
        self._grp_criteria.setTitle(tr('pass_criteria'))
        self._grp_result.setTitle(tr('test_result'))
        self._grp_log.setTitle(tr('log_file'))
        # Reading labels
        self.lbl_elapsed.setText(tr('elapsed'))
        self.lbl_remaining.setText(tr('remaining'))
        self.lbl_temp.setText(tr('inlet_temp'))
        self.lbl_sp.setText(tr('setpoint'))
        self.lbl_flow.setText(tr('flow_rate'))
        self.lbl_voltage.setText(tr('voltage'))
        self.lbl_current.setText(tr('current'))
        self.lbl_power.setText(tr('power'))
        self.lbl_alarm.setText(tr('alarms'))
        # Buttons
        self.btn_test_start.setText(tr('btn_test_start'))
        self.btn_test_stop.setText(tr('btn_test_stop'))
        self.edit_serial.setPlaceholderText(tr('serial_ph'))
        self._refresh_criteria()
        # Re-render banner in current language
        self._update_banner(self._banner_state, self._banner_msg)

    def _refresh_criteria(self):
        """Update the pass/fail criteria label from current settings."""
        sp  = settings.get('temp_setpoint')
        tol = settings.get('temp_tolerance')
        dur = settings.get('test_duration')
        self.lbl_crit.setText(
            f"✓  Inlet temp {sp}°C ± {tol}°C\n"
            f"    for full {dur} minutes\n\n"
            f"✓  Flow rate ≥ 1 ℓ/min\n"
            f"    continuously\n\n"
            f"✓  No TCU alarms\n"
            f"    (BS = 400400)\n\n"
            f"✓  Test duration {dur} min\n"
            f"    completed without abort"
        )

    def refresh_settings(self):
        """
        Called by main_window when settings are applied.
        Updates all widgets that depend on configurable test parameters.
        """
        sp  = settings.get('temp_setpoint')
        tol = settings.get('temp_tolerance')
        dur = settings.get('test_duration')

        # Update criteria label
        self._refresh_criteria()

        # Update progress bar range
        self.progress.setRange(0, dur * 60)

        # Update tolerance band lines on graph
        self._sp_hi.setValue(sp + tol)
        self._sp_lo.setValue(sp - tol)

        # Update setpoint reference line if it exists
        if hasattr(self, '_setpoint_line'):
            self._setpoint_line.setValue(sp)

    def _tick(self):
        """Called every second to update elapsed/remaining display."""
        if not self._test_active or self._start_time is None:
            return
        elapsed_s = time.time() - self._start_time
        elapsed_m = elapsed_s / 60.0
        remaining_m = max(0, settings.get('test_duration') - elapsed_m)
        self.val_elapsed.setText(f"{elapsed_m:.1f} min")
        self.val_remaining.setText(f"{remaining_m:.1f} min")
        self.progress.setValue(int(min(elapsed_s, settings.get('test_duration') * 60)))

    # ── Public: called by main window ─────────────────────────────────────────
    def update(self, sample, status_msg: str = '', passed=None):
        """Update readings and graph from DAQ sample."""
        if self._t0_graph is None:
            self._t0_graph = sample.timestamp

        t_min = (sample.timestamp - self._t0_graph) / 60.0

        # Always update graph
        if sample.inlet_temp is not None:
            self._times.append(t_min)
            self._temps.append(sample.inlet_temp)
            self._curve_tcu.setData(list(self._times), list(self._temps))

        if sample.flow_rate is not None:
            self._flow_times.append(t_min)
            self._flow_vals.append(sample.flow_rate)
            self._curve_flow.setData(list(self._flow_times), list(self._flow_vals))

        # Only update readings and pass/fail when test is active
        if not self._test_active:
            return

        def fmt_temp(v): return f"{v:.2f} °C" if v is not None else "---"
        def fmt_flow(v): return f"{v:.1f} ℓ/min" if v is not None else "---"

        self.val_temp.setText(fmt_temp(sample.inlet_temp))
        self.val_sp.setText(fmt_temp(sample.setpoint))
        self.val_flow.setText(fmt_flow(sample.flow_rate))
        self.val_voltage.setText(f"{sample.voltage:.1f} V"  if sample.voltage is not None else "---")
        self.val_current.setText(f"{sample.current:.3f} A"  if sample.current is not None else "---")
        self.val_power.setText(  f"{sample.power:.1f} W"    if sample.power   is not None else "---")

        # Alarms
        if sample.alarms == ['No alarms']:
            self.val_alarm.setText("✓  No alarms")
            self.val_alarm.setObjectName("status_ok")
        else:
            self.val_alarm.setText("✗  " + '; '.join(sample.alarms))
            self.val_alarm.setObjectName("status_err")
        self.val_alarm.style().unpolish(self.val_alarm)
        self.val_alarm.style().polish(self.val_alarm)

        # Check pass/fail
        if passed is True:
            self._end_test('PASS', status_msg)
        elif passed is False:
            self._end_test('FAIL', status_msg)

    def set_logfile(self, path: str):
        self.lbl_logfile.setText(path)

    def _end_test(self, result: str, reason: str):
        self._test_active = False
        self._timer.stop()
        self._result = result
        self.btn_test_start.setEnabled(True)
        self.btn_test_stop.setEnabled(False)
        self.edit_serial.setEnabled(True)
        self._update_banner(result.lower(), reason)
        self.lbl_result.setText(result)
        self.lbl_result_reason.setText(reason)
        if result == 'PASS':
            self.lbl_result.setStyleSheet(f"color: {GREEN}; font-size: 36px;")
        elif result == 'FAIL':
            self.lbl_result.setStyleSheet(f"color: {RED}; font-size: 36px;")
        else:
            self.lbl_result.setStyleSheet(f"color: {AMBER}; font-size: 36px;")

    def _update_banner(self, state: str, msg: str):
        self._banner_state = state   # track for retranslate
        self._banner_msg   = msg
        if state == 'running':
            self.banner.setText(tr("test_running"))
            self.banner.setStyleSheet(
                f"background: #064e3b; border: 1px solid {GREEN};"
                f"color: {GREEN}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
        elif state == 'pass':
            self.banner.setText(f"✓  {tr('test_result')} PASS — {msg}")
            self.banner.setStyleSheet(
                f"background: #064e3b; border: 1px solid {GREEN};"
                f"color: {GREEN}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
        elif state == 'fail':
            self.banner.setText(f"✗  {tr('test_result')} FAIL — {msg}")
            self.banner.setStyleSheet(
                f"background: #4c0519; border: 1px solid {RED};"
                f"color: {RED}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
        elif state == 'aborted':
            self.banner.setText(f"■  {tr('test_result')} ABORTED")
            self.banner.setStyleSheet(
                f"background: {SURFACE}; border: 1px solid {AMBER};"
                f"color: {AMBER}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
        else:
            self.banner.setText(tr("ready_msg"))
            self.banner.setStyleSheet(
                f"background: {SURFACE}; border: 1px solid {BORDER};"
                f"color: {AMBER}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
