# =============================================================================
# settings_tab.py — Settings Tab (sub-tabbed)
# =============================================================================
# Sub-tabs: Serial | Post-repair test | Heater | Response test | Display
# All new heater/response constants are user-configurable except HEATER_MAX_WATTS.
# Settings persist to settings.json via SettingsManager.
# =============================================================================

import hashlib

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QComboBox,
    QDoubleSpinBox, QSpinBox, QLineEdit, QTabWidget,
    QSizePolicy, QDialog, QDialogButtonBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox
)
from gui.osk import OskLineEdit as QLineEdit, OskSpinBox as QSpinBox, OskDoubleSpinBox as QDoubleSpinBox


from PyQt5.QtCore import Qt, pyqtSignal

from settings_manager import settings, DEFAULTS
from translations import tr
from config import HEATER_MAX_WATTS


class SettingsTab(QWidget):
    """Settings panel with sub-tabs."""

    sig_theme_changed    = pyqtSignal(str)
    sig_language_changed = pyqtSignal(str)
    sig_ports_changed    = pyqtSignal()
    sig_user_removed     = pyqtSignal(str)   # emitted when a web user is deleted

    def __init__(self, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self._scale = scale
        self._build_ui()
        self._load_current()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 12, 16, 12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_post_repair_tab(), tr('subtab_post_repair'))
        self._tabs.addTab(self._build_heater_tab(),      tr('subtab_heater'))
        self._tabs.addTab(self._build_display_tab(),     tr('subtab_display'))
        self._tabs.addTab(self._build_advanced_tab(),    tr('subtab_advanced'))
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs)

        btn_row = QHBoxLayout()
        self.btn_apply = QPushButton(tr('btn_apply'))
        self.btn_apply.setObjectName('btn_start')
        self.btn_reset = QPushButton(tr('btn_reset'))
        self.btn_reset.setObjectName('btn_stop')
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_reset)
        root.addLayout(btn_row)

        self.lbl_status = QLabel('')
        self.lbl_status.setObjectName('status_ok')
        self.lbl_status.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_status)

        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_reset.clicked.connect(self._on_reset)

    # ── Serial sub-tab ────────────────────────────────────────────────────────
    # ── Post-repair test sub-tab ───────────────────────────────────────────────
    def _build_post_repair_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        # ── Pass conditions ────────────────────────────────────────────────
        self._grp_test = QGroupBox(tr('settings_test'))
        g = QGridLayout(self._grp_test)
        g.setSpacing(10)
        g.setColumnStretch(1, 1)

        self.temp_sp_spin = QDoubleSpinBox()
        self.temp_sp_spin.setRange(17.0, 27.0)
        self.temp_sp_spin.setSingleStep(0.5)
        self.temp_sp_spin.setDecimals(1)
        self.temp_sp_spin.setSuffix(' °C')

        self.temp_tol_spin = QDoubleSpinBox()
        self.temp_tol_spin.setRange(0.1, 2.0)
        self.temp_tol_spin.setSingleStep(0.1)
        self.temp_tol_spin.setDecimals(1)
        self.temp_tol_spin.setSuffix(' °C')

        self.flow_sp_spin = QDoubleSpinBox()
        self.flow_sp_spin.setRange(1.0, 60.0)
        self.flow_sp_spin.setSingleStep(1.0)
        self.flow_sp_spin.setDecimals(1)
        self.flow_sp_spin.setSuffix(' L/min')

        self.flow_tol_spin = QDoubleSpinBox()
        self.flow_tol_spin.setRange(0.1, 5.0)
        self.flow_tol_spin.setSingleStep(0.1)
        self.flow_tol_spin.setDecimals(1)
        self.flow_tol_spin.setSuffix(' L/min')

        self.test_dur_spin = QSpinBox()
        self.test_dur_spin.setRange(1, 480)
        self.test_dur_spin.setSuffix(' min')

        self.poll_int_spin = QSpinBox()
        self.poll_int_spin.setRange(1, 60)
        self.poll_int_spin.setSuffix(' sec')

        self._lbl_temp_sp   = QLabel(tr('temp_sp_lbl'))
        self._lbl_temp_tol  = QLabel(tr('temp_tol_lbl'))
        self._lbl_flow_sp   = QLabel('Flow setpoint')
        self._lbl_flow_tol  = QLabel('Flow tolerance')
        self._lbl_test_dur  = QLabel(tr('test_dur_lbl'))
        self._lbl_poll_int  = QLabel(tr('poll_int_lbl'))

        g.addWidget(self._lbl_temp_sp,  0, 0); g.addWidget(self.temp_sp_spin,  0, 1)
        g.addWidget(self._lbl_temp_tol, 1, 0); g.addWidget(self.temp_tol_spin, 1, 1)
        g.addWidget(self._lbl_flow_sp,  2, 0); g.addWidget(self.flow_sp_spin,  2, 1)
        g.addWidget(self._lbl_flow_tol, 3, 0); g.addWidget(self.flow_tol_spin, 3, 1)
        g.addWidget(self._lbl_test_dur, 4, 0); g.addWidget(self.test_dur_spin, 4, 1)
        g.addWidget(self._lbl_poll_int, 5, 0); g.addWidget(self.poll_int_spin, 5, 1)
        v.addWidget(self._grp_test)

        # ── Heat Load Test (2kW sequence test) ────────────────────────────────
        self._grp_resp = QGroupBox('Heat Load Test')
        sg = QGridLayout(self._grp_resp)
        sg.setSpacing(10)
        sg.setColumnStretch(1, 1)

        self.seq_settle_dur_spin = QSpinBox()
        self.seq_settle_dur_spin.setRange(10, 1800)
        self.seq_settle_dur_spin.setSuffix(' s')

        self.seq_tail_dur_spin = QSpinBox()
        self.seq_tail_dur_spin.setRange(0, 1800)
        self.seq_tail_dur_spin.setSuffix(' s')

        self.seq_z_threshold_spin = QDoubleSpinBox()
        self.seq_z_threshold_spin.setRange(0.5, 5.0)
        self.seq_z_threshold_spin.setSingleStep(0.1)
        self.seq_z_threshold_spin.setDecimals(3)

        self.seq_random_min_w_spin = QSpinBox()
        self.seq_random_min_w_spin.setRange(0, 2000)
        self.seq_random_min_w_spin.setSuffix(' W')

        self.seq_random_max_w_spin = QSpinBox()
        self.seq_random_max_w_spin.setRange(0, 2000)
        self.seq_random_max_w_spin.setSuffix(' W')

        self.seq_random_len_min_spin = QSpinBox()
        self.seq_random_len_min_spin.setRange(1, 100)

        self.seq_random_len_max_spin = QSpinBox()
        self.seq_random_len_max_spin.setRange(1, 100)

        self._lbl_seq_settle   = QLabel('Settle duration (per stage)')
        self._lbl_seq_tail     = QLabel('Tail duration')
        self._lbl_seq_z        = QLabel('z-score threshold')
        self._lbl_seq_rand_min = QLabel('Random sequence: min watts')
        self._lbl_seq_rand_max = QLabel('Random sequence: max watts')
        self._lbl_seq_len_min  = QLabel('Random sequence: min length')
        self._lbl_seq_len_max  = QLabel('Random sequence: max length')

        rows = [
            (self._lbl_seq_settle,   self.seq_settle_dur_spin),
            (self._lbl_seq_tail,     self.seq_tail_dur_spin),
            (self._lbl_seq_z,        self.seq_z_threshold_spin),
            (self._lbl_seq_rand_min, self.seq_random_min_w_spin),
            (self._lbl_seq_rand_max, self.seq_random_max_w_spin),
            (self._lbl_seq_len_min,  self.seq_random_len_min_spin),
            (self._lbl_seq_len_max,  self.seq_random_len_max_spin),
        ]
        for i, (lbl, widget) in enumerate(rows):
            sg.addWidget(lbl, i, 0)
            sg.addWidget(widget, i, 1)
        v.addWidget(self._grp_resp)

        # ── AMAT0 Stress Test ──────────────────────────────────────────────────
        self._grp_stress = QGroupBox('AMAT0 Stress Test')
        tg = QGridLayout(self._grp_stress)
        tg.setSpacing(10)
        tg.setColumnStretch(1, 1)

        self.stress_tolerance_spin = QDoubleSpinBox()
        self.stress_tolerance_spin.setRange(0.01, 2.0)
        self.stress_tolerance_spin.setSingleStep(0.05)
        self.stress_tolerance_spin.setDecimals(2)
        self.stress_tolerance_spin.setSuffix(' °C')

        self.stress_settle_dur_spin = QSpinBox()
        self.stress_settle_dur_spin.setRange(10, 1800)
        self.stress_settle_dur_spin.setSuffix(' s')

        self.stress_duration_spin = QSpinBox()
        self.stress_duration_spin.setRange(60, 9000)
        self.stress_duration_spin.setSuffix(' s')

        self.stress_min_endurance_spin = QSpinBox()
        self.stress_min_endurance_spin.setRange(0, 9000)
        self.stress_min_endurance_spin.setSuffix(' s')

        self.stress_min_seed_runs_spin = QSpinBox()
        self.stress_min_seed_runs_spin.setRange(2, 1000)

        self._lbl_stress_tol       = QLabel('In-tolerance band')
        self._lbl_stress_settle    = QLabel('Settle duration')
        self._lbl_stress_duration  = QLabel('Test duration (fixed)')
        self._lbl_stress_endurance = QLabel('Min. endurance duration')
        self._lbl_stress_min_seed  = QLabel('Min. reference dataset size')

        trows = [
            (self._lbl_stress_tol,       self.stress_tolerance_spin),
            (self._lbl_stress_settle,    self.stress_settle_dur_spin),
            (self._lbl_stress_duration,  self.stress_duration_spin),
            (self._lbl_stress_endurance, self.stress_min_endurance_spin),
            (self._lbl_stress_min_seed,  self.stress_min_seed_runs_spin),
        ]
        for i, (lbl, widget) in enumerate(trows):
            tg.addWidget(lbl, i, 0)
            tg.addWidget(widget, i, 1)
        v.addWidget(self._grp_stress)

        v.addStretch()
        return w

    # ── Heater sub-tab ────────────────────────────────────────────────────────
    def _build_heater_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self._grp_heater = QGroupBox(tr('settings_heater_ctrl'))
        g = QGridLayout(self._grp_heater)
        g.setSpacing(10)
        g.setColumnStretch(1, 1)

        self.heater_port_edit  = QLineEdit()
        self.heater_baud_combo = QComboBox()
        self.heater_baud_combo.addItems(['4800', '9600', '19200', '38400'])

        self._lbl_heater_max = QLabel(
            f'Heater controlled via PLC MEWTOCOL\n'
            f'Max output: {HEATER_MAX_WATTS} W (W5 saturation)\n'
            f'K range: 0\u20134000 via FP0-A21 0\u201320mA'
        )
        self._lbl_heater_max.setObjectName('label_dim')

        self._lbl_hport = QLabel(tr('heater_port_lbl'))
        self._lbl_hbaud = QLabel(tr('heater_baud_lbl'))

        g.addWidget(self._lbl_hport, 0, 0); g.addWidget(self.heater_port_edit,  0, 1)
        g.addWidget(self._lbl_hbaud, 1, 0); g.addWidget(self.heater_baud_combo, 1, 1)
        g.addWidget(self._lbl_heater_max, 2, 0, 1, 2)

        v.addWidget(self._grp_heater)
        v.addStretch()
        return w

    # ── Display sub-tab ───────────────────────────────────────────────────────
    def _build_display_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self._grp_ui = QGroupBox(tr('settings_ui'))
        g = QGridLayout(self._grp_ui)
        g.setSpacing(10)
        g.setColumnStretch(1, 1)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(tr('theme_light'), 'light')
        self.theme_combo.addItem(tr('theme_dark'),  'dark')

        self.lang_combo = QComboBox()
        self.lang_combo.addItem('English', 'en')
        self.lang_combo.addItem('中文',     'zh')

        self._lbl_theme    = QLabel(tr('theme_lbl'))
        self._lbl_language = QLabel(tr('language_lbl'))

        g.addWidget(self._lbl_theme,    0, 0); g.addWidget(self.theme_combo, 0, 1)
        g.addWidget(self._lbl_language, 1, 0); g.addWidget(self.lang_combo,  1, 1)

        v.addWidget(self._grp_ui)
        v.addStretch()
        return w

    # ── Load current settings ─────────────────────────────────────────────────
    def _load_current(self):
        # Serial
        self.tcu_port_edit.setText(settings.get('tcu_port'))
        self._set_combo(self.tcu_baud_combo,  str(settings.get('tcu_baud')))
        self.pzem_port_edit.setText(settings.get('pzem_port'))
        self._set_combo(self.pzem_baud_combo, str(settings.get('pzem_baud')))
        # Post-repair test
        self.temp_sp_spin.setValue(settings.get('temp_setpoint'))
        self.temp_tol_spin.setValue(settings.get('temp_tolerance'))
        self.flow_sp_spin.setValue(settings.get('flow_setpoint'))
        self.flow_tol_spin.setValue(settings.get('flow_tolerance'))
        self.test_dur_spin.setValue(settings.get('test_duration'))
        self.poll_int_spin.setValue(settings.get('poll_interval'))
        # Heater
        self.heater_port_edit.setText(settings.get('heater_port'))
        self._set_combo(self.heater_baud_combo, str(settings.get('heater_baud')))
        # Heat Load Test (2kW sequence test)
        self.seq_settle_dur_spin.setValue(settings.get('seq_test_settle_duration_s'))
        self.seq_tail_dur_spin.setValue(settings.get('seq_test_tail_duration_s'))
        self.seq_z_threshold_spin.setValue(settings.get('seq_test_z_threshold'))
        self.seq_random_min_w_spin.setValue(settings.get('seq_test_random_min_w'))
        self.seq_random_max_w_spin.setValue(settings.get('seq_test_random_max_w'))
        self.seq_random_len_min_spin.setValue(settings.get('seq_test_random_len_min'))
        self.seq_random_len_max_spin.setValue(settings.get('seq_test_random_len_max'))
        # AMAT0 Stress Test
        self.stress_tolerance_spin.setValue(settings.get('stress_test_tolerance'))
        self.stress_settle_dur_spin.setValue(settings.get('stress_test_settle_duration_s'))
        self.stress_duration_spin.setValue(settings.get('stress_test_duration_s'))
        self.stress_min_endurance_spin.setValue(settings.get('stress_test_min_endurance_s'))
        self.stress_min_seed_runs_spin.setValue(settings.get('stress_test_min_seed_runs'))
        # Display
        self._set_combo_data(self.theme_combo, settings.get('theme'))
        self._set_combo_data(self.lang_combo,  settings.get('language'))

    # ── Apply ─────────────────────────────────────────────────────────────────
    def _on_apply(self):
        port_changed = False

        # Serial
        for key, val in [
            ('tcu_port',  self.tcu_port_edit.text().strip()),
            ('tcu_baud',  int(self.tcu_baud_combo.currentText())),
            ('pzem_port', self.pzem_port_edit.text().strip()),
            ('pzem_baud', int(self.pzem_baud_combo.currentText())),
        ]:
            if val != settings.get(key):
                port_changed = True
            settings.set(key, val)

        # Post-repair test
        settings.set('temp_setpoint',  self.temp_sp_spin.value())
        settings.set('temp_tolerance', self.temp_tol_spin.value())
        settings.set('flow_setpoint',  self.flow_sp_spin.value())
        settings.set('flow_tolerance', self.flow_tol_spin.value())
        settings.set('test_duration',  self.test_dur_spin.value())
        settings.set('poll_interval',  self.poll_int_spin.value())

        # Heater (PLC)
        settings.set('heater_port', self.heater_port_edit.text().strip())
        settings.set('heater_baud', int(self.heater_baud_combo.currentText()))

        # Heat Load Test (2kW sequence test)
        settings.set('seq_test_settle_duration_s', self.seq_settle_dur_spin.value())
        settings.set('seq_test_tail_duration_s',   self.seq_tail_dur_spin.value())
        settings.set('seq_test_z_threshold',       self.seq_z_threshold_spin.value())
        settings.set('seq_test_random_min_w',      self.seq_random_min_w_spin.value())
        settings.set('seq_test_random_max_w',      self.seq_random_max_w_spin.value())
        settings.set('seq_test_random_len_min',    self.seq_random_len_min_spin.value())
        settings.set('seq_test_random_len_max',    self.seq_random_len_max_spin.value())

        # AMAT0 Stress Test
        settings.set('stress_test_tolerance',         self.stress_tolerance_spin.value())
        settings.set('stress_test_settle_duration_s', self.stress_settle_dur_spin.value())
        settings.set('stress_test_duration_s',        self.stress_duration_spin.value())
        settings.set('stress_test_min_endurance_s',   self.stress_min_endurance_spin.value())
        settings.set('stress_test_min_seed_runs',     self.stress_min_seed_runs_spin.value())

        # Display
        new_theme = self.theme_combo.currentData()
        if new_theme != settings.get('theme'):
            settings.set('theme', new_theme)
            self.sig_theme_changed.emit(new_theme)

        new_lang = self.lang_combo.currentData()
        settings.set('language', new_lang)
        self.sig_language_changed.emit(new_lang)

        if port_changed:
            self.sig_ports_changed.emit()

        self.lbl_status.setText(tr('applied_ok'))

    # ── Reset ─────────────────────────────────────────────────────────────────
    def _on_reset(self):
        for key, value in DEFAULTS.items():
            settings.set(key, value)
        self._load_current()
        self.lbl_status.setText(tr('applied_ok'))
        self.sig_theme_changed.emit(settings.get('theme'))
        self.sig_language_changed.emit(settings.get('language'))
        self.sig_ports_changed.emit()

    # ── Retranslate ───────────────────────────────────────────────────────────
    def retranslate(self):
        # Sub-tab labels
        self._tabs.setTabText(0, tr('subtab_post_repair'))
        self._tabs.setTabText(1, tr('subtab_heater'))
        self._tabs.setTabText(2, tr('subtab_display'))
        self._tabs.setTabText(3, tr('subtab_advanced'))
        # Group box titles
        self._grp_serial_adv.setTitle(tr('settings_serial'))
        self._grp_test.setTitle(tr('settings_test'))
        self._grp_heater.setTitle(tr('settings_heater_ctrl'))
        self._grp_resp.setTitle('Heat Load Test')
        self._grp_stress.setTitle('AMAT0 Stress Test')
        self._grp_ui.setTitle(tr('settings_ui'))
        # Serial labels
        self._lbl_tcu_port.setText(tr('tcu_port_lbl'))
        self._lbl_tcu_baud.setText(tr('tcu_baud_lbl'))
        self._lbl_pzem_port.setText(tr('pzem_port_lbl'))
        self._lbl_pzem_baud.setText(tr('pzem_baud_lbl'))
        self.restart_note.setText(tr('restart_note'))
        # Post-repair labels
        self._lbl_temp_sp.setText(tr('temp_sp_lbl'))
        self._lbl_temp_tol.setText(tr('temp_tol_lbl'))
        self._lbl_test_dur.setText(tr('test_dur_lbl'))
        self._lbl_poll_int.setText(tr('poll_int_lbl'))
        # Heater (PLC) labels
        self._lbl_hport.setText(tr('heater_port_lbl'))
        self._lbl_hbaud.setText(tr('heater_baud_lbl'))
        # Display labels
        self._lbl_theme.setText(tr('theme_lbl'))
        self._lbl_language.setText(tr('language_lbl'))
        # Buttons
        self.btn_apply.setText(tr('btn_apply'))
        self.btn_reset.setText(tr('btn_reset'))
        self.lbl_status.setText('')
        # Reload combos with translated items
        current_theme = self.theme_combo.currentData()
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItem(tr('theme_light'), 'light')
        self.theme_combo.addItem(tr('theme_dark'),  'dark')
        self._set_combo_data(self.theme_combo, current_theme)
        self.theme_combo.blockSignals(False)

    # ── Access sub-tab ────────────────────────────────────────────────────────
    def _build_advanced_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        # Password prompt shown initially
        self._access_locked = True
        self._access_content = QWidget()
        self._access_content.setVisible(False)

        self._grp_auth = QGroupBox('Authentication required')
        auth_layout = QVBoxLayout(self._grp_auth)
        auth_layout.addWidget(QLabel('Enter admin password to access this tab:'))
        self._access_pw_edit = QLineEdit()
        self._access_pw_edit.setEchoMode(QLineEdit.Password)
        self._access_pw_edit.setPlaceholderText('Admin password')
        auth_layout.addWidget(self._access_pw_edit)
        self._access_pw_btn = QPushButton('Unlock')
        self._access_pw_btn.setObjectName('btn_start')
        self._access_pw_btn.clicked.connect(self._on_access_unlock)
        auth_layout.addWidget(self._access_pw_btn)
        self._access_pw_err = QLabel('')
        self._access_pw_err.setStyleSheet('color: red;')
        auth_layout.addWidget(self._access_pw_err)

        # Access content (shown after authentication)
        content_layout = QVBoxLayout(self._access_content)

        # Inactivity timeout
        self._grp_inactivity = QGroupBox('RPi4 Inactivity Timeout')
        g = QGridLayout(self._grp_inactivity)
        self._inactivity_spin = QSpinBox()
        self._inactivity_spin.setRange(1, 60)
        self._inactivity_spin.setSuffix(' min')
        self._inactivity_spin.setValue(settings.get('rpi_inactivity_timeout_min'))
        g.addWidget(QLabel('Inactivity timeout:'), 0, 0)
        g.addWidget(self._inactivity_spin, 0, 1)
        content_layout.addWidget(self._grp_inactivity)

        # Serial ports (moved from main settings tabs)
        self._grp_serial_adv = QGroupBox(tr('settings_serial'))
        g2 = QGridLayout(self._grp_serial_adv)
        g2.setSpacing(10)
        g2.setColumnStretch(1, 1)
        self.tcu_port_edit   = QLineEdit()
        self.tcu_baud_combo  = QComboBox()
        self.tcu_baud_combo.addItems(['1200', '2400', '4800', '9600'])
        self.pzem_port_edit  = QLineEdit()
        self.pzem_baud_combo = QComboBox()
        self.pzem_baud_combo.addItems(['4800', '9600', '19200'])
        self.tcu_port_edit.setText(settings.get('tcu_port'))
        self._set_combo(self.tcu_baud_combo, str(settings.get('tcu_baud')))
        self.pzem_port_edit.setText(settings.get('pzem_port'))
        self._set_combo(self.pzem_baud_combo, str(settings.get('pzem_baud')))
        self._lbl_tcu_port  = QLabel(tr('tcu_port_lbl'))
        self._lbl_tcu_baud  = QLabel(tr('tcu_baud_lbl'))
        self._lbl_pzem_port = QLabel(tr('pzem_port_lbl'))
        self._lbl_pzem_baud = QLabel(tr('pzem_baud_lbl'))
        g2.addWidget(self._lbl_tcu_port,   0, 0); g2.addWidget(self.tcu_port_edit,   0, 1)
        g2.addWidget(self._lbl_tcu_baud,   1, 0); g2.addWidget(self.tcu_baud_combo,  1, 1)
        g2.addWidget(self._lbl_pzem_port,  2, 0); g2.addWidget(self.pzem_port_edit,  2, 1)
        g2.addWidget(self._lbl_pzem_baud,  3, 0); g2.addWidget(self.pzem_baud_combo, 3, 1)
        self.restart_note = QLabel(tr('restart_note'))
        self.restart_note.setObjectName('label_dim')
        self.restart_note.setWordWrap(True)
        g2.addWidget(self.restart_note, 4, 0, 1, 2)
        content_layout.addWidget(self._grp_serial_adv)

        # Soft wattage limit
        self._grp_soft_limit = QGroupBox('Heater Soft Limit')
        g3 = QGridLayout(self._grp_soft_limit)
        self._soft_limit_spin = QSpinBox()
        self._soft_limit_spin.setRange(0, HEATER_MAX_WATTS)
        self._soft_limit_spin.setSuffix(' W')
        self._soft_limit_spin.setValue(settings.get('heater_soft_limit_w'))
        g3.addWidget(QLabel('Soft limit (admin password required above):'), 0, 0)
        g3.addWidget(self._soft_limit_spin, 0, 1)
        content_layout.addWidget(self._grp_soft_limit)

        # Change admin password
        self._grp_pw = QGroupBox('Change Admin Password')
        pw_g = QGridLayout(self._grp_pw)
        self._new_pw_edit    = QLineEdit()
        self._new_pw_edit.setEchoMode(QLineEdit.Password)
        self._new_pw_edit.setPlaceholderText('New password')
        self._confirm_pw_edit = QLineEdit()
        self._confirm_pw_edit.setEchoMode(QLineEdit.Password)
        self._confirm_pw_edit.setPlaceholderText('Confirm new password')
        self._change_pw_btn  = QPushButton('Change Password')
        self._change_pw_btn.setObjectName('btn_start')
        self._change_pw_btn.clicked.connect(self._on_change_password)
        self._pw_status_lbl  = QLabel('')
        pw_g.addWidget(QLabel('New password:'),    0, 0)
        pw_g.addWidget(self._new_pw_edit,          0, 1)
        pw_g.addWidget(QLabel('Confirm:'),         1, 0)
        pw_g.addWidget(self._confirm_pw_edit,      1, 1)
        pw_g.addWidget(self._change_pw_btn,        2, 0, 1, 2)
        pw_g.addWidget(self._pw_status_lbl,        3, 0, 1, 2)
        content_layout.addWidget(self._grp_pw)

        # User management
        self._grp_users = QGroupBox('Web User Management')
        users_v = QVBoxLayout(self._grp_users)
        self._users_table = QTableWidget(0, 3)
        self._users_table.setHorizontalHeaderLabels(['Username', 'Role', 'Action'])
        self._users_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        users_v.addWidget(self._users_table)

        add_row = QHBoxLayout()
        self._new_user_edit = QLineEdit()
        self._new_user_edit.setPlaceholderText('Username (work ID)')
        self._new_user_pw_edit = QLineEdit()
        self._new_user_pw_edit.setEchoMode(QLineEdit.Password)
        self._new_user_pw_edit.setPlaceholderText('Password')
        self._new_user_role  = QComboBox()
        self._new_user_role.addItem('Technician', 'technician')
        self._new_user_role.addItem('Supervisor', 'supervisor')
        self._add_user_btn   = QPushButton('Add User')
        self._add_user_btn.setObjectName('btn_start')
        self._add_user_btn.clicked.connect(self._on_add_user)
        add_row.addWidget(self._new_user_edit)
        add_row.addWidget(self._new_user_pw_edit)
        add_row.addWidget(self._new_user_role)
        add_row.addWidget(self._add_user_btn)
        users_v.addLayout(add_row)
        self._user_status_lbl = QLabel('')
        users_v.addWidget(self._user_status_lbl)
        content_layout.addWidget(self._grp_users)

        # Apply button for inactivity setting
        self._access_apply_btn = QPushButton('Apply')
        self._access_apply_btn.setObjectName('btn_start')
        self._access_apply_btn.clicked.connect(self._on_access_apply)
        content_layout.addWidget(self._access_apply_btn)
        content_layout.addStretch()

        v.addWidget(self._grp_auth)
        v.addWidget(self._access_content)
        return w

    def _on_tab_changed(self, index: int):
        """Lock access tab every time user navigates away and back."""
        if not isinstance(index, int):
            return
        access_idx = self._tabs.count() - 1
        if index == access_idx:
            self._lock_access_tab()
        else:
            self._lock_access_tab()

    def _lock_access_tab(self):
        self._access_locked = True
        self._access_content.setVisible(False)
        self._grp_auth.setVisible(True)
        self._access_pw_edit.clear()
        self._access_pw_err.setText('')

    def _on_access_unlock(self):
        pw = self._access_pw_edit.text()
        if not isinstance(pw, str) or not pw:
            self._access_pw_err.setText('Password cannot be empty.')
            return
        hashed  = hashlib.sha256(pw.encode()).hexdigest()
        stored  = settings.get('access_password_hash')
        if hashed != stored:
            self._access_pw_err.setText('Incorrect password.')
            self._access_pw_edit.clear()
            return
        self._access_locked = False
        self._grp_auth.setVisible(False)
        self._access_content.setVisible(True)
        self._refresh_users_table()

    def _on_change_password(self):
        new_pw     = self._new_pw_edit.text()
        confirm_pw = self._confirm_pw_edit.text()
        if not isinstance(new_pw, str) or len(new_pw) < 6:
            self._pw_status_lbl.setText('Password must be at least 6 characters.')
            return
        if new_pw != confirm_pw:
            self._pw_status_lbl.setText('Passwords do not match.')
            return
        hashed = hashlib.sha256(new_pw.encode()).hexdigest()
        settings.set('access_password_hash', hashed)
        self._pw_status_lbl.setText('✓ Password changed.')
        self._new_pw_edit.clear()
        self._confirm_pw_edit.clear()

    def _on_access_apply(self):
        val = self._inactivity_spin.value()
        if not isinstance(val, int) or val <= 0:
            return
        settings.set('rpi_inactivity_timeout_min', val)
        # Serial ports
        settings.set('tcu_port',  self.tcu_port_edit.text().strip())
        settings.set('tcu_baud',  int(self.tcu_baud_combo.currentText()))
        settings.set('pzem_port', self.pzem_port_edit.text().strip())
        settings.set('pzem_baud', int(self.pzem_baud_combo.currentText()))
        # Soft limit
        settings.set('heater_soft_limit_w', self._soft_limit_spin.value())
        self._access_apply_btn.setText('✓ Applied')
        self.sig_ports_changed.emit()

    def _refresh_users_table(self):
        import json, os
        path = 'users.json'
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                users = json.load(f)
        except Exception:
            return
        self._users_table.setRowCount(0)
        for i, (uname, udata) in enumerate(users.items()):
            if not isinstance(udata, dict):
                continue
            self._users_table.insertRow(i)
            self._users_table.setItem(i, 0, QTableWidgetItem(uname))
            self._users_table.setItem(i, 1, QTableWidgetItem(udata.get('role', '')))
            del_btn = QPushButton('Remove')
            del_btn.setObjectName('btn_stop')
            del_btn.clicked.connect(lambda _, u=uname: self._on_remove_user(u))
            self._users_table.setCellWidget(i, 2, del_btn)

    def _on_add_user(self):
        import json, os, hashlib as hl
        uname = self._new_user_edit.text().strip()
        pw    = self._new_user_pw_edit.text()
        role  = self._new_user_role.currentData()
        if not uname or not pw:
            self._user_status_lbl.setText('Username and password required.')
            return
        path = 'users.json'
        users = {}
        if os.path.exists(path):
            try:
                with open(path) as f:
                    users = json.load(f)
            except Exception:
                pass
        if uname in users:
            self._user_status_lbl.setText(f'User "{uname}" already exists.')
            return
        users[uname] = {
            'password_hash': hl.sha256(pw.encode()).hexdigest(),
            'role': role
        }
        try:
            with open(path, 'w') as f:
                json.dump(users, f, indent=2)
            self._user_status_lbl.setText(f'✓ User "{uname}" added.')
            self._new_user_edit.clear()
            self._new_user_pw_edit.clear()
            self._refresh_users_table()
        except Exception as e:
            self._user_status_lbl.setText(f'Error: {e}')

    def _on_remove_user(self, uname: str):
        import json, os
        if not isinstance(uname, str):
            return
        reply = QMessageBox.question(
            self, 'Remove User',
            f'Remove user "{uname}"? Their active session will be invalidated.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        path = 'users.json'
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                users = json.load(f)
            users.pop(uname, None)
            with open(path, 'w') as f:
                json.dump(users, f, indent=2)
            self.sig_user_removed.emit(uname)
            self._user_status_lbl.setText(f'✓ User "{uname}" removed.')
            self._refresh_users_table()
        except Exception as e:
            self._user_status_lbl.setText(f'Error: {e}')

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_combo(self, combo: QComboBox, text: str):
        idx = combo.findText(text)
        combo.setCurrentIndex(max(0, idx))

    def _set_combo_data(self, combo: QComboBox, data):
        idx = combo.findData(data)
        combo.setCurrentIndex(max(0, idx))
