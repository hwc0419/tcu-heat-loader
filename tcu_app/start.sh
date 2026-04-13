#!/bin/bash
# =============================================================================
# start.sh — TCU Controller App launcher
# =============================================================================
cd "$(dirname "$0")"

# Check USB-RS232 adapter (TCU)
if [ ! -e /dev/ttyUSB0 ]; then
    echo "WARNING: /dev/ttyUSB0 not found — check USB-RS232 adapter (TCU)"
    echo "Update TCU_PORT in config.py if port differs."
fi

# Check GPIO UART (PZEM-004T energy meter)
if [ ! -e /dev/ttyAMA0 ]; then
    echo "WARNING: /dev/ttyAMA0 not found — GPIO UART not enabled"
    echo "Run: sudo raspi-config → Interface Options → Serial Port"
    echo "Also add dtoverlay=disable-bt to /boot/firmware/config.txt"
fi

# Install dependencies if needed
python3 -c "import PyQt5" 2>/dev/null || pip3 install PyQt5 --break-system-packages
python3 -c "import pyqtgraph" 2>/dev/null || pip3 install pyqtgraph --break-system-packages
python3 -c "import serial" 2>/dev/null || pip3 install pyserial --break-system-packages
python3 -c "import minimalmodbus" 2>/dev/null || pip3 install minimalmodbus --break-system-packages
python3 -c "import minimalmodbus" 2>/dev/null || pip3 install minimalmodbus --break-system-packages

echo "Starting TCU Controller App..."
python3 main.py
