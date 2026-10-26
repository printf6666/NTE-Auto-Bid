# -*- coding: utf-8 -*-
"""工作线程：在后台跑截屏 → 场景检测 → 动作的主循环，并与界面互通

和原 main.main() 的循环等价，区别只在于：
- 等待被切成小片，随时响应「停止」与「步进」
- 日志、状态、统计通过 Control.signals 发给界面
- 每一步操作前检查提权，提权丢失时以友好文案结束而不是静默卡死
"""
import logging
import threading
import time
import traceback

from bus import Command
from stats import Stats
from window import elevation_error


class ThreadLogHandler(logging.Handler):
    """把 logging 记录转发到界面日志面板"""

    def __init__(self, control):
        super().__init__(level=logging.INFO)
        self.control = control

    def emit(self, record):
        try:
            message = record.getMessage()
            if record.exc_info:
                message += " | " + str(record.exc_info[1])
            self.control.signals.log.emit(
                time.strftime("%H:%M:%S", time.localtime(record.created)), message)
        except Exception:
            pass


class BotWorker(threading.Thread):
    def __init__(self, control, holder, stats: Stats, logger_name="yihuan", mode="normal"):
        super().__init__(daemon=True)
        self.control = control
        self.holder = holder
        self.stats = stats
        self.name = "BotWorker"
        self.log = logging.getLogger(logger_name)
        self._mode = mode or "normal"
        self._stop_event = threading.Event()
        self._step_event = threading.Event()
        self._step_mode = False
        self._running = False
        self._stage = ""
        self._detail = ""
        self._round = None
        self._cycle = None
        self._capturer = None
        self._runner = None
        self._flow = None

    # ------------------------------------------------------------------ 工具
    @property
    def config(self):
        return self.holder.config

    def state_snapshot(self):
        return {
            "running": self._running,
            "stage": self._stage,
            "detail": self._detail,
            "cycle": self._cycle,
            "round": self._round,
            "step_mode": self._step_mode,
            "waiting_step": bool(self._step_mode and not self._step_event.is_set()),
        }

    def push_state(self):
        self.control.signals.state.emit(self.state_snapshot())

    def push_stats(self):
        self.control.signals.stats.emit(self.stats.snapshot())

    def set_stage(self, stage, detail="", round_number=None):
        self._stage = stage
        self._detail = detail
        if round_number is not None:
            self._round = round_number
        self.push_state()

    # 供 Flow 调用的钩子 ------------------------------------------------
    def on_phase(self, phase, state):
        self._cycle = state.cycle
        self._round = state.current_round
        labels = {"boot": "启动中", "awaiting": "等待进入竞拍",
                  "playing": "竞拍中", "cooldown": "结算冷却"}
        detail = f"第 {state.cycle} 局"
        if phase in ("playing", "cooldown") and state.current_round:
            detail += f" · 第 {state.current_round} 回合"
        if phase == "cooldown":
            left = max(0, int(state.cooldown_until - time.time()))
            detail += f" · 冷却 {left}s"
        self._stage = labels.get(phase, phase)
        self._detail = detail
        self.push_state()

    def on_round(self, round_number, state):
        self._cycle = state.cycle
        self.set_stage("竞拍中", f"第 {state.cycle} 局 · 第 {round_number} 回合", round_number)

    def on_bid(self, round_number, bid_value, state):
        self.set_stage("出价", f"第 {state.cycle} 局 · 第 {round_number} 回合 · {bid_value / 10000:.0f}万",
                       round_number)

    def on_settle(self, won, state):
        self._cycle = state.cycle
        self.stats.add("cycles")
        if won:
            self.stats.add("wins")
        self.push_stats()
        self.set_stage("结算", f"第 {state.cycle} 局完成" + ("，本局拍下" if won else "，他人拍下"),
                       state.current_round)

    # 协作式中断 --------------------------------------------------------
    def check_interrupt(self):
        """暂停点：处理停止命令；步进模式下等待用户放行"""
        if self._stop_event.is_set():
            raise StopRequested("已停止")
        while True:
            command = self.control.poll()
            if command is None:
                break
            name, _ = command
            if name in (Command.STOP, Command.STOP_TASK):
                self._stop_event.set()
                raise StopRequested("已停止")
            if name == Command.STEP:
                self._step_event.set()
        if self._step_mode and not self._step_event.is_set():
            self.set_stage("等待步进", self._detail or "待确认下一步")
            while not self._stop_event.is_set():
                command = self.control.poll(timeout=0.1)
                if command is None:
                    continue
                if command[0] in (Command.STOP, Command.STOP_TASK):
                    self._stop_event.set()
                    raise StopRequested("已停止")
                if command[0] == Command.STEP:
                    self._step_event.set()
                    break
            if self._stop_event.is_set():
                raise StopRequested("已停止")
        if self._stage == "等待步进":
            self.set_stage("运行中", self._detail)

    def await_step(self, prompt):
        """步进模式：等待界面上的「下一步」按钮（点击前调用）"""
        if not self._step_mode or self._stop_event.is_set():
            return
        self._step_event.clear()
        detail_backup = self._detail
        self._detail = prompt
        self.set_stage("等待步进", prompt)
        self.control.signals.step_prompt.emit(prompt)
        while not self._stop_event.is_set():
            command = self.control.poll(timeout=0.1)
            if command is None:
                continue
            if command[0] in (Command.STOP, Command.STOP_TASK):
                self._stop_event.set()
                raise StopRequested("已停止")
            if command[0] == Command.STEP:
                break
        self._step_event.clear()
        self._detail = detail_backup
        self.set_stage("运行中", detail_backup)

    def sleep(self, seconds, reason="", interruptible=True):
        """可中断等待"""
        if seconds <= 0:
            return
        if not interruptible:
            end = time.monotonic() + seconds
            while True:
                left = end - time.monotonic()
                if left <= 0:
                    return
                time.sleep(min(left, 0.2))
                if self._stop_event.is_set():
                    raise StopRequested("已停止")
            return
        end = time.monotonic() + seconds
        while True:
            left = end - time.monotonic()
            if left <= 0:
                return
            self.check_interrupt()
            # 0.2 秒切片：停止响应依旧即时，唤醒次数比 0.1 秒少一半（省电）
            time.sleep(min(left, 0.2))

    def require_elevation(self):
        error = elevation_error(self.config.get("window", {}).get("title") or "异环")
        if error:
            raise FatalError(error)

    # ------------------------------------------------------------------ 主循环
    def run(self):
        self._running = True
        self._stage = "初始化"
        self._detail = "准备运行环境"
        self._stop_event.clear()
        self._step_event.clear()
        reason = "已停止"
        started = False
        try:
            self._step_mode = bool(self.config.get("debug", {}).get("step", False))
            self.push_state()
            self.log.info("正在初始化 OCR 引擎…")
            from actions import ActionRunner
            from mouse import Mouse
            from ocr import OCREngine
            from scenes import Flow
            from screen import ScreenCapturer

            ocr_engine = OCREngine(self.config)
            self.log.info("OCR 引擎就绪，检查运行环境…")
            self.require_elevation()

            from state import State
            mouse = Mouse(self.config)
            self._runner = ActionRunner(self.config, mouse, worker=self)
            self._capturer = ScreenCapturer()
            state = State()
            self._flow = Flow(self.config, state, ocr_engine, self._runner,
                              self._capturer, control=self.control, worker=self,
                              mode=self._mode)
            run_mode = "空跑" if self._runner.dry_run else "步进" if self._runner.step else "自动"
            flow_mode = {"normal": "普通", "giant": "巨物", "supreme": "至尊"}.get(
                self._mode, self._mode)
            self.log.info("异环自动竞拍已启动，模式: %s · %s模式", run_mode, flow_mode)
            started = True
            # 先把 boot 相位推给界面，避免启动等待期间阶段栏是空的
            self._cycle = state.cycle
            self.on_phase(state.phase, state)

            while not self._stop_event.is_set():
                begin = time.monotonic()
                self._flow.tick()  # 各阶段按需截取识别框小区域，冷却等待期零截图
                self.check_interrupt()
                elapsed = time.monotonic() - begin
                interval = float(self.config["loop"].get("interval", 1.0))
                if elapsed < interval:
                    self.sleep(interval - elapsed)
        except StopRequested as stop:
            reason = str(stop)
        except FatalError as fatal:
            reason = f"致命错误：{fatal}"
            self.log.error("%s", fatal)
        except SystemExit as exit_info:
            reason = "流程结束" if not exit_info.code else f"致命错误（退出码 {exit_info.code}）"
        except Exception as error:  # noqa: BLE001
            reason = f"异常退出：{error}"
            self.log.error("运行异常：%s", error)
            for line in traceback.format_exc().strip().splitlines()[-4:]:
                self.log.error("  %s", line)
        finally:
            try:
                if self._capturer is not None:
                    self._capturer.close()
            except Exception:
                pass
            self._running = False
            self._round = None
            self._stage = "已停止" if started else "未启动"
            if started:
                self.log.info("运行结束：%s", reason)
            self.push_state()
            self.stats.save()
            self.control.signals.finished.emit(reason)


class StopRequested(Exception):
    """协作中断：由用户停止触发"""


class FatalError(Exception):
    """致命错误：无法继续运行（缺权限 / 配置错误等）"""
