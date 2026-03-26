#!/bin/bash
# =============================================================================
# start.sh — TCU Controller App launcher
# =============================================================================
cd "$(dirname "$0")"

# Check USB-RS232 adapter
if [ ! -e /dev/ttyUSB0 ]; then
    echo "WARNING: /dev/ttyUSB0 not found — check USB-RS232 adapter"
    echo "App will start but TCU connection will fail."
    echo "Update TCU_PORT in config.py if port differs."
fi

# Install dependencies if needed
python3 -c "import PyQt5" 2>/dev/null || pip3 install PyQt5 --break-system-packages
python3 -c "import pyqtgraph" 2>/dev/null || pip3 install pyqtgraph --break-system-packages
python3 -c "import serial" 2>/dev/null || pip3 install pyserial --break-system-packages

echo "Starting TCU Controller App..."
python3 main.py
