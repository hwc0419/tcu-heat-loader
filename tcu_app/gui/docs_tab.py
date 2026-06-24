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
    QFrame, QSizePolicy, QPushButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
import os

from gui.styles import (
    PANEL, SURFACE, BORDER, ACCENT, GREEN, RED, AMBER, TEXT, TEXT_DIM,
    pt_primary, pt_secondary
)
from config import MANUAL_DIR, MANUAL_PAGE_COUNT, DOCS_ASSETS_DIR


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
        self._subtabs.addTab(self._build_about_app(),      'ABOUT THIS APP')
        self._subtabs.addTab(self._build_system_overview(), 'SYSTEM OVERVIEW')
        self._subtabs.addTab(self._build_tcu_specs(),     'TCU SPECS')
        self._subtabs.addTab(self._build_rs232_ref(),     'RS232 COMMANDS')
        self._subtabs.addTab(self._build_status_bytes(),  'STATUS BYTES')
        self._subtabs.addTab(self._build_test_procedure(),'TEST PROCEDURE')
        self._subtabs.addTab(self._build_manual_viewer(), 'TCU HAAKE MANUAL')
        self._subtabs.addTab(self._build_wiring_guide(),  'WIRING')
        self._subtabs.addTab(self._build_plc_guide(),     'PLC')
        self._subtabs.addTab(self._build_alarm_guide(),   'ALARM GUIDE')
        self._subtabs.addTab(self._build_feature_list(),  'FEATURE LIST')
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
            'Source: TCU_RS232_Interface.txt (Haake ASM manual section 6, '
            '"ASM Control Software"). All commands sent via RS232. Every '
            'command terminated by <CR> only — an additional <LF> is ignored '
            'and should not be sent. Every executable command is acknowledged '
            'with $<CR><LF> once processed (START is the one exception — it '
            'acknowledges immediately, since further commands can be issued '
            'during the temperature control phase). Non-executable or '
            'incorrect commands return F<CR><LF>.'))
        layout.addWidget(self._note(
            'Serial settings: 600/1200/2400 baud (adjustable via DIP switch) '
            '· 8 data bits · optional parity · 1 stop bit · optional CTS/RTS '
            'handshake · ASCII character code. This app uses 2400 baud, 8N1, '
            'no handshake.'))
        layout.addWidget(self._note(
            'The manual specifies the D (flow rate) reply as a 2-digit '
            'INTEGER, e.g. "02 1/min$". In practice the real TCU sends '
            'decimal values like "2.5 l/min$" — the app parses with float(), '
            'which handles both, but don\'t assume the manual\'s format is '
            'exactly what you\'ll see on the wire.', AMBER))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('General Commands'))
        layout.addWidget(self._table(
            ['Command', 'Reply', 'Description'],
            [
                ['V<CR>', '1.2-4/90-017$', 'Current software version'],
                ['RESET<CR>', 'KALIBRIERT$ / NICHT KALIBRIERT$', 'Return unit to switched-on state and recalibrate'],
                ['START<CR>', '$ (immediate)', 'Start temperature control — must be re-sent each time the module is switched on'],
                ['STOP<CR>', '$', 'Stop temperature control / filling / pretemperature controlling'],
                ['M<CR>', 'XX.XX C$', 'Inlet temperature, 0.00-28.00°C'],
                ['D<CR>', 'XX l/min$', 'Flow rate, 0-60 l/min — see float/int note above'],
                ['SOLL  XX.XX<CR>', '$', 'Set setpoint, 17.00-27.00°C only ("  " = 2 spaces)'],
                ['SOLL<CR>', '$', 'Read current setpoint'],
                ['ER<CR>', '$ / F', 'Release safety circuit — F if fault source not eliminated'],
                ['BS<CR>', '<B1><B2><B3>$', 'Operating status, 3 bytes hex — see Status Bytes tab'],
                ['BSB<CR>', 'bit sequence$', 'Same as BS but pre-decoded as individual bits'],
            ],
            [3, 3, 6]
        ))

        layout.addWidget(self._h2('Filling Commands'))
        layout.addWidget(self._table(
            ['Command', 'Reply', 'Description'],
            [
                ['AFV<CR>', 'status stream, then $', 'Fill system + pretemperature control to within ±0.2°C of setpoint — BLOCKING, status messages (TF/VT/temperature/AF) repeat until full, several minutes'],
                ['OMF<CR>', '$', 'Release manual filling (top-up button then works)'],
                ['CMF<CR>', '$', 'Lock manual filling'],
                ['MF<CR>', '0$ / 1$', 'Manual filling status (1 = possible, 0 = locked)'],
            ],
            [3, 3, 6]
        ))
        layout.addWidget(self._note(
            'AFV is the safe, automatic way to begin temperature control on a '
            'unit that\'s outside the 17-27°C range. It can be replaced by the '
            'special commands TFV/VT (see below) but those require detailed '
            'system knowledge and give no status feedback.'))

        layout.addWidget(self._h2('Special Commands'))
        layout.addWidget(self._p(
            'Lower-level commands — most are software switches that release a '
            'function without starting it (e.g. heating cannot switch on via '
            'HEIN until the main contactor is active via PIE/HSE first). '
            'Used by AFV internally; rarely needed directly.'))
        layout.addWidget(self._table(
            ['Command', 'Reply', 'Description'],
            [
                ['TFV<CR>', '$', 'Fill circulator + pretemp. control to ±0.2°C (no status stream)'],
                ['VT<CR>', '$', 'Pretemperature control circulator only, no fill (no status stream)'],
                ['MTB<CR> / OTB<CR>', '$', 'Activate / switch off the 17-27°C temperature limit'],
                ['TB<CR>', '0$ / 1$', 'Temperature limit status (1 = with limit, 0 = without)'],
                ['OVI<CR> / CVI<CR>', '$', 'Open / close filling valve (software release only)'],
                ['VI<CR>', '0$ / 1$', 'Filling valve status'],
                ['PIE<CR> / PIA<CR>', '$', 'Pump 1 (internal) ON / OFF — also switches main contactor'],
                ['PI<CR>', '0$ / 1$', 'Pump 1 status'],
                ['PEE<CR> / PEA<CR>', '$', 'Pump 2 (external) ON / OFF — opens/closes ext. valve too, 2s delay'],
                ['PE<CR>', '0$ / 1$', 'Pump 2 status'],
                ['OVE<CR> / CVE<CR>', '$', 'Open / close external solenoid valve — CVE stops pump first'],
                ['VE<CR>', '0$ / 1$', 'External valve status'],
                ['OKE<CR> / CKE<CR>', '$', 'Open / close external circuit (valve + pump 2 together)'],
                ['KE<CR>', '0$ / 1$', 'External circuit status'],
                ['KPE<CR> / KPA<CR>', '$', 'Compressor ON / OFF — min. 2 min between OFF and ON again'],
                ['KP<CR>', '0$ / 1$', 'Compressor status'],
                ['HEIN<CR> / HAUS<CR>', '$', 'Heating ON / OFF — requires main contactor already active'],
                ['HEIZ<CR>', '0$ / 1$', 'Heating status'],
                ['HSE<CR> / HSA<CR>', '$', 'Main contactor ON / OFF'],
                ['HS<CR>', '0$ / 1$', 'Main contactor status'],
                ['R<CR>', 'XX.XXXX C$', 'Temperature control sensor (raw)'],
                ['E1<CR> / E2<CR> / E3<CR>', '<B><sign>XX.XXXX V$', 'Raw voltage at measuring sensor / control sensor / flow sensor'],
                ['REF<CR>', '<B><sign>XX.XXXX V$', 'Reference voltage (1.8V) used for PT500 temperature measurement — check this if temp readings look wrong'],
                ['Y<CR>', '<sign><y> - <ynorm>$', 'Heating correcting variable, raw and normalised (0-100%)'],
                ['XDN/XDA/DIF/SUM/GR/IA/IN<CR>', 'XXXXXX$', 'PID control loop internals — set/actual deviation, gradient, integral terms'],
                ['BYTE  <ADR><CR>', 'XX$', 'Read RAM storage address directly (0-255) — test purposes only'],
                ['ABS<CR>', '<A1><A2><A3>$', 'Original alarm status, 3 bytes hex'],
            ],
            [3, 3, 6]
        ))

        layout.addWidget(self._h2('Important Notes'))
        layout.addWidget(self._note(
            'AFV is a blocking command — TCU sends continuous status messages '
            'until fill is complete. Do not send other commands during AFV.'))
        layout.addWidget(self._note(
            'SOLL setpoint is limited to 17.00-27.00°C. '
            'Values outside this range are silently rejected by the TCU.'))
        layout.addWidget(self._note(
            'ER command only works after the fault condition has been physically cleared. '
            'Sending ER while fault is still present returns F instead of $.'))
        layout.addWidget(self._note(
            'Cooling compressor needs at least 2 minutes between switching OFF '
            'and back ON — ignoring this can damage the compressor.', RED))

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

        layout.addWidget(self._h1('AMAT0 Heat Load Test Procedure'))
        layout.addWidget(self._p(
            'Validates that a repaired Haake ASM TCU can support the Photo Tool heat load. '
            'The test measures temperature and flow rate over time for the TCU under test '
            'and compares it against a reference dataset of known-good TCUs. '
            'The test passes if the temp/flow rate profile matches the reference dataset '
            'and the transient response time is statistically similar.'))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('Before Testing'))
        layout.addWidget(self._table(
            ['Step', 'Action'],
            [
                ['1', 'On the M4422-22 415V mains switch, turn both PCW valves open and TCU switch on'],
                ['2', 'Ensure all water pipes are connected and the water circuit is closed: '
                      'AMAT out → 2kW heater in → 2kW heater out → TCU in → TCU out → AMAT in'],
                ['3', 'Point Fluke62 Max IR gun at AMAT0 heater tank — ensure the IR gun is on at all times'],
                ['4', 'Set AMAT0 setpoint temp to 80°C, wait for IR gun to show 45°C (takes ~20 minutes)'],
            ],
            [1, 9]
        ))

        layout.addWidget(self._h2('During Testing'))
        layout.addWidget(self._table(
            ['Step', 'Action'],
            [
                ['1', 'On the touchscreen, go to TCU++ app → AMAT0 Transient Test, '
                      'enter TCU Serial No. then press Start'],
                ['2', 'While the test is running, watch both the temp and flow rate graphs. '
                      'The shape of both graphs should match the reference. '
                      'Reference graphs are in: '
                      '/home/hwc0419/projects/tcu-heat-loader/tcu_app/pictures/'],
                ['3', 'The test will end automatically and conclude Pass or Fail'],
            ],
            [1, 9]
        ))

        layout.addWidget(self._h2('After Testing'))
        layout.addWidget(self._table(
            ['Step', 'Action'],
            [
                ['1', 'Export the temp and flow rate graphs — choose a folder to save them to '
                      '(default: /home/hwc0419/projects/tcu-heat-loader/tcu_app/)'],
                ['2', 'Shutdown RPi, turn off power supply to display and RPi, remove the SD card'],
                ['3', 'Bring the SD card to Office Level 2, find the RPi there and insert the SD card'],
                ['4', 'Turn on RPi, connect phone hotspot to RPi, open web browser and '
                      'log in to your Cloud Drive (OneDrive or Google Drive)'],
                ['5', 'Upload the graphs and raw data file from the RPi to your Cloud Drive'],
            ],
            [1, 9]
        ))

        layout.addStretch()
        return self._scroll(w)


    def _build_manual_viewer(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('TCU Haake Manual'))
        layout.addWidget(self._p(
            'Full scanned manual, 50 pages. Page numbers below are the file\'s '
            'own page sequence (1–50); the manual\'s own printed page numbers '
            'are offset by 1 from this (e.g. file page 36 = printed page 35).'))
        layout.addWidget(self._note(
            'Stored as manual_pages/1.jpeg .. 50.jpeg — this is the original '
            'scanned page set, not re-rendered from a real PDF.'))

        nav_row = QHBoxLayout()
        self._manual_btn_prev = QPushButton('◀ Previous')
        self._manual_btn_prev.clicked.connect(self._manual_prev_page)
        self._manual_page_lbl = self._h2(f'Page 1 / {MANUAL_PAGE_COUNT}')
        self._manual_btn_next = QPushButton('Next ▶')
        self._manual_btn_next.clicked.connect(self._manual_next_page)
        nav_row.addWidget(self._manual_btn_prev)
        nav_row.addStretch()
        nav_row.addWidget(self._manual_page_lbl)
        nav_row.addStretch()
        nav_row.addWidget(self._manual_btn_next)
        layout.addLayout(nav_row)

        self._manual_page_num = 1
        self._manual_image_lbl = QLabel()
        self._manual_image_lbl.setAlignment(Qt.AlignCenter)
        self._manual_image_lbl.setMinimumHeight(int(600 * self._scale))
        layout.addWidget(self._manual_image_lbl)
        self._manual_load_page(1)

        layout.addStretch()
        return self._scroll(w)

    def _manual_load_page(self, page_num: int):
        """Load and display one manual page image. page_num is clamped to
        [1, MANUAL_PAGE_COUNT] — never goes outside the known fixed page set."""
        page_num = max(1, min(MANUAL_PAGE_COUNT, page_num))
        self._manual_page_num = page_num
        path = os.path.join(MANUAL_DIR, f'{page_num}.jpeg')
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._manual_image_lbl.setText(f'Could not load {path}')
        else:
            scaled = pixmap.scaledToWidth(
                int(700 * self._scale), Qt.SmoothTransformation)
            self._manual_image_lbl.setPixmap(scaled)
        self._manual_page_lbl.setText(f'Page {page_num} / {MANUAL_PAGE_COUNT}')
        self._manual_btn_prev.setEnabled(page_num > 1)
        self._manual_btn_next.setEnabled(page_num < MANUAL_PAGE_COUNT)

    def _manual_prev_page(self):
        self._manual_load_page(self._manual_page_num - 1)

    def _manual_next_page(self):
        self._manual_load_page(self._manual_page_num + 1)

    # ── Tab: About This App ──────────────────────────────────────────────────

    def _build_about_app(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('About This App'))
        layout.addWidget(self._p(
            'What each tab in TCU++ is for, what it can do, and when you\'d '
            'actually reach for it. One inner tab per top-level tab in the app.'))

        inner_tabs = QTabWidget()
        inner_tabs.tabBar().setExpanding(False)
        for name, builder in [
            ('MONITOR',        self._about_monitor),
            ('AMAT0 TEST',     self._about_amat0_test),
            ('2KW PULSE TEST', self._about_2kw_pulse_test),
            ('HEATER',         self._about_heater),
            ('SETTINGS',       self._about_settings),
        ]:
            inner_tabs.addTab(builder(), name)
        layout.addWidget(inner_tabs)

        return w

    def _about_tab_page(self, one_liner, features, use_cases):
        """Shared layout for one inner About-This-App page: a one-line
        summary, a full feature table, and a use-cases table. features and
        use_cases are each a list of (name, description) pairs."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._p(one_liner))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('What it can do'))
        layout.addWidget(self._table(['Feature', 'Description'], features, [4, 6]))

        layout.addWidget(self._h2('When to use it'))
        layout.addWidget(self._table(['Situation', 'Why this tab helps'], use_cases, [4, 6]))

        layout.addStretch()
        return self._scroll(w)

    def _about_monitor(self):
        return self._about_tab_page(
            one_liner='The at-a-glance home base for the TCU\'s live state, and the '
                      'place to send direct hardware commands outside of a formal test.',
            features=[
                ['Live readings', 'Inlet temperature, flow rate, and setpoint, updated every second'],
                ['Rolling graph', 'Temperature and flow plotted over the last polling window, updated every second'],
                ['PRECOND button', 'Raise TCU internal tank temperature to setpoint, without a full fill cycle'],
                ['START / STOP', 'Direct TCU temperature-control start/stop, independent of any test'],
                ['FILL / Clear Alarm / Close Valve / Set Setpoint', 'Direct, single-command access to the rest of the TCU\'s control surface'],
                ['Command log', 'Every RS232 command sent and the TCU\'s reply, tap to pop out + Export to .txt'],
                ['Alarm history', 'Every alarm condition the TCU has reported this session, tap to pop out + Export to .txt'],
                ['Flow/Temp toggle', 'Switch the live graph between the two signals without leaving the tab'],
            ],
            use_cases=[
                ['Confirming the TCU is alive and responding before starting any test', 'Live readings + command log give an immediate health check, no test needs to be running'],
                ['TCU was just powered on or just finished a fill', 'PRECOND brings the tank to setpoint quickly, without re-running a full AFV fill'],
                ['Diagnosing an intermittent comms or alarm issue', 'Command log and alarm history are both exportable, so a problem pattern can be shared or reviewed offline'],
                ['Manually recovering from an alarm or unexpected state', 'Clear Alarm / Close Valve / direct Stop give a way to intervene without starting a new test'],
            ],
        )

    def _about_amat0_test(self):
        return self._about_tab_page(
            one_liner='Burst-and-decay pass/fail test for a repaired TCU, scored against '
                      'a growing reference dataset of known-good units. Two sub-tabs: '
                      'Main (the actual test) and Reference (builds the comparison data).',
            features=[
                ['Gated Start (Main)', 'Start is locked until the reference dataset has enough runs to score against meaningfully'],
                ['TCU serial number entry', 'Ties each test result to the specific physical unit tested'],
                ['Fixed-duration logging', 'Configurable test length in Settings, so every run is directly comparable'],
                ['Temp + flow dual-axis graph', 'Watch both signals at once during a run'],
                ['Transient start/end markers', 'Shows exactly where the algorithm placed the transient window, on every run'],
                ['Four-condition pass/fail', 'Time, temp-shape, flow-shape, and endurance all checked independently against the reference dataset'],
                ['Auto-filing', 'Every scored run automatically grows the pass/fail dataset — no manual step'],
                ['Run history dropdown (Main)', 'Pull up any of the last 100 runs\' graphs for comparison'],
                ['5-point statistical summary (Main)', 'Quick sense of the reference dataset\'s spread without exporting data'],
                ['Simplified test flow (Reference)', 'Build the reference dataset from known-good units, no scoring overhead'],
                ['Dataset table + delete + CSV import (Reference)', 'View, prune, or backfill the reference dataset directly'],
            ],
            use_cases=[
                ['A TCU has just been repaired and needs sign-off', 'Main sub-tab gives an objective, repeatable pass/fail verdict instead of an operator judgment call'],
                ['The reference dataset is too small or new to trust yet', 'Reference sub-tab is exactly for this — run known-good units through it with no scoring pressure'],
                ['A result looks surprising and you want to sanity-check it', 'The run history dropdown plus the 5-point summary let you compare this run against the dataset directly, in-app'],
                ['You already have CSV logs from past good units', 'Reference sub-tab\'s Import lets you backfill the dataset without re-running physical tests'],
            ],
        )

    def _about_2kw_pulse_test(self):
        return self._about_tab_page(
            one_liner='Tests the TCU\'s 2kW heater through a user-defined sequence of '
                      'instant load changes, scoring each stage\'s settle time against '
                      'a dataset binned by watts.',
            features=[
                ['Sequence editor', 'Define an exact, repeatable pattern of watt values to step through'],
                ['Random sequence generator', 'Generate a varied test sequence quickly, ranges configurable in Settings'],
                ['Per-stage settle-time scoring', 'Each individual load step is checked against history for that specific wattage, not just the sequence as a whole'],
                ['Automatic trailing 0W stage', 'Every sequence ends with a cool-down stage automatically, not something you have to remember to add'],
                ['Searchable run history (Ctrl+F)', 'Find and re-load a past sequence quickly instead of scrolling a long list'],
            ],
            use_cases=[
                ['Testing the heater\'s actual duty-cycle responsiveness', 'A custom sequence can mirror the real photo-tool load pattern, not just a single step'],
                ['Quickly generating varied coverage for a broader test pass', 'Random sequence generation avoids hand-typing dozens of watt values'],
                ['Investigating a slow-settling load level specifically', 'Per-stage scoring (binned by watts) isolates whether the problem is at one wattage or systemic'],
                ['Repeating a sequence used on a previous unit for direct comparison', 'Search the run history (Ctrl+F) and reload it instead of re-typing it'],
            ],
        )

    def _about_heater(self):
        return self._about_tab_page(
            one_liner='Direct, manual control of the heater\'s power level, outside of '
                      'any formal test — for setup, calibration checks, or troubleshooting.',
            features=[
                ['Manual watts entry', 'Drive the heater to a specific power level directly'],
                ['Live setpoint/actual readout', 'Confirm the heater is actually responding to commands'],
                ['Modbus response log', 'Diagnose heater communication issues independent of the TCU/PLC link'],
            ],
            use_cases=[
                ['Confirming the heater itself responds before relying on it in a test', 'Manual entry plus the live readout gives a direct, isolated check'],
                ['Calibration or commissioning work on a new or repaired heater', 'Set specific watt levels and observe the actual response directly'],
                ['Suspecting a heater comms problem rather than a TCU problem', 'The Modbus log isolates heater communication from the rest of the system'],
            ],
        )

    def _about_settings(self):
        return self._about_tab_page(
            one_liner='Configuration for serial ports, test pass/fail parameters, '
                      'and display preferences — everything the operator might need '
                      'to tune without editing files directly.',
            features=[
                ['Serial port configuration', 'TCU/PZEM/PLC port and baud settings, under Advanced (password-gated)'],
                ['Post-repair test parameters', 'Pass/fail thresholds and timing for both the AMAT0 and 2kW Pulse tests'],
                ['Theme (light/dark)', 'Match the display to the workshop\'s lighting conditions'],
                ['Language (English/Chinese)', 'Support operators more comfortable in either language'],
                ['Scrollable sub-tabs', 'Post-repair test and Advanced sub-tabs scroll on shorter screens instead of clipping content'],
            ],
            use_cases=[
                ['A serial port changed (e.g. after re-cabling or a new adapter)', 'Update the port directly in Settings rather than editing config files on the device'],
                ['Tightening or loosening a test\'s pass/fail strictness', 'AMAT0 and 2kW Pulse Test parameters are both adjustable here as the process matures'],
                ['Switching operators between English and Chinese', 'Language toggle applies across the whole app immediately'],
                ['Working in a brightly lit or darkened workshop area', 'Theme toggle adjusts the whole app\'s display for visibility'],
            ],
        )

    def _build_system_overview(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('System Overview'))
        layout.addWidget(self._p(
            'What changed in the system architecture during the AMAT0 pivot, '
            'what the current setup actually is, and why the original 2kW '
            'heater circuit is still worth documenting even though the AMAT0 '
            'Stress Test no longer uses it directly.'))

        diagram_path = os.path.join(DOCS_ASSETS_DIR, 'System_Overview.png')
        diagram_pixmap = QPixmap(diagram_path)
        diagram_lbl = QLabel()
        diagram_lbl.setAlignment(Qt.AlignCenter)
        if diagram_pixmap.isNull():
            diagram_lbl.setText(f'Could not load {diagram_path}')
        else:
            diagram_lbl.setPixmap(
                diagram_pixmap.scaledToWidth(int(900 * self._scale), Qt.SmoothTransformation))
        layout.addWidget(diagram_lbl)
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('What changed from the original diagram'))
        layout.addWidget(self._p(
            'A new :AMAT0 block was added, separate from the existing :Heater '
            'block — two distinct pieces of hardware, not a relabel. The '
            'original :Heater (the 2kW resistive heater driven by the W5SP/'
            'W5SZ Power Regulator, fed by NFB/MC, controlled via the PLC\'s '
            'DC I/O current loop) is still physically present and wired '
            'exactly as before. AMAT0 is a separate pre-heated tank, heated '
            'externally by its own dedicated 2kW heater before each test run, '
            'then disconnected from that heater and connected to the TCU\'s '
            'water circuit for the burst-and-decay test itself. AMAT0 is not '
            'part of the W5/NFB/MC control chain at all.'))
        layout.addWidget(self._p(
            'The Power Meter\'s connection was corrected to match reality: it '
            'connects via direct RPi GPIO UART, with no USB or RS485 adapter '
            'in the path. An earlier diagram showed an RS485-to-USB adapter '
            '(a cp2102) routing the Power Meter through a USB-A port — that '
            'adapter is real hardware, but it\'s currently disconnected: the '
            'PZEM\'s CT resistor overheated during a previous installation '
            'attempt, and the cp2102 link was never reconnected afterward.'))

        layout.addWidget(self._h2('Current setup, in short'))
        layout.addWidget(self._p(
            'The TCU\'s own water circuit and 2kW heater remain wired exactly '
            'as before this pivot — nothing about that physical circuit was '
            'touched. What changed is purely the test methodology: the app no '
            'longer runs a sustained heat-load test against that heater, '
            'because sustained heat load on the TCU could no longer be '
            'guaranteed in the test rig. The AMAT0 tank — heated separately, '
            'then connected only for the duration of a burst-and-decay '
            'measurement — is now the primary test fixture.'))

        layout.addWidget(self._h2('The 2kW heater can still be used — it just needs repiping'))
        layout.addWidget(self._p(
            'AMAT0 and the 2kW heater\'s circuit both connect to the same '
            'point on the TCU\'s water loop, so only one can be connected at '
            'a time. Using the 2kW heater again means physically disconnecting '
            'AMAT0 and re-plumbing the water lines back — there\'s no software '
            'switch for this, it\'s a manual piping change on the rig itself.'))
        layout.addWidget(self._p(
            'This matters beyond just restoring the old test: the 2kW heater, '
            'the W5SP/W5SZ phase-angle power regulator, and the PLC\'s '
            'continuous 0–4000 K-value control loop over MEWTOCOL are a '
            'general-purpose heat-load simulation capability, not specific to '
            'this project. The same control chain — RPi writes a K value to '
            'PLC DT100 over MEWTOCOL, the PLC drives the W5 via its FP0-A21 '
            'analogue output, the W5 phase-fires the heater — could drive a '
            '2kW resistive load for a different heat-load simulation project '
            'entirely, with no PLC program changes. Because of that, keeping '
            'the PLC/wiring documentation (see the WIRING and PLC tabs) '
            'accurate is worth doing even while day-to-day testing has moved '
            'to AMAT0.'))

        layout.addWidget(self._h2('Outstanding project items'))
        layout.addWidget(self._table(
            ['Item', 'Status'],
            [
                ['PZEM-004T power meter', 'Non-functional (CT resistor overheated) — needs replacement'],
                ['SD card approval', 'Pending — from Ronald'],
                ['TCU↔PLC serial link', 'High failure rate — signal integrity issue diagnosed, fix (self-powered USB-RS232 adapter) not yet installed'],
                ['15.6" touchscreen', 'Needs mounting on control panel'],
                ['Inline PT100 sensor', 'Needs installation near TCU inlet pipe'],
            ],
            [3, 7]
        ))

        layout.addStretch()
        return self._scroll(w)

    def _build_wiring_guide(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('Wiring'))
        layout.addWidget(self._p(
            'Every connection into and out of the RPi4: the TCU controller, the PLC, '
            'the Power Meter, the RTC, and the Touchscreen. See SYSTEM OVERVIEW for the '
            'full block diagram this page is describing in detail.'))
        layout.addWidget(self._divider())

        # ── RPi connections summary ──────────────────────────────────────
        layout.addWidget(self._h2('What connects to the RPi, and how'))
        layout.addWidget(self._table(
            ['Peripheral', 'Physical link', 'Adapter / interface used'],
            [
                ['TCU Controller', 'USB-A port', 'FTDI DT5011 — RS232-to-USB'],
                ['PLC', 'UART pins (GPIO 14/15)', 'MAX3232 — TTL-to-RS232 level shifter'],
                ['Power Meter (PZEM-004T)', 'GPIO UART (/dev/ttyAMA0)', 'Direct — no adapter (see Power Meter section)'],
                ['RTC', 'I2C pins (GPIO 2/3)', 'Direct — standard I2C module'],
                ['Touchscreen — touch input', 'USB-A port', 'Direct — touchscreen relays touch input to RPi over USB'],
                ['Touchscreen — display', 'HDMI (not RPi GPIO/USB)', 'Standard HDMI video, separate from the USB touch link'],
            ],
            [3, 3, 4]
        ))
        layout.addWidget(self._note(
            'cp2102 (RS485-to-USB) is present on the board but currently disconnected — '
            'it was wired to the Power Meter for an RS485 link that\'s no longer in use '
            'since the PZEM\'s CT resistor overheated. See SYSTEM OVERVIEW for the full story.',
            AMBER))

        # ── TCU Controller via FTDI DT5011 ──────────────────────────────
        layout.addWidget(self._h2('TCU Controller — FTDI DT5011 (RS232-to-USB)'))
        layout.addWidget(self._p(
            'The TCU Controller\'s DB9 RS232 port connects to an FTDI DT5011 adapter, '
            'which presents to the RPi as a standard USB serial device.'))
        layout.addWidget(self._table(
            ['From', 'To', 'Notes'],
            [
                ['TCU Controller DB9 port', 'FTDI DT5011 RS232 side', 'Standard DB9 RS232, full handshake not required'],
                ['FTDI DT5011 USB side', 'RPi USB-A port', 'Enumerates as /dev/ttyUSB0 (or similar) on Linux'],
            ],
            [4, 4, 2]
        ))
        layout.addWidget(self._note(
            'See the MEWTOCOL Debugging page for the signal integrity issue found on '
            'this link and its planned fix (a self-powered USB-RS232 adapter).'))

        # ── PLC via MAX3232 ───────────────────────────────────────────────
        layout.addWidget(self._h2('PLC — MAX3232 (TTL-to-RS232)'))
        layout.addWidget(self._p(
            'The RPi\'s UART pins are 3.3V TTL logic — the PLC\'s RS232C port expects '
            '±12V RS232 signal levels, so a MAX3232 level shifter sits between them.'))
        layout.addWidget(self._table(
            ['From', 'To', 'Notes'],
            [
                ['RPi UART TX (GPIO 14, Pin 8)', 'MAX3232 TTL-in', 'RPi → PLC direction'],
                ['RPi UART RX (GPIO 15, Pin 10)', 'MAX3232 TTL-out', 'PLC → RPi direction'],
                ['MAX3232 RS232-out', 'PLC RS232C port', 'MEWTOCOL serial link'],
            ],
            [4, 4, 2]
        ))
        layout.addWidget(self._note(
            'RPi UART pins are shared between this link and any other UART use on the '
            'board — confirm /dev/ttyAMA0 is reserved for the PZEM (GPIO UART) and this '
            'PLC link uses the correct, separate UART if the board has more than one.',
            AMBER))

        # ── RTC ───────────────────────────────────────────────────────────
        layout.addWidget(self._h2('Real-Time Clock (RTC) — I2C'))
        layout.addWidget(self._p(
            'Standard I2C RTC module, keeping correct time across power cycles on a '
            'headless RPi with no internet/NTP access.'))
        layout.addWidget(self._table(
            ['RTC Pin', 'RPi Pin', 'GPIO', 'Description'],
            [
                ['VCC', 'Pin 1', '3.3V', 'RTC power supply'],
                ['SDA', 'Pin 3', 'GPIO 2 (I2C SDA)', 'I2C data line'],
                ['SCL', 'Pin 5', 'GPIO 3 (I2C SCL)', 'I2C clock line'],
                ['GND', 'Pin 9', 'GND', 'Common ground'],
            ],
            [2, 2, 4, 4]
        ))
        layout.addWidget(self._note(
            'The app does not currently read the RTC in software — daq_thread.py\'s '
            'Sample.timestamp comes from the RPi\'s own system clock (time.time()), not '
            'this module. The RTC is wired and available for future use but not yet '
            'integrated into the app.', AMBER))

        # ── Touchscreen ───────────────────────────────────────────────────
        layout.addWidget(self._h2('Touchscreen'))
        layout.addWidget(self._p(
            'The display itself connects via HDMI (standard video, not covered here — '
            'see the monitor/cable that came with the touchscreen). Touch input is the '
            'only part that goes through the RPi\'s USB/GPIO side: the touchscreen\'s '
            'touch controller relays touch input to the RPi over a USB-A connection, '
            'the same as a USB mouse would.'))
        layout.addWidget(self._table(
            ['Function', 'Connection'],
            [
                ['Display (video)', 'HDMI — separate cable, not USB/GPIO'],
                ['Touch input', 'USB-A port — touch events relayed to RPi over USB'],
            ],
            [3, 7]
        ))

        layout.addWidget(self._divider())

        # ── Power Meter (existing PZEM content, preserved as its own section) ──
        layout.addWidget(self._h2('Power Meter — PZEM-004T v3.0'))
        layout.addWidget(self._p(
            'The PZEM-004T measures true watts delivered to the heater. '
            'Connected to RPi via GPIO UART — no USB port used.'))

        layout.addWidget(self._h2('RPi GPIO Wiring (Power Meter)'))
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
        layout.addWidget(self._note(
            'CT resistor overheated during a previous installation — this link is '
            'currently non-functional pending a replacement power meter. '
            'See SYSTEM OVERVIEW for status.', RED))

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

    def _build_plc_guide(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('PLC'))
        layout.addWidget(self._p(
            'The control unit running this project\'s heater-control logic, and the '
            'general-purpose chain (RPi → PLC → W5) that could drive a different '
            'heat-load simulation project\'s heater too — see SYSTEM OVERVIEW for why '
            'that matters.'))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('Model'))
        layout.addWidget(self._table(
            ['Item', 'Value'],
            [
                ['Control unit', 'Panasonic FP0-C14CRS'],
                ['I/O expansion unit', 'Panasonic FP0-A21'],
                ['HMI panel', 'GT02 (physically present, old ladder logic relays no longer used)'],
            ],
            [3, 7]
        ))
        layout.addWidget(self._note(
            'See PLC LADDER LOGIC ANALYSIS for the original 1325-step program this '
            'control unit shipped with — it is now retired and cannot be recompiled or '
            'reflashed (FPWIN Pro 7 strips compiler-reserved registers on recompile, '
            'and referencing them at runtime causes error 40).', AMBER))

        layout.addWidget(self._h2('MEWTOCOL Serial Interface'))
        layout.addWidget(self._p(
            'The RPi communicates with the PLC over MEWTOCOL-COM, a Panasonic-proprietary '
            'ASCII protocol, via the PLC\'s built-in COM port (RS232 levels).'))
        layout.addWidget(self._table(
            ['Parameter', 'Value'],
            [
                ['Protocol', 'MEWTOCOL-COM'],
                ['Baud rate', '9600'],
                ['Parity', 'ODD'],
                ['Port', 'PLC COM port (S/R/G terminals)'],
                ['Level shifting', 'MAX3232 (RS232↔TTL) between PLC COM and RPi UART — see WIRING'],
            ],
            [3, 7]
        ))
        layout.addWidget(self._p(
            'The RPi writes a K value (0–4000) to PLC register DT100 every time the '
            'commanded heat load changes, and reads it back for diagnostics. The PLC '
            'program passes DT100 straight through to the FP0-A21 analogue output as '
            '0–20mA, driving the W5 SCR\'s 4–20mA control input.'))
        layout.addWidget(self._note(
            'See MEWTOCOL DEBUGGING for a signal integrity issue found on this link '
            '(the MAX3232\'s RS232 receiver loading the PLC\'s transmitter down when '
            'powered from the RPi\'s 3.3V rail) and its planned fix.'))

        layout.addWidget(self._h2('I/O Expansion Unit — FP0-A21'))
        layout.addWidget(self._p(
            'Adds 2 analogue input channels and 1 analogue output channel to the base '
            'FP0-C14CRS control unit. This project only uses the analogue output '
            'channel (driving the W5); the 2 input channels are unused.'))
        layout.addWidget(self._table(
            ['Item', 'Value'],
            [
                ['Output channels', '1'],
                ['Output current range', '0 to 20 mA'],
                ['Output voltage range (alternate mode, unused here)', '−10 to +10 V'],
                ['Output resolution', '1/4000'],
                ['Input channels (unused in this project)', '2'],
                ['Input current range', '0 to 20 mA'],
                ['Rated operating voltage', '24VDC (21.6–26.4VDC range)'],
                ['Rated current consumption', '100mA or less'],
            ],
            [5, 5]
        ))
        layout.addWidget(self._note(
            'Source: Panasonic FP0 Analogue Units datasheet. Output mode (voltage vs '
            'current) is set by a physical mode switch on the module — confirm it\'s '
            'set to current (0–20mA) before assuming DT100 writes translate correctly; '
            'a voltage-mode module driving a current-mode W5 input would silently '
            'produce nonsense readings rather than an obvious error.', AMBER))

        layout.addStretch()
        return self._scroll(w)

    def _build_feature_list(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._h1('Feature List'))
        layout.addWidget(self._p(
            'Every feature currently supported by the app, grouped by tab, with what '
            'it\'s actually for.'))
        layout.addWidget(self._divider())

        layout.addWidget(self._h2('Monitor'))
        layout.addWidget(self._table(
            ['Feature', 'Use case'],
            [
                ['Live readings (temp, flow, status)', 'At-a-glance TCU health check before/during any test'],
                ['Rolling graph, updated every second', 'Spot trends or instability the live numbers alone would miss'],
                ['PRECOND button', 'Bring TCU internal tank up to setpoint before starting a test, without a full fill cycle'],
                ['START / STOP / Clear Alarm / Close Valve', 'Direct TCU command access for setup, troubleshooting, or manual operation outside a formal test'],
                ['Command log', 'Audit trail of every RS232 command sent and the TCU\'s response, for diagnosing comms issues'],
                ['Alarm history', 'Record of every alarm condition seen, for troubleshooting intermittent faults'],
            ],
            [4, 6]
        ))

        layout.addWidget(self._h2('AMAT0 Test — Main'))
        layout.addWidget(self._table(
            ['Feature', 'Use case'],
            [
                ['Gated Start (min. reference dataset size)', 'Prevents running a real pass/fail test before there\'s enough reference data to score against meaningfully'],
                ['TCU serial number entry', 'Ties each test result to the specific physical unit tested, for traceability'],
                ['Fixed-duration logging', 'Standardised test length, configurable in Settings, so every run is directly comparable'],
                ['Temp + flow dual-axis live graph', 'Watch both signals at once during a run without switching views'],
                ['Transient start/end markers', 'Visually confirms exactly where the detection algorithm placed the transient window, on every run'],
                ['Four-condition pass/fail (time, temp-shape, flow-shape, endurance)', 'Objective, automatic verdict on whether a repaired unit matches known-good behaviour'],
                ['Auto-filing into pass/fail dataset', 'Every scored run grows the dataset automatically — no manual step to keep the reference data current'],
                ['Run history dropdown', 'Pull up any of the last 100 runs\' graphs for comparison or review, without leaving the tab'],
                ['5-point statistical summary', 'Quick sense of the reference dataset\'s spread (min/Q1/median/Q3/max transient duration) without exporting data'],
            ],
            [4, 6]
        ))

        layout.addWidget(self._h2('AMAT0 Test — Reference'))
        layout.addWidget(self._table(
            ['Feature', 'Use case'],
            [
                ['Simplified always-passes test flow', 'Build the reference dataset from known-good units without the Main tab\'s scoring overhead'],
                ['Dataset progress counter (X / minimum)', 'Shows exactly how much more reference data is needed before the Main test unlocks'],
                ['Dataset table (view all runs)', 'See every pass/fail run on record, with serial, duration, and verdict at a glance'],
                ['Delete run', 'Remove a bad or mistaken entry from the dataset without editing files by hand'],
                ['Import from CSV', 'Bring in a previously-collected run log (matching the app\'s own CSV schema) as reference data'],
                ['View selected run\'s graph', 'Visually inspect any dataset entry\'s temp/flow curve before trusting it as a reference'],
            ],
            [4, 6]
        ))

        layout.addWidget(self._h2('2kW Pulse Test'))
        layout.addWidget(self._p(
            'See TEST PROCEDURE and the wiki\'s 2kW Sequence Test page for the full '
            'methodology — summarised here as features.'))
        layout.addWidget(self._table(
            ['Feature', 'Use case'],
            [
                ['User-defined load sequence', 'Test a specific, repeatable pattern of instant heat-load switches relevant to the actual photo-tool duty cycle'],
                ['Random sequence generator', 'Quickly generate varied test sequences without manually typing out watt values'],
                ['Per-stage settle-time scoring', 'Checks each individual load step\'s settle behaviour against a dataset binned by watts, not just the sequence as a whole'],
                ['Searchable run history', 'Find and re-load a previous sequence quickly via Ctrl+F, instead of scrolling a long list'],
            ],
            [4, 6]
        ))

        layout.addWidget(self._h2('Heater'))
        layout.addWidget(self._table(
            ['Feature', 'Use case'],
            [
                ['Manual watts entry', 'Drive the heater to a specific power level directly, outside any formal test — for setup, calibration checks, or troubleshooting'],
                ['Live setpoint/actual readout', 'Confirm the heater is actually responding to commands before relying on it in a test'],
                ['Modbus response log', 'Diagnose heater communication issues independent of the TCU/PLC link'],
            ],
            [4, 6]
        ))

        layout.addWidget(self._h2('Settings'))
        layout.addWidget(self._table(
            ['Feature', 'Use case'],
            [
                ['Serial port configuration', 'Adjust TCU/PZEM/PLC port and baud settings without editing config files directly'],
                ['Post-repair test parameters', 'Tune pass/fail thresholds and timing for both the AMAT0 and 2kW Pulse tests as the process matures'],
                ['Theme (light/dark)', 'Match the display to the workshop\'s lighting conditions'],
                ['Language (English/Chinese)', 'Support operators more comfortable in either language'],
            ],
            [4, 6]
        ))

        layout.addWidget(self._h2('Documentation'))
        layout.addWidget(self._p(
            'This tab itself — built-in reference material (this page, the wiring '
            'diagrams, the RS232 command reference, the scanned manual, and more) so '
            'operators don\'t need a separate device or printout on the workshop floor.'))

        layout.addStretch()
        return self._scroll(w)

    # ── Tab 6: Alarm Response Guide ───────────────────────────────────────────

    def _build_alarm_guide(self):
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
                ['(A) Temp exceeded 27°C upper limit', 'Cooling failure or heat load too high', 'Press Precond and wait for temperature to return to 22°C (Refer to TCU Haake manual pg35 — temperature cannot exceed 27.5°C for safety)'],
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
