#!/usr/bin/env python3
# =============================================================================
# main.py — TCU Controller App entry point
# =============================================================================
# Run: python3 main.py
# Or:  ./start.sh
#
# Replaces Haake TCU Service Software with:
#   - English interface
#   - CSV data + error logging
#   - Full RS232 command log
#   - Heat load test mode (30-min pass/fail)
#   - PyQtGraph real-time temperature graphs
# =============================================================================

import sys
import os

# Ensure correct working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from gui.main_window import MainWindow


def main():
    # RPi touchscreen: rotate if needed
    # os.environ['QT_QPA_EGLFS_ROTATION'] = '90'

    app = QApplication(sys.argv)
    app.setApplicationName('TCU++')

    # Touchscreen: enable touch events
    app.setAttribute(Qt.AA_SynthesizeTouchForUnhandledMouseEvents, False)

    window = MainWindow()

    # Launch fullscreen if --fullscreen flag passed (used by systemd service)
    if '--fullscreen' in sys.argv:
        window.showFullScreen()
    else:
        window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
