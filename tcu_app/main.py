#!/usr/bin/env python3
# =============================================================================
# main.py — TCU Controller App entry point
# =============================================================================

import sys
import os
import subprocess

# Ensure correct working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QLineEdit, QDoubleSpinBox, QSpinBox
from PyQt5.QtCore import Qt, QObject, QEvent
from gui.main_window import MainWindow

_OSK_WIDGETS = (QLineEdit, QDoubleSpinBox, QSpinBox)
_osk_proc    = None


def _osk_show():
    global _osk_proc
    if _osk_proc is None or _osk_proc.poll() is not None:
        _osk_proc = subprocess.Popen(['onboard'])


def _osk_hide():
    global _osk_proc
    if _osk_proc and _osk_proc.poll() is None:
        _osk_proc.terminate()
        _osk_proc = None


class OskFilter(QObject):
    """Show/hide Onboard when Qt input widgets gain/lose focus."""

    def eventFilter(self, obj, event):
        if isinstance(obj, _OSK_WIDGETS):
            if event.type() == QEvent.FocusIn:
                _osk_show()
            elif event.type() == QEvent.FocusOut:
                _osk_hide()
        return False


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('TCU++')
    app.setAttribute(Qt.AA_SynthesizeTouchForUnhandledMouseEvents, False)

    # Install OSK event filter on all widgets
    osk_filter = OskFilter()
    app.installEventFilter(osk_filter)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
