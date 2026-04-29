# =============================================================================
# osk.py — On-screen keyboard + touch-friendly input widgets
# =============================================================================

import subprocess
from PyQt5.QtWidgets import (
    QLineEdit, QSpinBox, QDoubleSpinBox, QInputDialog
)

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
    """QLineEdit that shows Onboard on tap."""

    def focusInEvent(self, event):
        _show()
        super().focusInEvent(event)

    def mousePressEvent(self, event):
        _show()
        super().mousePressEvent(event)


class OskSpinBox(QSpinBox):
    """QSpinBox that opens a number dialog on tap — touchscreen friendly."""

    def mousePressEvent(self, event):
        val, ok = QInputDialog.getInt(
            self, 'Enter value', '',
            value=self.value(),
            min=self.minimum(),
            max=self.maximum(),
            step=self.singleStep()
        )
        if ok:
            self.setValue(val)

    def focusInEvent(self, event):
        _show()
        super().focusInEvent(event)


class OskDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that opens a number dialog on tap — touchscreen friendly."""

    def mousePressEvent(self, event):
        val, ok = QInputDialog.getDouble(
            self, 'Enter value', '',
            value=self.value(),
            min=self.minimum(),
            max=self.maximum(),
            decimals=self.decimals()
        )
        if ok:
            self.setValue(val)

    def focusInEvent(self, event):
        _show()
        super().focusInEvent(event)

