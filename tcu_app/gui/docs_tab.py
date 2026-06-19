# =============================================================================
# docs_tab.py — Documentation Tab
# =============================================================================
# Built-in reference documentation for operators and technicians.
# Covers:
#   1. Haake ASM TCU hardware specifications
#   2. RS232 command reference
#   3. BS status byte decoding table (section 6.5 of Haake manual)
#   4. Heat load test procedure (pre-test, test sequence, pass/fail, post-test)
#   5. PZEM-004T wiring and setup
#   6. Alarm response guide
# =============================================================================

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QScrollArea, QGroupBox, QGridLayout,
    QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.styles import (
    PANEL, SURFACE, BORDER, ACCENT, GREEN, RED, AMBER, TEXT, TEXT_DIM,
    pt_primary, pt_secondary
)


class DocsTab(QWidget):
    """
    Built-in documentation tab — reference material for operators.
    Organised into sub-tabs for quick navigation.
    """

    def __init__(self, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self._scale = scale
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sub-tab navigation
        self._subtabs = QTabWidget()
        self._subtabs.tabBar().setExpanding(False)
        self._subtabs.addTab(self._build_tcu_specs(),     'TCU SPECS')
        self._subtabs.addTab(self._build_rs232_ref(),     'RS232 COMMANDS')
        self._subtabs.addTab(self._build_status_bytes(),  'STATUS BYTES')
        self._subtabs.addTab(self._build_test_procedure(),'TEST PROCEDURE')
        self._subtabs.addTab(self._build_pzem_guide(),    'PZEM WIRING')
        self._subtabs.addTab(self._build_alarm_guide(),   'ALARM GUIDE')
        root.addWidget(self._subtabs)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _scroll(self, widget):
        """Wrap a widget in a scroll area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        scroll.setFrameShape(QFrame.NoFrame)
        return scroll

    def _section(self, title):
        """Create a labelled section group box."""
        box = QGroupBox(title)
        return box

    def _h1(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: {pt_primary(14, self._scale)}px; "
            f"font-weight: bold; font-family: 'Courier New'; "
            f"padding: 8px 0 4px 0;")
        return lbl

    def _h2(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {TEXT}; font-size: {pt_secondary(12, self._scale)}px; "
            f"font-weight: bold; font-family: 'Courier New'; "
            f"padding: 4px 0 2px 0;")
        return lbl

    def _p(self, text, color=None):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {color or TEXT}; "
            f"font-size: {pt_primary(11, self._scale)}px; "
            f"font-family: 'Courier New'; padding: 2px 0;")
        return lbl

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {BORDER};")
        return line

    def _table(self, headers, rows, col_stretches=None):
        """Build a simple grid table."""
        frame = QFrame()
        frame.setStyleSheet(
            f"background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 2px;")
        grid = QGridLayout(frame)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)

        fs = pt_secondary(10, self._scale)

        # Header row
        for col, h in enumerate(headers):
            cell = QLabel(f"  {h}  ")
            cell.setStyleSheet(
                f"background: {ACCENT}; color: white; "
                f"font-size: {fs}px; font-weight: bold; "
                f"font-family: 'Courier New'; padding: 4px 6px; "
                f"border-right: 1px solid {BORDER};")
            cell.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(cell, 0, col)

        # Data rows
        for row_idx, row in enumerate(rows):
            bg = PANEL if row_idx % 2 == 0 else SURFACE
            for col_idx, val in enumerate(row):
                # Colour coding for status byte table
                if '(A)' in str(val):
                    fg = AMBER
                elif '(S)' in str(val):
                    fg = RED
                elif '✓' in str(val) or 'Normal' in str(val):
                    fg = GREEN
                else:
                    fg = TEXT
                cell = QLabel(f"  {val}  ")
                cell.setWordWrap(True)
                cell.setStyleSheet(
                    f"background: {bg}; color: {fg}; "
                    f"font-size: {fs}px; font-family: 'Courier New'; "
                    f"padding: 4px 6px; border-right: 1px solid {BORDER}; "
                    f"border-top: 1px solid {BORDER};")
                cell.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                grid.addWidget(cell, row_idx + 1, col_idx)

        if col_stretches:
            for col, stretch in enumerate(col_stretches):
                grid.setColumnStretch(col, stretch)

        return frame

    def _note(self, text, color=None):
        lbl = QLabel(f"ℹ  {text}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"background: {SURFACE}; color: {color or AMBER}; "
            f"border-left: 3px solid {color or AMBER}; "
            f"padding: 6px 10px; "
            f"font-size: {pt_secondary(10, self._scale)}px; "
            f"font-family: 'Courier New';")
        return lbl

    # ── Tab 1: TCU Specifications ─────────────────────────────────────────────

    def _build_tcu_specs(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('Haake ASM Temperature Control Unit — Hardware Specifications'))
        layout.addWidget(self._p(
            'Source: Haake ASM TCU Service Manual (Part No. 002-9034). '
            'The TCU maintains DI water temperature for ASML photo tool cooling circuits.'))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('General Specifications'))
        layout.addWidget(self._table(
            ['Parameter', 'Value', 'Notes'],
            [
                ['Model', 'Haake ASM Temperature Control Unit', ''],
                ['Operating temp range', '17°C to 27°C', 'Safety limits trigger alarm + shutdown'],
                ['Temperature accuracy', '±0.02°C', 'Fine control mode'],
                ['Cooling capacity', '1200W at 20°C outlet', 'KEY SPEC — design basis for jig'],
                ['Heating capacity', '1500W', ''],
                ['Flow rate (at 0.5 bar ΔP)', '50 ℓ/min', ''],
                ['Max pressure (50Hz)', '2.3 bar', ''],
                ['Heat transfer liquid', 'DI water', 'Deionised water only'],
                ['Refrigerant', 'R134a, 750g charge', ''],
                ['Power supply', '3Ph/N/PE 380V ±10% 50/60Hz', ''],
                ['RS232 interface', '25-pin Sub-D, 2400 baud, 8N1', 'Use FTDI DT5011 adapter'],
            ],
            [3, 4, 4]
        ))

        layout.addWidget(self._h2('Physical Setup'))
        layout.addWidget(self._table(
            ['Item', 'Detail'],
            [
                ['Location', 'Subfab — below ASML photo tool'],
                ['Pipe size', '1 inch BSP (confirmed by physical measurement)'],
                ['Pipe run', '~10m between TCU and photo tool'],
                ['Ambient temp', '25°C in subfab (3°C above TCU setpoint of 22°C)'],
                ['Internal sensor', 'PT500 — read via RS232 M command (not wired directly)'],
                ['Adapter', 'FTDI DT5011 USB-RS232 — DB9 Female, straight-through cable'],
                ['Windows port', 'COM5 (Toshiba Portege)'],
                ['Linux port', '/dev/ttyUSB0 (Raspberry Pi 4)'],
            ],
            [3, 7]
        ))

        layout.addWidget(self._h2('Normal Operating State'))
        layout.addWidget(self._note(
            'Normal BS status at idle: 400000  |  Normal BS status while running: 400400  '
            '(b2 bit 2 = main contactor ON — this is expected, not a fault)', GREEN))

        layout.addStretch()
        return self._scroll(w)

    # ── Tab 2: RS232 Command Reference ────────────────────────────────────────

    def _build_rs232_ref(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('RS232 Command Reference'))
        layout.addWidget(self._p(
            'Source: Haake ASM TCU manual pages 24–25. '
            'All commands sent via RS232 at 2400 baud, 8N1, no handshake. '
            'Commands terminated with <CR>. Responses terminated with $<CR><LF>.'))
        layout.addWidget(self._note(
            'Serial settings: 2400 baud · 8 data bits · No parity · 1 stop bit · '
            'rtscts=False · dsrdtr=False'))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('Query Commands'))
        layout.addWidget(self._table(
            ['Command', 'Response Format', 'Description', 'Example'],
            [
                ['M<CR>', 'XX.XX C$', 'Inlet fluid temperature (°C) — ±0.02°C accuracy', '21.93 C$'],
                ['D<CR>', 'XX.X l/min$', 'Flow rate in ℓ/min — parsed as float', '2.5 l/min$'],
                ['SOLL<CR>', 'XX.XX$', 'Read current setpoint temperature', '22.00$'],
                ['BS<CR>', 'XXXXXX$', 'Operating status — 3 bytes hex (see Status Bytes tab)', '400400$'],
            ],
            [2, 3, 5, 2]
        ))

        layout.addWidget(self._h2('Control Commands'))
        layout.addWidget(self._table(
            ['Command', 'Response', 'Description'],
            [
                ['START<CR>', '$', 'Start temperature control — TCU begins cooling/heating'],
                ['STOP<CR>', '$', 'Stop temperature control'],
                ['SOLL  XX.XX<CR>', '$', 'Set setpoint (17.00–27.00°C only — outside range rejected)'],
                ['ER<CR>', '$', 'Release alarm — send after fault is cleared to reset safety circuit'],
                ['AFV<CR>', 'status stream then $', 'Fill system + pre-temperature control — BLOCKING, takes several minutes'],
                ['VT<CR>', '$', 'Pre-temperature control only (no fill)'],
                ['CVE<CR>', '$', 'Close valve'],
            ],
            [3, 2, 5]
        ))

        layout.addWidget(self._h2('Important Notes'))
        layout.addWidget(self._note(
            'Flow rate (D command) must be parsed as FLOAT not INT — '
            'response is "00.0 l/min$" format'))
        layout.addWidget(self._note(
            'AFV is a blocking command — TCU sends continuous status messages '
            'until fill is complete. Do not send other commands during AFV.'))
        layout.addWidget(self._note(
            'SOLL setpoint is limited to 17.00–27.00°C. '
            'Values outside this range are silently rejected by the TCU.'))
        layout.addWidget(self._note(
            'ER command only works after the fault condition has been physically cleared. '
            'Sending ER while fault is still present has no effect.'))

        layout.addStretch()
        return self._scroll(w)

    # ── Tab 3: Status Bytes ───────────────────────────────────────────────────

    def _build_status_bytes(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('BS Status Byte Decoding'))
        layout.addWidget(self._p(
            'Source: Haake ASM TCU manual section 6.5. '
            'BS command returns 6 hex characters = 3 bytes (b1 b2 b3).'))
        layout.addWidget(self._note(
            'Normal idle:    BS = 400000  (b1=0x40, b2=0x00, b3=0x00)\n'
            'Normal running: BS = 400400  (b1=0x40, b2=0x04, b3=0x00)\n'
            'b1 bit 6 = Water level FULL (always set — normal)\n'
            'b2 bit 2 = Main contactor ON (set at START, cleared at STOP/ALARM — normal)',
            GREEN))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('Byte 1 (b1) — ASCII characters 1 and 2'))
        layout.addWidget(self._table(
            ['Bit', 'Condition', 'Meaning'],
            [
                ['7', 'Any', 'No meaning'],
                ['6', '= 1', '✓ Normal — Liquid level mark FULL exceeded (always set in normal operation)'],
                ['5', '= 1', 'Liquid level mark ASM not reached — check water supply'],
                ['4', '= 1', '(A) Liquid level mark MIN not reached — risk of dry run'],
                ['3', '= 1', '(A) Pump 2 (ext.) operating temperature exceeded'],
                ['2', '= 1', '(A) Pump 1 (int.) operating temperature exceeded'],
                ['1', '= 1', '(A) Temperature exceeded 27°C upper limit'],
                ['0', '= 1', '(A) Temperature below 17°C lower limit'],
            ],
            [1, 2, 7]
        ))

        layout.addWidget(self._h2('Byte 2 (b2) — ASCII characters 3 and 4'))
        layout.addWidget(self._table(
            ['Bit', 'Condition', 'Meaning'],
            [
                ['7', '= 1', '(A) ALARM — unit switches off automatically'],
                ['6', '= 1', 'START/STOP commands and internal monitoring blocked'],
                ['5', '= 1', '(A) Temperature below 3°C or above 40°C operating range'],
                ['4', '= 1', '(A) Temperature sensor breakage or short-circuit'],
                ['3', '= 1', '(A) Calibration fault'],
                ['2', '= 1', '✓ Normal — Main contactor activated (=1 at START, =0 at STOP/ALARM)'],
                ['1', '= 1', '(A) Fault in heating circuit'],
                ['0', '= 1', '(A) Operating pressure not reached'],
            ],
            [1, 2, 7]
        ))

        layout.addWidget(self._h2('Byte 3 (b3) — ASCII characters 5 and 6'))
        layout.addWidget(self._table(
            ['Bit', 'Condition', 'Meaning'],
            [
                ['7', '= 1', 'Supply voltage not present in safety circuit'],
                ['6', 'Any', 'No meaning'],
                ['5', 'Any', 'No meaning'],
                ['4', '= 1', '(S) Hardware fault: main contactor — switch unit OFF'],
                ['3', '= 1', '(S) Hardware fault: watchdog switching — switch unit OFF'],
                ['2', '= 1', '(S) Hardware fault: alarm triggering switching — switch unit OFF'],
                ['1', '= 1', '(S) Hardware fault: unlocking switching — switch unit OFF'],
                ['0', '= 1', '(S) Hardware fault: start test — switch unit OFF'],
            ],
            [1, 2, 7]
        ))

        layout.addWidget(self._h2('Legend'))
        layout.addWidget(self._table(
            ['Code', 'Meaning'],
            [
                ['(A)', 'Alarm source — TCU will trigger alarm and may shut down'],
                ['(S)', 'Severe — START and ER commands cannot be carried out. Unit must be switched off and on.'],
                ['✓ Normal', 'This bit being set is expected during normal operation — not a fault'],
            ],
            [2, 8]
        ))

        layout.addStretch()
        return self._scroll(w)

    # ── Tab 4: Test Procedure ─────────────────────────────────────────────────

    def _build_test_procedure(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('Heat Load Test Procedure'))
        layout.addWidget(self._p(
            'Validates that a repaired Haake ASM TCU can maintain 22°C setpoint '
            'under simulated photo tool heat load for 180 minutes continuously.'))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('Pass / Fail Criteria'))
        layout.addWidget(self._table(
            ['Criteria', 'Threshold', 'Source'],
            [
                ['Inlet temperature', '22.0°C ±0.5°C for full 180 min', 'TCU RS232 M command'],
                ['Flow rate', '≥1 ℓ/min continuously', 'TCU RS232 D command'],
                ['TCU alarm status', 'No alarms (BS = 400400 running)', 'TCU RS232 BS command'],
                ['Test duration', '180 minutes completed without abort', 'Software timer'],
            ],
            [3, 4, 3]
        ))
        layout.addWidget(self._note(
            'Temperature tolerance 0.5°C and duration 180 min are manager requirements. '
            'Both are configurable in the Settings tab.', AMBER))

        layout.addWidget(self._h2('Pre-Test Checklist'))
        layout.addWidget(self._table(
            ['Step', 'Action', 'Expected Result'],
            [
                ['1', 'Connect TCU under test to heat loader inlet/outlet pipes (1" BSP)', 'Secure, leak-free connection'],
                ['2', 'Power on TCU — turn main switch to position 1', 'ALARM light blinks, EMPTY light on (normal)'],
                ['3', 'Click FILL (AFV) button in app — wait for completion', 'System fills with water, status shows complete'],
                ['4', 'Click START button in app', 'TCU begins temperature control'],
                ['5', 'Confirm setpoint is 22.0°C in MONITOR tab', 'Setpoint reads 22.00°C'],
                ['6', 'Power on heat loader panel — green LED lights', 'Mains present confirmed'],
                ['7', 'Select 2000W stage on GT02 HMI touchscreen', '~1403W actual delivered to heater'],
                ['8', 'Confirm flow rate >0 ℓ/min in MONITOR tab', 'TCU pump circulating fluid'],
            ],
            [1, 5, 4]
        ))

        layout.addWidget(self._h2('Test Sequence'))
        layout.addWidget(self._table(
            ['Step', 'Action', 'Duration'],
            [
                ['1', 'Enter TCU serial number in HEAT LOAD TEST tab', '—'],
                ['2', 'Click START TEST button', '—'],
                ['3', 'Monitor inlet temperature — should stabilise at 22°C ±0.5°C', '~10–20 min stabilisation'],
                ['4', 'App automatically logs data every second to CSV', '180 min continuous'],
                ['5', 'App automatically declares PASS or FAIL at 180 min', 'Auto'],
                ['6', 'Turn manual switch OFF on heat loader panel', '—'],
                ['7', 'Click STOP on TCU (app STOP button)', '—'],
                ['8', 'CSV log saved automatically with TCU serial number', '—'],
            ],
            [1, 6, 3]
        ))

        layout.addWidget(self._h2('Post-Test Actions'))
        layout.addWidget(self._table(
            ['Result', 'Action'],
            [
                ['PASS', 'TCU cleared for return to production — file CSV log to shared drive'],
                ['FAIL', 'Document failure reason from CSV, escalate for further repair'],
                ['ABORTED', 'Investigate reason for abort — rerun test if no fault found'],
            ],
            [2, 8]
        ))

        layout.addWidget(self._h2('CSV Log File'))
        layout.addWidget(self._p(
            'Log saved to: logs/TCU_test_<serial>_<YYYYMMDD_HHMMSS>.csv'))
        layout.addWidget(self._table(
            ['Column', 'Description'],
            [
                ['Timestamp', 'HH:MM:SS'],
                ['Elapsed (min)', 'Minutes since test start'],
                ['Setpoint (C)', 'TCU target temperature from SOLL command'],
                ['Inlet Temp TCU (C)', 'Fluid inlet temp from M command'],
                ['Flow (L/min)', 'Flow rate from D command'],
                ['Voltage (V)', 'PZEM-004T measured voltage'],
                ['Current (A)', 'PZEM-004T measured current'],
                ['Power (W)', 'PZEM-004T true watts (handles phase angle SCR load)'],
                ['Alarms', 'Parsed BS status byte alarm descriptions'],
                ['Mode', 'MONITOR or TEST'],
                ['Status', 'RUNNING / PASS / FAIL with reason'],
            ],
            [3, 7]
        ))

        layout.addStretch()
        return self._scroll(w)

    # ── Tab 5: PZEM Wiring ────────────────────────────────────────────────────

    def _build_pzem_guide(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('PZEM-004T v3.0 Energy Meter — Wiring and Setup'))
        layout.addWidget(self._p(
            'The PZEM-004T measures true watts delivered to the heater. '
            'Connected to RPi via GPIO UART — no USB port used.'))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('RPi GPIO Wiring'))
        layout.addWidget(self._table(
            ['PZEM-004T Pin', 'RPi Pin', 'GPIO', 'Description'],
            [
                ['TX', 'Pin 10', 'GPIO 15 (RX)', 'PZEM transmit → RPi receive'],
                ['RX', 'Pin 8',  'GPIO 14 (TX)', 'PZEM receive ← RPi transmit'],
                ['5V', 'Pin 2',  '5V power',     'PZEM power supply'],
                ['GND', 'Pin 6', 'GND',          'Common ground'],
            ],
            [3, 2, 3, 4]
        ))
        layout.addWidget(self._note(
            'Use RPi GPIO UART (/dev/ttyAMA0) — NOT /dev/ttyUSB0. '
            'GPIO UART setup required before first use (see below).', AMBER))

        layout.addWidget(self._h2('CT Clamp Installation'))
        layout.addWidget(self._table(
            ['Step', 'Action'],
            [
                ['1', 'Open the split-core CT clamp'],
                ['2', 'Clip CT around the heater LIVE wire only (not neutral)'],
                ['3', 'Close and latch the CT clamp securely'],
                ['4', 'Connect CT leads to PZEM-004T CT terminals'],
                ['5', 'Tap L/N voltage sense wires from W5 SCR output terminals'],
                ['6', 'Connect voltage sense leads to PZEM-004T V terminals'],
            ],
            [1, 9]
        ))
        layout.addWidget(self._note(
            'CT must clamp around ONE wire only (live). '
            'Clamping both live and neutral cancels the measurement.', RED))

        layout.addWidget(self._h2('Modbus RTU Settings'))
        layout.addWidget(self._table(
            ['Parameter', 'Value'],
            [
                ['Baud rate', '9600'],
                ['Data bits', '8'],
                ['Parity', 'None'],
                ['Stop bits', '1'],
                ['Slave address', '0xF8 (broadcast — works for single device)'],
                ['Linux port', '/dev/ttyAMA0'],
                ['Windows port', 'COM6 (USB-TTL adapter)'],
            ],
            [3, 7]
        ))

        layout.addWidget(self._h2('Register Map'))
        layout.addWidget(self._table(
            ['Register', 'Parameter', 'Scale', 'Unit'],
            [
                ['0x0000', 'Voltage', '÷10', 'V'],
                ['0x0001–0x0002', 'Current (Lo + Hi)', '÷1000', 'A'],
                ['0x0003–0x0004', 'Power (Lo + Hi)', '÷10', 'W'],
                ['0x0005–0x0006', 'Energy', '÷1', 'Wh'],
                ['0x0007', 'Frequency', '÷10', 'Hz'],
                ['0x0008', 'Power factor', '÷100', '—'],
            ],
            [3, 3, 2, 2]
        ))
        layout.addWidget(self._note(
            'Registers use integer scaling — NOT IEEE 754 floats. '
            'Function code: 0x04 (Read Input Registers).'))

        layout.addWidget(self._h2('RPi UART Setup (run once)'))
        layout.addWidget(self._p('Required before PZEM-004T will work on RPi:'))
        layout.addWidget(self._table(
            ['Step', 'Action'],
            [
                ['1', 'Run: sudo raspi-config'],
                ['2', 'Navigate: Interface Options → Serial Port'],
                ['3', '"Login shell over serial?" → No'],
                ['4', '"Serial port hardware enabled?" → Yes'],
                ['5', 'Add to /boot/firmware/config.txt: dtoverlay=disable-bt'],
                ['6', 'Run: sudo reboot'],
                ['7', 'Verify: ls /dev/ttyAMA0 should show the device'],
            ],
            [1, 9]
        ))

        layout.addStretch()
        return self._scroll(w)

    # ── Tab 6: Alarm Response Guide ───────────────────────────────────────────

    def _build_alarm_guide(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('Alarm Response Guide'))
        layout.addWidget(self._p(
            'Quick reference for operators when the command log shows alarm conditions. '
            'All alarms are decoded from BS status bytes in real time.'))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('Water Level Alarms'))
        layout.addWidget(self._table(
            ['Alarm', 'Likely Cause', 'Action'],
            [
                ['Water level ASM not reached', 'Water supply issue or air in system', 'Run FILL (AFV) — check water supply valve is open'],
                ['(A) Water level MIN not reached', 'Critically low water — risk of dry run', 'STOP test immediately — run FILL (AFV) before restarting'],
            ],
            [3, 4, 3]
        ))

        layout.addWidget(self._h2('Temperature Alarms'))
        layout.addWidget(self._table(
            ['Alarm', 'Likely Cause', 'Action'],
            [
                ['(A) Temp exceeded 27°C upper limit', 'Cooling failure or heat load too high', 'STOP test — check refrigeration, reduce heat load stage'],
                ['(A) Temp below 17°C lower limit', 'Overcooling or chiller fault', 'STOP test — check setpoint, check refrigerant charge'],
                ['(A) Temp below 3°C or above 40°C', 'Severe thermal fault', 'STOP test — unit requires service inspection'],
                ['(A) Temperature sensor fault', 'PT500 probe broken or short-circuit', 'STOP test — check PT500 probe connection inside TCU'],
            ],
            [3, 3, 4]
        ))

        layout.addWidget(self._h2('Operational Alarms'))
        layout.addWidget(self._table(
            ['Alarm', 'Likely Cause', 'Action'],
            [
                ['ALARM — unit switches off automatically', 'Any (A) fault triggered auto-shutdown', 'Clear fault condition → send ER command → restart'],
                ['START/STOP commands blocked', 'Unit in fault state', 'Clear fault → send ER → wait for release → restart'],
                ['(A) Fault in heating circuit', 'Heater element open circuit or relay fault', 'STOP test — check heater continuity, check contactor'],
                ['(A) Operating pressure not reached', 'Pump failure or valve closed', 'STOP test — check pump, check all valves open'],
                ['(A) Calibration fault', 'Internal sensor calibration error', 'Unit requires service — send for repair'],
            ],
            [3, 3, 4]
        ))

        layout.addWidget(self._h2('Hardware Faults (S) — Unit must be switched off'))
        layout.addWidget(self._note(
            '(S) faults mean START and ER commands cannot be carried out. '
            'Switch the TCU off and on. If fault persists, unit requires service.', RED))
        layout.addWidget(self._table(
            ['Alarm', 'Action'],
            [
                ['(S) Hardware fault: main contactor', 'Switch off → switch on → if persists: send for service'],
                ['(S) Hardware fault: watchdog switching', 'Switch off → switch on → if persists: send for service'],
                ['(S) Hardware fault: alarm triggering', 'Switch off → switch on → if persists: send for service'],
                ['(S) Hardware fault: unlocking switching', 'Switch off → switch on → if persists: send for service'],
                ['(S) Hardware fault: start test', 'Switch off → switch on → if persists: send for service'],
            ],
            [4, 6]
        ))

        layout.addWidget(self._h2('Releasing an Alarm'))
        layout.addWidget(self._table(
            ['Step', 'Action'],
            [
                ['1', 'Identify alarm from command log — note the specific fault description'],
                ['2', 'Physically clear the fault condition (e.g. refill water, fix heater)'],
                ['3', 'Click CLEAR ALARM (ER) button in Monitor tab'],
                ['4', 'Observe BS status — b2 bit 7 should clear (ALARM bit = 0)'],
                ['5', 'Click START to restart temperature control'],
                ['6', 'Monitor for 5 minutes to confirm alarm does not recur'],
            ],
            [1, 9]
        ))

        layout.addStretch()
        return self._scroll(w)
