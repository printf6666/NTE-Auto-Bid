# -*- coding: utf-8 -*-
"""运行统计：局数 / 回合 / 出价次数，存盘到 stats.json（跨自然日自动清零）"""
import json
import threading
import time

_KEYS = ("cycles", "rounds", "bids")


class Stats:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self.data = {"cycles": 0, "rounds": 0, "bids": 0, "day": ""}
        self._load()

    @staticmethod
    def _today():
        return time.strftime("%Y-%m-%d")

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as file:
                raw = json.load(file)
        except Exception:
            raw = {}
        for key in _KEYS:
            try:
                self.data[key] = max(0, int(raw.get(key, 0)))
            except Exception:
                self.data[key] = 0
        self.data["day"] = str(raw.get("day", ""))
        if self.data["day"] != self._today():
            self._zero()
            self._write()

    def _zero(self):
        for key in _KEYS:
            self.data[key] = 0
        self.data["day"] = self._today()

    def _write(self):
        try:
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump(self.data, file, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- 对外 ----------
    def reset(self):
        with self._lock:
            self._zero()
            self._write()

    def add(self, field, amount=1):
        with self._lock:
            if self.data["day"] != self._today():
                self._zero()
            self.data[field] = self.data.get(field, 0) + amount
            self._write()

    def save(self):
        with self._lock:
            self._write()

    def snapshot(self):
        with self._lock:
            return dict(self.data)
