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
        self._tabs.addTab(self._build_response_tab(),    tr('subtab_response_test'))
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
    def _build_serial_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self._grp_serial = QGroupBox(tr('settings_serial'))
        g = QGridLayout(self._grp_serial)
        g.setSpacing(10)
        g.setColumnStretch(1, 1)

        self.tcu_port_edit = QLineEdit()
        self.tcu_baud_combo = QComboBox()
        self.tcu_baud_combo.addItems(['1200', '2400', '4800', '9600'])
        self.pzem_port_edit = QLineEdit()
        self.pzem_baud_combo = QComboBox()
        self.pzem_baud_combo.addItems(['4800', '9600', '19200'])

        self._lbl_tcu_port  = QLabel(tr('tcu_port_lbl'))
        self._lbl_tcu_baud  = QLabel(tr('tcu_baud_lbl'))
        self._lbl_pzem_port = QLabel(tr('pzem_port_lbl'))
        self._lbl_pzem_baud = QLabel(tr('pzem_baud_lbl'))

        g.addWidget(self._lbl_tcu_port,   0, 0); g.addWidget(self.tcu_port_edit,   0, 1)
        g.addWidget(self._lbl_tcu_baud,   1, 0); g.addWidget(self.tcu_baud_combo,  1, 1)
        g.addWidget(self._lbl_pzem_port,  2, 0); g.addWidget(self.pzem_port_edit,  2, 1)
        g.addWidget(self._lbl_pzem_baud,  3, 0); g.addWidget(self.pzem_baud_combo, 3, 1)

        self.restart_note = QLabel(tr('restart_note'))
        self.restart_note.setObjectName('label_dim')
        self.restart_note.setWordWrap(True)
        g.addWidget(self.restart_note, 4, 0, 1, 2)

        v.addWidget(self._grp_serial)
        v.addStretch()
        return w

    # ── Post-repair test sub-tab ───────────────────────────────────────────────
    def _build_post_repair_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
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

        self.test_dur_spin = QSpinBox()
        self.test_dur_spin.setRange(1, 480)
        self.test_dur_spin.setSuffix(' min')

        self.poll_int_spin = QSpinBox()
        self.poll_int_spin.setRange(1, 60)
        self.poll_int_spin.setSuffix(' sec')

        self.flow_grace_spin = QSpinBox()
        self.flow_grace_spin.setRange(1, 60)
        self.flow_grace_spin.setSuffix(' sec')

        self._lbl_temp_sp   = QLabel(tr('temp_sp_lbl'))
        self._lbl_temp_tol  = QLabel(tr('temp_tol_lbl'))
        self._lbl_test_dur  = QLabel(tr('test_dur_lbl'))
        self._lbl_poll_int  = QLabel(tr('poll_int_lbl'))
        self._lbl_flow_grace = QLabel('Flow fail grace')

        g.addWidget(self._lbl_temp_sp,   0, 0); g.addWidget(self.temp_sp_spin,   0, 1)
        g.addWidget(self._lbl_temp_tol,  1, 0); g.addWidget(self.temp_tol_spin,  1, 1)
        g.addWidget(self._lbl_test_dur,  2, 0); g.addWidget(self.test_dur_spin,  2, 1)
        g.addWidget(self._lbl_poll_int,  3, 0); g.addWidget(self.poll_int_spin,  3, 1)
        g.addWidget(self._lbl_flow_grace, 4, 0); g.addWidget(self.flow_grace_spin, 4, 1)

        v.addWidget(self._grp_test)
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
        self.heater_slave_spin = QSpinBox()
        self.heater_slave_spin.setRange(1, 247)
        self.heater_reg_sp_spin = QSpinBox()
        self.heater_reg_sp_spin.setRange(0, 0xFFFF)
        self.heater_reg_act_spin = QSpinBox()
        self.heater_reg_act_spin.setRange(0, 0xFFFF)
        self.heater_tol_spin = QSpinBox()
        self.heater_tol_spin.setRange(0, 2000)
        self.heater_tol_spin.setSuffix(' W')
        self.heater_display_combo = QComboBox()
        self.heater_display_combo.addItem(tr('display_percent'), 'percent')
        self.heater_display_combo.addItem(tr('display_watts'),   'watts')
        self.heater_display_combo.addItem(tr('display_both'),    'both')

        self._lbl_heater_max = QLabel(f'{tr("heater_max_lbl")}: {HEATER_MAX_WATTS} W')
        self._lbl_heater_max.setObjectName('label_dim')

        self._lbl_hport   = QLabel(tr('heater_port_lbl'))
        self._lbl_hbaud   = QLabel(tr('heater_baud_lbl'))
        self._lbl_hslave  = QLabel(tr('heater_slave_lbl'))
        self._lbl_hreg_sp = QLabel(tr('heater_reg_sp_lbl'))
        self._lbl_hreg_act= QLabel(tr('heater_reg_act_lbl'))
        self._lbl_htol    = QLabel(tr('heater_tol_lbl'))
        self._lbl_hdisp   = QLabel(tr('heater_display_lbl'))

        rows = [
            (self._lbl_hport,    self.heater_port_edit),
            (self._lbl_hbaud,    self.heater_baud_combo),
            (self._lbl_hslave,   self.heater_slave_spin),
            (self._lbl_hreg_sp,  self.heater_reg_sp_spin),
            (self._lbl_hreg_act, self.heater_reg_act_spin),
            (self._lbl_htol,     self.heater_tol_spin),
            (self._lbl_hdisp,    self.heater_display_combo),
        ]
        for i, (lbl, widget) in enumerate(rows):
            g.addWidget(lbl, i, 0)
            g.addWidget(widget, i, 1)
        g.addWidget(self._lbl_heater_max, len(rows), 0, 1, 2)

        v.addWidget(self._grp_heater)
        v.addStretch()
        return w

    # ── Response test sub-tab ─────────────────────────────────────────────────
    def _build_response_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self._grp_resp = QGroupBox(tr('settings_response'))
        g = QGridLayout(self._grp_resp)
        g.setSpacing(10)
        g.setColumnStretch(1, 1)

        self.step_start_spin = QSpinBox()
        self.step_start_spin.setRange(0, HEATER_MAX_WATTS)
        self.step_start_spin.setSuffix(' W')
        self.step_end_spin = QSpinBox()
        self.step_end_spin.setRange(0, HEATER_MAX_WATTS)
        self.step_end_spin.setSuffix(' W')
        self.step_size_spin = QSpinBox()
        self.step_size_spin.setRange(100, HEATER_MAX_WATTS)
        self.step_size_spin.setSuffix(' W')
        self.dwell_spin = QSpinBox()
        self.dwell_spin.setRange(1, 60)
        self.dwell_spin.setSuffix(' min')
        self.step_dur_spin = QSpinBox()
        self.step_dur_spin.setRange(1, 120)
        self.step_dur_spin.setSuffix(' min')
        self.ss_window_spin = QSpinBox()
        self.ss_window_spin.setRange(10, 300)
        self.ss_window_spin.setSuffix(' sec')
        self.ss_tol_spin = QDoubleSpinBox()
        self.ss_tol_spin.setRange(0.01, 1.0)
        self.ss_tol_spin.setDecimals(2)
        self.ss_tol_spin.setSuffix(' °C')
        self.thermal_thresh_spin = QDoubleSpinBox()
        self.thermal_thresh_spin.setRange(0.01, 1.0)
        self.thermal_thresh_spin.setDecimals(2)
        self.thermal_thresh_spin.setSuffix(' °C')
        self.thermal_samples_spin = QSpinBox()
        self.thermal_samples_spin.setRange(1, 20)
        self.thermal_sigma_spin = QSpinBox()
        self.thermal_sigma_spin.setRange(1, 10)

        self._lbl_step_start  = QLabel(tr('step_start_lbl'))
        self._lbl_step_end    = QLabel(tr('step_end_lbl'))
        self._lbl_step_size   = QLabel(tr('step_size_lbl'))
        self._lbl_dwell       = QLabel(tr('dwell_time_lbl'))
        self._lbl_step_dur    = QLabel(tr('step_dur_lbl'))
        self._lbl_ss_window   = QLabel(tr('ss_window_lbl'))
        self._lbl_ss_tol      = QLabel(tr('ss_tolerance_lbl'))
        self._lbl_thresh      = QLabel(tr('thermal_threshold_lbl'))
        self._lbl_samples     = QLabel(tr('thermal_samples_lbl'))
        self._lbl_sigma       = QLabel(tr('thermal_sigma_lbl'))

        rows = [
            (self._lbl_step_start, self.step_start_spin),
            (self._lbl_step_end,   self.step_end_spin),
            (self._lbl_step_size,  self.step_size_spin),
            (self._lbl_dwell,      self.dwell_spin),
            (self._lbl_step_dur,   self.step_dur_spin),
            (self._lbl_ss_window,  self.ss_window_spin),
            (self._lbl_ss_tol,     self.ss_tol_spin),
            (self._lbl_thresh,     self.thermal_thresh_spin),
            (self._lbl_samples,    self.thermal_samples_spin),
            (self._lbl_sigma,      self.thermal_sigma_spin),
        ]
        for i, (lbl, widget) in enumerate(rows):
            g.addWidget(lbl, i, 0)
            g.addWidget(widget, i, 1)

        v.addWidget(self._grp_resp)
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
        self.test_dur_spin.setValue(settings.get('test_duration'))
        self.poll_int_spin.setValue(settings.get('poll_interval'))
        self.flow_grace_spin.setValue(settings.get('flow_fail_grace'))
        # Heater
        self.heater_port_edit.setText(settings.get('heater_port'))
        self._set_combo(self.heater_baud_combo, str(settings.get('heater_baud')))
        self.heater_slave_spin.setValue(settings.get('heater_slave_id'))
        self.heater_reg_sp_spin.setValue(settings.get('heater_reg_setpoint'))
        self.heater_reg_act_spin.setValue(settings.get('heater_reg_actual'))
        self.heater_tol_spin.setValue(settings.get('heater_watts_tolerance'))
        self._set_combo_data(self.heater_display_combo, settings.get('heater_display_mode'))
        # Response test
        self.step_start_spin.setValue(settings.get('heater_step_start_w'))
        self.step_end_spin.setValue(settings.get('heater_step_end_w'))
        self.step_size_spin.setValue(settings.get('heater_step_size_w'))
        self.dwell_spin.setValue(settings.get('heater_dwell_time_min'))
        self.step_dur_spin.setValue(settings.get('step_test_duration_min'))
        self.ss_window_spin.setValue(settings.get('steady_state_window_sec'))
        self.ss_tol_spin.setValue(settings.get('steady_state_tolerance'))
        self.thermal_thresh_spin.setValue(settings.get('thermal_response_threshold'))
        self.thermal_samples_spin.setValue(settings.get('thermal_response_min_samples'))
        self.thermal_sigma_spin.setValue(settings.get('thermal_response_sigma'))
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
        settings.set('test_duration',  self.test_dur_spin.value())
        settings.set('poll_interval',  self.poll_int_spin.value())
        settings.set('flow_fail_grace', self.flow_grace_spin.value())

        # Heater
        settings.set('heater_port',          self.heater_port_edit.text().strip())
        settings.set('heater_baud',          int(self.heater_baud_combo.currentText()))
        settings.set('heater_slave_id',      self.heater_slave_spin.value())
        settings.set('heater_reg_setpoint',  self.heater_reg_sp_spin.value())
        settings.set('heater_reg_actual',    self.heater_reg_act_spin.value())
        settings.set('heater_watts_tolerance', self.heater_tol_spin.value())
        settings.set('heater_display_mode',  self.heater_display_combo.currentData())

        # Response test
        settings.set('heater_step_start_w',       self.step_start_spin.value())
        settings.set('heater_step_end_w',         self.step_end_spin.value())
        settings.set('heater_step_size_w',        self.step_size_spin.value())
        settings.set('heater_dwell_time_min',      self.dwell_spin.value())
        settings.set('step_test_duration_min',     self.step_dur_spin.value())
        settings.set('steady_state_window_sec',    self.ss_window_spin.value())
        settings.set('steady_state_tolerance',     self.ss_tol_spin.value())
        settings.set('thermal_response_threshold', self.thermal_thresh_spin.value())
        settings.set('thermal_response_min_samples', self.thermal_samples_spin.value())
        settings.set('thermal_response_sigma',     self.thermal_sigma_spin.value())

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
        self._tabs.setTabText(2, tr('subtab_response_test'))
        self._tabs.setTabText(3, tr('subtab_display'))
        self._tabs.setTabText(4, tr('subtab_advanced'))
        # Group box titles
        self._grp_serial.setTitle(tr('settings_serial'))
        self._grp_test.setTitle(tr('settings_test'))
        self._grp_heater.setTitle(tr('settings_heater_ctrl'))
        self._grp_resp.setTitle(tr('settings_response'))
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
        # Heater labels
        self._lbl_hport.setText(tr('heater_port_lbl'))
        self._lbl_hbaud.setText(tr('heater_baud_lbl'))
        self._lbl_hslave.setText(tr('heater_slave_lbl'))
        self._lbl_hreg_sp.setText(tr('heater_reg_sp_lbl'))
        self._lbl_hreg_act.setText(tr('heater_reg_act_lbl'))
        self._lbl_htol.setText(tr('heater_tol_lbl'))
        self._lbl_hdisp.setText(tr('heater_display_lbl'))
        self._lbl_heater_max.setText(f'{tr("heater_max_lbl")}: {HEATER_MAX_WATTS} W')
        # Response test labels
        self._lbl_step_start.setText(tr('step_start_lbl'))
        self._lbl_step_end.setText(tr('step_end_lbl'))
        self._lbl_step_size.setText(tr('step_size_lbl'))
        self._lbl_dwell.setText(tr('dwell_time_lbl'))
        self._lbl_step_dur.setText(tr('step_dur_lbl'))
        self._lbl_ss_window.setText(tr('ss_window_lbl'))
        self._lbl_ss_tol.setText(tr('ss_tolerance_lbl'))
        self._lbl_thresh.setText(tr('thermal_threshold_lbl'))
        self._lbl_samples.setText(tr('thermal_samples_lbl'))
        self._lbl_sigma.setText(tr('thermal_sigma_lbl'))
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

        current_disp = self.heater_display_combo.currentData()
        self.heater_display_combo.blockSignals(True)
        self.heater_display_combo.clear()
        self.heater_display_combo.addItem(tr('display_percent'), 'percent')
        self.heater_display_combo.addItem(tr('display_watts'),   'watts')
        self.heater_display_combo.addItem(tr('display_both'),    'both')
        self._set_combo_data(self.heater_display_combo, current_disp)
        self.heater_display_combo.blockSignals(False)

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
