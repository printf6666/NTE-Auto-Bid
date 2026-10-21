# -*- coding: utf-8 -*-
"""右侧日志面板：运行日志 / 搜索 / 清空 / 复制 / 导出 / 折叠"""
import os
import time

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QTextBlockFormat, QTextCursor, QTextCharFormat
from PyQt5.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget)

from theme import COLORS
from widgets import IconButton

_TAG_COLORS = {
    "估价": "#7d838c",
    "出价": "#00a870",
    "高价": "#e8730c",
    "结算": "#2b7fd4",
    "回合": "#26292e",
    "空跑": "#9a6fd0",
    "等待竞拍": "#7d838c",
    "主界面": "#7d838c",
    "启动": "#7d838c",
}
_EMPTY_HINT = "暂无日志"


class LogPanel(QFrame):
    """运行日志面板"""

    collapsed_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LogCard")
        self.setStyleSheet(
            f"QFrame#LogCard{{background:{COLORS['panel']};border:1px solid {COLORS['border']};"
            f"border-radius:10px;}}")
        self._collapsed = False
        self._records = []  # [(time, text, tag)]
        self.store = None   # log_store.LogStore，注入后每条日志同步落盘
        self._build()

    # ------------------------------------------------------------------ 构建
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 12, 10, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(2)
        self.title = QLabel("运行日志")
        self.title.setProperty("role", "title")
        header.addWidget(self.title)
        self.header_spacer = QWidget()
        self.header_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header.addWidget(self.header_spacer)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索日志")
        self.search_box.setFixedHeight(26)
        self.search_box.setFixedWidth(96)
        self.search_box.setVisible(False)
        self.search_box.textChanged.connect(self._apply_filter)
        header.addWidget(self.search_box)

        self.search_btn = IconButton("search", "搜索")
        self.search_btn.clicked.connect(self._toggle_search)
        self.clear_btn = IconButton("trash", "清空日志")
        self.clear_btn.clicked.connect(self.clear)
        self.copy_btn = IconButton("copy", "复制全部日志")
        self.copy_btn.clicked.connect(self.copy_all)
        self.export_btn = IconButton("download", "导出日志到文件")
        self.export_btn.clicked.connect(self.export)
        self.fold_btn = IconButton("unfold", "收起 / 展开面板")
        self.fold_btn.clicked.connect(lambda: self.set_collapsed(not self._collapsed))
        for button in (self.search_btn, self.clear_btn, self.copy_btn, self.export_btn):
            header.addWidget(button)
        outer.addLayout(header)

        self.body = QFrame()
        self.body.setObjectName("LogPanel")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        self.view = QTextBrowser(self.body)
        self.view.setObjectName("Log")
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setOpenExternalLinks(False)
        self.view.setStyleSheet(
            f"QTextBrowser#Log{{background:transparent;border:none;padding:10px 12px;"
            f"color:{COLORS['text']};font-size:16px;}}")
        body_layout.addWidget(self.view, 1)

        self.empty = QLabel(_EMPTY_HINT, self.body)
        self.empty.setObjectName("EmptyLog")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        body_layout.addWidget(self.empty)
        outer.addWidget(self.body, 1)

        self._toggle_empty(True)

    # ------------------------------------------------------------------ 折叠
    def set_collapsed(self, collapsed):
        self._collapsed = collapsed
        self.title.setVisible(not collapsed)
        self.body.setVisible(not collapsed)
        self.search_box.setVisible(False if collapsed else self.search_box.isVisible())
        for button in (self.search_btn, self.clear_btn, self.copy_btn, self.export_btn):
            button.setVisible(not collapsed)
        self.fold_btn.setIcon(self._fold_icon())
        self.fold_btn.setVisible(True)
        self.header_spacer.setVisible(not collapsed)
        # 折叠态：面板自身收紧宽度，只保留折叠按钮
        self.setMinimumWidth(52 if collapsed else 280)
        if collapsed:
            self.setMaximumWidth(52)
        else:
            self.setMaximumWidth(16777215)
        self.collapsed_changed.emit(collapsed)

    def _fold_icon(self):
        from theme import icon
        return icon("fold" if not self._collapsed else "unfold", COLORS["text_muted"], 16)

    def is_collapsed(self):
        return self._collapsed

    # ------------------------------------------------------------------ 日志
    def _toggle_empty(self, is_empty):
        self.empty.setVisible(is_empty and not self._collapsed)
        self.view.setVisible(not is_empty)

    def append(self, timestamp, text):
        tag = ""
        if text.startswith("[") and "]" in text:
            tag = text[1:text.index("]")]
        if self.store is not None:
            self.store.append(timestamp, text)
        self._records.append((timestamp, text, tag))
        if len(self._records) > 5000:
            self._records = self._records[-3000:]
            self._render()
            return
        self._toggle_empty(False)
        keyword = self.search_box.text().strip()
        if not keyword or keyword in text:
            self._insert(timestamp, text, tag)

    def restore(self, records):
        """启动时回填历史日志（只渲染，不再落盘，避免重复写入）"""
        if not records:
            return
        for timestamp, text in records:
            tag = ""
            if text.startswith("[") and "]" in text:
                tag = text[1:text.index("]")]
            self._records.append((timestamp, text, tag))
        if len(self._records) > 5000:
            self._records = self._records[-5000:]
        self._toggle_empty(False)
        self._render()

    def _insert(self, timestamp, text, tag):
        cursor = self.view.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.view.document().isEmpty():
            block = QTextBlockFormat()
            block.setTopMargin(3)
            block.setBottomMargin(3)
            cursor.insertBlock(block)
            cursor.setBlockFormat(block)

        time_format = QTextCharFormat()
        time_format.setForeground(QColor(COLORS["text_faint"]))
        font = QFont("Consolas")
        font.setPixelSize(11)
        time_format.setFont(font)
        cursor.insertText(f"{timestamp} ", time_format)

        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor(_TAG_COLORS.get(tag, COLORS["text"])))
        tag_format.setFontWeight(QFont.DemiBold)
        if tag:
            head, _, rest = text.partition("]")
            cursor.insertText(" " + head + "]", tag_format)
            body = rest.strip()
        else:
            body = text
        body_format = QTextCharFormat()
        body_format.setForeground(QColor(COLORS["text"]))
        cursor.insertText(" " + body, body_format)
        self.view.setTextCursor(cursor)
        self.view.ensureCursorVisible()

    def _render(self):
        self.view.clear()
        keyword = self.search_box.text().strip()
        for timestamp, text, tag in self._records:
            if keyword and keyword not in text:
                continue
            self._insert(timestamp, text, tag)
        self._toggle_empty(not self._records)

    def _apply_filter(self, *_):
        self._render()

    def _toggle_search(self):
        visible = not self.search_box.isVisible()
        self.search_box.setVisible(visible)
        if visible:
            self.search_box.setFocus()
        else:
            self.search_box.clear()

    def clear(self):
        self._records.clear()
        self.view.clear()
        self._toggle_empty(True)
        if self.store is not None:
            self.store.clear_today()

    def plain_text(self):
        return "\n".join(f"{timestamp}  {text}" for timestamp, text, _ in self._records)

    def copy_all(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.plain_text())

    def export(self):
        default = os.path.join(os.path.expanduser("~"), "Desktop",
                               f"挂机日志_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", default, "文本文件 (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.plain_text())
            self.append(time.strftime("%H:%M:%S"), f"[导出] 日志已保存到 {path}")
        except Exception as error:
            self.append(time.strftime("%H:%M:%S"), f"[错误] 导出失败：{error}")
