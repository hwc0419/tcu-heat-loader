# =============================================================================
# response_test_tab.py — Step Response Test Tab
# =============================================================================
# Steps heater from HEATER_STEP_START_W to HEATER_STEP_END_W in
# HEATER_STEP_SIZE_W increments. Per stage:
#   1. Set heater → start 30-min timer + logging
#   2. Detect transient start (dynamic threshold)
#   3. Detect steady state (rolling window)
#   4. Pause timer → record transient metrics
#   5. Resume timer until 30 min
#   6. Record steady state metrics → step to N+1
# Exports SVG graphs to logs/reports/ and shows summary in-app.
# =============================================================================

import os
import csv
import time
import math
from collections import deque
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QSizePolicy, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg

from settings_manager import settings
from translations import tr
from config import (
    HEATER_MAX_WATTS, LOG_DIR, REPORTS_DIR,
)

_GRAPH_MAX_POINTS = 3600   # 60 min at 1 sample/sec
_MAX_STAGES       = 20     # upper bound for stage loop


class _StageResult:
    """Holds all metrics for one test stage."""
    def __init__(self, stage_w: int):
        self.stage_w          = stage_w
        self.t_cmd            = None   # wall time setpoint sent
        self.t_thermal        = None   # wall time thermal response detected
        self.t_steady         = None   # wall time steady state detected
        self.transient_mean   = None
        self.transient_std    = None
        self.transient_max    = None
        self.transient_min    = None
        self.steady_mean      = None
        self.steady_std       = None
        self.steady_max       = None
        self.steady_min       = None
        self.pzem_mean_w      = None
        self.pzem_mean_v      = None
        self.pzem_mean_a      = None
        self.passed           = None   # bool — 30-min pass/fail


class ResponseTestTab(QWidget):
    """Step response test tab."""

    sig_set_watts = pyqtSignal(int)   # request heater setpoint change
    sig_estop     = pyqtSignal()      # emergency stop

    def __init__(self, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self._scale        = scale
        self._running      = False
        self._stage_idx    = 0
        self._stages       = []        # list of watts per stage
        self._results      = []        # list of _StageResult
        self._current      = None      # _StageResult in progress
        self._t_start      = None      # monotonic time at test start
        self._t_stage      = None      # monotonic time at stage start
        self._timer_paused = False
        self._pause_elapsed= 0.0       # seconds accumulated before pause
        self._phase        = 'idle'    # idle/transient/steady/dwell
        self._baseline_buf = deque(maxlen=60)
        self._ss_buf       = deque()
        self._transient_buf= []
        self._steady_buf   = []
        self._pzem_buf     = []
        self._consecutive  = 0
        self._graph_times  = deque(maxlen=_GRAPH_MAX_POINTS)
        self._water_temps  = deque(maxlen=_GRAPH_MAX_POINTS)
        self._element_temps= deque(maxlen=_GRAPH_MAX_POINTS)
        self._inlet_temps  = deque(maxlen=_GRAPH_MAX_POINTS)
        self._t0           = time.monotonic()
        self._stage_lines  = []
        self._csv_path     = None
        self._csv_rows     = []
        self._build_ui()
        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._on_tick)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 12, 16, 12)

        top = QHBoxLayout()
        top.addLayout(self._build_status_panel(), stretch=1)
        top.addLayout(self._build_controls_panel(), stretch=1)
        root.addLayout(top)
        root.addWidget(self._build_graph(), stretch=3)
        root.addWidget(self._build_summary_graph(), stretch=2)

    def _build_status_panel(self):
        layout = QVBoxLayout()
        self._grp_status = QGroupBox(tr('resp_status'))
        g = QGridLayout(self._grp_status)
        g.setSpacing(8)

        self._lbl_phase    = QLabel('—')
        self._lbl_stage    = QLabel('—')
        self._lbl_elapsed  = QLabel('00:00')
        self._lbl_t_cmd    = QLabel('—')
        self._lbl_t_thermal= QLabel('—')
        self._lbl_t_steady = QLabel('—')

        rows = [
            ('Phase:',            self._lbl_phase),
            (tr('resp_stage'),    self._lbl_stage),
            (tr('elapsed') + ':', self._lbl_elapsed),
            ('t_cmd:',            self._lbl_t_cmd),
            ('t_thermal:',        self._lbl_t_thermal),
            ('t_steady:',         self._lbl_t_steady),
        ]
        for i, (lbl, widget) in enumerate(rows):
            g.addWidget(QLabel(lbl), i, 0)
            g.addWidget(widget,      i, 1)

        layout.addWidget(self._grp_status)
        layout.addStretch()
        return layout

    def _build_controls_panel(self):
        layout = QVBoxLayout()
        self._grp_ctrl = QGroupBox(tr('test_controls'))
        v = QVBoxLayout(self._grp_ctrl)

        self._btn_start = QPushButton(tr('btn_resp_start'))
        self._btn_start.setObjectName('btn_start')
        self._btn_start.clicked.connect(self._on_start)

        self._btn_stop = QPushButton(tr('btn_resp_stop'))
        self._btn_stop.setObjectName('btn_stop')
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_abort)

        v.addWidget(self._btn_start)
        v.addWidget(self._btn_stop)
        layout.addWidget(self._grp_ctrl)
        layout.addStretch()
        return layout

    def _build_graph(self):
        self._grp_graph = QGroupBox(tr('resp_graph'))
        v = QVBoxLayout(self._grp_graph)
        self._plot = pg.PlotWidget()
        self._plot.setLabel('left',   'Temperature', units='°C')
        self._plot.setLabel('bottom', 'Time', units='s')
        self._plot.addLegend()
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._plot.setMinimumHeight(200)

        self._curve_water   = self._plot.plot(pen=pg.mkPen('#2196F3', width=2),
                                               name='Water @ —')
        self._curve_element = self._plot.plot(pen=pg.mkPen('#F44336', width=2),
                                               name='Element @ —')
        self._curve_inlet   = self._plot.plot(pen=pg.mkPen('#4CAF50', width=2),
                                               name='TCU Inlet')
        v.addWidget(self._plot)
        return self._grp_graph

    def _build_summary_graph(self):
        self._grp_summary = QGroupBox(tr('resp_summary'))
        v = QVBoxLayout(self._grp_summary)
        self._summary_plot = pg.PlotWidget()
        self._summary_plot.setLabel('left',   'Response time', units='s')
        self._summary_plot.setLabel('bottom', 'Heat load', units='W')
        self._summary_plot.showGrid(x=True, y=True, alpha=0.3)
        self._summary_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._summary_plot.setMinimumHeight(150)
        self._summary_curve = self._summary_plot.plot(
            pen=pg.mkPen('#FF9800', width=2),
            symbol='o', symbolSize=6, symbolBrush='#FF9800')
        v.addWidget(self._summary_plot)
        return self._grp_summary

    # ── Start / Abort ─────────────────────────────────────────────────────────
    def _on_start(self):
        step_start = settings.get('heater_step_start_w')
        step_end   = settings.get('heater_step_end_w')
        step_size  = settings.get('heater_step_size_w')

        if not all(isinstance(v, int) for v in (step_start, step_end, step_size)):
            QMessageBox.warning(self, 'Config Error', 'Invalid step settings in config.')
            return
        if step_size <= 0 or step_start >= step_end:
            QMessageBox.warning(self, 'Config Error', 'Invalid step range or size.')
            return

        # Check soft limit — prompt admin password if step_end exceeds it
        soft_limit = settings.get('heater_soft_limit_w')
        if step_end > soft_limit:
            if not self._prompt_admin_password():
                QMessageBox.warning(self, 'Start Rejected',
                    f'Step End ({step_end}W) exceeds soft limit ({soft_limit}W).\n'
                    'Admin authentication required.')
                return

        self._stages = list(range(step_start, step_end + step_size, step_size))
        # Clamp to _MAX_STAGES upper bound
        self._stages = self._stages[:_MAX_STAGES]

        self._results   = []
        self._stage_idx = 0
        self._running   = True
        self._t_start   = time.monotonic()

        os.makedirs(REPORTS_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._csv_path = os.path.join(LOG_DIR, f'step_response_{ts}.csv')
        self._csv_rows = []

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)

        self._ticker.start()
        self._begin_stage()

    def _on_abort(self):
        self._running = False
        self._ticker.stop()
        self.sig_set_watts.emit(0)
        self._phase = 'idle'
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._lbl_phase.setText('Aborted')
        self._save_csv()
        self._update_summary_graph()

    # ── Stage management ──────────────────────────────────────────────────────
    def _begin_stage(self):
        if self._stage_idx >= len(self._stages):
            self._finish_test()
            return
        watts = self._stages[self._stage_idx]
        self._current = _StageResult(watts)
        self._current.t_cmd = time.monotonic()
        self._baseline_buf.clear()
        self._ss_buf.clear()
        self._transient_buf.clear()
        self._steady_buf  = []
        self._pzem_buf    = []
        self._consecutive = 0
        self._t_stage     = time.monotonic()
        self._timer_paused= False
        self._pause_elapsed = 0.0
        self._phase = 'transient'

        self.sig_set_watts.emit(watts)
        self._lbl_stage.setText(f'{watts} W')
        self._lbl_phase.setText('Transient')
        self._add_stage_line()
        self._update_graph_labels(watts)

    def _add_stage_line(self):
        t = time.monotonic() - self._t0
        line = pg.InfiniteLine(pos=t, angle=90,
                               pen=pg.mkPen('#9C27B0', style=Qt.DashLine, width=1))
        self._plot.addItem(line)
        self._stage_lines.append(line)

    def _update_graph_labels(self, watts: int):
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

    # ── Per-tick logic ────────────────────────────────────────────────────────
    def _on_tick(self):
        if not self._running:
            return
        elapsed = self._get_stage_elapsed()
        dur_sec = settings.get('step_test_duration_min') * 60
        mm, ss  = divmod(int(elapsed), 60)
        self._lbl_elapsed.setText(f'{mm:02d}:{ss:02d}')

        if elapsed >= dur_sec:
            self._finish_stage()

    def _get_stage_elapsed(self) -> float:
        if self._timer_paused:
            return self._pause_elapsed
        return self._pause_elapsed + (time.monotonic() - self._t_stage)

    def _finish_stage(self):
        r = self._current
        if self._steady_buf:
            vals = self._steady_buf
            r.steady_mean = _mean(vals)
            r.steady_std  = _std(vals)
            r.steady_max  = max(vals)
            r.steady_min  = min(vals)
        if self._pzem_buf:
            r.pzem_mean_w = _mean([x[0] for x in self._pzem_buf])
            r.pzem_mean_v = _mean([x[1] for x in self._pzem_buf])
            r.pzem_mean_a = _mean([x[2] for x in self._pzem_buf])
        r.passed = self._check_pass()
        self._results.append(r)
        self._csv_rows.append(self._result_to_row(r))
        self._stage_idx += 1
        self._begin_stage()

    def _finish_test(self):
        self._running = False
        self._ticker.stop()
        self.sig_set_watts.emit(0)
        self._phase = 'idle'
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._lbl_phase.setText('Complete')
        self._save_csv()
        self._update_summary_graph()
        self._export_svgs()

    # ── Sample ingestion ──────────────────────────────────────────────────────
    def update_sample(self, sample):
        """Called by main_window on every DAQ sample."""
        now = time.monotonic() - self._t0
        water   = getattr(sample, 'water_temp',   None)
        element = getattr(sample, 'element_temp', None)
        water   = water   if water   is not None else float('nan')
        element = element if element is not None else float('nan')
        inlet   = sample.inlet_temp if sample.inlet_temp is not None else float('nan')

        self._graph_times.append(now)
        self._water_temps.append(water)
        self._element_temps.append(element)
        self._inlet_temps.append(inlet)

        t = list(self._graph_times)
        self._curve_water.setData(t, list(self._water_temps))
        self._curve_element.setData(t, list(self._element_temps))
        self._curve_inlet.setData(t, list(self._inlet_temps))

        if not self._running or self._current is None:
            return

        if not math.isnan(water):
            self._process_water_sample(water, sample)

    def _process_water_sample(self, water: float, sample):
        r = self._current
        if self._phase == 'transient':
            self._baseline_buf.append(water)
            self._transient_buf.append(water)
            self._check_transient_start(water, r)
        elif self._phase == 'steady_detect':
            self._transient_buf.append(water)
            self._check_steady_state(water, r)
        elif self._phase == 'steady':
            self._steady_buf.append(water)
            p = sample.power   or 0.0
            v = sample.voltage or 0.0
            a = sample.current or 0.0
            self._pzem_buf.append((p, v, a))
            if self._timer_paused:
                self._timer_paused = False
                self._t_stage = time.monotonic()

    def _check_transient_start(self, water: float, r: '_StageResult'):
        if len(self._baseline_buf) < settings.get('thermal_response_min_samples'):
            return
        baseline_vals = list(self._baseline_buf)
        mean_b = _mean(baseline_vals)
        std_b  = _std(baseline_vals)
        sigma  = settings.get('thermal_response_sigma')
        thresh = settings.get('thermal_response_threshold')
        dynamic_thresh = mean_b + max(thresh, sigma * std_b)

        if water > dynamic_thresh:
            self._consecutive += 1
        else:
            self._consecutive = 0

        min_samples = settings.get('thermal_response_min_samples')
        if self._consecutive >= min_samples:
            r.t_thermal = time.monotonic()
            self._phase = 'steady_detect'
            self._lbl_phase.setText('Detecting steady state')
            lag = r.t_thermal - r.t_cmd
            self._lbl_t_thermal.setText(f'{lag:.1f}s after cmd')
            self._ss_buf.clear()
            self._consecutive = 0

    def _check_steady_state(self, water: float, r: '_StageResult'):
        window_sec = settings.get('steady_state_window_sec')
        tolerance  = settings.get('steady_state_tolerance')
        self._ss_buf.append((time.monotonic(), water))

        # Remove samples outside window
        cutoff = time.monotonic() - window_sec
        while self._ss_buf and self._ss_buf[0][0] < cutoff:
            self._ss_buf.popleft()

        if len(self._ss_buf) < window_sec:
            return

        vals  = [v for _, v in self._ss_buf]
        mean_ = _mean(vals)
        all_within = all(abs(v - mean_) <= tolerance for v in vals)

        if all_within:
            r.t_steady = time.monotonic()
            self._phase = 'steady'
            self._lbl_phase.setText('Steady state — timer resumed')
            lag_total = r.t_steady - r.t_cmd
            self._lbl_t_steady.setText(f'{lag_total:.1f}s after cmd')
            # Record transient metrics
            if self._transient_buf:
                r.transient_mean = _mean(self._transient_buf)
                r.transient_std  = _std(self._transient_buf)
                r.transient_max  = max(self._transient_buf)
                r.transient_min  = min(self._transient_buf)
            # Pause elapsed was updated during transient — resume timer
            self._pause_elapsed += time.monotonic() - self._t_stage
            self._timer_paused = True   # will resume on next steady sample

    # ── Pass/fail check ───────────────────────────────────────────────────────
    def _check_pass(self) -> bool:
        if not self._steady_buf:
            return False
        sp  = settings.get('temp_setpoint')
        tol = settings.get('temp_tolerance')
        return all(abs(v - sp) <= tol for v in self._steady_buf)

    # ── TCU abnormal — auto-stop ───────────────────────────────────────────────
    def on_tcu_abnormal(self):
        """Called by main_window when BS != 400400."""
        if self._running:
            self.sig_set_watts.emit(0)
            self._on_abort()
            QMessageBox.warning(self, 'Test Aborted',
                'TCU reported abnormal status. Heater off. Test aborted.')

    # ── CSV export ────────────────────────────────────────────────────────────
    def _save_csv(self):
        if not self._csv_path or not self._csv_rows:
            return
        headers = [
            'Stage (W)', 't_cmd', 't_thermal (s)', 't_steady (s)',
            'Total response (s)',
            'Transient mean (°C)', 'Transient std (°C)',
            'Transient max (°C)',  'Transient min (°C)',
            'Steady mean (°C)',    'Steady std (°C)',
            'Steady max (°C)',     'Steady min (°C)',
            'PZEM mean W', 'PZEM mean V', 'PZEM mean A',
            'Pass/Fail',
        ]
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(self._csv_path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(headers)
                for row in self._csv_rows:
                    w.writerow(row)
        except Exception as e:
            print(f"ResponseTest: CSV save error — {e}")

    def _result_to_row(self, r: '_StageResult') -> list:
        def fmt(v):
            return f'{v:.3f}' if v is not None else ''
        t_thermal = (r.t_thermal - r.t_cmd) if r.t_thermal else ''
        t_steady  = (r.t_steady  - r.t_cmd) if r.t_steady  else ''
        total     = (r.t_steady  - r.t_cmd) if (r.t_steady and r.t_cmd) else ''
        return [
            r.stage_w,
            datetime.fromtimestamp(r.t_cmd).strftime('%H:%M:%S') if r.t_cmd else '',
            fmt(t_thermal), fmt(t_steady), fmt(total),
            fmt(r.transient_mean), fmt(r.transient_std),
            fmt(r.transient_max),  fmt(r.transient_min),
            fmt(r.steady_mean),    fmt(r.steady_std),
            fmt(r.steady_max),     fmt(r.steady_min),
            fmt(r.pzem_mean_w),    fmt(r.pzem_mean_v),    fmt(r.pzem_mean_a),
            'PASS' if r.passed else 'FAIL',
        ]

    # ── Summary graph ─────────────────────────────────────────────────────────
    def _update_summary_graph(self):
        xs, ys = [], []
        for r in self._results:
            if r.t_cmd and r.t_steady:
                xs.append(r.stage_w)
                ys.append(r.t_steady - r.t_cmd)
        if xs:
            self._summary_curve.setData(xs, ys)

    # ── SVG export ────────────────────────────────────────────────────────────
    def _export_svgs(self):
        for r in self._results:
            if r.t_cmd is None or r.t_steady is None:
                continue
            total = r.t_steady - r.t_cmd
            self._write_svg(r.stage_w, total,
                            r.transient_mean, r.transient_max, r.transient_min)

    def _write_svg(self, watts: int, response_s: float,
                   mean, mx, mn):
        fname = os.path.join(REPORTS_DIR, f'stage_{watts}W.svg')
        mean_s = f'{mean:.2f}' if mean is not None else 'N/A'
        max_s  = f'{mx:.2f}'   if mx   is not None else 'N/A'
        min_s  = f'{mn:.2f}'   if mn   is not None else 'N/A'
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
            f'<rect width="400" height="200" fill="#f9f9f9" stroke="#ccc"/>'
            f'<text x="200" y="30" text-anchor="middle" '
            f'font-family="Arial" font-size="14" font-weight="bold">'
            f'Stage {watts}W — Transient Response</text>'
            f'<text x="20" y="70" font-family="Arial" font-size="12">'
            f'Response time: {response_s:.1f}s</text>'
            f'<text x="20" y="95" font-family="Arial" font-size="12">'
            f'Water temp mean: {mean_s}°C</text>'
            f'<text x="20" y="120" font-family="Arial" font-size="12">'
            f'Water temp max: {max_s}°C</text>'
            f'<text x="20" y="145" font-family="Arial" font-size="12">'
            f'Water temp min: {min_s}°C</text>'
            '</svg>'
        )
        try:
            with open(fname, 'w') as f:
                f.write(svg)
        except Exception as e:
            print(f"ResponseTest: SVG export error — {e}")

    # ── Retranslate ───────────────────────────────────────────────────────────
    def _prompt_admin_password(self) -> bool:
        """Show password dialog. Returns True if correct admin password entered."""
        import hashlib
        from PyQt5.QtWidgets import QInputDialog, QLineEdit
        pw, ok = QInputDialog.getText(
            self, 'Admin Authentication',
            f'Step End exceeds soft limit ({settings.get("heater_soft_limit_w")}W).\n'
            'Enter admin password to proceed:',
            QLineEdit.Password)
        if not ok or not pw:
            return False
        hashed = hashlib.sha256(pw.encode()).hexdigest()
        return hashed == settings.get('access_password_hash')

    def retranslate(self):
        self._grp_status.setTitle(tr('resp_status'))
        self._grp_ctrl.setTitle(tr('test_controls'))
        self._grp_graph.setTitle(tr('resp_graph'))
        self._grp_summary.setTitle(tr('resp_summary'))
        self._btn_start.setText(tr('btn_resp_start'))
        self._btn_stop.setText(tr('btn_resp_stop'))


# ── Stat helpers ──────────────────────────────────────────────────────────────
def _mean(vals: list) -> float:
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _std(vals: list) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))
