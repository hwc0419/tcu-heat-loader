# =============================================================================
# stress_test_tab.py — AMAT0 Stress Test
# =============================================================================
# Procedure: AMAT0 heated to ~80C on a separate 2kW heater, then connected
# to the TCU. Operator presses Start — the TCU start command is sent and
# per-second logging begins. Temp settles from the hot-water burst, and the
# run is evaluated against a growing dataset of every run ever performed
# (pass or fail, all added) via per-timestep z-scores over a truncated
# common window plus scalar z-scores for the two transient-time metrics.
# See wiki: AMAT0 Stress Test, and stress_test_logic.py for the statistics.
# =============================================================================

import os
import csv
import time
from datetime import datetime
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QLineEdit, QComboBox,
)

from gui.graph_utils import make_graph_panel
from gui.styles import GREEN, RED, AMBER, TEXT_DIM, pt_secondary
from settings_manager import settings
from translations import tr
from config import (
    TEMP_SETPOINT, STRESS_TEST_TOLERANCE, STRESS_TEST_SETTLE_S,
    STRESS_TEST_TAIL_S, STRESS_TEST_Z_THRESHOLD, STRESS_TEST_MAX_DURATION_S,
    STRESS_TEST_HISTORY_MAX, LOG_DIR,
)
from stress_test_logic import (
    detect_transient_times, should_stop_logging, compute_log_row_fields,
    save_run, load_all_runs, compute_dataset_stats, save_dataset_stats,
    load_dataset_stats, evaluate_run, compute_five_point_summary,
)

_MAX_GRAPH_PTS = STRESS_TEST_MAX_DURATION_S + 1   # fixed upper bound


class StressTestTab(QWidget):
    """AMAT0 stress test panel — burst-and-decay vs growing reference dataset."""

    sig_test_start = pyqtSignal()   # tells main_window to send TCU start + begin logging
    sig_test_stop  = pyqtSignal()

    def __init__(self, scale: float = 1.0, parent=None):
        self._scale = scale
        super().__init__(parent)

        self._test_active = False
        self._run_id       = None
        self._temp_series  = []
        self._flow_series  = []
        self._dataset_max_test_end_time = None
        self._own_floor    = None   # this run's own settle_time floor (used only
                                     # when no dataset floor exists yet — re-captured
                                     # fresh each time settle_time resets after a wobble)
        self._writer  = None
        self._logfile = None

        self._graph_t    = deque(maxlen=_MAX_GRAPH_PTS)
        self._graph_temp = deque(maxlen=_MAX_GRAPH_PTS)
        self._graph_flow = deque(maxlen=_MAX_GRAPH_PTS)

        self._history_runs = []   # last up-to-100 run dicts, newest last; combo index i+1 -> this[i]
        self._viewing_history = False   # True while a past run is shown instead of the live graph

        self._build_ui()
        self._setup_graph()
        self._refresh_history()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        left  = QVBoxLayout()
        right = QVBoxLayout()
        root.addLayout(left, 2)
        root.addLayout(right, 1)

        self.banner = QLabel('Ready — connect AMAT0 to TCU, then press Start')
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setMinimumHeight(int(36 * self._scale))
        self._style_banner('ready', '')
        left.addWidget(self.banner)

        history_row = QHBoxLayout()
        history_row.addWidget(QLabel('History:'))
        self.combo_history = QComboBox()
        self.combo_history.addItem('Live / current run')
        self.combo_history.currentIndexChanged.connect(self._on_history_selected)
        history_row.addWidget(self.combo_history, 1)
        left.addLayout(history_row)

        graph_container, self._plot, _ = make_graph_panel('AMAT0 Stress Test', self._scale)
        left.addWidget(graph_container, 1)

        serial_row = QHBoxLayout()
        serial_row.addWidget(QLabel('TCU Serial No.:'))
        self.edit_serial = QLineEdit()
        self.edit_serial.setPlaceholderText('Required before starting')
        self.edit_serial.textChanged.connect(self._on_serial_changed)
        serial_row.addWidget(self.edit_serial)
        left.addLayout(serial_row)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton('Start')
        self.btn_start.setObjectName('btn_start')
        self.btn_start.setEnabled(False)   # disabled until a serial number is entered
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_stop = QPushButton('Stop')
        self.btn_stop.setObjectName('btn_stop')
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        left.addLayout(btn_row)

        grp_info = QGroupBox('Test Info')
        ig = QGridLayout(grp_info)
        self.val_elapsed   = QLabel('--')
        self.val_transient_start = QLabel('--')
        self.val_test_end  = QLabel('--')
        self.val_transient_end   = QLabel('--')
        self.val_dataset_n = QLabel('--')
        rows = [
            ('Elapsed', self.val_elapsed),
            ('Transient start', self.val_transient_start),
            ('Test end time', self.val_test_end),
            ('Transient end', self.val_transient_end),
            ('Dataset size', self.val_dataset_n),
        ]
        for i, (lbl, widget) in enumerate(rows):
            ig.addWidget(QLabel(lbl), i, 0)
            ig.addWidget(widget, i, 1)
        right.addWidget(grp_info)

        grp_result = QGroupBox('Result')
        rg = QVBoxLayout(grp_result)
        self.lbl_result = QLabel('--')
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setStyleSheet(f'font-size: 28px; color: {TEXT_DIM};')
        rg.addWidget(self.lbl_result)
        self.lbl_logfile = QLabel(tr('not_started'))
        self.lbl_logfile.setObjectName('label_dim')
        self.lbl_logfile.setWordWrap(True)
        rg.addWidget(self.lbl_logfile)
        right.addWidget(grp_result)

        grp_stats = QGroupBox('Dataset Statistics (5-point summary)')
        sg = QGridLayout(grp_stats)
        sg.addWidget(QLabel(''), 0, 0)
        sg.addWidget(QLabel('Min'), 0, 1)
        sg.addWidget(QLabel('Q1'), 0, 2)
        sg.addWidget(QLabel('Median'), 0, 3)
        sg.addWidget(QLabel('Q3'), 0, 4)
        sg.addWidget(QLabel('Max'), 0, 5)
        self.val_summary_start = [QLabel('--') for _ in range(5)]
        self.val_summary_end   = [QLabel('--') for _ in range(5)]
        sg.addWidget(QLabel('Transient start'), 1, 0)
        for i, lbl in enumerate(self.val_summary_start):
            sg.addWidget(lbl, 1, i + 1)
        sg.addWidget(QLabel('Transient end'), 2, 0)
        for i, lbl in enumerate(self.val_summary_end):
            sg.addWidget(lbl, 2, i + 1)
        right.addWidget(grp_stats)

        right.addStretch()

    def _setup_graph(self):
        plot_item = self._plot.getPlotItem()
        plot_item.setLabel('left', 'Temperature', units='°C')
        plot_item.setLabel('bottom', 'Time', units='s')
        plot_item.showGrid(x=True, y=True, alpha=0.2)
        self._curve_temp = plot_item.plot([], [], pen=pg.mkPen('#0077B6', width=2), name='Temperature')

        # Flow rate on a second Y-axis (right side) — different units/scale
        # from temperature, so it needs its own linked ViewBox rather than
        # sharing the left axis.
        self._flow_vb = pg.ViewBox()
        plot_item.showAxis('right')
        plot_item.scene().addItem(self._flow_vb)
        plot_item.getAxis('right').linkToView(self._flow_vb)
        self._flow_vb.setXLink(plot_item)
        plot_item.getAxis('right').setLabel('Flow Rate', units='L/min')
        self._curve_flow = pg.PlotCurveItem([], [], pen=pg.mkPen('#FFB703', width=2))
        self._flow_vb.addItem(self._curve_flow)

        def _sync_flow_view():
            self._flow_vb.setGeometry(plot_item.vb.sceneBoundingRect())
        plot_item.vb.sigResized.connect(_sync_flow_view)
        _sync_flow_view()

        self._fail_lines = []   # vertical InfiniteLine items for failing timesteps
        self._transient_markers = []   # vertical InfiniteLine items for transient start/end, drawn every run

    # ── Test control ─────────────────────────────────────────────────────────

    def _on_serial_changed(self, text: str):
        if not self._test_active:
            self.btn_start.setEnabled(bool(text.strip()))

    def _refresh_history(self, all_runs=None):
        """Reload the dropdown with the most recent STRESS_TEST_HISTORY_MAX runs.
        Pass all_runs if the caller already has a fresh load_all_runs() result,
        to avoid reading every run file from disk a second time."""
        if all_runs is None:
            all_runs = load_all_runs()
        self._history_runs = all_runs[-STRESS_TEST_HISTORY_MAX:]   # most recent N, oldest-first within that window
        self.combo_history.blockSignals(True)
        self.combo_history.clear()
        self.combo_history.addItem('Live / current run')
        for run in self._history_runs:   # bound: at most STRESS_TEST_HISTORY_MAX iterations
            serial = run.get('tcu_serial') or '(no serial)'
            label = f"{run['run_id']} — {serial}"
            self.combo_history.addItem(label)
        self.combo_history.blockSignals(False)
        self._update_summary_display(all_runs)

    def _update_summary_display(self, all_runs: list):
        summary = compute_five_point_summary(all_runs)
        if summary is None:
            for lbl in self.val_summary_start + self.val_summary_end:
                lbl.setText('--')
            return
        for lbl, key in zip(self.val_summary_start, ('min', 'q1', 'median', 'q3', 'max')):
            lbl.setText(f"{summary['transient_start_time'][key]:.1f}")
        for lbl, key in zip(self.val_summary_end, ('min', 'q1', 'median', 'q3', 'max')):
            lbl.setText(f"{summary['transient_end_time'][key]:.1f}")

    def _on_history_selected(self, index: int):
        if index <= 0:
            # "Live / current run" — restore whatever the live graph currently holds
            self._viewing_history = False
            self._curve_temp.setData(list(self._graph_t), list(self._graph_temp))
            self._curve_flow.setData(list(self._graph_t), list(self._graph_flow))
            self._clear_transient_markers()
            return
        self._viewing_history = True
        run = self._history_runs[index - 1]
        t = list(range(len(run['temp_series'])))
        self._curve_temp.setData(t, run['temp_series'])
        self._curve_flow.setData(t, run.get('flow_series', []))
        self._draw_transient_markers(run['transient_start_time'], run['transient_end_time'])

    def _on_start_clicked(self):
        if self._test_active:
            return
        if not self.edit_serial.text().strip():
            return   # defensive guard — button should already be disabled in this case
        self.combo_history.setCurrentIndex(0)   # snap back to live view if a history run was selected
        self._viewing_history = False
        self._test_active = True
        self._temp_series = []
        self._flow_series = []
        self._own_floor   = None
        self._graph_t.clear()
        self._graph_temp.clear()
        self._graph_flow.clear()
        self._clear_fail_lines()
        self._clear_transient_markers()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.edit_serial.setEnabled(False)   # locked for the duration of the run
        self._style_banner('running', '')

        stats = load_dataset_stats()
        self._dataset_max_test_end_time = stats['max_test_end_time'] if stats else None
        self.val_dataset_n.setText(str(stats['n_runs']) if stats else '0')

        self._run_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, f'stress_test_{self._run_id}.csv')
        self._logfile = open(log_path, 'w', newline='')
        self._writer = csv.writer(self._logfile)
        self._writer.writerow([
            'elapsed_s', 'temp', 'flow_rate', 'in_tolerance',
            'transient_start_time', 'test_end_time', 'transient_end_time',
        ])
        self.lbl_logfile.setText(log_path)

        self.sig_test_start.emit()
        self._timer.start(1000)

    def _on_stop_clicked(self):
        self._finalise(aborted=True)

    def _tick(self):
        if not self._test_active:
            return
        elapsed_s = len(self._temp_series) - 1
        if elapsed_s >= STRESS_TEST_MAX_DURATION_S:
            self._finalise(aborted=True)
            return
        row = compute_log_row_fields(
            self._temp_series, TEMP_SETPOINT, STRESS_TEST_TOLERANCE, STRESS_TEST_SETTLE_S)
        self.val_elapsed.setText(f'{elapsed_s} s')
        self.val_transient_start.setText(
            str(row['transient_start_time']) if row['transient_start_time'] is not None else '--')
        self.val_test_end.setText(
            str(row['test_end_time']) if row['test_end_time'] is not None else '--')
        self.val_transient_end.setText(
            str(row['transient_end_time']) if row['transient_end_time'] is not None else '--')

        # Maintain this run's own floor: re-captured fresh every time
        # test_end_time transitions from None to a value (i.e. right after a
        # fresh settle is achieved, whether at the start or after a wobble
        # reset). Only used as the required floor when no dataset history
        # exists yet — see should_stop_logging's required_test_end_time arg.
        if row['test_end_time'] is None:
            self._own_floor = None
        elif self._own_floor is None:
            self._own_floor = row['test_end_time']

        required_floor = (
            self._own_floor if self._dataset_max_test_end_time is None
            else self._dataset_max_test_end_time
        )
        if should_stop_logging(row['test_end_time'], required_floor,
                                STRESS_TEST_TAIL_S, elapsed_s):
            self._finalise(aborted=False, row=row)

    def update_sample(self, sample):
        """Called every second by main_window with the latest DAQ sample."""
        if not self._test_active:
            return
        temp = sample.inlet_temp if sample.inlet_temp is not None else (
            self._temp_series[-1] if self._temp_series else TEMP_SETPOINT)
        flow = sample.flow_rate if sample.flow_rate is not None else (
            self._flow_series[-1] if self._flow_series else 0.0)
        self._temp_series.append(temp)
        self._flow_series.append(flow)

        t = len(self._temp_series) - 1
        self._graph_t.append(t)
        self._graph_temp.append(temp)
        self._graph_flow.append(flow)
        if not self._viewing_history:
            self._curve_temp.setData(list(self._graph_t), list(self._graph_temp))
            self._curve_flow.setData(list(self._graph_t), list(self._graph_flow))

        row = compute_log_row_fields(
            self._temp_series, TEMP_SETPOINT, STRESS_TEST_TOLERANCE, STRESS_TEST_SETTLE_S)
        if self._writer is not None:
            self._writer.writerow([
                t, f'{temp:.3f}', f'{flow:.2f}', int(row['in_tolerance']),
                row['transient_start_time'], row['test_end_time'], row['transient_end_time'],
            ])
            self._logfile.flush()

    def on_tcu_abnormal(self):
        """Called by main_window if TCU BS status goes abnormal mid-test."""
        if self._test_active:
            self._finalise(aborted=True, reason='TCU abnormal — aborted')

    def _finalise(self, aborted: bool, row=None, reason=None):
        if not self._test_active:
            return
        self._test_active = False
        self._timer.stop()
        self.btn_start.setEnabled(bool(self.edit_serial.text().strip()))
        self.btn_stop.setEnabled(False)
        self.edit_serial.setEnabled(True)

        if self._logfile is not None:
            self._logfile.close()
            self._logfile = None
            self._writer = None

        if aborted:
            self._style_banner('aborted', reason or 'Aborted by operator')
            self.lbl_result.setText('ABORTED')
            self.lbl_result.setStyleSheet(f'font-size: 28px; color: {AMBER};')
            self.sig_test_stop.emit()
            return

        start, test_end_time, end = (
            row['transient_start_time'], row['test_end_time'], row['transient_end_time'])
        self._draw_transient_markers(start, end)

        stats = load_dataset_stats()
        result = evaluate_run(self._temp_series, self._flow_series, start, end, stats)
        save_run(self._run_id, self._temp_series, self._flow_series,
                  start, test_end_time, end, result['passed'],
                  tcu_serial=self.edit_serial.text().strip())
        runs = load_all_runs()
        new_stats = compute_dataset_stats(runs)
        save_dataset_stats(new_stats)
        self.val_dataset_n.setText(str(new_stats['n_runs']))
        self._refresh_history(runs)

        if result['passed'] is None:
            self._style_banner('ready', 'Recorded — not enough dataset history to evaluate yet')
            self.lbl_result.setText('RECORDED')
            self.lbl_result.setStyleSheet(f'font-size: 28px; color: {TEXT_DIM};')
        elif result['passed']:
            self._style_banner('pass', '')
            self.lbl_result.setText('PASS')
            self.lbl_result.setStyleSheet(f'font-size: 28px; color: {GREEN};')
        else:
            self._style_banner('fail', '')
            self.lbl_result.setText('FAIL')
            self.lbl_result.setStyleSheet(f'font-size: 28px; color: {RED};')
            self._draw_fail_lines(result['failing_timesteps'])

        self.sig_test_stop.emit()

    # ── Transient start/end markers (drawn on every run, pass or fail) ─────────

    def _clear_transient_markers(self):
        for line in self._transient_markers:
            self._plot.removeItem(line)
        self._transient_markers = []

    def _draw_transient_markers(self, transient_start_time, transient_end_time):
        self._clear_transient_markers()
        for t, label in ((transient_start_time, 'start'), (transient_end_time, 'end')):
            if t is None:
                continue
            line = pg.InfiniteLine(
                pos=t, angle=90, pen=pg.mkPen(AMBER, width=2),
                label=f'transient {label}', labelOpts={'position': 0.9, 'color': AMBER})
            self._plot.addItem(line)
            self._transient_markers.append(line)

    # ── Fail-line annotation ────────────────────────────────────────────────

    def _clear_fail_lines(self):
        for line in self._fail_lines:
            self._plot.removeItem(line)
        self._fail_lines = []

    def _draw_fail_lines(self, failing_timesteps: list):
        self._clear_fail_lines()
        for t in failing_timesteps:   # bound: len(failing_timesteps) <= window size, already bounded
            line = pg.InfiniteLine(pos=t, angle=90, pen=pg.mkPen(RED, width=1, style=Qt.DashLine))
            self._plot.addItem(line)
            self._fail_lines.append(line)

    # ── Styling / retranslate ────────────────────────────────────────────────

    def _style_banner(self, state: str, msg: str):
        if state == 'running':
            self.banner.setText('RUNNING')
            self.banner.setStyleSheet(
                f'background: #064e3b; border: 1px solid {GREEN};'
                f'color: {GREEN}; font-size: {pt_secondary(13, self._scale)}px; letter-spacing: 2px; padding: 6px;')
        elif state == 'pass':
            self.banner.setText('✓  PASS')
            self.banner.setStyleSheet(
                f'background: #064e3b; border: 1px solid {GREEN};'
                f'color: {GREEN}; font-size: {pt_secondary(13, self._scale)}px; letter-spacing: 2px; padding: 6px;')
        elif state == 'fail':
            self.banner.setText(f'✗  FAIL — {msg}')
            self.banner.setStyleSheet(
                f'background: #4c0519; border: 1px solid {RED};'
                f'color: {RED}; font-size: {pt_secondary(13, self._scale)}px; letter-spacing: 2px; padding: 6px;')
        elif state == 'aborted':
            self.banner.setText(f'Aborted — {msg}')
            self.banner.setStyleSheet(
                f'background: #422006; border: 1px solid {AMBER};'
                f'color: {AMBER}; font-size: {pt_secondary(13, self._scale)}px; letter-spacing: 2px; padding: 6px;')
        else:
            self.banner.setText(msg or 'Ready — connect AMAT0 to TCU, then press Start')
            self.banner.setStyleSheet(
                f'background: #1a1a1a; border: 1px solid {TEXT_DIM};'
                f'color: {TEXT_DIM}; font-size: {pt_secondary(13, self._scale)}px; letter-spacing: 2px; padding: 6px;')

    def retranslate(self):
        pass   # static English labels for now — matches current app-wide convention elsewhere
