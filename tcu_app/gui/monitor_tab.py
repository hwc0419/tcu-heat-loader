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

from gui.styles import PANEL, SURFACE, BORDER, ACCENT, GREEN, RED, AMBER, TEXT, TEXT_DIM
from settings_manager import settings
from translations import tr


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

    def __init__(self, scale: float = 1.0, parent=None):
        self._scale = scale
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
        readings_box = QGroupBox(tr("live_readings"))
        rg = QGridLayout(readings_box)
        rg.setSpacing(12)

        def make_reading(label_text):
            lbl = QLabel(label_text)
            lbl.setObjectName("label_dim")
            val = QLabel("---")
            val.setObjectName("val_large")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lbl, val

        self.lbl_temp,     self.val_temp     = make_reading(tr("inlet_temp"))
        self.lbl_setpoint, self.val_setpoint = make_reading(tr("setpoint"))
        self.lbl_flow,     self.val_flow     = make_reading(tr("flow_rate"))
        self.lbl_voltage,  self.val_voltage  = make_reading(tr("voltage"))
        self.lbl_current,  self.val_current  = make_reading(tr("current"))
        self.lbl_power,    self.val_power    = make_reading(tr("power"))

        for row, (lbl, val) in enumerate([
            (self.lbl_temp,     self.val_temp),
            (self.lbl_setpoint, self.val_setpoint),
            (self.lbl_flow,     self.val_flow),
            (self.lbl_voltage,  self.val_voltage),
            (self.lbl_current,  self.val_current),
            (self.lbl_power,    self.val_power),
        ]):
            rg.addWidget(lbl, row, 0)
            rg.addWidget(val, row, 1)

        left.addWidget(readings_box)

        # Alarm status
        alarm_box = QGroupBox(tr("alarm_status"))
        ag = QVBoxLayout(alarm_box)
        self.val_alarm = QLabel(tr("no_alarms"))
        self.val_alarm.setObjectName("status_ok")
        self.val_alarm.setWordWrap(True)
        ag.addWidget(self.val_alarm)
        left.addWidget(alarm_box)

        # Temperature graph
        graph_box = QGroupBox(tr("temp_trend"))
        gg = QVBoxLayout(graph_box)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setMinimumHeight(int(200 * self._scale))
        gg.addWidget(self.plot_widget)
        left.addWidget(graph_box, stretch=1)

        root.addLayout(left, stretch=3)

        # ── Right column: controls + command log ──────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        # TCU controls
        ctrl_box = QGroupBox(tr("tcu_controls"))
        cg = QVBoxLayout(ctrl_box)
        cg.setSpacing(8)

        self.btn_start = QPushButton(tr("btn_start"))
        self.btn_start.setObjectName("btn_start")
        self.btn_stop  = QPushButton(tr("btn_stop"))
        self.btn_stop.setObjectName("btn_stop")
        self.btn_fill  = QPushButton(tr("btn_fill"))
        self.btn_fill.setObjectName("btn_fill")
        self.btn_precond    = QPushButton(tr("btn_precond"))
        self.btn_clr_alarm  = QPushButton(tr("btn_clr_alarm"))
        self.btn_close_valve = QPushButton(tr("btn_close_valve"))

        for btn in [self.btn_start, self.btn_stop, self.btn_fill,
                    self.btn_precond, self.btn_clr_alarm, self.btn_close_valve]:
            btn.setMinimumHeight(int(42 * self._scale))
            cg.addWidget(btn)

        right.addWidget(ctrl_box)

        # Setpoint control
        sp_box = QGroupBox(tr("set_setpoint"))
        sg = QHBoxLayout(sp_box)
        self.spin_setpoint = QDoubleSpinBox()
        self.spin_setpoint.setRange(17.0, 27.0)
        self.spin_setpoint.setSingleStep(0.5)
        self.spin_setpoint.setValue(settings.get('temp_setpoint'))
        self.spin_setpoint.setDecimals(2)
        self.spin_setpoint.setSuffix(" °C")
        self.btn_set_sp = QPushButton(tr("btn_set"))
        sg.addWidget(self.spin_setpoint)
        sg.addWidget(self.btn_set_sp)
        right.addWidget(sp_box)

        # Command log
        log_box = QGroupBox(tr("cmd_log"))
        lg = QVBoxLayout(log_box)
        self.cmd_log = QTextEdit()
        self.cmd_log.setReadOnly(True)
        self.cmd_log.setMinimumHeight(int(200 * self._scale))
        lg.addWidget(self.cmd_log)
        right.addWidget(log_box, stretch=1)

        # Alarm history
        ah_box = QGroupBox(tr("alarm_history"))
        ah = QVBoxLayout(ah_box)
        self.alarm_log = QTextEdit()
        self.alarm_log.setReadOnly(True)
        self.alarm_log.setMaximumHeight(int(120 * self._scale))
        ah.addWidget(self.alarm_log)
        right.addWidget(ah_box)

        # Connection status
        self.lbl_conn = QLabel(tr("disconnected"))
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
        self._curve_power = pw.plot(
            pen=pg.mkPen(color=AMBER, width=2),
            name='Power (W)')
        self._setpoint_line = pg.InfiniteLine(
            angle=0, pos=settings.get('temp_setpoint'),
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine),
            label='Setpoint', labelOpts={'color': RED})
        pw.addItem(self._setpoint_line)

        self._times_power = deque(maxlen=WINDOW)
        self._power_vals  = deque(maxlen=WINDOW)

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
        self.val_voltage.setText(f"{sample.voltage:.1f} V"    if sample.voltage is not None else "---")
        self.val_current.setText(f"{sample.current:.3f} A"    if sample.current is not None else "---")
        self.val_power.setText(  f"{sample.power:.1f} W"      if sample.power   is not None else "---")

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

        if sample.power is not None:
            self._times_power.append(t)
            self._power_vals.append(sample.power)
            self._curve_power.setData(list(self._times_power), list(self._power_vals))

        # Command log
        if sample.raw_log or sample.decoded_log:
            import time as _time
            ts = _time.strftime('%H:%M:%S')

            # Colour scheme: red for faults, amber for warnings, green for normal
            if sample.is_abnormal:
                hdr_color = RED
            else:
                hdr_color = TEXT_DIM

            # Append timestamp + raw RS232 line
            if sample.raw_log:
                self.cmd_log.setTextColor(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor(hdr_color))
                self.cmd_log.append(f"[{ts}]  {sample.raw_log.replace(chr(10), '  |  ')}")

            # Append decoded human-readable status lines
            for line in sample.decoded_log:
                if line.startswith('✕'):
                    color = RED
                elif line.startswith('⚠'):
                    color = AMBER
                elif '✓' in line:
                    color = GREEN
                else:
                    color = TEXT_DIM
                self.cmd_log.setTextColor(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor(color))
                self.cmd_log.append(f"         {line}")

            # Blank separator line
            self.cmd_log.setTextColor(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor(BORDER))
            self.cmd_log.append('')

            # Trim to 500 blocks max
            doc = self.cmd_log.document()
            while doc.blockCount() > 500:
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

    def retranslate(self):
        """Update all labels to current language — called on language change."""
        self.lbl_temp.setText(tr('inlet_temp'))
        self.lbl_setpoint.setText(tr('setpoint'))
        self.lbl_flow.setText(tr('flow_rate'))
        self.lbl_voltage.setText(tr('voltage'))
        self.lbl_current.setText(tr('current'))
        self.lbl_power.setText(tr('power'))
        self.btn_start.setText(tr('btn_start'))
        self.btn_stop.setText(tr('btn_stop'))
        self.btn_fill.setText(tr('btn_fill'))
        self.btn_precond.setText(tr('btn_precond'))
        self.btn_clr_alarm.setText(tr('btn_clr_alarm'))
        self.btn_close_valve.setText(tr('btn_close_valve'))
        self.btn_set.setText(tr('btn_set'))

    def refresh_settings(self):
        """
        Called by main_window when settings are applied.
        Updates setpoint spinbox and graph setpoint line.
        """
        sp = settings.get('temp_setpoint')
        self.spin_setpoint.setValue(sp)
        self._setpoint_line.setValue(sp)

    def set_connected(self, connected: bool):
        if connected:
            self.lbl_conn.setText(tr("connected"))
            self.lbl_conn.setObjectName("status_ok")
        else:
            self.lbl_conn.setText(tr("disconnected"))
            self.lbl_conn.setObjectName("status_err")
        self.lbl_conn.style().unpolish(self.lbl_conn)
        self.lbl_conn.style().polish(self.lbl_conn)

    def log_command(self, cmd: str, response: str = ''):
        """Log an operator-triggered RS232 command with timestamp and colour."""
        from PyQt5.QtGui import QColor
        ts = datetime.now().strftime('%H:%M:%S')
        self.cmd_log.setTextColor(QColor(ACCENT))
        self.cmd_log.append(f"[{ts}] ▶ OPERATOR: {cmd}  →  {response}")
        self.cmd_log.setTextColor(QColor(TEXT_DIM))
        self.cmd_log.verticalScrollBar().setValue(
            self.cmd_log.verticalScrollBar().maximum())
