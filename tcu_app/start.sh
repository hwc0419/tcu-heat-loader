#!/bin/bash
# =============================================================================
# start.sh — TCU++ Launcher (RPi 4)
# =============================================================================
# Starts the TCU++ PyQt5 app in fullscreen mode.
# Called by systemd tcu-app.service on boot.
#
# Manual start:
#   cd tcu_app && ./start.sh
# =============================================================================

cd "$(dirname "$0")"

# Verify TCU RS232 adapter is present
if [ ! -e /dev/ttyUSB0 ]; then
    echo "WARNING: /dev/ttyUSB0 not found — TCU RS232 adapter may not be connected"
fi

# Verify PZEM UART is present
if [ ! -e /dev/ttyAMA0 ]; then
    echo "WARNING: /dev/ttyAMA0 not found — check raspi-config UART setup"
fi

# Launch app in fullscreen
exec python3 main.py --fullscreen
