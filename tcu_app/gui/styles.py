# =============================================================================
# styles.py — Dark industrial theme for TCU Controller App
# =============================================================================
# All font sizes, paddings and minimum dimensions scale dynamically based on
# the screen resolution detected at startup via get_app_style(scale).
# Call get_app_style(scale) from main_window.py after computing scale factor.
# =============================================================================

DARK       = "#0D0D0D"
PANEL      = "#141414"
SURFACE    = "#1C1C1C"
BORDER     = "#2A2A2A"
ACCENT     = "#00B4D8"
ACCENT2    = "#0077B6"
GREEN      = "#06D6A0"
RED        = "#EF476F"
AMBER      = "#FFB703"
TEXT       = "#E8E8E8"
TEXT_DIM   = "#888888"
TEXT_BRIGHT= "#FFFFFF"


def get_app_style(scale: float = 1.0) -> str:
    """
    Generate the full application stylesheet scaled to the current display.

    scale is computed in main_window.py as:
        screen_width / 1920   (reference resolution)
    clamped between 0.65 (small laptop) and 1.0 (full HD and above).

    Typical values:
        13" 1366x768  → scale ≈ 0.71
        13" 1920x1080 → scale = 1.0  (HiDPI, already full HD)
        15.6" 1920x1080 → scale = 1.0
    """

    def px(base: int) -> str:
        """Scale a pixel value and return as CSS px string."""
        return f"{max(1, round(base * scale))}px"

    def pt(base: int) -> str:
        """Scale a font size and return as CSS px string."""
        return f"{max(8, round(base * scale))}px"

    return f"""
QMainWindow, QWidget {{
    background-color: {DARK};
    color: {TEXT};
    font-family: 'Courier New', monospace;
    font-size: {pt(13)};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {PANEL};
}}

QTabBar::tab {{
    background: {SURFACE};
    color: {TEXT_DIM};
    padding: {px(6)} {px(10)};
    border: 1px solid {BORDER};
    border-bottom: none;
    font-size: {pt(11)};
    letter-spacing: 0px;
    text-transform: uppercase;
}}

QTabBar::tab:selected {{
    background: {PANEL};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

QTabBar::tab:hover {{
    color: {TEXT};
}}

QPushButton {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: {px(8)} {px(14)};
    font-family: 'Courier New', monospace;
    font-size: {pt(11)};
    letter-spacing: {px(1)};
    text-transform: uppercase;
    min-width: {px(90)};
    min-height: {px(32)};
}}

QPushButton:hover {{
    background-color: {BORDER};
    border-color: {ACCENT};
    color: {ACCENT};
}}

QPushButton:pressed {{
    background-color: {ACCENT2};
    color: {TEXT_BRIGHT};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {SURFACE};
}}

QPushButton#btn_start {{
    background-color: #064e3b;
    border-color: {GREEN};
    color: {GREEN};
}}
QPushButton#btn_start:hover {{
    background-color: #065f46;
}}

QPushButton#btn_stop {{
    background-color: #4c0519;
    border-color: {RED};
    color: {RED};
}}
QPushButton#btn_stop:hover {{
    background-color: #881337;
}}

QPushButton#btn_fill {{
    background-color: #1e3a5f;
    border-color: {ACCENT};
    color: {ACCENT};
}}

QPushButton#btn_test_start {{
    background-color: #064e3b;
    border-color: {GREEN};
    color: {GREEN};
    font-size: {pt(13)};
    min-height: {px(42)};
    letter-spacing: {px(1)};
}}

QPushButton#btn_test_stop {{
    background-color: #4c0519;
    border-color: {RED};
    color: {RED};
    font-size: {pt(13)};
    min-height: {px(42)};
}}

QGroupBox {{
    border: 1px solid {BORDER};
    margin-top: {px(10)};
    padding: {px(6)};
    font-size: {pt(10)};
    color: {TEXT_DIM};
    letter-spacing: {px(1)};
    text-transform: uppercase;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: {px(8)};
    padding: 0 {px(4)};
    color: {TEXT_DIM};
}}

QLineEdit, QDoubleSpinBox, QSpinBox {{
    background-color: {SURFACE};
    color: {TEXT_BRIGHT};
    border: 1px solid {BORDER};
    padding: {px(5)} {px(8)};
    font-family: 'Courier New', monospace;
    font-size: {pt(12)};
}}

QLineEdit:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}

QTextEdit {{
    background-color: {SURFACE};
    color: #88cc88;
    border: 1px solid {BORDER};
    font-family: 'Courier New', monospace;
    font-size: {pt(10)};
    padding: {px(3)};
}}

QLabel#val_large {{
    font-size: {pt(30)};
    font-family: 'Courier New', monospace;
    color: {ACCENT};
    letter-spacing: {px(1)};
}}

QLabel#val_medium {{
    font-size: {pt(18)};
    font-family: 'Courier New', monospace;
    color: {TEXT_BRIGHT};
}}

QLabel#status_ok {{
    color: {GREEN};
    font-size: {pt(12)};
    letter-spacing: {px(1)};
}}

QLabel#status_warn {{
    color: {AMBER};
    font-size: {pt(12)};
    letter-spacing: {px(1)};
}}

QLabel#status_err {{
    color: {RED};
    font-size: {pt(12)};
    letter-spacing: {px(1)};
}}

QLabel#label_dim {{
    color: {TEXT_DIM};
    font-size: {pt(10)};
    letter-spacing: {px(1)};
    text-transform: uppercase;
}}

QScrollBar:vertical {{
    background: {SURFACE};
    width: {px(8)};
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: {px(20)};
}}

QProgressBar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    height: {px(8)};
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
}}
"""


# Legacy constant — kept for any direct imports elsewhere
APP_STYLE = get_app_style(1.0)
