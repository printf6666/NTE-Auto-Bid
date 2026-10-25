# -*- coding: utf-8 -*-
"""主窗口：1280×720 挂机任务界面

┌──────────────────────────────────────────────┬──────────────────┐
│ 挂机任务  ×                                             | 运行日志    │
│ ┌──────────────────────────────────────────┐ | （可折叠）  │
│ │ 收藏组合标题 + 状态                [编辑] │ |            │
│ │  今日局数 / 今日拍下 / 采集日期            │ |            │
│ │  采集日期                                  │ |            │
│ │  ── 分割线 ──                              │ |            │
│ │  运行流程面板（内嵌采集配置）              │ |            │
│ │  [参数配置] [高级设置] [空跑] [步进]       │ |            │
│ └──────────────────────────────────────────┘ |            │
│ ─── 统计：今日局数 / 今日拍下 ───              │            │
│                              [▶ 开始任务]     │            │
└──────────────────────────────────────────────┴──────────────────┘
"""
import os
import time

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                             QSizePolicy, QSplitter, QTabWidget, QVBoxLayout, QWidget)

from bus import Command
from settings_page import SettingsPage
from theme import COLORS, QSS, avatar, icon, rounded_square
from widgets import DateField, MetaItem, Row, StatTile, divider
from log_panel import LogPanel

APP_TITLE = "挂机任务 · 异环自动竞拍"


class ModeCard(QFrame):
    """模式选择卡片：可选中 / 禁用两种状态"""

    clicked = pyqtSignal(str)

    def __init__(self, key, title, icon_name, desc, enabled=True, parent=None):
        super().__init__(parent)
        self.key = key
        self.title = title
        self.enabled = enabled
        self._icon_name = icon_name
        self._selected = False
        self.setObjectName("ModeCard")
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ForbiddenCursor)

        box = QVBoxLayout(self)
        box.setContentsMargins(16, 12, 16, 12)
        box.setSpacing(8)

        head = Row(30, 10)
        self.mark = QLabel()
        self.mark.setPixmap(icon(icon_name, COLORS["text_muted"], 20).pixmap(20, 20))
        head.box.addWidget(self.mark)
        self.name_label = QLabel(title)
        head.box.addWidget(self.name_label)
        head.box.addStretch(1)
        self.check_label = QLabel()
        self.check_label.setVisible(False)
        head.box.addWidget(self.check_label)
        box.addWidget(head)

        self.desc_label = QLabel(desc)
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.desc_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        box.addWidget(self.desc_label, 1)

        self.state_label = QLabel("暂未开放" if not enabled else "点击选择")
        box.addWidget(self.state_label)

        self.set_selected(False)

    def set_selected(self, selected):
        self._selected = bool(selected) and self.enabled
        accent = COLORS["green"] if self.enabled else COLORS["border_strong"]
        if self._selected:
            border, background = COLORS["green"], COLORS["green_light"]
            name_color = COLORS["green_dark"]
            desc_color = COLORS["green_dark"]
        elif self.enabled:
            border, background = COLORS["border_strong"], COLORS["panel"]
            name_color = COLORS["text_strong"]
            desc_color = COLORS["text_muted"]
        else:
            border, background = COLORS["border"], COLORS["panel_alt"]
            name_color = COLORS["text_faint"]
            desc_color = COLORS["text_muted"]

        self.setStyleSheet(
            f"QFrame#ModeCard{{background:{background};border:2px solid {border};"
            f"border-radius:10px;}}")
        self.name_label.setStyleSheet(
            f"color:{name_color}; font-size:19px; font-weight:600;")
        self.desc_label.setStyleSheet(f"color:{desc_color}; font-size:16px;")
        self.state_label.setStyleSheet(
            f"color:{COLORS['green_dark'] if self._selected else desc_color}; font-size:15px;")
        self.state_label.setText(
            "当前使用" if self._selected else ("暂未开放" if not self.enabled else "点击选择"))
        self.mark.setPixmap(icon(self._icon_name, accent if self.enabled else COLORS["text_faint"],
                                 20).pixmap(20, 20))
        if self._selected:
            self.check_label.setPixmap(icon("check", COLORS["green"], 20).pixmap(20, 20))
            self.check_label.setVisible(True)
        else:
            self.check_label.setVisible(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)


class TaskCard(QFrame):
    """主任务卡片：标题、元信息、日期、运行状态与操作区"""

    def __init__(self, holder, control, stats, settings: SettingsPage, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.holder = holder
        self.control = control
        self.stats = stats
        self.settings = settings
        self._running = False
        self._stage = "未启动"
        self._cycle = None
        self._round = None
        self._start_time = None
        self._captures = 0
        self.runtime = None
        self.date_field = DateField()
        self.date_field.setFixedWidth(238)
        self.date_field.setFixedHeight(38)
        self.date_field.dateChanged.connect(self._on_date_changed)
        self._build()

    def _on_date_changed(self, *_):
        date = self.date_field.value()
        self._capture_caption = f"{date.year}-{date.month:02d}-{date.day:02d}"
        self.settings.set_capture_count(self._captures, self._capture_caption)

    # ------------------------------------------------------------------ 构建
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(10)

        # --- 标题行：名称 + 状态 + 实时元信息 ---
        top = Row(38, 8)
        title = QLabel("自动竞拍 · 异环")
        title.setProperty("role", "title")
        top.box.addWidget(title)
        self.status_chip = QLabel()
        self.status_chip.setFixedHeight(28)
        self.status_chip.setText("○ 未运行")
        self.status_chip.setStyleSheet(
            "padding:0 10px; border-radius:4px; font-size:15px;"
            f"background:{COLORS['panel_alt']}; color:{COLORS['text_muted']};")
        top.box.addWidget(self.status_chip)
        top.box.addStretch(1)
        self.meta_cycle = MetaItem("flag", "第 — 局")
        self.meta_round = MetaItem("calendar", "第 — 回合")
        self.meta_timer = MetaItem("clock", "00:00:00")
        for item in (self.meta_cycle, self.meta_round, self.meta_timer):
            top.box.addWidget(item)
        outer.addWidget(top)

        # --- 采集日期 + 统计卡片（竖向排列） ---
        date_row = Row(42, 8)
        prompt = QLabel("采集日期")
        prompt.setProperty("role", "faint")
        date_row.box.addWidget(prompt)
        date_row.box.addWidget(self.date_field)
        date_row.box.addStretch(1)
        outer.addWidget(date_row)

        self.tiles = {
            "cycles": StatTile("flag", "今日局数", "0"),
            "wins": StatTile("coin", "今日拍下", "0"),
        }
        tiles_box = QVBoxLayout()
        tiles_box.setSpacing(8)
        for tile in self.tiles.values():
            tile.setFixedHeight(58)
            tiles_box.addWidget(tile)
        outer.addLayout(tiles_box)

        outer.addWidget(divider())
        outer.addWidget(self._build_status_board(), 1)
        outer.addLayout(self._build_footer())

    def _build_status_board(self):
        """模式选择：普通 / 巨物 / 至尊（三种均已实现）"""
        board = QFrame()
        board.setObjectName("CardBody")
        board.setMinimumHeight(266)
        board.setMaximumHeight(296)
        grid = QHBoxLayout(board)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        self.mode_cards = {}
        self._mode = "normal"
        specs = [
            ("normal", "普通模式", "flag",
             "第一回合使用超级鉴定仪器随机展示 6 件藏品, 估价 > 512万则本局切换高价公式。", True),
            ("giant", "巨物模式", "target",
             "第一回合使用超级鉴定仪器展示 6 件藏品，"
             "第二回合使用特殊鉴定仪器展示轮廓最大的一件藏品，"
             "估价 > 512万则本局切换高价公式。", True),
            ("supreme", "至尊模式", "shield",
             "第一回合使用超级鉴定仪器展示 6 件藏品，"
             "第二回合使用九格均价仪器显示九格藏品的平均价值，"
             "均价 > 30万则本局切换高价公式，"
             "第三回合使用至尊鉴定仪器展示信息完全未知且品质最高的一件藏品。", True),
        ]
        for key, title, icon_name, desc, enabled in specs:
            card = ModeCard(key, title, icon_name, desc, enabled)
            card.clicked.connect(self._on_mode_clicked)
            self.mode_cards[key] = card
            grid.addWidget(card, 1)

        self._apply_mode_style()
        return board

    def _on_mode_clicked(self, key):
        card = self.mode_cards.get(key)
        if card is None:
            return
        if not card.enabled:
            self.footer_label.setText(f"{card.title}暂未开放，敬请期待")
            return
        self._mode = key
        self._apply_mode_style()
        self.footer_label.setText(f"已选择「{card.title}」")

    def _apply_mode_style(self):
        for key, card in self.mode_cards.items():
            card.set_selected(key == self._mode)

    def set_mode(self, key):
        if key in self.mode_cards and self.mode_cards[key].enabled:
            self._mode = key
            self._apply_mode_style()

    @property
    def mode(self):
        return self._mode


    def _build_footer(self):
        footer = QHBoxLayout()
        footer.setSpacing(8)
        mine = QLabel()
        mine.setPixmap(avatar("异", 26))
        footer.addWidget(mine)
        self.footer_label = QLabel("等待开始")
        self.footer_label.setStyleSheet(f"color:{COLORS['text_muted']}; font-size:16px;")
        footer.addWidget(self.footer_label)
        footer.addStretch(1)

        self.step_btn = QPushButton("下一步")
        self.step_btn.setCursor(Qt.PointingHandCursor)
        self.step_btn.setVisible(False)
        self.step_btn.clicked.connect(lambda: self.control.send(Command.STEP))
        footer.addWidget(self.step_btn)

        self.task_btn = QPushButton("开始任务")
        self.task_btn.setObjectName("Primary")
        self.task_btn.setCursor(Qt.PointingHandCursor)
        self.task_btn.setIcon(icon("play", "#ffffff", 20))
        self.task_btn.setIconSize(QSize(20, 20))
        self.task_btn.setFixedHeight(52)
        self.task_btn.setMinimumWidth(190)
        self.task_btn.clicked.connect(self.toggle_run)
        footer.addWidget(self.task_btn)
        return footer

    # ------------------------------------------------------------------ 状态
    def set_status(self, state):
        running = bool(state.get("running"))
        stage = state.get("stage", "未启动")
        self._stage = stage
        self._running = running
        self._cycle = state.get("cycle")
        self._round = state.get("round")
        detail = state.get("detail") or ""

        if running:
            self.status_chip.setText("● 运行中")
            self.status_chip.setStyleSheet(
                f"padding:0 10px; border-radius:4px; font-size:15px;"
                f"background:{COLORS['green_light']}; color:{COLORS['green_dark']};")
            self.task_btn.setText("  停止任务")
            self.task_btn.setProperty("variant", "danger")
            self._restyle(self.task_btn)
            self.task_btn.setIcon(icon("stop", "#e34d59", 20))
            self.footer_label.setText(f"运行中 · {detail or stage}")
        else:
            self.status_chip.setText("○ 未运行" if self._cycle is None else "○ 已停止")
            self.status_chip.setStyleSheet(
                "padding:0 10px; border-radius:4px; font-size:15px;"
                f"background:{COLORS['panel_alt']}; color:{COLORS['text_muted']};")
            self.task_btn.setText("  开始任务")
            self.task_btn.setProperty("variant", "normal")
            self._restyle(self.task_btn)
            self.task_btn.setIcon(icon("play", "#ffffff", 20))
            self.footer_label.setText(stage if stage != "未启动" else "等待开始 · 点击开始任务后自动挂机")
        self.step_btn.setVisible(running and bool(state.get("waiting_step")))
        self.meta_cycle.set_text(f"第 {self._cycle or '—'} 局")
        self.meta_round.set_text(f"第 {self._round or '—'} 回合")

    @staticmethod
    def _restyle(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def set_stats(self, data):
        self.tiles["cycles"].set_value(f"{data.get('cycles', 0):,}")
        self.tiles["wins"].set_value(f"{data.get('wins', 0):,}")

    def refresh_board(self, state=None):
        """刷新状态胶囊的提示信息（出价参数）"""
        config = self.holder.snapshot()
        bid_config = config.get("bid", {})
        from bid import CONFIRM_POPUP_THRESHOLD, HIGH_THRESHOLD
        self.status_chip.setToolTip(
            f"出价倍率 {bid_config.get('multiplier', 1.3):g} · "
            f"高价阈值 {HIGH_THRESHOLD // 10000} 万（固定）· "
            f"二次确认 {CONFIRM_POPUP_THRESHOLD // 10000} 万（固定）")

    def set_timer(self, running):
        if running:
            if self._start_time is None:
                self._start_time = time.monotonic()
            seconds = int(time.monotonic() - self._start_time)
            self.meta_timer.set_text(f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}")
        elif self._start_time is not None:
            self.meta_timer.set_text("已停止")

    def reset_timer(self):
        self._start_time = None
        self.meta_timer.set_text("00:00:00")

    def attach_runtime(self, runtime):
        """runtime 提供 start()/stop()，由 app.py 注入"""
        self.runtime = runtime

    def toggle_run(self):
        if self._running:
            self.runtime.stop()
            self.footer_label.setText("正在停止…")
            self.task_btn.setEnabled(False)
            QTimer.singleShot(1500, lambda: self.task_btn.setEnabled(True))
        else:
            self.reset_timer()
            self.runtime.start(self.mode)


class MainWindow(QMainWindow):
    def __init__(self, holder, control, stats, parent=None):
        super().__init__(parent)
        self.holder = holder
        self.control = control
        self.stats = stats
        self._captures = 0
        self._state = {"running": False}
        self._closing = False
        self.runtime = None
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(self._app_icon())
        self.setFixedSize(1440, 810)
        self.setStyleSheet(QSS)
        self._build()
        self._connect()
        # 计时器只在任务运行时走（1 秒一次），空闲时完全停掉，避免无谓唤醒
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)
        self._restore_logs()
        self._sync_from_config()

    def _restore_logs(self):
        """把磁盘上的历史日志回填到面板，接着上次继续"""
        try:
            from log_store import LogStore
            self.log_store = LogStore(self.holder.base_dir)
        except Exception:
            self.log_store = None
            return
        self.log_panel.store = self.log_store
        records = self.log_store.recent()
        if records:
            self.log_panel.restore(records)

    def attach_runtime(self, runtime):
        """runtime 提供 start()/stop()/shutdown()，由 app.py 注入"""
        self.runtime = runtime
        self.task_card.attach_runtime(runtime)

    # ------------------------------------------------------------------ 构建
    @staticmethod
    def _app_icon():
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.drawPixmap(0, 0, rounded_square(COLORS["green"], 32, 8))
        painter.drawPixmap(8, 8, icon("player", "#ffffff", 16).pixmap(16, 16))
        painter.end()
        return QIcon(pixmap)

    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(8)
        self.splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 12, 8, 12)
        left_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.settings = SettingsPage(self.holder)
        self.tabs.addTab(self._build_task_tab(), "挂机任务")
        self.tabs.addTab(self.settings, "参数配置")
        left_layout.addWidget(self.tabs)
        self.splitter.addWidget(left)

        self.log_panel = LogPanel()
        self.splitter.addWidget(self.log_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([900, 530])
        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(root)

    def _build_task_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(0)
        self.task_card = TaskCard(self.holder, self.control, self.stats, self.settings)
        layout.addWidget(self.task_card)
        return page

    # ------------------------------------------------------------------ 连接
    def _connect(self):
        signals = self.control.signals
        signals.log.connect(self.log_panel.append)
        signals.state.connect(self.on_state)
        signals.stats.connect(self.task_card.set_stats)
        signals.step_prompt.connect(
            lambda text: self.task_card.footer_label.setText(f"待确认：{text}"))
        signals.finished.connect(self.on_finished)
        self.settings.saved.connect(self._on_settings_changed)
        self.settings.reset_requested.connect(self._on_reset_settings)
        self.settings.rate_changed.connect(lambda *_: None)
        self.settings.dry_run_box.toggled.connect(self._sync_from_config)
        self.settings.step_box.toggled.connect(self._sync_from_config)
        self.log_panel.collapsed_changed.connect(self._on_log_collapsed)

    def _on_log_collapsed(self, collapsed):
        total = max(self.splitter.width(), 1000)
        if collapsed:
            self.splitter.setSizes([total - 52, 52])
        else:
            self.splitter.setSizes([total - 530, 530])

    def _sync_from_config(self, *_):
        self.task_card.set_stats(self.stats.snapshot())
        self.task_card.refresh_board(self._state)
        date = self.task_card.date_field.value()
        self.settings.set_capture_count(self._captures, f"{date.year}-{date.month:02d}-{date.day:02d}")

    def _on_settings_changed(self):
        self._sync_from_config()

    def _on_reset_settings(self):
        """恢复默认：保留坐标与动作，仅把节奏/出价参数恢复为出厂值"""
        defaults = {
            "interval": 1.0, "startup_wait": 5.0, "round_wait": 3.0,
            "cooldown_wait": 18.0, "action_gap": 0.5,
        }

        def mutate(config):
            loop = config.setdefault("loop", {})
            loop.update(defaults)

        self.holder.update(mutate)
        self.settings.load_values()
        self._sync_from_config()
        self.log_panel.append(time.strftime("%H:%M:%S"), "[设置] 节奏参数已恢复默认值（未保存到磁盘）")

    # ------------------------------------------------------------------ 运行状态
    def on_state(self, state):
        self._state = state
        running = bool(state.get("running"))
        self.task_card.set_status(state)
        self.task_card.refresh_board(state)
        if running:
            if not self._tick_timer.isActive():
                self._tick_timer.start()
        else:
            self._tick_timer.stop()
            self.task_card.reset_timer()

    def on_finished(self, reason):
        self.task_card.set_status({"running": False, "stage": "已停止",
                                   "cycle": None, "round": None, "detail": reason})
        self.log_panel.append(time.strftime("%H:%M:%S"), f"[结束] {reason}")

    # ------------------------------------------------------------------ 调试
    def grab_image(self):
        """离屏渲染整个窗口为 QImage（绕过某些环境下 grab() 崩溃的问题）"""
        self.ensurePolished()
        self.layout().activate()
        size = self.frameGeometry().size() if self.isVisible() else self.size()
        image = QImage(size, QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        self.render(painter)
        painter.end()
        return image

    def _on_tick(self):
        self.task_card.set_timer(True)

    # ------------------------------------------------------------------ 关闭
    def closeEvent(self, event):
        if self._state.get("running") and not self._closing:
            from PyQt5.QtWidgets import QMessageBox
            answer = QMessageBox.question(
                self, "退出", "任务正在运行，退出将停止挂机并关闭窗口，确定退出？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._closing = True
            if self.runtime is not None:
                self.runtime.shutdown()
        self._tick_timer.stop()
        self.stats.save()
        if getattr(self, "log_store", None) is not None:
            self.log_store.close()
        event.accept()


def create_app():
    # 界面按 1440×810 逻辑像素排版，缩放钉成 4/3 → 屏幕上是 1920×1080，
    # 字体与控件同比例放大。关闭自动 DPI 缩放，避免被系统缩放二次放大。
    os.environ.setdefault("QT_SCALE_FACTOR", "1.3333")
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, False)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_TITLE)
    font = app.font()
    font.setFamily("Microsoft YaHei UI")
    font.setPixelSize(15)
    app.setFont(font)
    return app
