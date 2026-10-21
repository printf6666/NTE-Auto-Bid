# -*- coding: utf-8 -*-
"""界面主题：配色、QSS 样式表、线性图标"""

from PyQt5.QtCore import QByteArray, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtSvg import QSvgRenderer

# ---------- 配色 ----------
class _Color(str):
    """十六进制色串；既能拼进 QSS，也能直接用 str(...) 转成 QColor"""

    def __eq__(self, other):
        return str.__eq__(self, other)

    def __hash__(self):
        return str.__hash__(self)


COLORS = {
    "bg": _Color("#ffffff"),
    "panel": _Color("#ffffff"),
    "panel_alt": _Color("#f7f8f9"),
    "border": _Color("#ebedf0"),
    "border_strong": _Color("#e2e5e9"),
    "hover": _Color("#f2f4f6"),
    "text": _Color("#26292e"),
    "text_strong": _Color("#121417"),
    "text_muted": _Color("#7d838c"),
    "text_faint": _Color("#b8bdc4"),
    "green": _Color("#00a870"),
    "green_dark": _Color("#008f60"),
    "green_light": _Color("#e8f7f1"),
}

FONT_FAMILY = "Microsoft YaHei UI, Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"

QSS = f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: 17px;
    color: {COLORS['text']};
}}
QWidget#Root {{
    background: {COLORS['bg']};
}}
QLabel[role="title"] {{
    color: {COLORS['text_strong']};
    font-size: 18px;
    font-weight: 600;
}}
QLabel[role="caption"] {{
    color: {COLORS['text_muted']};
    font-size: 16px;
}}
QLabel[role="faint"] {{
    color: {COLORS['text_faint']};
    font-size: 16px;
}}

/* ---------- 标签页 ---------- */
QTabWidget::pane {{ border: none; background: {COLORS['bg']}; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: {COLORS['text_muted']};
    padding: 0 2px;
    margin-right: 8px;
    min-width: 108px;
    min-height: 40px;
    font-size: 17px;
}}
QTabBar::tab:selected {{
    color: {COLORS['green']};
    border-bottom: 2px solid {COLORS['green']};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ color: {COLORS['text']}; }}
QTabBar::close-button {{
    image: none;
    subcontrol-position: right;
}}

/* ---------- 卡片 / 框体 ---------- */
QFrame#Card {{
    background: {COLORS['panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
}}
QFrame#CardBody {{
    background: transparent;
    border: none;
}}
QFrame#DropZone {{
    background: {COLORS['panel_alt']};
    border: 1px dashed {COLORS['border_strong']};
    border-radius: 8px;
}}
QFrame#LogPanel {{
    background: {COLORS['panel_alt']};
    border: none;
    border-radius: 10px;
}}
QLabel#EmptyLog {{
    color: {COLORS['text_faint']};
    font-size: 17px;
    background: transparent;
}}
QTextBrowser#Log {{
    background: transparent;
    border: none;
    padding: 10px 12px;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {COLORS['panel']};
    border: 1px solid {COLORS['border_strong']};
    border-radius: 6px;
    padding: 5px 14px;
    min-height: 26px;
    color: {COLORS['text']};
}}
QPushButton:hover {{ background: {COLORS['hover']}; }}
QPushButton:pressed {{ background: {COLORS['border']}; }}
QPushButton:disabled {{ color: {COLORS['text_faint']}; border-color: {COLORS['border']}; }}

QPushButton#Primary {{
    background: {COLORS['green']};
    border: 1px solid {COLORS['green']};
    border-radius: 9px;
    color: #ffffff;
    font-size: 19px;
    font-weight: 600;
    padding: 0 38px;
    min-height: 48px;
}}
QPushButton#Primary:hover {{ background: {COLORS['green_dark']}; border-color: {COLORS['green_dark']}; }}
QPushButton#Primary:pressed {{ background: #007d54; border-color: #007d54; }}
QPushButton#Primary[variant="danger"] {{
    background: #ffffff; color: #e34d59; border: 1px solid #f2c4c7;
}}
QPushButton#Primary[variant="danger"]:hover {{ background: #fdf2f2; }}

QPushButton#IconButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 0;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
}}
QPushButton#IconButton:hover {{ background: {COLORS['hover']}; }}
QPushButton#IconButton:checked {{ background: {COLORS['green_light']}; }}

QPushButton#Chip {{
    background: {COLORS['panel']};
    border: 1px solid {COLORS['border_strong']};
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 24px;
    font-size: 16px;
}}
QPushButton#Chip:hover {{ background: {COLORS['hover']}; }}
QPushButton#Chip:checked {{
    background: {COLORS['green_light']};
    border-color: #b4e5d3;
    color: {COLORS['green_dark']};
    font-weight: 600;
}}
QPushButton#Subtle {{
    background: transparent;
    border: 1px solid {COLORS['border_strong']};
    color: {COLORS['text_muted']};
    border-radius: 6px;
    padding: 3px 10px;
    min-height: 22px;
    font-size: 16px;
}}
QPushButton#Subtle:hover {{ background: {COLORS['hover']}; color: {COLORS['text']}; }}

/* ---------- 输入控件 ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {COLORS['panel']};
    border: 1px solid {COLORS['border_strong']};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 24px;
    selection-background-color: #b9e8d7;
    selection-color: #0b3b2c;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLORS['green']};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: {COLORS['panel_alt']};
    color: {COLORS['text_muted']};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}

QCheckBox {{ spacing: 8px; color: {COLORS['text']}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {COLORS['border_strong']};
    border-radius: 4px;
    background: #ffffff;
}}
QCheckBox::indicator:hover {{ border-color: {COLORS['green']}; }}
QCheckBox::indicator:checked {{
    background: {COLORS['green']};
    border-color: {COLORS['green']};
    image: url(none);
}}

/* ---------- 分割条 ---------- */
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {COLORS['hover']}; }}
QFrame#Divider {{ background: {COLORS['border']}; border: none; }}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: #d8dce1; border-radius: 4px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: #c3c8cf; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: #d8dce1; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QFrame#Tile {{
    background: {COLORS['panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
}}
QFrame#Tile:hover {{ border-color: #d3e9df; background: #fcfefd; }}

QToolTip {{
    background: #ffffff;
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_strong']};
    padding: 4px 8px;
}}
"""

# ---------- 线性图标（Feather 风格，24 网格）----------
_PATHS = {
    "grid": ["M9 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z",
             "M11 7h2", "M11 11h2", "M11 15h2"],
    "play": ["M8 5.5v13l11-6.5z"],
    "player": ["M12 3v12l7-3.5z", "M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"],
    "stop": ["M6.5 6.5h11v11h-11z"],
    "step": ["M6 5l8 7-8 7z", "M17 5v14"],
    "trash": ["M4 7h16", "M10 4h4a1 1 0 0 1 1 1v2h-6V5a1 1 0 0 1 1-1z",
              "M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12", "M10 11v6", "M14 11v6"],
    "tag": ["M20.6 12.6l-8 8a2 2 0 0 1-2.8 0l-6.4-6.4a2 2 0 0 1-.6-1.4V4a1 1 0 0 1 1-1h8.8a2 2 0 0 1 1.4.6l6.6 6.6a2 2 0 0 1 0 2.8z",
            "M8 8h.01"],
    "sliders": ["M4 6h10", "M18 6h2", "M4 12h4", "M12 12h8", "M4 18h12", "M20 18h0",
                "M16 4v4", "M10 10v4", "M18 16v4"],
    "unfold": ["M8 4l4 4 4-4", "M8 20l4-4 4 4", "M12 8v8"],
    "fold": ["M8 8l4-4 4 4", "M8 16l4 4 4-4", "M12 4v16"],
    "check": ["M4 12.5l5 5L20 6.5"],
    "search": ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "M20.5 20.5l-4.2-4.2"],
    "copy": ["M9 9h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2z",
             "M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"],
    "download": ["M12 3v12", "M7 10l5 5 5-5", "M4 20h16"],
    "close": ["M6 6l12 12", "M18 6L6 18"],
    "dot": [],
    "crosshair": ["M12 3v4", "M12 17v4", "M3 12h4", "M17 12h4", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
    "calendar": ["M5 5h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
                 "M8 3v4", "M16 3v4", "M3 11h18"],
    "bubble": ["M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4V6a1 1 0 0 1 1-1z"],
    "folder": ["M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"],
    "info": ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 11v6", "M12 7.5h.01"],
    "target": ["M12 3v3", "M12 18v3", "M3 12h3", "M18 12h3",
               "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z", "M12 10.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"],
    "coin": ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M9 9.5c0-1.4 1.3-2.5 3-2.5s3 1.1 3 2.5-1.3 2-3 2.5-3 1.1-3 2.5S10.3 17 12 17s3-1.1 3-2.5", "M12 5.5v13"],
    "refresh": ["M20 12a8 8 0 1 1-2.6-5.9", "M20 4v4h-4"],
    "edit": ["M4 20h4l10-10a2.8 2.8 0 0 0-4-4L4 16z", "M13.5 6.5l4 4"],
    "shield": ["M12 3l8 3v6c0 4.5-3.3 7.8-8 9-4.7-1.2-8-4.5-8-9V6z", "M9 12l2.2 2.2L15.5 10"],
    "clock": ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 7.5V12l3 2"],
    "flag": ["M5 21V4", "M5 4h11l-1.6 3.6L16 12H5"],
}


class _Color(str):
    """十六进制色串，同时可被 Qt 当作 QColor 使用（QPainter.setPen 等）"""

    def __new__(cls, value):
        obj = super().__new__(cls, value)
        obj._color = QColor(value)
        return obj

    def __eq__(self, other):
        return str.__eq__(self, other)

    def __hash__(self):
        return str.__hash__(self)

    def __repr__(self):
        return f"QColor('{str(self)}')"


def qcolor(key):
    """取配色并转成 QColor（QPainter 需要真正的 QColor）"""
    return QColor(str(COLORS[key]))


def _svg(name, color, width=1.8):
    paths = _PATHS.get(name, [])
    body = "".join(f'<path d="{d}" fill="none"/>' for d in paths)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" '
        f'fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


def icon(name, color=None, size=16):
    """生成指定颜色的线性图标"""
    color = str(color or COLORS["text"])
    renderer = QSvgRenderer(QByteArray(_svg(name, color).encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


def avatar(text, size=36, bg="#00a870", fg="#ffffff"):
    """圆形文字头像"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(bg))
    painter.drawEllipse(0, 0, size, size)
    font = painter.font()
    font.setFamily("Microsoft YaHei UI")
    font.setPixelSize(int(size * 0.44))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QPen(QColor(fg)))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, text[:1])
    painter.end()
    return QPixmap(pixmap)


def rounded_square(color, size=10, radius=3):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    painter.drawPath(path)
    painter.end()
    return QPixmap(pixmap)
