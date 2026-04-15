# =============================================================================
# settings_tab.py — Settings Tab
# =============================================================================
# Allows users to configure ports, test parameters, theme and language.
# All changes take effect immediately via SettingsManager callbacks.
# Settings persist to settings.json across restarts.
# =============================================================================

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QComboBox,
    QDoubleSpinBox, QSpinBox, QLineEdit, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal

from settings_manager import settings, DEFAULTS
from translations import tr


class SettingsTab(QWidget):
    """
    Settings panel — configure ports, test params, theme and language.
    Emits sig_apply(key, value) for each changed setting so main_window
    can hot-reload the affected components.
    """

    sig_theme_changed    = pyqtSignal(str)   # 'light' or 'dark'
    sig_language_changed = pyqtSignal(str)   # 'en', 'zh', 'ms'
    sig_ports_changed    = pyqtSignal()      # any port/baud changed

    def __init__(self, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self._scale = scale
        self._build_ui()
        self._load_current()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        # Two column layout
        cols = QHBoxLayout()
        cols.setSpacing(16)
        left  = QVBoxLayout()
        right = QVBoxLayout()
        left.setSpacing(12)
        right.setSpacing(12)

        # ── Left: Serial ports ────────────────────────────────────────────────
        self._grp_port = QGroupBox(tr('settings_serial'))
        port_box = self._grp_port
        pg = QGridLayout(port_box)
        pg.setSpacing(10)
        pg.setColumnStretch(1, 1)

        self.tcu_port_edit = QLineEdit()
        self.tcu_baud_combo = QComboBox()
        self.tcu_baud_combo.addItems(['1200', '2400', '4800', '9600'])

        self.pzem_port_edit = QLineEdit()
        self.pzem_baud_combo = QComboBox()
        self.pzem_baud_combo.addItems(['4800', '9600', '19200'])

        pg.addWidget(QLabel(tr('tcu_port_lbl')),  0, 0)
        pg.addWidget(self.tcu_port_edit,           0, 1)
        pg.addWidget(QLabel(tr('tcu_baud_lbl')),  1, 0)
        pg.addWidget(self.tcu_baud_combo,          1, 1)
        pg.addWidget(QLabel(tr('pzem_port_lbl')), 2, 0)
        pg.addWidget(self.pzem_port_edit,          2, 1)
        pg.addWidget(QLabel(tr('pzem_baud_lbl')), 3, 0)
        pg.addWidget(self.pzem_baud_combo,         3, 1)

        self.restart_note = QLabel(tr('restart_note'))
        self.restart_note.setObjectName('label_dim')
        self.restart_note.setWordWrap(True)
        pg.addWidget(self.restart_note, 4, 0, 1, 2)
        left.addWidget(port_box)

        # ── Left: Test parameters ─────────────────────────────────────────────
        self._grp_test = QGroupBox(tr('settings_test'))
        test_box = self._grp_test
        tg = QGridLayout(test_box)
        tg.setSpacing(10)
        tg.setColumnStretch(1, 1)

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

        tg.addWidget(QLabel(tr('temp_sp_lbl')),   0, 0)
        tg.addWidget(self.temp_sp_spin,             0, 1)
        tg.addWidget(QLabel(tr('temp_tol_lbl')),  1, 0)
        tg.addWidget(self.temp_tol_spin,            1, 1)
        tg.addWidget(QLabel(tr('test_dur_lbl')),  2, 0)
        tg.addWidget(self.test_dur_spin,            2, 1)
        tg.addWidget(QLabel(tr('poll_int_lbl')),  3, 0)
        tg.addWidget(self.poll_int_spin,            3, 1)
        left.addWidget(test_box)
        left.addStretch()

        # ── Right: Display & Language ─────────────────────────────────────────
        self._grp_ui = QGroupBox(tr('settings_ui'))
        ui_box = self._grp_ui
        ug = QGridLayout(ui_box)
        ug.setSpacing(10)
        ug.setColumnStretch(1, 1)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(tr('theme_light'), 'light')
        self.theme_combo.addItem(tr('theme_dark'),  'dark')

        self.lang_combo = QComboBox()
        self.lang_combo.addItem('English',  'en')
        self.lang_combo.addItem('中文',      'zh')
        self.lang_combo.addItem('Bahasa Melayu', 'ms')

        ug.addWidget(QLabel(tr('theme_lbl')),    0, 0)
        ug.addWidget(self.theme_combo,            0, 1)
        ug.addWidget(QLabel(tr('language_lbl')), 1, 0)
        ug.addWidget(self.lang_combo,             1, 1)
        right.addWidget(ui_box)

        # ── Right: Apply / Reset buttons ──────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_apply = QPushButton(tr('btn_apply'))
        self.btn_apply.setObjectName('btn_start')
        self.btn_reset = QPushButton(tr('btn_reset'))
        self.btn_reset.setObjectName('btn_stop')
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_reset)
        right.addLayout(btn_row)

        # Status label
        self.lbl_status = QLabel('')
        self.lbl_status.setObjectName('status_ok')
        self.lbl_status.setAlignment(Qt.AlignCenter)
        right.addWidget(self.lbl_status)
        right.addStretch()

        cols.addLayout(left,  stretch=1)
        cols.addLayout(right, stretch=1)
        root.addLayout(cols)

        # ── Wire buttons ──────────────────────────────────────────────────────
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_reset.clicked.connect(self._on_reset)

    # ── Load current settings into widgets ────────────────────────────────────
    def _load_current(self):
        self.tcu_port_edit.setText(settings.get('tcu_port'))
        idx = self.tcu_baud_combo.findText(str(settings.get('tcu_baud')))
        self.tcu_baud_combo.setCurrentIndex(max(0, idx))

        self.pzem_port_edit.setText(settings.get('pzem_port'))
        idx = self.pzem_baud_combo.findText(str(settings.get('pzem_baud')))
        self.pzem_baud_combo.setCurrentIndex(max(0, idx))

        self.temp_sp_spin.setValue(settings.get('temp_setpoint'))
        self.temp_tol_spin.setValue(settings.get('temp_tolerance'))
        self.test_dur_spin.setValue(settings.get('test_duration'))
        self.poll_int_spin.setValue(settings.get('poll_interval'))

        idx = self.theme_combo.findData(settings.get('theme'))
        self.theme_combo.setCurrentIndex(max(0, idx))

        idx = self.lang_combo.findData(settings.get('language'))
        self.lang_combo.setCurrentIndex(max(0, idx))

    # ── Apply button ──────────────────────────────────────────────────────────
    def _on_apply(self):
        port_changed = False

        # Serial ports
        new_tcu_port = self.tcu_port_edit.text().strip()
        new_tcu_baud = int(self.tcu_baud_combo.currentText())
        new_pzem_port = self.pzem_port_edit.text().strip()
        new_pzem_baud = int(self.pzem_baud_combo.currentText())

        if new_tcu_port  != settings.get('tcu_port'):  port_changed = True
        if new_tcu_baud  != settings.get('tcu_baud'):  port_changed = True
        if new_pzem_port != settings.get('pzem_port'): port_changed = True
        if new_pzem_baud != settings.get('pzem_baud'): port_changed = True

        settings.set('tcu_port',       new_tcu_port)
        settings.set('tcu_baud',       new_tcu_baud)
        settings.set('pzem_port',      new_pzem_port)
        settings.set('pzem_baud',      new_pzem_baud)

        # Test parameters
        settings.set('temp_setpoint',  self.temp_sp_spin.value())
        settings.set('temp_tolerance', self.temp_tol_spin.value())
        settings.set('test_duration',  self.test_dur_spin.value())
        settings.set('poll_interval',  self.poll_int_spin.value())

        # Theme
        new_theme = self.theme_combo.currentData()
        if new_theme != settings.get('theme'):
            settings.set('theme', new_theme)
            self.sig_theme_changed.emit(new_theme)

        # Language
        new_lang = self.lang_combo.currentData()
        if new_lang != settings.get('language'):
            settings.set('language', new_lang)
            self.sig_language_changed.emit(new_lang)

        if port_changed:
            self.sig_ports_changed.emit()

        self.lbl_status.setText(tr('applied_ok'))
        self.lbl_status.setObjectName('status_ok')
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)

    # ── Reset to defaults ─────────────────────────────────────────────────────
    def _on_reset(self):
        for key, value in DEFAULTS.items():
            settings.set(key, value)
        self._load_current()
        self.lbl_status.setText(tr('applied_ok'))
        self.sig_theme_changed.emit(settings.get('theme'))
        self.sig_language_changed.emit(settings.get('language'))
        self.sig_ports_changed.emit()

    # ── Called by main_window when language changes ───────────────────────────
    def retranslate(self):
        """Update all labels to current language."""
        # Group box titles
        self._grp_port.setTitle(tr('settings_serial'))
        self._grp_test.setTitle(tr('settings_test'))
        self._grp_ui.setTitle(tr('settings_ui'))
        # Buttons
        self.btn_apply.setText(tr('btn_apply'))
        self.btn_reset.setText(tr('btn_reset'))
        # Notes
        self.restart_note.setText(tr('restart_note'))
        self.lbl_status.setText('')
