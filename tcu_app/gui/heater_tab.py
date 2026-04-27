# =============================================================================
# heater_tab.py — Heater Control Tab
# =============================================================================
# Controls the vendor thyristor heater via Modbus RTU.
# Supervisor: view only. Technician with lock: full control.
# Auto-off: test end, abort, TCU abnormal (BS != 400400).
# =============================================================================

import time
from collections import deque
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QGroupBox,
    QTextEdit, QSizePolicy, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg

from settings_manager import settings
from translations import tr
from config import HEATER_MAX_WATTS

_GRAPH_MAX_POINTS = 600   # 10 min at 1 sample/sec


class HeaterTab(QWidget):
    """
    Heater control tab — setpoint slider, live temperature graph,
    actual power readout and Modbus log.
    """

    sig_set_watts    = pyqtSignal(int)   # emitted when operator sets new setpoint
    sig_estop        = pyqtSignal()      # emitted when emergency stop triggered

    def __init__(self, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self._scale        = scale
        self._locked       = True    # default enabled for desktop use
        self._role         = 'technician'
        self._current_pct  = 0
        self._graph_times  = deque(maxlen=_GRAPH_MAX_POINTS)
        self._water_temps  = deque(maxlen=_GRAPH_MAX_POINTS)
        self._element_temps= deque(maxlen=_GRAPH_MAX_POINTS)
        self._inlet_temps  = deque(maxlen=_GRAPH_MAX_POINTS)
        self._t_start      = time.monotonic()
        self._build_ui()
        self._set_controls_enabled(True)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 12, 16, 12)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addLayout(self._build_setpoint_panel(), stretch=1)
        top.addLayout(self._build_actual_panel(),   stretch=1)
        root.addLayout(top)
        root.addWidget(self._build_graph())
        root.addWidget(self._build_modbus_log())

    def _build_setpoint_panel(self):
        layout = QVBoxLayout()
        self._grp_sp = QGroupBox(tr('heater_setpoint'))
        g = QGridLayout(self._grp_sp)
        g.setSpacing(8)

        self._lbl_pct   = QLabel('0 %')
        self._lbl_pct.setAlignment(Qt.AlignCenter)
        self._lbl_watts = QLabel('0 W')
        self._lbl_watts.setAlignment(Qt.AlignCenter)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setSingleStep(1)
        self._slider.setValue(0)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.valueChanged.connect(self._on_slider_moved)

        self._spin = QSpinBox()
        self._spin.setRange(0, 100)
        self._spin.setSuffix(' %')
        self._spin.valueChanged.connect(self._on_spin_changed)

        self._btn_off = QPushButton(tr('btn_heater_off'))
        self._btn_off.setObjectName('btn_stop')
        self._btn_off.clicked.connect(self._on_heater_off)

        g.addWidget(self._lbl_pct,    0, 0, 1, 2)
        g.addWidget(self._lbl_watts,  1, 0, 1, 2)
        g.addWidget(self._slider,     2, 0, 1, 2)
        g.addWidget(QLabel('%'),      3, 0)
        g.addWidget(self._spin,       3, 1)
        g.addWidget(self._btn_off,    4, 0, 1, 2)

        layout.addWidget(self._grp_sp)
        return layout

    def _build_actual_panel(self):
        layout = QVBoxLayout()
        self._grp_actual = QGroupBox(tr('heater_actual'))
        g = QGridLayout(self._grp_actual)
        g.setSpacing(8)

        self._lbl_actual_w = QLabel('— W')
        self._lbl_actual_v = QLabel('— V')
        self._lbl_actual_a = QLabel('— A')
        for lbl in (self._lbl_actual_w, self._lbl_actual_v, self._lbl_actual_a):
            lbl.setAlignment(Qt.AlignCenter)

        g.addWidget(QLabel('Power:'),   0, 0)
        g.addWidget(self._lbl_actual_w, 0, 1)
        g.addWidget(QLabel('Voltage:'), 1, 0)
        g.addWidget(self._lbl_actual_v, 1, 1)
        g.addWidget(QLabel('Current:'), 2, 0)
        g.addWidget(self._lbl_actual_a, 2, 1)

        layout.addWidget(self._grp_actual)
        return layout

    def _build_graph(self):
        self._grp_graph = QGroupBox(tr('heater_graph'))
        v = QVBoxLayout(self._grp_graph)
        self._plot = pg.PlotWidget()
        self._plot.setLabel('left',   'Temperature', units='°C')
        self._plot.setLabel('bottom', 'Time', units='s')
        self._plot.addLegend()
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._plot.setMinimumHeight(200)

        self._curve_water   = self._plot.plot(pen=pg.mkPen('#2196F3', width=2),
                                               name='Water @ 0W')
        self._curve_element = self._plot.plot(pen=pg.mkPen('#F44336', width=2),
                                               name='Element @ 0W')
        self._curve_inlet   = self._plot.plot(pen=pg.mkPen('#4CAF50', width=2),
                                               name='TCU Inlet')
        v.addWidget(self._plot)
        return self._grp_graph

    def _build_modbus_log(self):
        self._grp_log = QGroupBox(tr('heater_modbus_log'))
        v = QVBoxLayout(self._grp_log)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        v.addWidget(self._log)
        return self._grp_log

    # ── Slot: slider moved (preview only) ────────────────────────────────────
    def _on_slider_moved(self, pct: int):
        if not isinstance(pct, int):
            return
        self._current_pct = pct
        self._spin.blockSignals(True)
        self._spin.setValue(pct)
        self._spin.blockSignals(False)
        self._update_setpoint_labels(pct)

    # ── Slot: slider released (send Modbus command) ───────────────────────────
    def _on_slider_released(self):
        pct = self._slider.value()
        if not isinstance(pct, int):
            return
        self._send_setpoint(pct)

    # ── Slot: spinbox changed ─────────────────────────────────────────────────
    def _on_spin_changed(self, pct: int):
        if not isinstance(pct, int):
            return
        self._slider.blockSignals(True)
        self._slider.setValue(pct)
        self._slider.blockSignals(False)
        self._current_pct = pct
        self._update_setpoint_labels(pct)
        self._send_setpoint(pct)

    def _on_heater_off(self):
        self._send_setpoint(0)

    def _send_setpoint(self, pct: int):
        """Convert percentage to watts and emit signal.
        Prompts admin password if watts exceeds soft limit.
        Rejects if watts > HEATER_MAX_WATTS."""
        if not isinstance(pct, int):
            return
        watts = int(pct * HEATER_MAX_WATTS / 100)
        if watts > HEATER_MAX_WATTS:
            QMessageBox.warning(self, 'Setpoint Error',
                f'Setpoint {watts}W exceeds maximum {HEATER_MAX_WATTS}W.\n'
                'Please try a lower value.')
            return
        soft_limit = settings.get('heater_soft_limit_w')
        if watts > soft_limit:
            if not self._prompt_admin_password():
                QMessageBox.warning(self, 'Setpoint Rejected',
                    f'Admin authentication failed.\n'
                    f'Setpoint above {soft_limit}W requires admin password.')
                return
        self._log_modbus(f'→ SET {watts}W ({pct}%)')
        self.sig_set_watts.emit(watts)

    def _prompt_admin_password(self) -> bool:
        """Show password dialog. Returns True if correct admin password entered."""
        import hashlib
        from PyQt5.QtWidgets import QInputDialog, QLineEdit
        pw, ok = QInputDialog.getText(
            self, 'Admin Authentication',
            f'Setpoint exceeds soft limit ({settings.get("heater_soft_limit_w")}W).\n'
            'Enter admin password to proceed:',
            QLineEdit.Password)
        if not ok or not pw:
            return False
        hashed = hashlib.sha256(pw.encode()).hexdigest()
        return hashed == settings.get('access_password_hash')

    # ── Public: called by main_window with new DAQ sample ────────────────────
    def update_sample(self, sample):
        """Update graph and actual power display with latest DAQ sample."""
        now = time.monotonic() - self._t_start
        self._graph_times.append(now)

        # water_temp and element_temp only exist once MAX31865/MAX31855 hardware arrives
        water   = getattr(sample, 'water_temp',   None)
        element = getattr(sample, 'element_temp', None)
        water   = water   if water   is not None else float('nan')
        element = element if element is not None else float('nan')
        inlet   = sample.inlet_temp if sample.inlet_temp is not None else float('nan')

        self._water_temps.append(water)
        self._element_temps.append(element)
        self._inlet_temps.append(inlet)

        t = list(self._graph_times)
        self._curve_water.setData(t, list(self._water_temps))
        self._curve_element.setData(t, list(self._element_temps))
        self._curve_inlet.setData(t, list(self._inlet_temps))

        if sample.power   is not None:
            self._lbl_actual_w.setText(f'{sample.power:.0f} W')
        if sample.voltage is not None:
            self._lbl_actual_v.setText(f'{sample.voltage:.1f} V')
        if sample.current is not None:
            self._lbl_actual_a.setText(f'{sample.current:.2f} A')

    def update_setpoint_watts(self, watts: int):
        """Called when heater setpoint changes — update graph line labels."""
        if not isinstance(watts, int):
            return
        mode = settings.get('heater_display_mode')
        pct  = int(watts * 100 / HEATER_MAX_WATTS)
        if mode == 'percent':
            label = f'{pct}%'
        elif mode == 'watts':
            label = f'{watts}W'
        else:
            label = f'{pct}% / {watts}W'
        self._curve_water.opts['name']   = f'Water @ {label}'
        self._curve_element.opts['name'] = f'Element @ {label}'
        self._plot.plotItem.legend.clear()
        for item in (self._curve_water, self._curve_element, self._curve_inlet):
            self._plot.plotItem.legend.addItem(item, item.opts['name'])

    def log_modbus_response(self, msg: str):
        """Append a Modbus response message to the log."""
        if not isinstance(msg, str):
            return
        self._log_modbus(f'← {msg}')

    def set_lock_state(self, locked: bool, role: str):
        """Called by main_window when operator lock state changes."""
        self._locked = locked
        self._role   = role
        self._set_controls_enabled(locked and role == 'technician')

    def emergency_off(self):
        """Immediately set heater to 0W — called by E-stop."""
        self._send_setpoint(0)
        self._log_modbus('⚠ EMERGENCY STOP — heater set to 0W')

    # ── Private helpers ───────────────────────────────────────────────────────
    def _update_setpoint_labels(self, pct: int):
        watts = int(pct * HEATER_MAX_WATTS / 100)
        mode  = settings.get('heater_display_mode')
        if mode == 'percent':
            self._lbl_pct.setText(f'{pct} %')
            self._lbl_watts.setVisible(False)
        elif mode == 'watts':
            self._lbl_pct.setVisible(False)
            self._lbl_watts.setText(f'{watts} W')
        else:
            self._lbl_pct.setVisible(True)
            self._lbl_watts.setVisible(True)
            self._lbl_pct.setText(f'{pct} %')
            self._lbl_watts.setText(f'{watts} W')

    def _set_controls_enabled(self, enabled: bool):
        for w in (self._slider, self._spin, self._btn_off):
            w.setEnabled(enabled)

    def _log_modbus(self, msg: str):
        self._log.append(msg)

    # ── Retranslate ───────────────────────────────────────────────────────────
    def retranslate(self):
        self._grp_sp.setTitle(tr('heater_setpoint'))
        self._grp_actual.setTitle(tr('heater_actual'))
        self._grp_graph.setTitle(tr('heater_graph'))
        self._grp_log.setTitle(tr('heater_modbus_log'))
        self._btn_off.setText(tr('btn_heater_off'))
