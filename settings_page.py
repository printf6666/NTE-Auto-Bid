# -*- coding: utf-8 -*-
"""设置页：采集配置（频率/日期/分辨率）、出价参数、运行节奏、保存与重置"""
import json
from datetime import datetime

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                             QSpinBox, QVBoxLayout, QWidget)

from theme import COLORS, icon
from widgets import (Chip, DateField, FloatField, FormRow, IconButton, MetaItem, NumberField,
                     SectionHeader, divider, spacer)


def _card(parent=None):
    frame = QFrame(parent)
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 12)
    layout.setSpacing(8)
    return frame, layout


class SettingsPage(QWidget):
    """分三块：采集配置 / 出价策略 / 运行节奏，改动即时写回配置"""

    saved = pyqtSignal()
    reset_requested = pyqtSignal()
    rate_changed = pyqtSignal(float)

    def __init__(self, holder, parent=None):
        super().__init__(parent)
        self.holder = holder
        self._loading = False

        outer = QVBoxLayout(self)
        # 底边距 14：与挂机任务页「开始任务」按钮底边（任务卡 14px 底边距）对齐
        outer.setContentsMargins(0, 8, 0, 14)
        outer.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                             "QScrollArea>QWidget>QWidget{background:transparent;}")
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 4, 0)
        column.setSpacing(10)
        # 说明卡放滚动区内：内容超高时由滚动区吸收，底部按钮条不会再被窗口底边裁掉
        column.addWidget(self._build_intro())
        column.addWidget(self._build_capture())
        column.addWidget(self._build_bid())
        column.addWidget(self._build_loop())
        column.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        outer.addWidget(self._build_actions())

        self.load_values()

    # ------------------------------------------------------------ 顶部说明
    def _build_intro(self):
        frame, layout = _card()
        row = QHBoxLayout()
        row.setSpacing(12)
        badge = QLabel()
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background:{COLORS['green_light']}; border-radius:9px;")
        badge.setPixmap(icon("sliders", COLORS["green"], 18).pixmap(18, 18))
        row.addWidget(badge)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        title = QLabel("挂机任务 · 异环自动竞拍")
        title.setProperty("role", "title")
        texts.addWidget(title)
        row.addLayout(texts, 1)
        self.path_label = QLabel("config.json")
        self.path_label.setProperty("role", "faint")
        self.path_label.setToolTip(str(self.holder.base_dir / "config.json"))
        row.addWidget(self.path_label)
        open_btn = QPushButton("打开配置目录")
        open_btn.setObjectName("Subtle")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(self._open_dir)
        row.addWidget(open_btn)
        layout.addLayout(row)
        return frame

    def _open_dir(self):
        import os
        os.startfile(str(self.holder.base_dir))

    # ------------------------------------------------------------ 采集配置
    def _build_capture(self):
        frame, layout = _card()
        header = SectionHeader("采集配置", "crosshair")
        layout.addWidget(header)

        self.rate_combo = QComboBox()
        self.rate_combo.setFixedWidth(150)
        self.rate_combo.setFixedHeight(30)
        for text, sec in (("连续采集（1 秒）", 1.0), ("标准（2 秒）", 2.0),
                          ("节能（4 秒）", 4.0), ("低频（8 秒）", 8.0)):
            self.rate_combo.addItem(text, sec)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(_label("识别间隔"))
        self.interval_field = FloatField(1.0, 88)
        top.addWidget(self.interval_field)
        top.addWidget(QLabel("秒"))
        hint = QLabel("等待竞拍时每隔这么久截屏识别一次价格")
        hint.setProperty("role", "faint")
        top.addWidget(hint)
        top.addStretch(1)
        self.count_label = MetaItem("clock", "今日 0 次采集")
        top.addWidget(self.count_label)
        layout.addLayout(top)

        layout.addWidget(divider())

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self.width_field = NumberField(2560, 96)
        self.height_field = NumberField(1600, 96)
        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        size_row.addWidget(self.width_field)
        size_row.addWidget(QLabel("×"))
        size_row.addWidget(self.height_field)
        size_row.addStretch(1)
        size_wrap = QWidget()
        size_wrap.setLayout(size_row)
        grid.addWidget(_label("游戏分辨率"), 0, 0)
        grid.addWidget(size_wrap, 0, 1)
        self.title_field = QLineEdit()
        self.title_field.setPlaceholderText("留空则不切换窗口，例如：异环")
        self.title_field.setFixedHeight(30)
        grid.addWidget(_label("游戏窗口标题"), 0, 2)
        grid.addWidget(self.title_field, 0, 3)
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)

        self.dry_run_box = QCheckBox("空跑模式（只识别不点击，用于验证公式与坐标）")
        self.step_box = QCheckBox("步进模式（每次点击前等待「下一步」）")
        for box in (self.dry_run_box, self.step_box):
            box.setCursor(Qt.PointingHandCursor)
            layout.addWidget(box)

        for widget in (self.width_field, self.height_field):
            widget.valueChanged.connect(self._commit)
        self.title_field.editingFinished.connect(self._commit)
        self.rate_combo.currentIndexChanged.connect(self._on_rate)
        self.interval_field.valueChanged.connect(self._commit)
        self.dry_run_box.toggled.connect(self._commit)
        self.step_box.toggled.connect(self._commit)
        return frame

    def _on_rate(self, *_):
        """选预设频率时同步到「识别间隔」输入框"""
        value = self.rate_combo.currentData()
        if value is not None and not self._loading:
            self._loading = True
            self.interval_field.set_value(float(value))
            self._loading = False
        self._commit()

    # ------------------------------------------------------------ 出价策略
    def _build_bid(self):
        frame, layout = _card()
        layout.addWidget(SectionHeader("出价策略", "coin"))

        self.multiplier_field = FloatField(1.3)
        self.bonus_min_field = NumberField(1, 70)
        self.bonus_max_field = NumberField(5, 70)
        self.sell_threshold_field = NumberField(5120000, 130)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.addWidget(_label("估价倍率"), 0, 0)
        grid.addWidget(self.multiplier_field, 0, 1)
        grid.addWidget(_label("随机加价"), 0, 2)
        bonus_row = QHBoxLayout()
        bonus_row.setSpacing(6)
        bonus_row.addWidget(self.bonus_min_field)
        bonus_row.addWidget(QLabel("~"))
        bonus_row.addWidget(self.bonus_max_field)
        bonus_row.addWidget(QLabel("万/轮"))
        bonus_row.addStretch(1)
        bonus_wrap = QWidget()
        bonus_wrap.setLayout(bonus_row)
        grid.addWidget(bonus_wrap, 0, 3)
        grid.addWidget(_label("出售红键阈值"), 1, 0)
        grid.addWidget(self.sell_threshold_field, 1, 1)
        grid.setColumnStretch(4, 1)
        layout.addLayout(grid)

        from bid import CONFIRM_POPUP_THRESHOLD, HIGH_THRESHOLD
        note = QLabel(
            f"估价 > {HIGH_THRESHOLD // 10000} 万改用高价公式；"
            f"出价 > {CONFIRM_POPUP_THRESHOLD // 10000} 万自动点「继续」；"
            "最终估价 > 出售阈值 时直接出售")
        note.setProperty("role", "faint")
        note.setWordWrap(True)
        layout.addWidget(note)

        for widget in (self.multiplier_field, self.bonus_min_field, self.bonus_max_field,
                       self.sell_threshold_field):
            widget.valueChanged.connect(self._commit)
        return frame

    # ------------------------------------------------------------ 运行节奏
    def _build_loop(self):
        frame, layout = _card()
        layout.addWidget(SectionHeader("运行节奏", "clock"))

        grid = QHBoxLayout()
        grid.setSpacing(16)
        self.startup_field = FloatField(5.0)
        self.round_field = FloatField(3.0)
        self.cooldown_field = FloatField(18.0)
        self.action_field = FloatField(0.5)
        columns = [
            ("启动等待", self.startup_field, "秒"),
            ("回合等待", self.round_field, "秒"),
            ("冷却等待", self.cooldown_field, "秒"),
            ("动作间隔", self.action_field, "秒"),
        ]
        for title, field, unit in columns:
            box = QVBoxLayout()
            box.setSpacing(2)
            caption = QLabel(title)
            caption.setProperty("role", "faint")
            row = QHBoxLayout()
            row.setSpacing(4)
            row.addWidget(field)
            row.addWidget(QLabel(unit))
            row.addStretch(1)
            box.addWidget(caption)
            box.addLayout(row)
            grid.addLayout(box, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

        for widget in (self.startup_field, self.round_field, self.cooldown_field, self.action_field):
            widget.valueChanged.connect(self._commit)
        return frame

    # ------------------------------------------------------------ 底部按钮
    def _build_actions(self):
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 4, 0, 0)
        row.setSpacing(8)
        self.dirty_label = QLabel("已与 config.json 同步")
        self.dirty_label.setProperty("role", "faint")
        row.addWidget(self.dirty_label)
        row.addStretch(1)
        reset_btn = QPushButton("恢复默认")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._on_reset)
        save_btn = QPushButton("保存配置")
        save_btn.setObjectName("Primary")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setText("  保存配置")
        save_btn.setIcon(icon("check", "#ffffff", 15))
        save_btn.setIconSize(QSize(15, 15))
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self.save_config)
        row.addWidget(reset_btn)
        row.addWidget(save_btn)
        return bar

    # ------------------------------------------------------------ 读写配置
    def load_values(self):
        self._loading = True
        config = self.holder.snapshot()
        screen = config.get("screen", {})
        self.width_field.set_value(screen.get("width", 2560))
        self.height_field.set_value(screen.get("height", 1600))
        self.title_field.setText(config.get("window", {}).get("title", ""))

        loop = config.get("loop", {})
        interval = float(loop.get("interval", 1.0))
        index = self.rate_combo.findData(interval)
        self.rate_combo.setCurrentIndex(index if index >= 0 else 0)
        if index < 0:
            self.rate_combo.addItem(f"自定义（{interval:g} 秒）", interval)
            self.rate_combo.setCurrentIndex(self.rate_combo.count() - 1)
        self.startup_field.set_value(loop.get("startup_wait", 5.0))
        self.round_field.set_value(loop.get("round_wait", 3.0))
        self.cooldown_field.set_value(loop.get("cooldown_wait", 18.0))
        self.action_field.set_value(loop.get("action_gap", 0.5))

        bid = config.get("bid", {})
        self.multiplier_field.set_value(bid.get("multiplier", 1.3))
        self.interval_field.set_value(loop.get("interval", 1.0))
        self.bonus_min_field.set_value(bid.get("bonus_wan_min", 1))
        self.bonus_max_field.set_value(bid.get("bonus_wan_max", 5))
        self.sell_threshold_field.set_value(bid.get("sell_red_threshold", 5120000))

        debug = config.get("debug", {})
        self.dry_run_box.setChecked(bool(debug.get("dry_run", False)))
        self.step_box.setChecked(bool(debug.get("step", False)))
        self._loading = False
        self.dirty_label.setText("已与 config.json 同步")
        self.dirty_label.setStyleSheet(f"color:{COLORS['text_faint']}; font-size:16px;")

    def set_capture_count(self, count, date_text=""):
        extra = f" · {date_text}" if date_text else ""
        self.count_label.set_text(f"今日 {count} 次采集{extra}")

    def _commit(self, *_):
        """界面 → 配置（内存），由上层负责落盘"""
        if self._loading:
            return
        values = {
            "interval": self.interval_field.value(1.0),
            "startup_wait": self.startup_field.value(5.0),
            "round_wait": self.round_field.value(3.0),
            "cooldown_wait": self.cooldown_field.value(18.0),
            "action_gap": self.action_field.value(0.5),
            "multiplier": self.multiplier_field.value(1.3),
            "bonus_wan_min": self.bonus_min_field.value(1),
            "bonus_wan_max": self.bonus_max_field.value(5),
            "sell_red_threshold": self.sell_threshold_field.value(5120000),
            "width": self.width_field.value(2560),
            "height": self.height_field.value(1600),
            "title": self.title_field.text().strip(),
            "dry_run": self.dry_run_box.isChecked(),
            "step": self.step_box.isChecked(),
        }

        def mutate(config):
            config.setdefault("screen", {})["width"] = values["width"]
            config.setdefault("screen", {})["height"] = values["height"]
            config.setdefault("window", {})["title"] = values["title"]
            loop = config.setdefault("loop", {})
            for key in ("interval", "startup_wait", "round_wait", "cooldown_wait", "action_gap"):
                loop[key] = values[key]
            bid = config.setdefault("bid", {})
            for key in ("multiplier", "bonus_wan_min", "bonus_wan_max", "sell_red_threshold"):
                bid[key] = values[key]
            debug = config.setdefault("debug", {})
            debug["dry_run"] = values["dry_run"]
            debug["step"] = values["step"]

        self.holder.update(mutate)
        self.dirty_label.setText("参数已更新，运行中即时生效")
        self.dirty_label.setStyleSheet(f"color:{COLORS['green']}; font-size:16px;")
        self.saved.emit()

    def save_config(self):
        self._commit()
        target = self.holder.base_dir / "config.json"
        try:
            with open(target, "w", encoding="utf-8") as file:
                json.dump(self.holder.snapshot(), file, ensure_ascii=False, indent=2)
            self.dirty_label.setText(f"已保存 · {datetime.now():%H:%M:%S}")
            self.dirty_label.setStyleSheet(f"color:{COLORS['green']}; font-size:16px;")
        except Exception as error:
            self.dirty_label.setText(f"保存失败：{error}")
            self.dirty_label.setStyleSheet("color:#e34d59; font-size:16px;")

    def _on_reset(self):
        self.reset_requested.emit()


def _label(text):
    label = QLabel(text)
    label.setProperty("role", "caption")
    return label
