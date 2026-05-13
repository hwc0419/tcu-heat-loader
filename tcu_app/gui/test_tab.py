# =============================================================================
# test_tab.py — Mode 2: Heat Load Test
# =============================================================================

import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QTextEdit,
    QLineEdit, QProgressBar, QSizePolicy, QDialog
)
from gui.osk import OskLineEdit as QLineEdit, OskSpinBox as QSpinBox, OskDoubleSpinBox as QDoubleSpinBox
from gui.graph_utils import make_graph_panel

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg
from collections import deque
from datetime import datetime

from gui.styles import PANEL, SURFACE, BORDER, ACCENT, GREEN, RED, AMBER, TEXT, TEXT_DIM
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
        self._test_active       = False
        self._start_time        = None
        self._t0_graph          = None
        self._result            = None
        self._banner_state      = 'ready'
        self._banner_msg        = ''

        self._times      = deque(maxlen=_get_window())
        self._temps      = deque(maxlen=_get_window())
        self._heat_loads = deque(maxlen=_get_window())
        self._heat_times = deque(maxlen=_get_window())
        self._flow_times = deque(maxlen=_get_window())
        self._flow_vals  = deque(maxlen=_get_window())
        self._pwr_times  = deque(maxlen=_get_window())
        self._pwr_vals   = deque(maxlen=_get_window())
        self._show_temp  = True

        self._build_ui()
        self._setup_graph()
        self._build_popup()

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
        self.lbl_heating,   self.val_heating   = reading("Heating %")
        self.lbl_cooling,   self.val_cooling   = reading("Cooling %")

        # Two-column layout
        # Col 1: elapsed, remaining, inlet temp, setpoint, flow
        # Col 2: voltage, current, power, alarms, heating%, cooling%
        col1 = [
            (self.lbl_elapsed,   self.val_elapsed),
            (self.lbl_remaining, self.val_remaining),
            (self.lbl_temp,      self.val_temp),
            (self.lbl_sp,        self.val_sp),
            (self.lbl_flow,      self.val_flow),
        ]
        col2 = [
            (self.lbl_voltage,   self.val_voltage),
            (self.lbl_current,   self.val_current),
            (self.lbl_power,     self.val_power),
            (self.lbl_alarm,     self.val_alarm),
            (self.lbl_heating,   self.val_heating),
            (self.lbl_cooling,   self.val_cooling),
        ]
        for i, (l, v) in enumerate(col1):
            rg.addWidget(l, i, 0)
            rg.addWidget(v, i, 1)
        for i, (l, v) in enumerate(col2):
            rg.addWidget(l, i, 2)
            rg.addWidget(v, i, 3)
        rg.setColumnStretch(1, 1)
        rg.setColumnStretch(3, 1)

        left.addWidget(readings_box)

        # Graph with toggle + popup + export buttons in header
        self._grp_graph = QGroupBox("TEMPERATURE & HEAT LOAD (test duration)")
        gg = QVBoxLayout(self._grp_graph)
        hdr = QHBoxLayout()
        self._graph_lbl  = QLabel("Temperature")
        self._graph_lbl.setObjectName("graph_title")
        self._toggle_btn = QPushButton("→ Flow Rate")
        self._toggle_btn.setObjectName("btn_export")
        self._toggle_btn.setFixedWidth(int(110 * self._scale))
        self._toggle_btn.clicked.connect(self._on_toggle)
        self._popup_btn  = QPushButton("📈 Popup")
        self._popup_btn.setObjectName("btn_export")
        self._popup_btn.setFixedWidth(int(80 * self._scale))
        self._popup_btn.clicked.connect(self._on_show_popup)
        self._export_btn = QPushButton("⬇ Export")
        self._export_btn.setObjectName("btn_export")
        self._export_btn.setFixedWidth(int(80 * self._scale))
        self._export_btn.clicked.connect(self._on_export)
        hdr.addWidget(self._graph_lbl)
        hdr.addStretch()
        hdr.addWidget(self._toggle_btn)
        hdr.addWidget(self._popup_btn)
        hdr.addWidget(self._export_btn)
        gg.addLayout(hdr)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setMinimumHeight(int(220 * self._scale))
        gg.addWidget(self.plot_widget)
        left.addWidget(self._grp_graph, stretch=1)

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
        pw = self.plot_widget
        pw.showGrid(x=True, y=True, alpha=0.2)
        pw.setLabel('left', 'Temperature', units='°C', color=TEXT,
                    font={'family': 'Courier New', 'size': '11px'})
        pw.setLabel('bottom', 'Elapsed (min)', color=TEXT_DIM,
                    font={'family': 'Courier New', 'size': '10px'})
        pw.addLegend(offset=(10, 10))

        # Temperature curve (left Y)
        self._curve_tcu = pw.plot(
            pen=pg.mkPen(color=ACCENT, width=2), name='TCU Inlet (°C)')

        # Power curve (right Y via ViewBox)
        self._power_vb = pg.ViewBox()
        pw.scene().addItem(self._power_vb)
        pw.getAxis('right').linkToView(self._power_vb)
        pw.getAxis('right').setLabel('Power', units='W', color=AMBER)
        pw.showAxis('right')
        self._power_vb.setXLink(pw)
        self._curve_power = pg.PlotCurveItem(
            pen=pg.mkPen(color=AMBER, width=2), name='Power (W)')
        self._power_vb.addItem(self._curve_power)
        pw.plotItem.vb.sigResized.connect(self._sync_vb)

        # Flow curve (hidden initially)
        self._curve_flow_inline = pw.plot(
            pen=pg.mkPen('#2196F3', width=2), name='Flow (ℓ/min)')
        self._curve_flow_inline.setVisible(False)

        sp  = settings.get('temp_setpoint')
        tol = settings.get('temp_tolerance')
        self._sp_hi = pg.InfiniteLine(
            angle=0, pos=sp + tol,
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine))
        self._sp_lo = pg.InfiniteLine(
            angle=0, pos=sp - tol,
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine))
        pw.addItem(self._sp_hi)
        pw.addItem(self._sp_lo)

    def _sync_vb(self):
        self._power_vb.setGeometry(
            self.plot_widget.plotItem.vb.sceneBoundingRect())
        self._power_vb.linkedViewChanged(
            self.plot_widget.plotItem.vb, self._power_vb.XAxis)

    def _on_toggle(self):
        self._show_temp = not self._show_temp
        pw = self.plot_widget
        if self._show_temp:
            self._curve_tcu.setVisible(True)
            self._curve_power.setVisible(True)
            self._sp_hi.setVisible(True)
            self._sp_lo.setVisible(True)
            self._curve_flow_inline.setVisible(False)
            pw.setLabel('left', 'Temperature', units='°C')
            pw.showAxis('right')
            self._graph_lbl.setText('Temperature')
            self._toggle_btn.setText('→ Flow Rate')
        else:
            self._curve_tcu.setVisible(False)
            self._curve_power.setVisible(False)
            self._sp_hi.setVisible(False)
            self._sp_lo.setVisible(False)
            self._curve_flow_inline.setVisible(True)
            pw.setLabel('left', 'Flow rate', units='ℓ/min')
            pw.hideAxis('right')
            self._graph_lbl.setText('Flow Rate')
            self._toggle_btn.setText('← Temperature')

    def _on_export(self):
        from gui.graph_utils import export_graph
        title = 'temperature' if self._show_temp else 'flow_rate'
        export_graph(self.plot_widget, f'test_{title}')

    def _build_popup(self):
        self._popup = QDialog(self)
        self._popup.setWindowTitle('Test Graphs')
        self._popup.setMinimumSize(700, 500)
        v = QVBoxLayout(self._popup)
        temp_panel, self._popup_plot_temp, _ = make_graph_panel(
            'TCU Inlet Temperature', self._scale)
        self._popup_plot_temp.setLabel('left',   'Temperature', units='°C')
        self._popup_plot_temp.setLabel('bottom', 'Elapsed',     units='min')
        self._popup_plot_temp.showGrid(x=True, y=True, alpha=0.2)
        self._popup_curve_temp = self._popup_plot_temp.plot(
            pen=pg.mkPen(color=ACCENT, width=2), name='TCU Inlet')
        v.addWidget(temp_panel)
        flow_panel, self._popup_plot_flow, _ = make_graph_panel(
            'Flow Rate', self._scale)
        self._popup_plot_flow.setLabel('left',   'Flow rate', units='ℓ/min')
        self._popup_plot_flow.setLabel('bottom', 'Elapsed',   units='min')
        self._popup_plot_flow.showGrid(x=True, y=True, alpha=0.2)
        self._popup_curve_flow = self._popup_plot_flow.plot(
            pen=pg.mkPen('#2196F3', width=2), name='Flow rate')
        v.addWidget(flow_panel)

    def _on_show_popup(self):
        self._popup.show()
        self._popup.raise_()

    # ── Button handlers ───────────────────────────────────────────────────────
    def _on_start(self):
        serial = self.edit_serial.text().strip()
        if not serial:
            self.banner.setText(tr("enter_serial"))
            return
        self._test_active    = True
        self._start_time     = time.time()
        self._t0_graph       = None
        self._result         = None
        self._times.clear();      self._temps.clear()
        self._heat_times.clear(); self._heat_loads.clear()
        self._pwr_times.clear();  self._pwr_vals.clear()
        self._flow_times.clear(); self._flow_vals.clear()
        self._curve_tcu.setData([], [])
        self._curve_power.setData([], [])
        self._curve_flow_inline.setData([], [])
        if hasattr(self, '_popup_curve_temp'):
            self._popup_curve_temp.setData([], [])
        if hasattr(self, '_popup_curve_flow'):
            self._popup_curve_flow.setData([], [])
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
        self._grp_readings.setTitle(tr('live_readings'))
        self._grp_serial.setTitle(tr('tcu_serial'))
        self._grp_ctrl.setTitle(tr('test_controls'))
        self._grp_criteria.setTitle(tr('pass_criteria'))
        self._grp_result.setTitle(tr('test_result'))
        self._grp_log.setTitle(tr('log_file'))
        self.lbl_elapsed.setText(tr('elapsed'))
        self.lbl_remaining.setText(tr('remaining'))
        self.lbl_temp.setText(tr('inlet_temp'))
        self.lbl_sp.setText(tr('setpoint'))
        self.lbl_flow.setText(tr('flow_rate'))
        self.lbl_voltage.setText(tr('voltage'))
        self.lbl_current.setText(tr('current'))
        self.lbl_power.setText(tr('power'))
        self.lbl_alarm.setText(tr('alarms'))
        self.btn_test_start.setText(tr('btn_test_start'))
        self.btn_test_stop.setText(tr('btn_test_stop'))
        self.edit_serial.setPlaceholderText(tr('serial_ph'))
        self._refresh_criteria()
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
            f"    for 5+ consecutive seconds\n\n"
            f"✓  No TCU alarms\n"
            f"    (BS = 400400)\n\n"
            f"✓  Test duration {dur} min\n"
            f"    completed without abort"
        )

    def refresh_settings(self):
        """Called by main_window when settings are applied."""
        sp  = settings.get('temp_setpoint')
        tol = settings.get('temp_tolerance')
        dur = settings.get('test_duration')
        self._refresh_criteria()
        self.progress.setRange(0, dur * 60)
        self._sp_hi.setValue(sp + tol)
        self._sp_lo.setValue(sp - tol)
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
        # Gate all updates — no pre-test data leaks into graph
        if not self._test_active:
            return

        if self._t0_graph is None:
            self._t0_graph = sample.timestamp

        t_min = (sample.timestamp - self._t0_graph) / 60.0

        if sample.inlet_temp is not None:
            self._times.append(t_min)
            self._temps.append(sample.inlet_temp)
            self._curve_tcu.setData(list(self._times), list(self._temps))
            if hasattr(self, '_popup_curve_temp'):
                self._popup_curve_temp.setData(list(self._times), list(self._temps))

        if sample.power is not None:
            self._pwr_times.append(t_min)
            self._pwr_vals.append(sample.power)
            self._curve_power.setData(list(self._pwr_times), list(self._pwr_vals))

        if sample.flow_rate is not None:
            self._flow_times.append(t_min)
            self._flow_vals.append(sample.flow_rate)
            self._curve_flow_inline.setData(list(self._flow_times), list(self._flow_vals))
            if hasattr(self, '_popup_curve_flow'):
                self._popup_curve_flow.setData(list(self._flow_times), list(self._flow_vals))

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

        # Heating / cooling %
        heating_pct = getattr(sample, 'heating_pct', None)
        cooling_pct = getattr(sample, 'cooling_pct', None)
        if heating_pct is not None:
            self.val_heating.setText(f"{heating_pct:.1f} %")
        if cooling_pct is not None:
            self.val_cooling.setText(f"{cooling_pct:.1f} %")
        self.val_alarm.style().polish(self.val_alarm)

        # Check pass/fail conditions from test_logic
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
        self._banner_state = state
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
