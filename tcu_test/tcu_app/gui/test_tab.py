# =============================================================================
# test_tab.py — Mode 2: Heat Load Test
# =============================================================================

import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QTextEdit,
    QLineEdit, QProgressBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg
from collections import deque
from datetime import datetime

from gui.styles import DARK, PANEL, SURFACE, BORDER, ACCENT, GREEN, RED, AMBER, TEXT, TEXT_DIM

WINDOW = 1800   # 30 min at 1 Hz


class TestTab(QWidget):
    """
    Heat load test panel — 30-minute pass/fail test.
    Operator enters TCU serial, starts test, monitors progress.
    """

    sig_test_start = pyqtSignal(str)   # emits tcu_serial
    sig_test_stop  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_active  = False
        self._start_time   = None
        self._t0_graph     = None
        self._result       = None

        self._times  = deque(maxlen=WINDOW)
        self._temps  = deque(maxlen=WINDOW)
        self._times2 = deque(maxlen=WINDOW)
        self._temps2 = deque(maxlen=WINDOW)
        self._times3 = deque(maxlen=WINDOW)
        self._temps3 = deque(maxlen=WINDOW)
        self._heat_loads = deque(maxlen=WINDOW)
        self._heat_times = deque(maxlen=WINDOW)

        self._build_ui()
        self._setup_graph()

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
        self.banner = QLabel("READY — ENTER SERIAL NUMBER AND PRESS START TEST")
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setObjectName("status_warn")
        self.banner.setMinimumHeight(36)
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
        self.progress.setRange(0, 1800)   # 30 min in seconds
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        left.addWidget(self.progress)

        # Live readings grid
        readings_box = QGroupBox("LIVE READINGS")
        rg = QGridLayout(readings_box)
        rg.setSpacing(10)

        def reading(label):
            l = QLabel(label)
            l.setObjectName("label_dim")
            v = QLabel("---")
            v.setObjectName("val_medium")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return l, v

        self.lbl_elapsed,   self.val_elapsed   = reading("ELAPSED")
        self.lbl_remaining, self.val_remaining = reading("REMAINING")
        self.lbl_temp,      self.val_temp      = reading("INLET TEMP (TCU)")
        self.lbl_sp,        self.val_sp        = reading("SETPOINT")
        self.lbl_flow,      self.val_flow      = reading("FLOW RATE")
        self.lbl_pt100out,  self.val_pt100out  = reading("OUTLET TEMP (PT100)")
        self.lbl_deltat,    self.val_deltat    = reading("DELTA T")
        self.lbl_heatload,  self.val_heatload  = reading("HEAT LOAD")
        self.lbl_alarm,     self.val_alarm     = reading("ALARMS")
        self.lbl_crosschk,  self.val_crosschk  = reading("INLET CROSSCHECK")

        rows = [
            (self.lbl_elapsed, self.val_elapsed),
            (self.lbl_remaining, self.val_remaining),
            (self.lbl_temp, self.val_temp),
            (self.lbl_sp, self.val_sp),
            (self.lbl_flow, self.val_flow),
            (self.lbl_pt100out, self.val_pt100out),
            (self.lbl_deltat, self.val_deltat),
            (self.lbl_heatload, self.val_heatload),
            (self.lbl_alarm, self.val_alarm),
            (self.lbl_crosschk, self.val_crosschk),
        ]
        for i, (l, v) in enumerate(rows):
            rg.addWidget(l, i, 0)
            rg.addWidget(v, i, 1)

        left.addWidget(readings_box)

        # Graph
        graph_box = QGroupBox("TEMPERATURE & HEAT LOAD (test duration)")
        gg = QVBoxLayout(graph_box)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(SURFACE)
        self.plot_widget.setMinimumHeight(220)
        gg.addWidget(self.plot_widget)
        left.addWidget(graph_box, stretch=1)

        root.addLayout(left, stretch=3)

        # ── Right: controls ────────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        # Serial number input
        serial_box = QGroupBox("TCU SERIAL NUMBER")
        sg = QVBoxLayout(serial_box)
        self.edit_serial = QLineEdit()
        self.edit_serial.setPlaceholderText("e.g. ASM-001234")
        sg.addWidget(self.edit_serial)
        right.addWidget(serial_box)

        # Test controls
        ctrl_box = QGroupBox("TEST CONTROLS")
        cg = QVBoxLayout(ctrl_box)
        cg.setSpacing(10)

        self.btn_test_start = QPushButton("▶  START TEST")
        self.btn_test_start.setObjectName("btn_test_start")
        self.btn_test_stop  = QPushButton("■  ABORT TEST")
        self.btn_test_stop.setObjectName("btn_test_stop")
        self.btn_test_stop.setEnabled(False)

        cg.addWidget(self.btn_test_start)
        cg.addWidget(self.btn_test_stop)
        right.addWidget(ctrl_box)

        # Pass/fail criteria reminder
        criteria_box = QGroupBox("PASS / FAIL CRITERIA")
        cr = QVBoxLayout(criteria_box)
        criteria_text = (
            "✓  Inlet temp 22.0°C ± 0.1°C\n"
            "    for full 30 minutes\n\n"
            "✓  Flow rate ≥ 1 ℓ/min\n"
            "    continuously\n\n"
            "✓  No TCU alarms\n"
            "    (BS = 400000)\n\n"
            "✓  Test duration 30 min\n"
            "    completed without abort\n\n"
            "⚠  Inlet crosscheck ±0.5°C\n"
            "    WARNING only, not FAIL"
        )
        lbl_crit = QLabel(criteria_text)
        lbl_crit.setObjectName("label_dim")
        lbl_crit.setWordWrap(True)
        cr.addWidget(lbl_crit)
        right.addWidget(criteria_box)

        # Result display
        result_box = QGroupBox("TEST RESULT")
        rr = QVBoxLayout(result_box)
        self.lbl_result = QLabel("—")
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setObjectName("val_large")
        self.lbl_result.setMinimumHeight(60)
        rr.addWidget(self.lbl_result)
        self.lbl_result_reason = QLabel("")
        self.lbl_result_reason.setAlignment(Qt.AlignCenter)
        self.lbl_result_reason.setWordWrap(True)
        self.lbl_result_reason.setObjectName("label_dim")
        rr.addWidget(self.lbl_result_reason)
        right.addWidget(result_box)

        # Log file path
        log_box = QGroupBox("LOG FILE")
        ll = QVBoxLayout(log_box)
        self.lbl_logfile = QLabel("Not started")
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
        pw.setLabel('left', 'Temperature (°C)', color=TEXT,
                    font={'family': 'Courier New', 'size': '11px'})
        pw.setLabel('bottom', 'Elapsed (min)', color=TEXT_DIM,
                    font={'family': 'Courier New', 'size': '10px'})
        pw.addLegend(offset=(10, 10))

        self._curve_tcu = pw.plot(
            pen=pg.mkPen(color=ACCENT, width=2), name='TCU Inlet')
        self._curve_pt100_out = pw.plot(
            pen=pg.mkPen(color=AMBER, width=2), name='PT100 Outlet')

        # Setpoint band ±0.1°C
        self._sp_hi = pg.InfiniteLine(
            angle=0, pos=22.1,
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine))
        self._sp_lo = pg.InfiniteLine(
            angle=0, pos=21.9,
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine))
        pw.addItem(self._sp_hi)
        pw.addItem(self._sp_lo)

    # ── Button handlers ───────────────────────────────────────────────────────
    def _on_start(self):
        serial = self.edit_serial.text().strip()
        if not serial:
            self.banner.setText("⚠  ENTER TCU SERIAL NUMBER FIRST")
            return
        self._test_active = True
        self._start_time  = time.time()
        self._t0_graph    = None
        self._result      = None
        self._times.clear(); self._temps.clear()
        self._times2.clear(); self._temps2.clear()
        self._times3.clear(); self._temps3.clear()
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

    def _tick(self):
        """Called every second to update elapsed/remaining display."""
        if not self._test_active or self._start_time is None:
            return
        elapsed_s = time.time() - self._start_time
        elapsed_m = elapsed_s / 60.0
        remaining_m = max(0, 30.0 - elapsed_m)
        self.val_elapsed.setText(f"{elapsed_m:.1f} min")
        self.val_remaining.setText(f"{remaining_m:.1f} min")
        self.progress.setValue(int(min(elapsed_s, 1800)))

    # ── Public: called by main window ─────────────────────────────────────────
    def update(self, sample, status_msg: str = '', passed=None):
        """Update readings from DAQ sample."""
        if not self._test_active:
            return

        if self._t0_graph is None:
            self._t0_graph = sample.timestamp

        t_min = (sample.timestamp - self._t0_graph) / 60.0

        def fmt_temp(v): return f"{v:.2f} °C" if v is not None else "---"
        def fmt_flow(v): return f"{v:.1f} ℓ/min" if v is not None else "---"

        self.val_temp.setText(fmt_temp(sample.inlet_temp))
        self.val_sp.setText(fmt_temp(sample.setpoint))
        self.val_flow.setText(fmt_flow(sample.flow_rate))
        self.val_pt100out.setText(fmt_temp(sample.pt100_outlet))

        if sample.delta_t is not None:
            self.val_deltat.setText(f"{sample.delta_t:.2f} °C")
        if sample.heat_load is not None:
            self.val_heatload.setText(f"{sample.heat_load:.0f} W")

        # Alarms
        if sample.alarms == ['No alarms']:
            self.val_alarm.setText("✓  No alarms")
            self.val_alarm.setObjectName("status_ok")
        else:
            self.val_alarm.setText("✗  " + '; '.join(sample.alarms))
            self.val_alarm.setObjectName("status_err")
        self.val_alarm.style().unpolish(self.val_alarm)
        self.val_alarm.style().polish(self.val_alarm)

        # Crosscheck
        if sample.crosscheck_ok is None:
            self.val_crosschk.setText("N/A")
        elif sample.crosscheck_ok:
            self.val_crosschk.setText("✓  OK")
            self.val_crosschk.setObjectName("status_ok")
        else:
            self.val_crosschk.setText("⚠  " + sample.crosscheck_msg)
            self.val_crosschk.setObjectName("status_warn")
        self.val_crosschk.style().unpolish(self.val_crosschk)
        self.val_crosschk.style().polish(self.val_crosschk)

        # Graph
        if sample.inlet_temp is not None:
            self._times.append(t_min)
            self._temps.append(sample.inlet_temp)
            self._curve_tcu.setData(list(self._times), list(self._temps))

        if sample.pt100_outlet is not None:
            self._times2.append(t_min)
            self._temps2.append(sample.pt100_outlet)
            self._curve_pt100_out.setData(list(self._times2), list(self._temps2))

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
        if state == 'running':
            self.banner.setText("● TEST RUNNING — DO NOT DISCONNECT")
            self.banner.setStyleSheet(
                f"background: #064e3b; border: 1px solid {GREEN};"
                f"color: {GREEN}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
        elif state == 'pass':
            self.banner.setText(f"✓  TEST PASSED — {msg}")
            self.banner.setStyleSheet(
                f"background: #064e3b; border: 1px solid {GREEN};"
                f"color: {GREEN}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
        elif state == 'fail':
            self.banner.setText(f"✗  TEST FAILED — {msg}")
            self.banner.setStyleSheet(
                f"background: #4c0519; border: 1px solid {RED};"
                f"color: {RED}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
        elif state == 'aborted':
            self.banner.setText("■  TEST ABORTED")
            self.banner.setStyleSheet(
                f"background: {SURFACE}; border: 1px solid {AMBER};"
                f"color: {AMBER}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
        else:
            self.banner.setText("READY — ENTER SERIAL NUMBER AND PRESS START TEST")
            self.banner.setStyleSheet(
                f"background: {SURFACE}; border: 1px solid {BORDER};"
                f"color: {AMBER}; font-size: 13px; letter-spacing: 2px; padding: 6px;")
