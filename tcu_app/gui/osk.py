# =============================================================================
# osk.py — On-screen keyboard integration
# =============================================================================
# Drop-in replacements for QLineEdit, QSpinBox, QDoubleSpinBox that
# automatically show/hide Onboard when focused on a touchscreen.
# Usage: replace imports in any tab file:
#   from gui.osk import OskLineEdit as QLineEdit
#   from gui.osk import OskSpinBox as QSpinBox
#   from gui.osk import OskDoubleSpinBox as QDoubleSpinBox
# =============================================================================

import subprocess
from PyQt5.QtWidgets import QLineEdit, QSpinBox, QDoubleSpinBox

_proc = None


def _show():
    global _proc
    if _proc is None or _proc.poll() is not None:
        _proc = subprocess.Popen(['onboard', '--size=1200x220'])


def _hide():
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        _proc = None


class OskLineEdit(QLineEdit):
    def focusInEvent(self, event):
        _show()
        super().focusInEvent(event)


class OskSpinBox(QSpinBox):
    def focusInEvent(self, event):
        _show()
        super().focusInEvent(event)


class OskDoubleSpinBox(QDoubleSpinBox):
    def focusInEvent(self, event):
        _show()
        super().focusInEvent(event)
