# =============================================================================
# test_tab.py — Stepped Heat Load Test
# =============================================================================
# 80 steps, 0W → 8000W, 100W/step, 5 min/step.
# At each step, averages cooling_pct over last 3 min (setpoint ± 0.1°C filter).
# Fits linear model, extrapolates to 28604W, PASS if < 100%.
# =============================================================================

import time
import csv
import os
from collections import deque
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QProgressBar,
)

from gui.osk import OskLineEdit as QLineEdit
from gui.styles import PANEL, SURFACE, BORDER, ACCENT, GREEN, RED, AMBER, TEXT, TEXT_DIM
from settings_manager import settings
from translations import tr
from test_logic import (
    build_step_table, compute_step_avg, fit_and_extrapolate, parse_alarms,
    check_pass_fail, k_to_watts,
)
from config import (
    STEPPED_TEST_STEP_DURATION_S,
    STEPPED_TEST_AVG_WINDOW_S, STEPPED_TEST_MAX_DURATION_S,
    STEPPED_TEST_TARGET_WATTS, LOG_DIR,
)

_MAX_GRAPH_PTS = 540   # hard upper bound: 9h / 1min minimum step = 540 steps max


class TestTab(QWidget):
    """
    Stepped heat load test panel.
    Emits sig_set_k(k_value) to main window → heater when step changes.
    """

    sig_test_start = pyqtSignal(str)   # emits tcu_serial
    sig_test_stop  = pyqtSignal()
    sig_set_k      = pyqtSignal(int)   # emits K constant for current step
    sig_k_confirmed = pyqtSignal(int)  # received from main_window when PLC confirms K

    def __init__(self, scale: float = 1.0, parent=None):
        self._scale        = scale
        super().__init__(parent)
        self._test_active  = False
        self._start_time   = None
        self._banner_state = 'ready'
        self._banner_msg   = ''

        # Step state
        self._step_table   = build_step_table()   # list of (idx, watts, k)
        self._current_step = 0
        self._step_start   = None
        self._step_samples = []   # (timestamp, cooling_pct, inlet_temp)
        self._results      = []   # (k, avg_cooling_pct | None)
        self._k_pending    = False  # True while waiting for PLC to confirm K
        self._writer       = None
        self._logfile      = None

        # Graph data — fixed bound: _MAX_GRAPH_PTS points
        self._graph_watts   = deque(maxlen=_MAX_GRAPH_PTS)
        self._graph_cooling = deque(maxlen=_MAX_GRAPH_PTS)

        self._build_ui()
        self._setup_graph()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.sig_k_confirmed.connect(self._on_k_confirmed)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 10, 10, 10)

        left = QVBoxLayout()
        left.setSpacing(8)

        # Banner
        self.banner = QLabel(tr('ready_msg'))
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setMinimumHeight(int(36 * self._scale))
        self._style_banner('ready', '')
        left.addWidget(self.banner)

        # Progress — total steps
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)   # updated at test start with actual step count
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        left.addWidget(self.progress)

        # Step progress — within current step
        self.step_progress = QProgressBar()
        self.step_progress.setRange(0, STEPPED_TEST_STEP_DURATION_S)
        self.step_progress.setValue(0)
        self.step_progress.setTextVisible(False)
        self.step_progress.setFixedHeight(4)
        left.addWidget(self.step_progress)

        # Live readings
        grp = QGroupBox(tr('live_readings'))
        rg  = QGridLayout(grp)
        rg.setSpacing(8)

        def rd(label):
            l = QLabel(label); l.setObjectName('label_dim')
            v = QLabel('---'); v.setObjectName('val_medium')
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return l, v

        self.lbl_elapsed,   self.val_elapsed   = rd(tr('elapsed'))
        self.lbl_step,      self.val_step      = rd('Step')
        self.lbl_heater_w,  self.val_heater_w  = rd('Heater setpoint')
        self.lbl_temp,      self.val_temp      = rd(tr('inlet_temp'))
        self.lbl_sp,        self.val_sp        = rd(tr('setpoint'))
        self.lbl_flow,      self.val_flow      = rd(tr('flow_rate'))
        self.lbl_cooling,   self.val_cooling   = rd('Cooling %')
        self.lbl_alarm,     self.val_alarm     = rd(tr('alarms'))
        self.lbl_extrap,    self.val_extrap    = rd(f'Est. cooling @ {STEPPED_TEST_TARGET_WATTS}W')

        col1 = [
            (self.lbl_elapsed,  self.val_elapsed),
            (self.lbl_step,     self.val_step),
            (self.lbl_heater_w, self.val_heater_w),
            (self.lbl_temp,     self.val_temp),
            (self.lbl_sp,       self.val_sp),
        ]
        col2 = [
            (self.lbl_flow,    self.val_flow),
            (self.lbl_cooling, self.val_cooling),
            (self.lbl_alarm,   self.val_alarm),
            (self.lbl_extrap,  self.val_extrap),
        ]
        for i, (l, v) in enumerate(col1):
            rg.addWidget(l, i, 0); rg.addWidget(v, i, 1)
        for i, (l, v) in enumerate(col2):
            rg.addWidget(l, i, 2); rg.addWidget(v, i, 3)
        rg.setColumnStretch(1, 1); rg.setColumnStretch(3, 1)
        left.addWidget(grp)

        # Graph
        grp_g = QGroupBox('COOLING % vs HEAT LOAD (per-step averages)')
        gg    = QVBoxLayout(grp_g)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setMinimumHeight(int(220 * self._scale))
        gg.addWidget(self.plot_widget)
        left.addWidget(grp_g, stretch=1)
        root.addLayout(left, stretch=3)

        # Right panel
        right = QVBoxLayout(); right.setSpacing(8)

        grp_s = QGroupBox(tr('tcu_serial'))
        sg    = QVBoxLayout(grp_s)
        self.edit_serial = QLineEdit()
        self.edit_serial.setPlaceholderText(tr('serial_ph'))
        sg.addWidget(self.edit_serial)
        right.addWidget(grp_s)

        grp_c = QGroupBox(tr('test_controls'))
        cg    = QVBoxLayout(grp_c); cg.setSpacing(10)
        self.btn_start = QPushButton(tr('btn_test_start'))
        self.btn_start.setObjectName('btn_test_start')
        self.btn_stop  = QPushButton(tr('btn_test_stop'))
        self.btn_stop.setObjectName('btn_test_stop')
        self.btn_stop.setEnabled(False)
        cg.addWidget(self.btn_start); cg.addWidget(self.btn_stop)
        right.addWidget(grp_c)

        # Test info — values shown are defaults; actual values from settings at test start
        grp_i = QGroupBox('Test Parameters')
        ig    = QVBoxLayout(grp_i)
        max_w     = settings.get('stepped_max_watts')
        step_size = settings.get('stepped_step_size_w')
        step_dur  = settings.get('stepped_step_duration_s')
        n_steps   = max_w // step_size + 1
        total_min = n_steps * step_dur // 60
        self._lbl_test_params = QLabel(
            f'Steps:     {n_steps}  (0 → {max_w}W)\n'
            f'Step size: {step_dur // 60} min / {step_size}W\n'
            f'Duration:  ~{total_min} min ({total_min // 60}h {total_min % 60}m)\n'
            f'Target:    {STEPPED_TEST_TARGET_WATTS}W\n'
            f'Pass if:   extrap. cooling < 100%'
        )
        ig.addWidget(self._lbl_test_params)
        right.addWidget(grp_i)

        # Result
        grp_r = QGroupBox(tr('test_result'))
        rr    = QVBoxLayout(grp_r)
        self.lbl_result        = QLabel('—')
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setObjectName('val_large')
        self.lbl_result.setMinimumHeight(int(60 * self._scale))
        self.lbl_result_reason = QLabel('')
        self.lbl_result_reason.setAlignment(Qt.AlignCenter)
        self.lbl_result_reason.setWordWrap(True)
        self.lbl_result_reason.setObjectName('label_dim')
        rr.addWidget(self.lbl_result)
        rr.addWidget(self.lbl_result_reason)
        right.addWidget(grp_r)

        grp_l = QGroupBox(tr('log_file'))
        ll    = QVBoxLayout(grp_l)
        self.lbl_logfile = QLabel(tr('not_started'))
        self.lbl_logfile.setObjectName('label_dim')
        self.lbl_logfile.setWordWrap(True)
        ll.addWidget(self.lbl_logfile)
        right.addWidget(grp_l)

        right.addStretch()
        root.addLayout(right, stretch=1)

        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)

    def _setup_graph(self):
        pw = self.plot_widget
        pw.showGrid(x=True, y=True, alpha=0.2)
        pw.setLabel('left',   'Cooling %',   color=TEXT,
                    font={'family': 'Courier New', 'size': '11px'})
        pw.setLabel('bottom', 'Heat load (W)', color=TEXT_DIM,
                    font={'family': 'Courier New', 'size': '10px'})
        self._curve_data    = pw.plot(
            pen=None,
            symbol='o', symbolSize=6,
            symbolBrush=ACCENT, symbolPen='w',
            name='Step avg cooling %',
        )
        self._curve_fitline = pw.plot(
            pen=pg.mkPen(color=GREEN, width=2, style=Qt.DashLine),
            name='Linear fit',
        )
        self._vline_target = pg.InfiniteLine(
            angle=90, pos=STEPPED_TEST_TARGET_WATTS,
            pen=pg.mkPen(color=AMBER, width=1, style=Qt.DotLine),
            label=f'{STEPPED_TEST_TARGET_WATTS}W',
            labelOpts={'color': AMBER, 'position': 0.9},
        )
        self._hline_100 = pg.InfiniteLine(
            angle=0, pos=100,
            pen=pg.mkPen(color=RED, width=1, style=Qt.DotLine),
            label='100%',
            labelOpts={'color': RED, 'position': 0.95},
        )
        pw.addItem(self._vline_target)
        pw.addItem(self._hline_100)

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_start(self):
        serial = self.edit_serial.text().strip()
        if not serial:
            self.banner.setText(tr('enter_serial'))
            return
        self._test_active  = True
        self._start_time   = time.time()
        self._current_step = 0
        self._step_start   = time.time()
        self._step_samples = []
        self._results      = []
        self._graph_watts.clear()
        self._graph_cooling.clear()
        self._curve_data.setData([], [])
        self._curve_fitline.setData([], [])
        self.progress.setValue(0)
        self.step_progress.setValue(0)
        self.lbl_result.setText('—')
        self.lbl_result_reason.setText('')
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.edit_serial.setEnabled(False)

        # Rebuild step table from current settings
        self._step_table = build_step_table()
        n_steps   = len(self._step_table) - 1
        max_w     = settings.get('stepped_max_watts')
        step_size = settings.get('stepped_step_size_w')
        step_dur  = settings.get('stepped_step_duration_s')
        total_min = (n_steps + 1) * step_dur // 60
        self._lbl_test_params.setText(
            f'Steps:     {n_steps + 1}  (0 → {max_w}W)\n'
            f'Step size: {step_dur // 60} min / {step_size}W\n'
            f'Duration:  ~{total_min} min ({total_min // 60}h {total_min % 60}m)\n'
            f'Target:    {STEPPED_TEST_TARGET_WATTS}W\n'
            f'Pass if:   extrap. cooling < 100%'
        )
        self.step_progress.setRange(0, step_dur)
        self.progress.setRange(0, n_steps)

        self._timer.start(1000)

        _, w0, k0 = self._step_table[0]
        self._k_pending = True
        self.sig_set_k.emit(k0)
        self.sig_test_start.emit(serial)
        self._style_banner('running', '')

        os.makedirs(LOG_DIR, exist_ok=True)
        ts  = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._logpath = os.path.join(
            LOG_DIR, f'stepped_heat_load_{serial}_{ts}.csv')
        self._logfile = open(self._logpath, 'w', newline='')
        self._writer  = csv.writer(self._logfile)
        self._writer.writerow([
            'timestamp', 'step', 'target_watts', 'k_constant',
            'inlet_temp', 'flow_rate', 'cooling_pct',
            'step_elapsed_s', 'k_pending',
        ])
        self.lbl_logfile.setText(self._logpath)

    def _on_stop(self):
        self.sig_test_stop.emit()
        self.sig_set_k.emit(0)
        self._end_test('ABORTED', 'Stopped by operator')

    # ── Per-second tick ───────────────────────────────────────────────────────

    def _tick(self):
        if not self._test_active:
            return
        elapsed_s = time.time() - self._start_time
        if elapsed_s >= STEPPED_TEST_MAX_DURATION_S:
            self._finalise()
            return
        if self._k_pending:
            return   # waiting for PLC to confirm K — don't count time yet
        step_dur     = settings.get('stepped_step_duration_s')
        step_elapsed = time.time() - self._step_start
        self.step_progress.setValue(int(min(step_elapsed, step_dur)))
        elapsed_m = elapsed_s / 60.0
        self.val_elapsed.setText(f'{elapsed_m:.1f} min')
        if step_elapsed >= step_dur:
            self._advance_step()

    def _advance_step(self):
        """Finalise current step, move to next or end test."""
        idx, watts, k = self._step_table[self._current_step]
        setpoint = settings.get('temp_setpoint')
        avg      = compute_step_avg(self._step_samples, setpoint)
        self._results.append((k, avg))

        # Get baseline from step 0 result for net cooling graph
        baseline = 0.0
        if self._results and self._results[0][0] <= 0 and self._results[0][1] is not None:
            baseline = self._results[0][1]

        # Update graph with net cooling (raw - baseline), skip K=0 step
        if avg is not None and k > 0:
            net = avg - baseline
            self._graph_watts.append(k_to_watts(k))
            self._graph_cooling.append(net)
            self._curve_data.setData(
                list(self._graph_watts), list(self._graph_cooling))
            self._update_fitline()

        self.progress.setValue(self._current_step)

        # Advance
        self._current_step += 1
        if self._current_step >= len(self._step_table):
            self._finalise()
            return

        _, w_next, k_next = self._step_table[self._current_step]
        self._k_pending = True
        self.sig_set_k.emit(k_next)
        self.step_progress.setValue(0)
        self.val_step.setText(
            f'{self._current_step}/{len(self._step_table) - 1} — {w_next}W')
        self.val_heater_w.setText(f'{w_next} W')

    def _on_k_confirmed(self, k: int):
        """
        Called by main_window when PLC successfully confirms K value.
        Resets step start time and sample buffer — steady-state window
        begins from confirmed PLC response, not from when command was sent.
        """
        if not self._test_active:
            return
        self._k_pending  = False
        self._step_start = time.time()
        self._step_samples = []

    def _update_fitline(self):
        """Redraw linear fit line if ≥2 valid points."""
        valid = [(k, c) for k, c in self._results if c is not None]
        if len(valid) < 2:
            return
        fit = fit_and_extrapolate(valid)
        if fit['slope'] is None:
            return
        x_range = np.linspace(0, STEPPED_TEST_TARGET_WATTS * 1.05, 100)
        y_range = fit['slope'] * x_range + fit['intercept']
        self._curve_fitline.setData(x_range.tolist(), y_range.tolist())
        extrap = fit['extrap_pct']
        if extrap is not None:
            colour = GREEN if extrap < 100 else RED
            self.val_extrap.setText(f'{extrap:.1f} %')
            self.val_extrap.setStyleSheet(f'color: {colour};')

    def _finalise(self):
        """All steps done — report linearity and capacity independently."""
        fit = fit_and_extrapolate(self._results)
        if fit['extrap_pct'] is None:
            self._end_test('FAIL', 'Insufficient valid data points for fit')
            return

        rmse_threshold = settings.get('stepped_rmse_threshold_w')
        rmse           = fit.get('rmse', None)
        extrap         = fit['extrap_pct']
        r2             = fit['r_squared']
        n              = fit['n_points']

        # Linearity result
        if rmse is not None:
            linearity_ok  = rmse <= rmse_threshold
            linearity_str = (
                f'Linearity: {"PASS" if linearity_ok else "FAIL"} '
                f'(RMSE={rmse:.1f}W vs threshold {rmse_threshold:.1f}W)'
            )
        else:
            linearity_str = 'Linearity: N/A (RMSE not computed)'

        # Capacity result
        capacity_ok  = extrap < 100.0
        capacity_str = (
            f'Capacity: {"PASS" if capacity_ok else "FAIL"} '
            f'(extrap. cooling @ {STEPPED_TEST_TARGET_WATTS}W = {extrap:.1f}%)'
        )

        baseline     = fit.get('baseline_pct', 0.0)
        combined = (
            f'{linearity_str}  |  {capacity_str}  |  '
            f'baseline={baseline:.1f}%  R²={r2:.3f}  n={n}'
        )

        if linearity_ok and capacity_ok:
            self._end_test('PASS', combined)
        else:
            self._end_test('FAIL', combined)

    # ── Public: called by main window ─────────────────────────────────────────

    def update(self, sample, status_msg: str = '', passed=None):
        """Receive DAQ sample every second — log to CSV, update displays."""
        if not self._test_active:
            return

        # Current step info for logging
        idx, watts, k = self._step_table[self._current_step] \
            if self._current_step < len(self._step_table) else (0, 0, 0)
        step_elapsed = (time.time() - self._step_start) \
            if self._step_start is not None else 0.0

        # Per-second CSV log — always written regardless of k_pending state
        if self._writer is not None:
            self._writer.writerow([
                sample.timestamp, idx, watts, k,
                f'{sample.inlet_temp:.2f}' if sample.inlet_temp is not None else '',
                f'{sample.flow_rate:.1f}'  if sample.flow_rate  is not None else '',
                f'{sample.cooling_pct:.2f}'if sample.cooling_pct is not None else '',
                f'{step_elapsed:.1f}',
                int(self._k_pending),
            ])
            self._logfile.flush()

        # Buffer sample for steady-state average — only after PLC confirms K
        if not self._k_pending:
            self._step_samples.append((
                sample.timestamp,
                sample.cooling_pct,
                sample.inlet_temp,
            ))

        # Update live readings
        self.val_temp.setText(
            f'{sample.inlet_temp:.2f} °C' if sample.inlet_temp is not None else '---')
        self.val_sp.setText(
            f'{sample.setpoint:.2f} °C'   if sample.setpoint   is not None else '---')
        self.val_flow.setText(
            f'{sample.flow_rate:.1f} ℓ/min' if sample.flow_rate is not None else '---')
        self.val_cooling.setText(
            f'{sample.cooling_pct:.1f} %' if sample.cooling_pct is not None else '---')
        if sample.alarms == ['No alarms']:
            self.val_alarm.setText('✓  No alarms')
            self.val_alarm.setObjectName('status_ok')
        else:
            self.val_alarm.setText('✗  ' + '; '.join(sample.alarms))
            self.val_alarm.setObjectName('status_err')
        self.val_alarm.style().unpolish(self.val_alarm)
        self.val_alarm.style().polish(self.val_alarm)

        # Safety check every second — abort immediately if violated
        passed, reason = check_pass_fail(
            sample.inlet_temp, sample.flow_rate,
            sample.b1, sample.b2, sample.b3, 0
        )
        if passed is False:
            self.sig_set_k.emit(0)
            self._end_test('FAIL', reason)

    def set_logfile(self, path: str):
        self.lbl_logfile.setText(path)

    def retranslate(self):
        pass

    def refresh_settings(self):
        pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _end_test(self, result: str, reason: str):
        self._test_active = False
        self._timer.stop()
        if hasattr(self, '_logfile') and self._logfile:
            self._logfile.close()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.edit_serial.setEnabled(True)
        self._style_banner(result.lower(), reason)
        self.lbl_result.setText(result)
        self.lbl_result_reason.setText(reason)
        colour = GREEN if result == 'PASS' else RED if result == 'FAIL' else AMBER
        self.lbl_result.setStyleSheet(f'color: {colour}; font-size: 36px;')

    def _style_banner(self, state: str, msg: str):
        self._banner_state = state
        self._banner_msg   = msg
        if state == 'running':
            text = f'STEP {self._current_step}/{len(self._step_table) - 1} — RUNNING'
            self.banner.setText(text)
            self.banner.setStyleSheet(
                f'background: #064e3b; border: 1px solid {GREEN};'
                f'color: {GREEN}; font-size: 13px; letter-spacing: 2px; padding: 6px;')
        elif state == 'pass':
            self.banner.setText(f'✓  PASS — {msg}')
            self.banner.setStyleSheet(
                f'background: #064e3b; border: 1px solid {GREEN};'
                f'color: {GREEN}; font-size: 13px; letter-spacing: 2px; padding: 6px;')
        elif state == 'fail':
            self.banner.setText(f'✗  FAIL — {msg}')
            self.banner.setStyleSheet(
                f'background: #4c0519; border: 1px solid {RED};'
                f'color: {RED}; font-size: 13px; letter-spacing: 2px; padding: 6px;')
        elif state == 'aborted':
            self.banner.setText('■  ABORTED')
            self.banner.setStyleSheet(
                f'background: {SURFACE}; border: 1px solid {AMBER};'
                f'color: {AMBER}; font-size: 13px; letter-spacing: 2px; padding: 6px;')
        else:
            self.banner.setText(tr('ready_msg'))
            self.banner.setStyleSheet(
                f'background: {SURFACE}; border: 1px solid {BORDER};'
                f'color: {AMBER}; font-size: 13px; letter-spacing: 2px; padding: 6px;')
