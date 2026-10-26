# -*- coding: utf-8 -*-
"""屏幕截取：mss 抓取主显示器（物理像素）

grab_region 只抓 OCR 识别框那么大的小矩形（几十 KB），代替全屏 2560×1600
（约 16MB/张）整屏抓取，长时间挂机可大幅降低 CPU 与内存带宽占用。
截图失败（锁屏/UAC 安全桌面/会话切换瞬间）返回 1×1 黑图而不是抛异常，
让上层按"识别失败"重试，挂机不至于中断。
"""
import logging

import mss
import numpy as np

log = logging.getLogger("yihuan")


class ScreenCapturer:
    def __init__(self):
        self._mss = mss.mss()
        self._monitor = self._mss.monitors[1]

    def grab(self):
        """返回整屏 BGR 格式 numpy 数组（自检/调试用）"""
        return self._grab(self._monitor)

    def grab_region(self, region):
        """只抓 [[x1,y1],[x2,y2]] 矩形区域，返回 BGR numpy 数组（失败返回 1×1 黑图）"""
        (x1, y1), (x2, y2) = region
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = int(x2), int(y2)
        if x2 <= x1 or y2 <= y1:
            return np.zeros((1, 1, 3), dtype=np.uint8)
        # 越界部分裁剪到屏幕内（mss 对越界区域会抛异常）
        x2 = min(x2, x1 + max(0, self._monitor["width"] - x1))
        y2 = min(y2, y1 + max(0, self._monitor["height"] - y1))
        if x2 <= x1 or y2 <= y1:
            return np.zeros((1, 1, 3), dtype=np.uint8)
        return self._grab({"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1})

    def _grab(self, monitor):
        try:
            image = self._mss.grab(monitor)
        except Exception as error:  # noqa: BLE001 锁屏/会话切换瞬间截图会失败
            log.warning("[截屏] 抓取失败（%s），按识别失败处理", error)
            return np.zeros((1, 1, 3), dtype=np.uint8)
        return np.asarray(image)[:, :, :3]

    def close(self):
        self._mss.close()
