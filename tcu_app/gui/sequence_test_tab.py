# =============================================================================
# sequence_test_tab.py — 2kW Heat Load Sequence Test
# =============================================================================
# User defines a sequence of watt loads. TCU starts at K=0, waits for
# initial settle, then switches instantly (no ramping) to each value in the
# sequence in turn, waiting for settle after each switch. An automatic
# trailing 0W stage is always appended. Each stage's settle duration is
# evaluated against a growing per-10W-bin dataset built from every stage
# of every run ever performed. History of past sequences is recallable
# via a searchable list (Ctrl+F to jump).
# =============================================================================

import os
import csv
import random as _random
from datetime import datetime
from collections import deque

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QListWidget, QListWidgetItem,
    QShortcut, QInputDialog, QMessageBox,
)

from gui.osk import OskLineEdit as QLineEdit
from gui.graph_utils import make_graph_panel
from gui.styles import GREEN, RED, AMBER, TEXT_DIM
from settings_manager import settings
from translations import tr
from config import (
    TEMP_SETPOINT, LOG_DIR,
    SEQ_TEST_SETTLE_S, SEQ_TEST_TAIL_S, SEQ_TEST_Z_THRESHOLD,
    SEQ_TEST_MAX_DURATION_S, SEQ_TEST_MAX_STAGES,
)
from test_logic import watts_to_k
from sequence_test_logic import (
    find_settle_point, should_stop_for_settle,
    save_stage, load_all_stages, compute_bin_stats, save_bin_stats,
    load_bin_stats, evaluate_stage, generate_random_sequence,
)

_MAX_GRAPH_PTS = SEQ_TEST_MAX_DURATION_S + 1


class SequenceTestTab(QWidget):
    """2kW heat load sequence test panel."""

    sig_test_start = pyqtSignal(str)   # tcu_serial — main_window sends TCU start
    sig_test_stop  = pyqtSignal()
    sig_set_k      = pyqtSignal(int)
    sig_k_confirmed = pyqtSignal(int)

    def __init__(self, scale: float = 1.0, parent=None):
        self._scale = scale
        super().__init__(parent)

        self._test_active = False
        self._k_pending    = False
        self._run_id       = None
        self._sequence     = []     # list of watts, including auto-appended trailing 0
        self._stage_idx    = -1     # -1 = initial 0W settle, before first user stage
        self._stage_start_t = None
        self._temp_since_stage = []
        self._writer  = None
        self._logfile = None

        self._graph_t    = deque(maxlen=_MAX_GRAPH_PTS)
        self._graph_temp = deque(maxlen=_MAX_GRAPH_PTS)
        self._elapsed_s  = 0

        self._build_ui()
        self._setup_graph()
        self._load_history_into_list()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.sig_k_confirmed.connect(self._on_k_confirmed)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root  = QHBoxLayout(self)
        left  = QVBoxLayout()
        right = QVBoxLayout()
        root.addLayout(left, 2)
        root.addLayout(right, 1)

        self.banner = QLabel('Ready')
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setMinimumHeight(int(36 * self._scale))
        self._style_banner('ready', '')
        left.addWidget(self.banner)

        graph_container, self._plot, _ = make_graph_panel('Sequence Test', self._scale)
        left.addWidget(graph_container, 1)

        grp_seq = QGroupBox('Load Sequence (W, comma-separated)')
        sg = QVBoxLayout(grp_seq)
        self.edit_sequence = QLineEdit()
        self.edit_sequence.setPlaceholderText('e.g. 1000,1234,2000,1000')
        sg.addWidget(self.edit_sequence)

        seq_btn_row = QHBoxLayout()
        self.btn_random = QPushButton('🎲 Random Sequence')
        self.btn_random.clicked.connect(self._on_random_clicked)
        seq_btn_row.addWidget(self.btn_random)
        sg.addLayout(seq_btn_row)
        left.addWidget(grp_seq)

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

        grp_info = QGroupBox('Test Info')
        ig = QGridLayout(grp_info)
        self.val_stage    = QLabel('--')
        self.val_watts    = QLabel('--')
        self.val_elapsed  = QLabel('--')
        self.val_settle   = QLabel('--')
        rows = [
            ('Stage', self.val_stage),
            ('Current watts', self.val_watts),
            ('Stage elapsed', self.val_elapsed),
            ('Settle time', self.val_settle),
        ]
        for i, (lbl, widget) in enumerate(rows):
            ig.addWidget(QLabel(lbl), i, 0)
            ig.addWidget(widget, i, 1)
        right.addWidget(grp_info)

        grp_result = QGroupBox('Result')
        rg = QVBoxLayout(grp_result)
        self.lbl_result = QLabel('--')
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setStyleSheet(f'font-size: 24px; color: {TEXT_DIM};')
        rg.addWidget(self.lbl_result)
        self.lbl_logfile = QLabel(tr('not_started'))
        self.lbl_logfile.setObjectName('label_dim')
        self.lbl_logfile.setWordWrap(True)
        rg.addWidget(self.lbl_logfile)
        right.addWidget(grp_result)

        grp_history = QGroupBox('History (Ctrl+F to search)')
        hg = QVBoxLayout(grp_history)
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText('Search history…')
        self.edit_search.textChanged.connect(self._on_search_changed)
        hg.addWidget(self.edit_search)
        self.list_history = QListWidget()
        self.list_history.itemDoubleClicked.connect(self._on_history_item_chosen)
        hg.addWidget(self.list_history)
        right.addWidget(grp_history, 1)

        shortcut = QShortcut(QKeySequence('Ctrl+F'), self)
        shortcut.activated.connect(lambda: self.edit_search.setFocus())

    def _setup_graph(self):
        self._plot.setLabel('left', 'Temperature', units='°C')
        self._plot.setLabel('bottom', 'Time', units='s')
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._curve_temp = self._plot.plot([], [], pen=pg.mkPen('#0077B6', width=2))
        self._stage_lines = []

    # ── History buffer ──────────────────────────────────────────────────────

    def _load_history_into_list(self):
        self.list_history.clear()
        history = settings.get('seq_test_history') or []
        for entry in history:   # bound: len(history), grows by 1 per run, no pathological size expected
            ts  = entry.get('timestamp', '?')
            seq = entry.get('sequence', [])
            text = f"{ts} — {', '.join(str(w) for w in seq)}"
            self.list_history.addItem(QListWidgetItem(text))

    def _append_to_history(self, sequence: list):
        history = settings.get('seq_test_history') or []
        history.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sequence': sequence,
        })
        settings.set('seq_test_history', history)
        self._load_history_into_list()

    def _on_search_changed(self, text: str):
        text = text.lower()
        for i in range(self.list_history.count()):   # bound: history length
            item = self.list_history.item(i)
            item.setHidden(bool(text) and text not in item.text().lower())

    def _on_history_item_chosen(self, item: QListWidgetItem):
        text = item.text()
        if '—' not in text:
            return
        seq_part = text.split('—', 1)[1].strip()
        self.edit_sequence.setText(seq_part.replace(' ', ''))

    # ── Sequence editor helpers ─────────────────────────────────────────────

    def _on_random_clicked(self):
        w_min = settings.get('seq_test_random_min_w')
        w_max = settings.get('seq_test_random_max_w')
        len_min = settings.get('seq_test_random_len_min')
        len_max = settings.get('seq_test_random_len_max')
        seq = generate_random_sequence(w_min, w_max, len_min, len_max)
        self.edit_sequence.setText(','.join(str(w) for w in seq))

    def _parse_sequence(self):
        text = self.edit_sequence.text().strip()
        if not text:
            return None
        try:
            values = [int(v.strip()) for v in text.split(',') if v.strip()]
        except ValueError:
            return None
        if not values or len(values) > SEQ_TEST_MAX_STAGES:
            return None
        if any(v < 0 or v > 2000 for v in values):
            return None
        return values

    # ── Test control ─────────────────────────────────────────────────────────

    def _on_start_clicked(self):
        if self._test_active:
            return
        user_sequence = self._parse_sequence()
        if user_sequence is None:
            QMessageBox.warning(self, 'Invalid Sequence',
                                 f'Enter 1-{SEQ_TEST_MAX_STAGES} comma-separated watt values (0-2000).')
            return

        self._sequence  = user_sequence + [0]   # auto-appended trailing 0W stage
        self._stage_idx = -1   # initial settle at K=0 before stage 0
        self._temp_since_stage = []
        self._elapsed_s = 0
        self._graph_t.clear()
        self._graph_temp.clear()
        self._clear_stage_lines()
        self._test_active = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._style_banner('running', 'Waiting for initial settle')

        self._append_to_history(user_sequence)

        self._run_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, f'sequence_test_{self._run_id}.csv')
        self._logfile = open(log_path, 'w', newline='')
        self._writer = csv.writer(self._logfile)
        self._writer.writerow([
            'elapsed_s', 'stage_idx', 'commanded_watts', 'temp',
            'in_tolerance', 'settle_time_since_stage',
        ])
        self.lbl_logfile.setText(log_path)

        self._k_pending = True
        self.sig_set_k.emit(0)
        self.sig_test_start.emit('')
        self._timer.start(1000)

    def _on_stop_clicked(self):
        self._finalise(aborted=True)

    def _on_k_confirmed(self, k: int):
        if not self._test_active:
            return
        self._k_pending = False
        self._stage_start_t = self._elapsed_s
        self._temp_since_stage = []

    def _current_watts(self):
        if self._stage_idx < 0:
            return 0
        return self._sequence[self._stage_idx]

    def _tick(self):
        if not self._test_active:
            return
        self.val_stage.setText(
            'Initial settle' if self._stage_idx < 0
            else f'{self._stage_idx + 1}/{len(self._sequence)}')
        self.val_watts.setText(f'{self._current_watts()} W')
        if self._k_pending or self._stage_start_t is None:
            return
        stage_elapsed = self._elapsed_s - self._stage_start_t
        self.val_elapsed.setText(f'{stage_elapsed} s')

        first_dist, settle_time, last_dist = find_settle_point(
            self._temp_since_stage, TEMP_SETPOINT,
            settings.get('temp_tolerance', 0.1), SEQ_TEST_SETTLE_S)
        self.val_settle.setText(str(settle_time) if settle_time is not None else '--')

        if should_stop_for_settle(settle_time, None, 0, stage_elapsed):
            self._advance_stage(settle_time)

    def update_sample(self, sample):
        """Called every second by main_window with the latest DAQ sample."""
        if not self._test_active or self._k_pending:
            return
        temp = sample.inlet_temp if sample.inlet_temp is not None else (
            self._temp_since_stage[-1] if self._temp_since_stage else TEMP_SETPOINT)
        self._temp_since_stage.append(temp)
        self._elapsed_s += 1

        self._graph_t.append(self._elapsed_s)
        self._graph_temp.append(temp)
        self._curve_temp.setData(list(self._graph_t), list(self._graph_temp))

        tol = settings.get('temp_tolerance', 0.1)
        in_tol = abs(temp - TEMP_SETPOINT) <= tol
        if self._writer is not None:
            self._writer.writerow([
                self._elapsed_s, self._stage_idx, self._current_watts(),
                f'{temp:.3f}', int(in_tol), len(self._temp_since_stage) - 1,
            ])
            self._logfile.flush()

    def on_tcu_abnormal(self):
        if self._test_active:
            self._finalise(aborted=True, reason='TCU abnormal — aborted')

    def _advance_stage(self, settle_time: int):
        """Current stage settled — record it, evaluate, move to next stage."""
        if self._stage_idx >= 0:
            commanded_watts = self._sequence[self._stage_idx]
            bin_stats = load_bin_stats()
            result = evaluate_stage(commanded_watts, settle_time, bin_stats)
            stage_id = f'{self._run_id}_stage{self._stage_idx}'
            save_stage(stage_id, commanded_watts, settle_time, result['passed'])
            new_stages = load_all_stages()
            save_bin_stats(compute_bin_stats(new_stages))
            self._draw_stage_line(self._elapsed_s, commanded_watts, result['passed'])

        self._stage_idx += 1
        if self._stage_idx >= len(self._sequence):
            self._finalise(aborted=False)
            return

        next_watts = self._sequence[self._stage_idx]
        self._k_pending = True
        self.sig_set_k.emit(watts_to_k(next_watts))

    def _finalise(self, aborted: bool, reason=None):
        if not self._test_active:
            return
        self._test_active = False
        self._timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        if self._logfile is not None:
            self._logfile.close()
            self._logfile = None
            self._writer = None

        self.sig_set_k.emit(0)

        if aborted:
            self._style_banner('aborted', reason or 'Aborted by operator')
            self.lbl_result.setText('ABORTED')
            self.lbl_result.setStyleSheet(f'font-size: 24px; color: {AMBER};')
        else:
            self._style_banner('ready', 'Sequence complete')
            self.lbl_result.setText('COMPLETE')
            self.lbl_result.setStyleSheet(f'font-size: 24px; color: {GREEN};')

        self.sig_test_stop.emit()

    # ── Stage annotation ─────────────────────────────────────────────────────

    def _clear_stage_lines(self):
        for line in self._stage_lines:
            self._plot.removeItem(line)
        self._stage_lines = []

    def _draw_stage_line(self, t: int, watts: int, passed):
        colour = GREEN if passed else (RED if passed is False else TEXT_DIM)
        line = pg.InfiniteLine(pos=t, angle=90, pen=pg.mkPen(colour, width=1, style=Qt.DashLine))
        self._plot.addItem(line)
        self._stage_lines.append(line)

    # ── Styling / retranslate ────────────────────────────────────────────────

    def _style_banner(self, state: str, msg: str):
        if state == 'running':
            self.banner.setText(msg or 'RUNNING')
            self.banner.setStyleSheet(
                f'background: #064e3b; border: 1px solid {GREEN};'
                f'color: {GREEN}; font-size: 13px; letter-spacing: 2px; padding: 6px;')
        elif state == 'aborted':
            self.banner.setText(f'Aborted — {msg}')
            self.banner.setStyleSheet(
                f'background: #422006; border: 1px solid {AMBER};'
                f'color: {AMBER}; font-size: 13px; letter-spacing: 2px; padding: 6px;')
        else:
            self.banner.setText(msg or 'Ready')
            self.banner.setStyleSheet(
                f'background: #1a1a1a; border: 1px solid {TEXT_DIM};'
                f'color: {TEXT_DIM}; font-size: 13px; letter-spacing: 2px; padding: 6px;')

    def retranslate(self):
        pass

    def refresh_settings(self):
        pass
