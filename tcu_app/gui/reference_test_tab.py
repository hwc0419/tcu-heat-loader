# =============================================================================
# reference_test_tab.py — AMAT0 Test: Reference subtab
# =============================================================================
# Two jobs:
#   1. Run a simplified version of the AMAT0 test whose ONLY purpose is to
#      add to the pass/ reference dataset — no pass/fail verdict is shown
#      or computed, since the whole point is BUILDING the comparison set,
#      not evaluating against one. Every completed run here is auto-filed
#      into pass/ unconditionally.
#   2. Manage the reference dataset directly: view every pass/fail run in
#      a table, delete any entry, import a run from an externally-supplied
#      CSV (matching the app's own per-second log schema), and visualise
#      any selected run's temp/flow graph.
#
# The Main subtab (main_test_tab.py) is gated on this dataset reaching
# STRESS_TEST_MIN_SEED_RUNS pass/ entries — see stress_test_tab.py for the
# outer wrapper that holds both subtabs and the gating check.
# =============================================================================

import os
import csv
import glob
from datetime import datetime
from collections import deque

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
)
from gui.osk import OskLineEdit as QLineEdit

from gui.graph_utils import make_graph_panel
from gui.styles import GREEN, RED, AMBER, TEXT_DIM, pt_secondary
from config import (
    TEMP_SETPOINT, STRESS_TEST_TOLERANCE, STRESS_TEST_SETTLE_S,
    STRESS_TEST_DURATION_S, STRESS_TEST_MIN_SEED_RUNS,
    STRESS_TEST_MAX_DURATION_S, LOG_DIR,
)
from stress_test_logic import (
    compute_log_row_fields, should_stop_fixed_duration,
    save_run, load_runs, delete_run, detect_transient_times,
)

_MAX_GRAPH_PTS = STRESS_TEST_MAX_DURATION_S + 1
_MAX_TABLE_ROWS = 10000   # fixed upper bound — sanity ceiling on the dataset table


class ReferenceTestTab(QWidget):
    """AMAT0 Reference subtab — builds and manages the pass/ comparison dataset."""

    sig_test_start = pyqtSignal()
    sig_test_stop  = pyqtSignal()
    sig_dataset_changed = pyqtSignal()   # tells the outer wrapper to re-check the Main subtab's gate

    def __init__(self, scale: float = 1.0, parent=None):
        self._scale = scale
        super().__init__(parent)

        self._test_active = False
        self._run_id = None
        self._temp_series = []
        self._flow_series = []
        self._writer = None
        self._logfile = None

        self._graph_t    = deque(maxlen=_MAX_GRAPH_PTS)
        self._graph_temp = deque(maxlen=_MAX_GRAPH_PTS)
        self._graph_flow = deque(maxlen=_MAX_GRAPH_PTS)

        self._build_ui()
        self._setup_graph()
        self._refresh_table()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()
        top.addLayout(left, 2)
        top.addLayout(right, 1)
        root.addLayout(top, 1)

        self.lbl_count = QLabel('')
        self.lbl_count.setAlignment(Qt.AlignCenter)
        self._update_count_label()
        left.addWidget(self.lbl_count)

        graph_container, self._plot, _ = make_graph_panel('Reference Run', self._scale)
        left.addWidget(graph_container, 1)

        serial_row = QHBoxLayout()
        serial_row.addWidget(QLabel('TCU Serial No. (optional):'))
        self.edit_serial = QLineEdit()
        self.edit_serial.setPlaceholderText('Optional — reference runs are not scored')
        serial_row.addWidget(self.edit_serial)
        left.addLayout(serial_row)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton('Start')
        self.btn_start.setObjectName('btn_start')
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_stop = QPushButton('Stop')
        self.btn_stop.setObjectName('btn_stop')
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        left.addLayout(btn_row)

        self.lbl_status = QLabel('Ready — connect AMAT0 to TCU, then press Start')
        self.lbl_status.setObjectName('label_dim')
        self.lbl_status.setWordWrap(True)
        left.addWidget(self.lbl_status)

        # Live readings — fills the empty space below the run controls.
        grp_live = QGroupBox('Live Readings')
        lg = QGridLayout(grp_live)
        def _mk(label):
            lbl = QLabel(label)
            val = QLabel('--')
            val.setObjectName('value_label')
            return lbl, val
        self.lbl_r_temp,    self.val_r_temp    = _mk('Inlet Temp')
        self.lbl_r_flow,    self.val_r_flow    = _mk('Flow Rate')
        self.lbl_r_voltage, self.val_r_voltage = _mk('Voltage')
        self.lbl_r_current, self.val_r_current = _mk('Current')
        self.lbl_r_power,   self.val_r_power   = _mk('Power')
        for row_i, (lbl, val) in enumerate([
            (self.lbl_r_temp,    self.val_r_temp),
            (self.lbl_r_flow,    self.val_r_flow),
            (self.lbl_r_voltage, self.val_r_voltage),
            (self.lbl_r_current, self.val_r_current),
            (self.lbl_r_power,   self.val_r_power),
        ]):
            lg.addWidget(lbl, row_i, 0)
            lg.addWidget(val, row_i, 1)
        left.addWidget(grp_live)

        grp_info = QGroupBox('Run Info')
        ig = QGridLayout(grp_info)
        self.val_elapsed = QLabel('--')
        self.val_transient_start = QLabel('--')
        self.val_test_end = QLabel('--')
        self.val_transient_end = QLabel('--')
        for i, (lbl, widget) in enumerate([
            ('Elapsed', self.val_elapsed),
            ('Transient start', self.val_transient_start),
            ('Test end time', self.val_test_end),
            ('Transient end', self.val_transient_end),
        ]):
            ig.addWidget(QLabel(lbl), i, 0)
            ig.addWidget(widget, i, 1)
        right.addWidget(grp_info)
        right.addStretch()

        # ── Dataset management table ────────────────────────────────────────
        root.addWidget(self._h_divider())
        mgmt_header = QHBoxLayout()
        mgmt_header.addWidget(QLabel('Reference Dataset'))
        mgmt_header.addStretch()
        self.btn_import = QPushButton('Import from CSV...')
        self.btn_import.clicked.connect(self._on_import_clicked)
        mgmt_header.addWidget(self.btn_import)
        self.btn_view = QPushButton('View Selected')
        self.btn_view.clicked.connect(self._on_view_clicked)
        mgmt_header.addWidget(self.btn_view)
        self.btn_delete = QPushButton('Delete Selected')
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        mgmt_header.addWidget(self.btn_delete)
        root.addLayout(mgmt_header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ['Run ID', 'Serial', 'Transient Duration (s)', 'Verdict', 'Source'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table)

    def _h_divider(self):
        from PyQt5.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        return line

    def _setup_graph(self):
        plot_item = self._plot.getPlotItem()
        plot_item.setLabel('left', 'Temperature', units='°C')
        plot_item.setLabel('bottom', 'Time', units='s')
        plot_item.showGrid(x=True, y=True, alpha=0.2)
        self._curve_temp = plot_item.plot([], [], pen=pg.mkPen('#0077B6', width=2), name='Temperature')

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

    # ── Count label ─────────────────────────────────────────────────────────

    def _update_count_label(self):
        n = len(load_runs('pass'))
        if n >= STRESS_TEST_MIN_SEED_RUNS:
            self.lbl_count.setText(f'Reference dataset: {n} runs (minimum of {STRESS_TEST_MIN_SEED_RUNS} reached — Main test is available)')
            self.lbl_count.setStyleSheet(f'color: {GREEN}; font-weight: bold;')
        else:
            self.lbl_count.setText(f'Reference dataset: {n} / {STRESS_TEST_MIN_SEED_RUNS} runs — Main test is locked until {STRESS_TEST_MIN_SEED_RUNS} reference runs exist')
            self.lbl_count.setStyleSheet(f'color: {AMBER}; font-weight: bold;')

    # ── Test control ─────────────────────────────────────────────────────────

    def _on_start_clicked(self):
        if self._test_active:
            return
        self._test_active = True
        self._temp_series = []
        self._flow_series = []
        self._graph_t.clear()
        self._graph_temp.clear()
        self._graph_flow.clear()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.edit_serial.setEnabled(False)
        self.lbl_status.setText('Running — collecting reference data')
        self.lbl_status.setStyleSheet(f'color: {GREEN};')

        self._run_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, f'reference_run_{self._run_id}.csv')
        self._logfile = open(log_path, 'w', newline='')
        self._writer = csv.writer(self._logfile)
        self._writer.writerow([
            'elapsed_s', 'temp', 'flow_rate', 'in_tolerance',
            'transient_start_time', 'test_end_time', 'transient_end_time',
        ])

        self.sig_test_start.emit()
        self._timer.start(1000)

    def _on_stop_clicked(self):
        self._finalise(aborted=True)

    def _tick(self):
        if not self._test_active:
            return
        elapsed_s = len(self._temp_series) - 1
        if should_stop_fixed_duration(elapsed_s, STRESS_TEST_DURATION_S):
            self._finalise(aborted=False)
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

    def update_sample(self, sample):
        """Called every second by main_window with the latest DAQ sample."""
        self.val_r_temp.setText(
            f'{sample.inlet_temp:.2f} °C' if sample.inlet_temp is not None else '--')
        self.val_r_flow.setText(
            f'{sample.flow_rate:.1f} L/min' if sample.flow_rate is not None else '--')
        self.val_r_voltage.setText(
            f'{sample.voltage:.1f} V' if sample.voltage is not None else '--')
        self.val_r_current.setText(
            f'{sample.current:.3f} A' if sample.current is not None else '--')
        self.val_r_power.setText(
            f'{sample.power:.0f} W' if sample.power is not None else '--')

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
        if self._test_active:
            self._finalise(aborted=True, reason='TCU abnormal — aborted')

    def _finalise(self, aborted: bool, reason=None):
        if not self._test_active:
            return
        self._test_active = False
        self._timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.edit_serial.setEnabled(True)

        if self._logfile is not None:
            self._logfile.close()
            self._logfile = None
            self._writer = None

        if aborted:
            self.lbl_status.setText(reason or 'Aborted by operator — not added to reference dataset')
            self.lbl_status.setStyleSheet(f'color: {AMBER};')
            self.sig_test_stop.emit()
            return

        row = compute_log_row_fields(
            self._temp_series, TEMP_SETPOINT, STRESS_TEST_TOLERANCE, STRESS_TEST_SETTLE_S)
        start, test_end_time, end = (
            row['transient_start_time'], row['test_end_time'], row['transient_end_time'])

        # Reference runs always auto-file into pass/ unconditionally — the
        # whole point of this subtab is building the comparison dataset,
        # there is no verdict to compute here.
        save_run(self._run_id, STRESS_TEST_DURATION_S, 'pass',
                  self._temp_series, self._flow_series,
                  start, test_end_time, end,
                  tcu_serial=self.edit_serial.text().strip())

        self.lbl_status.setText('Added to reference dataset')
        self.lbl_status.setStyleSheet(f'color: {GREEN};')
        self._update_count_label()
        self._refresh_table()
        self.sig_dataset_changed.emit()
        self.sig_test_stop.emit()

    # ── Dataset management ───────────────────────────────────────────────────

    def _refresh_table(self):
        self._update_count_label()
        pass_runs = load_runs('pass')
        fail_runs = load_runs('fail')
        all_runs = [(r, 'pass') for r in pass_runs] + [(r, 'fail') for r in fail_runs]
        all_runs = all_runs[:_MAX_TABLE_ROWS]

        self.table.setRowCount(len(all_runs))
        for i, (run, verdict) in enumerate(all_runs):   # bound: _MAX_TABLE_ROWS
            duration = (
                run['transient_end_time'] - run['transient_start_time']
                if run.get('transient_start_time') is not None and run.get('transient_end_time') is not None
                else None
            )
            self.table.setItem(i, 0, QTableWidgetItem(run.get('run_id', '')))
            self.table.setItem(i, 1, QTableWidgetItem(run.get('tcu_serial') or ''))
            self.table.setItem(i, 2, QTableWidgetItem(str(duration) if duration is not None else '--'))
            self.table.setItem(i, 3, QTableWidgetItem(verdict.upper()))
            self.table.setItem(i, 4, QTableWidgetItem('imported' if run.get('imported') else 'test run'))

    def _selected_run(self):
        """Returns (run_dict, verdict) for the currently-selected table row, or (None, None)."""
        row_idx = self.table.currentRow()
        if row_idx < 0:
            return None, None
        run_id = self.table.item(row_idx, 0).text()
        verdict = self.table.item(row_idx, 3).text().lower()
        for run in load_runs(verdict):   # bound: dataset size, already capped by load_runs itself
            if run['run_id'] == run_id:
                return run, verdict
        return None, None

    def _on_delete_clicked(self):
        run, verdict = self._selected_run()
        if run is None:
            QMessageBox.information(self, 'No selection', 'Select a row in the table first.')
            return
        confirm = QMessageBox.question(
            self, 'Delete run',
            f'Remove {run["run_id"]} from the {verdict} dataset? This cannot be undone.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes:
            delete_run(run['run_id'], verdict)
            self._refresh_table()
            self.sig_dataset_changed.emit()

    def _on_view_clicked(self):
        run, verdict = self._selected_run()
        if run is None:
            QMessageBox.information(self, 'No selection', 'Select a row in the table first.')
            return
        t = list(range(len(run['temp_series'])))
        self._curve_temp.setData(t, run['temp_series'])
        self._curve_flow.setData(t, run.get('flow_series', []))
        self.val_transient_start.setText(str(run['transient_start_time']))
        self.val_test_end.setText(str(run['test_end_time']))
        self.val_transient_end.setText(str(run['transient_end_time']))
        self.val_elapsed.setText(f"{len(run['temp_series'])} s (viewing {run['run_id']})")

    def _on_import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import reference run CSV', '', 'CSV files (*.csv)')
        if not path:
            return
        try:
            with open(path) as f:
                rows = list(csv.DictReader(f))
            if not rows or 'temp' not in rows[0] or 'flow_rate' not in rows[0]:
                raise ValueError(
                    "CSV must have 'temp' and 'flow_rate' columns "
                    "(matching this app's own per-second log format)")
            temp_series = [float(r['temp']) for r in rows]
            flow_series = [float(r['flow_rate']) for r in rows]
            start, test_end, end = detect_transient_times(
                temp_series, TEMP_SETPOINT, STRESS_TEST_TOLERANCE, STRESS_TEST_SETTLE_S)
            run_id = os.path.splitext(os.path.basename(path))[0]
            save_run(run_id, STRESS_TEST_DURATION_S, 'pass', temp_series, flow_series,
                      start, test_end, end, tcu_serial='', imported=True)
            self._refresh_table()
            self.sig_dataset_changed.emit()
            QMessageBox.information(self, 'Imported',
                f'Imported {run_id} ({len(temp_series)} samples) into the reference dataset.')
        except (ValueError, KeyError, OSError) as e:
            QMessageBox.warning(self, 'Import failed', f'Could not import {path}:\n{e}')

    # ── Retranslate ───────────────────────────────────────────────────────────

    def retranslate(self):
        pass   # static English labels for now — matches current app-wide convention elsewhere
