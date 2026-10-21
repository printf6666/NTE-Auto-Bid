# -*- coding: utf-8 -*-
"""运行日志持久化：按天写入 logs/YYYY-MM-DD.log，启动时回填最近记录

设计要点：
- 常驻文件句柄 + flush，避免每条日志都开关文件（降低 IO 唤醒）
- 跨天自动切换到新文件
- 启动只回填最近 N 条，避免历史过长拖慢界面
- 自动清理超过 keep_days 的旧日志
"""
import threading
import time
from pathlib import Path

LOG_DIR_NAME = "logs"
DEFAULT_KEEP_DAYS = 30
DEFAULT_RESTORE_LINES = 2000


class LogStore:
    """日志文件读写：GUI 日志面板的磁盘后端"""

    def __init__(self, base_dir, keep_days=DEFAULT_KEEP_DAYS):
        self.dir = Path(base_dir) / LOG_DIR_NAME
        self.keep_days = int(keep_days)
        self._lock = threading.Lock()
        self._handle = None
        self._day = None
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self.prune()

    # ------------------------------------------------------------------ 写入
    def _path_for(self, day):
        return self.dir / f"{day}.log"

    def append(self, timestamp, text):
        """追加一条日志；正文中的换行压平成空格，保证一行一条"""
        body = str(text).replace("\r", " ").replace("\n", " ").strip()
        if not body:
            return
        line = f"{timestamp}\t{body}\n"
        day = time.strftime("%Y-%m-%d")
        with self._lock:
            if self._handle is None or self._day != day:
                self._close_locked()
                try:
                    self._handle = open(self._path_for(day), "a", encoding="utf-8")
                    self._day = day
                except OSError:
                    self._handle = None
                    self._day = None
                    return
            try:
                self._handle.write(line)
                self._handle.flush()
            except (OSError, ValueError):
                self._close_locked()

    # ------------------------------------------------------------------ 读取
    def recent(self, limit=DEFAULT_RESTORE_LINES):
        """返回最近 limit 条记录，按时间正序 [(时间, 正文)]"""
        limit = max(1, int(limit))
        collected = []
        try:
            files = sorted(self.dir.glob("*.log"), reverse=True)
        except OSError:
            return collected
        for path in files:
            try:
                with open(path, encoding="utf-8", errors="replace") as file:
                    lines = file.read().splitlines()
            except OSError:
                continue
            for line in reversed(lines):
                if "\t" not in line:
                    continue
                stamp, _, body = line.partition("\t")
                if not body.strip():
                    continue
                collected.append((stamp.strip(), body.strip()))
                if len(collected) >= limit:
                    break
            if len(collected) >= limit:
                break
        collected.reverse()
        return collected

    def last_day(self):
        """最近一条日志所属日期，用于界面提示"""
        try:
            files = sorted(self.dir.glob("*.log"), reverse=True)
        except OSError:
            return ""
        return files[0].stem if files else ""

    # ------------------------------------------------------------------ 维护
    def clear_today(self):
        """清空当天日志（界面「清空」按钮同步清盘，避免重启后又冒出来）"""
        with self._lock:
            self._close_locked()
            try:
                self._path_for(time.strftime("%Y-%m-%d")).unlink(missing_ok=True)
            except OSError:
                pass

    def prune(self):
        """删除超过 keep_days 天的日志文件"""
        if self.keep_days <= 0:
            return
        cutoff = time.time() - self.keep_days * 86400
        try:
            for path in self.dir.glob("*.log"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                except OSError:
                    continue
        except OSError:
            pass

    def close(self):
        with self._lock:
            self._close_locked()

    def _close_locked(self):
        if self._handle is not None:
            try:
                self._handle.close()
            except OSError:
                pass
            self._handle = None
        self._day = None
