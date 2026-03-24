#!/bin/bash
# =============================================================================
# start.sh — TCU Heat Load Test Launcher
# =============================================================================
# Run this script from the terminal on the RPi touchscreen display.
# Usage: ./start.sh
# =============================================================================

# Navigate to script directory regardless of where start.sh is called from
cd "$(dirname "$0")"

# Check USB-RS232 adapter is connected
if [ ! -e /dev/ttyUSB0 ]; then
    echo "ERROR: USB-RS232 adapter not found at /dev/ttyUSB0"
    echo "Check the adapter is plugged in, then run: ls /dev/ttyUSB*"
    echo "Update TCU_PORT in config.py if the port number differs."
    exit 1
fi

# Check pyserial is installed
python3 -c "import serial" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing pyserial..."
    pip3 install pyserial --break-system-packages
fi

# Launch test
echo "Starting TCU Heat Load Test..."
python3 main.py
