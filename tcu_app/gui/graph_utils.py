# =============================================================================
# graph_utils.py — Shared graph export utilities
# =============================================================================
# Provides:
#   - make_graph_panel(title) → (container_widget, plot_widget, export_btn)
#     Creates a titled panel with an export button in the top-right corner.
#   - export_graph(plot_widget, default_stem) → opens file dialog, saves PNG/SVG
# =============================================================================

import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSizePolicy
)
from PyQt5.QtCore import Qt
import pyqtgraph as pg
import pyqtgraph.exporters as pgexp

_MAX_FILTER_LEN = 2   # PNG + SVG options


def make_graph_panel(title: str, scale: float = 1.0):
    """
    Create a titled graph panel with an export button in the top-right corner.

    Returns:
        container  — QWidget to add to parent layout
        plot       — pg.PlotWidget (configure as needed)
        export_btn — QPushButton (already connected to export logic)
    """
    if not isinstance(title, str):
        title = ''

    container = QWidget()
    outer     = QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(2)

    # ── Title bar with export button ──────────────────────────────────────────
    header = QWidget()
    header.setObjectName('graph_header')
    hbox   = QHBoxLayout(header)
    hbox.setContentsMargins(8, 4, 4, 4)
    hbox.setSpacing(4)

    lbl = QLabel(title)
    lbl.setObjectName('graph_title')
    lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    container.title_label = lbl   # exposed so callers can retitle later (e.g. on language change)

    btn = QPushButton('⬇ Export')
    btn.setObjectName('btn_export')
    btn.setToolTip('Export graph as PNG or SVG')

    hbox.addWidget(lbl)
    hbox.addWidget(btn, alignment=Qt.AlignRight)

    # ── Plot widget ───────────────────────────────────────────────────────────
    plot = pg.PlotWidget()
    plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    outer.addWidget(header)
    outer.addWidget(plot)

    # Wire export button
    btn.clicked.connect(lambda: export_graph(plot, title))

    return container, plot, btn


def export_graph(plot_widget: pg.PlotWidget, default_stem: str = 'graph'):
    """
    Open file dialog and export plot_widget as PNG or SVG.
    Auto-suggests filename with timestamp.
    """
    if not isinstance(default_stem, str):
        default_stem = 'graph'

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    stem     = default_stem.lower().replace(' ', '_').replace('/', '_')
    filename = f'{stem}_{ts}'

    path, fmt = QFileDialog.getSaveFileName(
        None,
        'Export Graph',
        filename,
        'PNG Image (*.png);;SVG Vector (*.svg)'
    )

    if not path:
        return   # user cancelled

    if not isinstance(path, str) or not path:
        return

    try:
        if fmt == 'SVG Vector (*.svg)' or path.endswith('.svg'):
            if not path.endswith('.svg'):
                path += '.svg'
            exporter = pgexp.SVGExporter(plot_widget.plotItem)
        else:
            if not path.endswith('.png'):
                path += '.png'
            exporter = pgexp.ImageExporter(plot_widget.plotItem)

        exporter.export(path)
        print(f"Graph exported: {path}")
    except Exception as e:
        print(f"Export error: {e}")
