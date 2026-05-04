# =============================================================================
# osk.py — On-screen keyboard + touch-friendly input widgets
# =============================================================================

import subprocess
from PyQt5.QtWidgets import (
    QLineEdit, QSpinBox, QDoubleSpinBox,
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt

_proc = None
_MAX_NUMPAD_DIGITS = 12   # upper bound on input length


def _show():
    global _proc
    if _proc is None or _proc.poll() is not None:
        _proc = subprocess.Popen(['onboard', '--size=1200x220'])


class NumpadDialog(QDialog):
    """
    Touch-friendly numpad for integer and float input.
    Shows 0-9 digits, decimal point (for float), backspace and OK/Cancel.
    """

    def __init__(self, title: str, current: str,
                 allow_decimal: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(320)
        self._allow_decimal = allow_decimal
        self._build_ui(title, current)

    def _build_ui(self, title: str, current: str):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        self._display = QLineEdit(current)
        self._display.setReadOnly(True)
        self._display.setAlignment(Qt.AlignRight)
        self._display.setStyleSheet(
            'font-size: 28px; padding: 6px; border: 2px solid #ccc;')
        root.addWidget(self._display)

        grid = QGridLayout()
        grid.setSpacing(8)

        buttons = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('0', 3, 0), ('⌫', 3, 2),
        ]
        if self._allow_decimal:
            buttons.append(('.', 3, 1))

        for label, row, col in buttons:
            btn = QPushButton(label)
            btn.setFixedHeight(64)
            btn.setStyleSheet('font-size: 22px;')
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _, l=label: self._on_key(l))
            grid.addWidget(btn, row, col)

        root.addLayout(grid)

        # OK / Cancel
        btn_row = QHBoxLayout()
        ok_btn = QPushButton('OK')
        ok_btn.setFixedHeight(56)
        ok_btn.setStyleSheet('font-size: 20px; background:#065f46; color:white;')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.setFixedHeight(56)
        cancel_btn.setStyleSheet('font-size: 20px;')
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

    def _on_key(self, key: str):
        current = self._display.text()
        if key == '⌫':
            self._display.setText(current[:-1] or '0')
        elif key == '.' and '.' in current:
            return   # only one decimal point allowed
        elif len(current.replace('.', '').replace('-', '')) >= _MAX_NUMPAD_DIGITS:
            return   # fixed upper bound on input length
        else:
            if current == '0' and key != '.':
                self._display.setText(key)
            else:
                self._display.setText(current + key)

    def value(self) -> str:
        return self._display.text()


def _get_int(parent, title: str, current: int,
             mn: int, mx: int) -> tuple:
    dlg = NumpadDialog(title, str(current),
                       allow_decimal=False, parent=parent)
    if dlg.exec_() == QDialog.Accepted:
        try:
            val = int(dlg.value())
            val = max(mn, min(mx, val))
            return val, True
        except ValueError:
            pass
    return current, False


def _get_double(parent, title: str, current: float,
                mn: float, mx: float, decimals: int) -> tuple:
    dlg = NumpadDialog(title, f'{current:.{decimals}f}',
                       allow_decimal=True, parent=parent)
    if dlg.exec_() == QDialog.Accepted:
        try:
            val = round(float(dlg.value()), decimals)
            val = max(mn, min(mx, val))
            return val, True
        except ValueError:
            pass
    return current, False


class OskLineEdit(QLineEdit):
    """QLineEdit that shows Onboard keyboard on tap."""

    def focusInEvent(self, event):
        _show()
        super().focusInEvent(event)

    def mousePressEvent(self, event):
        _show()
        super().mousePressEvent(event)


class OskSpinBox(QSpinBox):
    """QSpinBox that shows a numpad dialog on tap."""

    def mousePressEvent(self, event):
        val, ok = _get_int(
            self, 'Enter value', self.value(),
            self.minimum(), self.maximum()
        )
        if ok:
            self.setValue(val)

    def mouseReleaseEvent(self, event):
        pass  # consumed by mousePressEvent

    def focusInEvent(self, event):
        super().focusInEvent(event)


class OskDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that shows a numpad dialog on tap."""

    def mousePressEvent(self, event):
        val, ok = _get_double(
            self, 'Enter value', self.value(),
            self.minimum(), self.maximum(), self.decimals()
        )
        if ok:
            self.setValue(val)

    def mouseReleaseEvent(self, event):
        pass  # consumed by mousePressEvent

    def focusInEvent(self, event):
        super().focusInEvent(event)


