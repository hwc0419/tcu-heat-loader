# =============================================================================
# stress_test_tab.py — AMAT0 Test (outer wrapper)
# =============================================================================
# Holds two subtabs:
#   Main      — the gated, scored pass/fail test (main_test_tab.MainTestTab)
#   Reference — builds/manages the pass/ comparison dataset
#               (reference_test_tab.ReferenceTestTab)
#
# Only one subtab's test can be running at a time — each one's own Start
# button independently guards against that, and update_sample()/
# on_tcu_abnormal() here forward to whichever is currently active (both
# subtabs no-op if they're not the one running, so forwarding to both
# unconditionally is safe).
# =============================================================================

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtCore import pyqtSignal

from gui.main_test_tab import MainTestTab
from gui.reference_test_tab import ReferenceTestTab

class StressTestTab(QWidget):
    """AMAT0 Test — outer wrapper holding the Main and Reference subtabs."""

    sig_test_start = pyqtSignal()
    sig_test_stop  = pyqtSignal()

    def __init__(self, scale: float = 1.0, parent=None):
        self._scale = scale
        super().__init__(parent)

        self._main_tab = MainTestTab(scale=scale)
        self._reference_tab = ReferenceTestTab(scale=scale)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._subtabs = QTabWidget()
        self._subtabs.addTab(self._main_tab, 'MAIN')
        self._subtabs.addTab(self._reference_tab, 'REFERENCE')
        layout.addWidget(self._subtabs)
        
        self._main_tab.sig_test_start.connect(self.sig_test_start)
        self._main_tab.sig_test_stop.connect(self.sig_test_stop)
        self._reference_tab.sig_test_start.connect(self.sig_test_start)
        self._reference_tab.sig_test_stop.connect(self.sig_test_stop)
        self._reference_tab.sig_dataset_changed.connect(self._main_tab._update_gate)

    def update_sample(self, sample):
        """Forward to both subtabs — each one no-ops internally if it's not
        the one currently running a test."""
        self._main_tab.update_sample(sample)
        self._reference_tab.update_sample(sample)

    def on_tcu_abnormal(self):
        self._main_tab.on_tcu_abnormal()
        self._reference_tab.on_tcu_abnormal()

    def retranslate(self):
        self._main_tab.retranslate()
        self._reference_tab.retranslate()
