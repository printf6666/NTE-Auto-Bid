# -*- coding: utf-8 -*-
"""可复用的小控件：卡片标题、表单行、胶囊按钮、数字输入、日历、统计块等"""
from PyQt5.QtCore import QDate, QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (QCalendarWidget, QDateEdit, QFrame, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from theme import COLORS, icon


def divider(vertical=False, color=None):
    """1px 分隔线"""
    line = QFrame()
    style = f"background:{color or COLORS['border']}; border:none;"
    if vertical:
        line.setFixedWidth(1)
    else:
        line.setFixedHeight(1)
    line.setStyleSheet(style)
    return line


def spacer():
    widget = QWidget()
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return widget


class Row(QWidget):
    """固定高度的水平行：避免 QLabel 在小面板里被拉高"""

    def __init__(self, height=22, spacing=6, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.box = QHBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(spacing)


class SectionHeader(QWidget):
    """卡片标题行：图标 + 标题 + 右侧操作区"""

    def __init__(self, title, icon_name=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        if icon_name:
            mark = QLabel()
            mark.setPixmap(icon(icon_name, COLORS["green"], 15).pixmap(15, 15))
            mark.setFixedWidth(16)
            layout.addWidget(mark)
        label = QLabel(title)
        label.setProperty("role", "title")
        layout.addWidget(label)
        self.body = layout

    def add(self, widget, stretch=0):
        self.body.addWidget(widget, stretch)
        return widget

    def stretch(self):
        self.body.addStretch(1)


class FormRow(QWidget):
    """一行：label + 控件 + 后缀 + 说明"""

    changed = pyqtSignal()

    def __init__(self, label, widget, suffix="", hint="", label_width=108, parent=None,
                 text_connect="valueChanged"):
        super().__init__(parent)
        self.widget = widget
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        text = QLabel(label)
        text.setProperty("role", "caption")
        text.setFixedWidth(label_width)
        layout.addWidget(text)
        layout.addWidget(widget)
        if suffix:
            tail = QLabel(suffix)
            tail.setProperty("role", "faint")
            layout.addWidget(tail)
        layout.addStretch(1)
        if hint:
            note = QLabel(hint)
            note.setProperty("role", "faint")
            layout.addWidget(note)
        signal = getattr(widget, text_connect, None)
        if signal is not None:
            signal.connect(lambda *_: self.changed.emit())


class Chip(QPushButton):
    """可切换的小胶囊按钮"""

    def __init__(self, text, icon_name=None, checkable=True, parent=None):
        super().__init__(text, parent)
        self.setObjectName("Chip")
        self.setCheckable(checkable)
        self.setCursor(Qt.PointingHandCursor)
        if icon_name:
            self.setIcon(icon(icon_name, COLORS["text_muted"], 14))
            self.setIconSize(QSize(14, 14))


class IconButton(QPushButton):
    """26x26 无边框图标按钮"""

    def __init__(self, icon_name, tooltip="", color=None, size=16, checkable=False, parent=None):
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setIcon(icon(icon_name, color or COLORS["text_muted"], size))
        self.setIconSize(QSize(size, size))
        self.setToolTip(tooltip)
        self.setCheckable(checkable)
        self.setCursor(Qt.PointingHandCursor)


class DateField(QDateEdit):
    """扁平日期框，点击弹出自绘风格的日历"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy 年 M 月 d 日")
        self.setDate(QDate.currentDate())
        self.setFixedHeight(34)
        self.setMinimumWidth(158)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QDateEdit {{
                background:#ffffff; border:1px solid {COLORS['border_strong']};
                border-radius:6px; padding:4px 10px; color:{COLORS['text']};
            }}
            QDateEdit:hover {{ border-color:{COLORS['green']}; }}
            QDateEdit::drop-down {{ border:none; width:22px; }}
        """)
        self.calendarWidget().setStyleSheet(f"""
            QCalendarWidget QWidget {{ background:#ffffff; color:{COLORS['text']}; }}
            QCalendarWidget QToolButton {{
                color:{COLORS['text']}; background:transparent; border:none; padding:4px 8px;
            }}
            QCalendarWidget QToolButton:hover {{ background:{COLORS['hover']}; border-radius:4px; }}
            QCalendarWidget QAbstractItemView:enabled {{
                selection-background-color:{COLORS['green']};
                selection-color:#ffffff;
                color:{COLORS['text']};
                outline:0;
            }}
            QCalendarWidget QAbstractItemView:disabled {{ color:{COLORS['text_faint']}; }}
        """)
        self.calendarWidget().setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendarWidget().setGridVisible(False)

    def value(self):
        return self.date().toPyDate()


class NumberField(QLineEdit):
    """整数输入框（配置里多是大整数，用 QLineEdit 避免 32 位溢出）"""

    valueChanged = pyqtSignal()

    def __init__(self, value=0, width=110, parent=None):
        super().__init__(parent)
        self.setFixedWidth(width)
        self.setFixedHeight(30)
        self.setAlignment(Qt.AlignRight)
        self.set_value(value)
        self.editingFinished.connect(self._normalize)

    def set_value(self, value):
        try:
            self.setText(f"{int(value):,}")
        except Exception:
            self.setText(str(value))

    def value(self, default=0):
        text = self.text().replace(",", "").replace("，", "").strip()
        try:
            return int(float(text))
        except Exception:
            return default

    def _normalize(self):
        self.set_value(self.value())
        self.valueChanged.emit()


class FloatField(QLineEdit):
    """小数输入框"""

    valueChanged = pyqtSignal()

    def __init__(self, value=0.0, width=96, parent=None):
        super().__init__(parent)
        self.setFixedWidth(width)
        self.setFixedHeight(30)
        self.setAlignment(Qt.AlignRight)
        self._last = float(value)
        self.set_value(value)
        self.editingFinished.connect(self._normalize)

    def set_value(self, value):
        self._last = float(value)
        self.setText(f"{float(value):g}")

    def value(self, default=None):
        try:
            self._last = float(self.text().strip())
        except Exception:
            if default is not None:
                self.set_value(default)
        return self._last

    def _normalize(self):
        self.set_value(self.value())
        self.valueChanged.emit()


class StatTile(QFrame):
    """统计小卡片：图标 + 标签（左） + 数值（右），适合竖向排布"""

    def __init__(self, icon_name, label, value="0", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 18, 6)
        layout.setSpacing(12)
        badge = QLabel()
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background:{COLORS['green_light']}; border-radius:9px;")
        badge.setPixmap(icon(icon_name, COLORS["green"], 19).pixmap(19, 19))
        layout.addWidget(badge)
        caption = QLabel(label)
        caption.setStyleSheet(f"color:{COLORS['text_muted']}; font-size:17px;")
        layout.addWidget(caption)
        layout.addStretch(1)
        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setStyleSheet(
            f"color:{COLORS['text_strong']}; font-size:27px; font-weight:600;")
        layout.addWidget(self.value_label)

    def set_value(self, text):
        self.value_label.setText(text)


class MetaItem(QWidget):
    """图标 + 灰字，用于卡片头部的元信息"""

    def __init__(self, icon_name, text, parent=None):
        super().__init__(parent)
        self._name = icon_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.mark = QLabel()
        self.mark.setFixedWidth(14)
        self.mark.setPixmap(icon(icon_name, COLORS["text_muted"], 14).pixmap(14, 14))
        layout.addWidget(self.mark)
        self.label = QLabel(text)
        self.label.setProperty("role", "faint")
        layout.addWidget(self.label)

    def set_text(self, text, color=None, bold=False):
        self.label.setText(text)
        style = f"color:{color or COLORS['text_muted']}; font-size:16px;"
        if bold:
            style += "font-weight:600;"
        self.label.setStyleSheet(style)


class CollectTile(QFrame):
    """收藏项：图标块 + 名称 + 说明 + 收藏按钮"""

    favoriteToggled = pyqtSignal(bool)

    def __init__(self, icon_name, title, desc, favorite=False, parent=None):
        super().__init__(parent)
        self.setObjectName("Tile")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        badge = QLabel()
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background:{COLORS['panel_alt']}; border-radius:7px;")
        badge.setPixmap(icon(icon_name, COLORS["green"], 15).pixmap(15, 15))
        layout.addWidget(badge)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        name = QLabel(title)
        name.setStyleSheet(f"color:{COLORS['text']}; font-size:16px; font-weight:600;")
        note = QLabel(desc)
        note.setProperty("role", "faint")
        texts.addWidget(name)
        texts.addWidget(note)
        layout.addLayout(texts, 1)
        self.star = IconButton("info", "收藏", size=15, checkable=True)
        self.star.setChecked(favorite)
        self.star.setVisible(False)
        layout.addWidget(self.star)
