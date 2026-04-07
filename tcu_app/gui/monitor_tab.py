# =============================================================================
# monitor_tab.py — Mode 1: Normal TCU Operation (replaces Haake TCU app)
# =============================================================================

import time
import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QTextEdit,
    QDoubleSpinBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
import pyqtgraph as pg
from collections import deque
from datetime import datetime

from gui.styles import DARK, PANEL, SURFACE, BORDER, ACCENT, GREEN, RED, AMBER, TEXT, TEXT_DIM


# Rolling window: 10 minutes at 1 Hz
WINDOW = 600


class MonitorTab(QWidget):
    """
    Normal TCU operation panel — replaces Haake TCU app.
    Shows live temperature, flow, alarms, command log.
    Provides Start/Stop/Fill/Precond/ClearAlarm/SetSetpoint controls.
    """

    # Signals emitted to main window for TCU commands
    sig_start       = pyqtSignal()
    sig_stop        = pyqtSignal()
    sig_fill        = pyqtSignal()
    sig_precond     = pyqtSignal()
    sig_clear_alarm = pyqtSignal()
    sig_close_valve = pyqtSignal()
    sig_set_setpoint = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._times     = deque(maxlen=WINDOW)
        self._temps     = deque(maxlen=WINDOW)
        self._flows     = deque(maxlen=WINDOW)
        self._t0        = None
        self._build_ui()
        self._setup_graph()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Left column: readings + graph ─────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(8)

        # Big readings row
        readings_box = QGroupBox("LIVE READINGS")
        rg = QGridLayout(readings_box)
        rg.setSpacing(12)

        def make_reading(label_text):
            lbl = QLabel(label_text)
            lbl.setObjectName("label_dim")
            val = QLabel("---")
            val.setObjectName("val_large")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lbl, val

        self.lbl_temp,     self.val_temp     = make_reading("INLET TEMP (TCU)")
        self.lbl_setpoint, self.val_setpoint = make_reading("SETPOINT")
        self.lbl_flow,     self.val_flow     = make_reading("FLOW RATE")

        for row, (lbl, val) in enumerate([
            (self.lbl_temp, self.val_temp),
            (self.lbl_setpoint, self.val_setpoint),
            (self.lbl_flow, self.val_flow),
        ]):
            rg.addWidget(lbl, row, 0)
            rg.addWidget(val, row, 1)

        left.addWidget(readings_box)

        # Alarm status
        alarm_box = QGroupBox("ALARM STATUS")
        ag = QVBoxLayout(alarm_box)
        self.val_alarm = QLabel("No alarms")
        self.val_alarm.setObjectName("status_ok")
        self.val_alarm.setWordWrap(True)
        ag.addWidget(self.val_alarm)
        left.addWidget(alarm_box)

        # Temperature graph
        graph_box = QGroupBox("TEMPERATURE TREND (last 10 min)")
        gg = QVBoxLayout(graph_box)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(SURFACE)
        self.plot_widget.setMinimumHeight(200)
        gg.addWidget(self.plot_widget)
        left.addWidget(graph_box, stretch=1)

        root.addLayout(left, stretch=3)

        # ── Right column: controls + command log ──────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        # TCU controls
        ctrl_box = QGroupBox("TCU CONTROLS")
        cg = QVBoxLayout(ctrl_box)
        cg.setSpacing(8)

        self.btn_start = QPushButton("START")
        self.btn_start.setObjectName("btn_start")
        self.btn_stop  = QPushButton("STOP")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_fill  = QPushButton("FILL  (AFV)")
        self.btn_fill.setObjectName("btn_fill")
        self.btn_precond    = QPushButton("PRECOND  (VT)")
        self.btn_clr_alarm  = QPushButton("CLEAR ALARM  (ER)")
        self.btn_close_valve = QPushButton("CLOSE VALVE  (CVE)")

        for btn in [self.btn_start, self.btn_stop, self.btn_fill,
                    self.btn_precond, self.btn_clr_alarm, self.btn_close_valve]:
            btn.setMinimumHeight(42)
            cg.addWidget(btn)

        right.addWidget(ctrl_box)

        # Setpoint control
        sp_box = QGroupBox("SET SETPOINT")
        sg = QHBoxLayout(sp_box)
        self.spin_setpoint = QDoubleSpinBox()
        self.spin_setpoint.setRange(17.0, 27.0)
        self.spin_setpoint.setSingleStep(0.5)
        from config import TEMP_SETPOINT
        self.spin_setpoint.setValue(TEMP_SETPOINT)
        self.spin_setpoint.setDecimals(2)
        self.spin_setpoint.setSuffix(" °C")
        self.btn_set_sp = QPushButton("SET")
        sg.addWidget(self.spin_setpoint)
        sg.addWidget(self.btn_set_sp)
        right.addWidget(sp_box)

        # Command log
        log_box = QGroupBox("COMMAND LOG  (RS232)")
        lg = QVBoxLayout(log_box)
        self.cmd_log = QTextEdit()
        self.cmd_log.setReadOnly(True)
        self.cmd_log.setMinimumHeight(200)
        lg.addWidget(self.cmd_log)
        right.addWidget(log_box, stretch=1)

        # Alarm history
        ah_box = QGroupBox("ALARM HISTORY")
        ah = QVBoxLayout(ah_box)
        self.alarm_log = QTextEdit()
        self.alarm_log.setReadOnly(True)
        self.alarm_log.setMaximumHeight(120)
        ah.addWidget(self.alarm_log)
        right.addWidget(ah_box)

        # Connection status
        self.lbl_conn = QLabel("● DISCONNECTED")
        self.lbl_conn.setObjectName("status_err")
        self.lbl_conn.setAlignment(Qt.AlignCenter)
        right.addWidget(self.lbl_conn)

        root.addLayout(right, stretch=1)

        # ── Wire buttons ──────────────────────────────────────────────────────
        self.btn_start.clicked.connect(self.sig_start)
        self.btn_stop.clicked.connect(self.sig_stop)
        self.btn_fill.clicked.connect(self.sig_fill)
        self.btn_precond.clicked.connect(self.sig_precond)
        self.btn_clr_alarm.clicked.connect(self.sig_clear_alarm)
        self.btn_close_valve.clicked.connect(self.sig_close_valve)
        self.btn_set_sp.clicked.connect(
            lambda: self.sig_set_setpoint.emit(self.spin_setpoint.value()))

    # ── Graph setup ───────────────────────────────────────────────────────────
    def _setup_graph(self):
        pw = self.plot_widget
        pw.showGrid(x=True, y=True, alpha=0.2)
        pw.setLabel('left', 'Temperature', units='°C',
                    color=TEXT, font={'family': 'Courier New', 'size': '11px'})
        pw.setLabel('bottom', 'Time (s)',
                    color=TEXT_DIM, font={'family': 'Courier New', 'size': '10px'})
        pw.addLegend(offset=(10, 10))

        self._curve_tcu = pw.plot(
            pen=pg.mkPen(color=ACCENT, width=2),
            name='TCU Inlet')
        from config import TEMP_SETPOINT
        self._setpoint_line = pg.InfiniteLine(
            angle=0, pos=TEMP_SETPOINT,
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine),
            label='Setpoint', labelOpts={'color': RED})
        pw.addItem(self._setpoint_line)

    # ── Public: update from DAQ sample ────────────────────────────────────────
    def update(self, sample):
        """Called by main window when a new DAQ sample arrives."""
        if self._t0 is None:
            self._t0 = sample.timestamp

        t = sample.timestamp - self._t0

        # Update readings
        def fmt_temp(v):
            return f"{v:.2f} °C" if v is not None else "---"
        def fmt_flow(v):
            return f"{v:.1f} ℓ/min" if v is not None else "---"
        def fmt_dt(v):
            return f"{v:.2f} °C" if v is not None else "---"

        self.val_temp.setText(fmt_temp(sample.inlet_temp))
        self.val_setpoint.setText(fmt_temp(sample.setpoint))
        self.val_flow.setText(fmt_flow(sample.flow_rate))

        # Alarm status
        if sample.alarms == ['No alarms']:
            self.val_alarm.setText("✓  No alarms")
            self.val_alarm.setObjectName("status_ok")
        else:
            alarm_text = '\n'.join(f"⚠  {a}" for a in sample.alarms)
            self.val_alarm.setText(alarm_text)
            self.val_alarm.setObjectName("status_err")
            ts = datetime.fromtimestamp(sample.timestamp).strftime('%H:%M:%S')
            for a in sample.alarms:
                self.alarm_log.append(f"[{ts}] {a}")

        self.val_alarm.style().unpolish(self.val_alarm)
        self.val_alarm.style().polish(self.val_alarm)

        # Graph data
        if sample.inlet_temp is not None:
            self._times.append(t)
            self._temps.append(sample.inlet_temp)
            self._curve_tcu.setData(list(self._times), list(self._temps))

        # Command log
        if sample.raw_log:
            self.cmd_log.append(sample.raw_log)
            doc = self.cmd_log.document()
            while doc.blockCount() > 200:
                cursor = self.cmd_log.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.select(cursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()
            self.cmd_log.verticalScrollBar().setValue(
                self.cmd_log.verticalScrollBar().maximum())

        # Update setpoint line
        if sample.setpoint:
            self._setpoint_line.setValue(sample.setpoint)

    def set_connected(self, connected: bool):
        if connected:
            self.lbl_conn.setText("● CONNECTED")
            self.lbl_conn.setObjectName("status_ok")
        else:
            self.lbl_conn.setText("● DISCONNECTED")
            self.lbl_conn.setObjectName("status_err")
        self.lbl_conn.style().unpolish(self.lbl_conn)
        self.lbl_conn.style().polish(self.lbl_conn)

    def log_command(self, cmd: str, response: str = ''):
        ts = datetime.now().strftime('%H:%M:%S')
        self.cmd_log.append(f"[{ts}] >{cmd}  <{response}")
        self.cmd_log.verticalScrollBar().setValue(
            self.cmd_log.verticalScrollBar().maximum())
