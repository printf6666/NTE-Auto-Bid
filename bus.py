# -*- coding: utf-8 -*-
"""UI 与工作线程之间的共享配置

- ConfigHolder：GUI 与脚本使用同一个 dict 对象，界面改动可即时生效
- Control：命令队列（GUI → 工作线程）+ 信号总线（工作线程 → GUI）
"""
import copy
import queue
import threading

from PyQt5.QtCore import QObject, pyqtSignal


class ConfigHolder:
    """线程安全的配置容器：GUI 读写与脚本读取共用同一份 dict"""

    def __init__(self, config, base_dir):
        self._lock = threading.RLock()
        self._config = config
        self.base_dir = base_dir

    @property
    def config(self):
        return self._config

    def load(self, config):
        with self._lock:
            self._config.clear()
            self._config.update(copy.deepcopy(config))

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._config)

    def update(self, mutate):
        """加锁修改配置：mutate(config) 原地修改，界面线程与工作线程互斥访问"""
        with self._lock:
            mutate(self._config)


class Command:
    START = "start"          # 开始 / 继续
    STOP = "stop"            # 立即停止（中断当前动作）
    STEP = "step"            # 步进模式：放行下一步
    STOP_TASK = "stop_task"  # 挂机停止：等当前动作结束，不再进入下一局


class Signals(QObject):
    log = pyqtSignal(str, str)        # (时间, 正文)
    state = pyqtSignal(dict)          # 运行状态快照
    stats = pyqtSignal(dict)          # 统计快照
    step_prompt = pyqtSignal(str)     # 步进模式：等待用户确认
    finished = pyqtSignal(str)        # 工作线程退出原因


class Control:
    """GUI 与工作线程共用的命令队列 + 信号总线"""

    def __init__(self):
        self.commands = queue.Queue()
        self.signals = Signals()

    def send(self, command, payload=None):
        self.commands.put((command, payload))

    def poll(self, timeout=0.0):
        """取出下一条命令，超时返回 None"""
        try:
            if timeout > 0:
                return self.commands.get(timeout=timeout)
            return self.commands.get_nowait()
        except queue.Empty:
            return None

    def drain(self, command=None):
        """丢弃队列中（指定类型的）命令"""
        keep = []
        while True:
            try:
                item = self.commands.get_nowait()
            except queue.Empty:
                break
            if command is not None and item[0] != command:
                keep.append(item)
        for item in keep:
            self.commands.put(item)
