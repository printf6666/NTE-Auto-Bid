# -*- coding: utf-8 -*-
"""屏幕截取：mss 抓取主显示器（物理像素）

grab_region 只抓 OCR 识别框那么大的小矩形（几十 KB），代替全屏 2560×1600
（约 16MB/张）整屏抓取，长时间挂机可大幅降低 CPU 与内存带宽占用。
"""
import mss
import numpy as np


class ScreenCapturer:
    def __init__(self):
        self._mss = mss.mss()
        self._monitor = self._mss.monitors[1]

    def grab(self):
        """返回整屏 BGR 格式 numpy 数组（自检/调试用）"""
        image = self._mss.grab(self._monitor)
        return np.asarray(image)[:, :, :3]

    def grab_region(self, region):
        """只抓 [[x1,y1],[x2,y2]] 矩形区域，返回 BGR numpy 数组"""
        (x1, y1), (x2, y2) = region
        monitor = {"left": int(x1), "top": int(y1),
                   "width": int(x2) - int(x1), "height": int(y2) - int(y1)}
        if monitor["width"] <= 0 or monitor["height"] <= 0:
            return np.zeros((1, 1, 3), dtype=np.uint8)
        monitor["left"] = max(0, monitor["left"])
        monitor["top"] = max(0, monitor["top"])
        image = self._mss.grab(monitor)
        return np.asarray(image)[:, :, :3]

    def close(self):
        self._mss.close()
