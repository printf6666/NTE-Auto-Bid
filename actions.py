# -*- coding: utf-8 -*-
"""动作执行：点击 / 等待 / 按键

- 正常模式：顺序执行
- debug.dry_run：只打印不点击、跳过等待（快速验证出价公式）
- debug.step：每个动作前等待界面上的「下一步」（验证点击顺序）
- 传入 worker 时：等待可被「停止」打断，并在每个点击前复查提权
坐标语义见 config._说明：动作组内 [x,y] 为点击中心点，{"wait": 秒} 为等待。
"""
import logging
import time

from window import elevation_error, focus_game_window

log = logging.getLogger("yihuan")


def describe(item):
    if isinstance(item, dict):
        if "wait" in item:
            return f"等待 {item['wait']} 秒"
        if "key" in item:
            return f"按键 {item['key']}"
    return f"点击 ({item[0]}, {item[1]})"


class ActionRunner:
    def __init__(self, config, mouse, worker=None):
        self.config = config
        self.mouse = mouse
        self.worker = worker
        debug = config.get("debug", {})
        self.dry_run = bool(debug.get("dry_run", False))
        self.step = bool(debug.get("step", False))
        self.action_gap = float(config["loop"].get("action_gap", 0.5))
        self.window_title = config.get("window", {}).get("title", "")

    def _sleep(self, seconds):
        """动作组内等待（不触发步进暂停）"""
        seconds = float(seconds)
        if seconds <= 0:
            return
        if self.worker is not None:
            self.worker.sleep(seconds, interruptible=False)
        else:
            time.sleep(seconds)

    def wait(self, seconds, reason=""):
        """场景级等待：dry_run 跳过，其余按真实时间睡（可被停止打断）"""
        seconds = float(seconds)
        if seconds <= 0:
            return
        if self.dry_run:
            log.info("[空跑] 跳过等待 %.1f 秒 %s", seconds, reason)
            return
        if self.worker is not None:
            self.worker.sleep(seconds, reason)
        else:
            time.sleep(seconds)

    def _gate(self, group_name, desc):
        """步进模式：等待界面上的「下一步」放行"""
        if not self.step or self.worker is None:
            return
        self.worker.await_step(f"{group_name} | {desc}")

    def run(self, group_name, steps):
        """执行一个动作序列（点击/等待/按键混合）"""
        if not steps:
            log.error("动作组「%s」为空", group_name)
            return
        if not self.dry_run:
            error = elevation_error(self.window_title or "异环")
            if error:
                self.fail(error)
        focus_game_window(self.window_title)
        for item in steps:
            desc = describe(item)
            if self.dry_run:
                log.info("[空跑] %s: %s", group_name, desc)
                continue
            if not isinstance(item, dict):
                self._gate(group_name, desc)
            self._execute_one(item)

    def _execute_one(self, item):
        if isinstance(item, dict):
            if "wait" in item:
                self._sleep(float(item["wait"]))
            elif "key" in item:
                self.mouse.press_key(item["key"])
                self._sleep(self.action_gap)
            return
        if self.worker is not None:
            self.worker.require_elevation()
        self.mouse.click(item[0], item[1])
        self._sleep(self.action_gap)

    def fail(self, message):
        """致命错误：打印一行并退出"""
        log.error(message)
        raise SystemExit(1)
