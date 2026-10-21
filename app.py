# -*- coding: utf-8 -*-
"""异环自动竞拍 · 图形界面入口

界面：1280×720 挂机任务窗口（左侧任务/配置，右侧运行日志）
后台：BotWorker 线程跑原有的截屏 → 场景检测 → 动作循环

用法：
    python app.py                直接启动（非管理员时会自动请求提权）
    python app.py --no-elevate   已用管理员身份启动时使用，跳过自提权
    异环自动竞拍.exe              打包版，行为同上

打包说明：BASE_DIR 在打包后指向 exe 所在目录（配置/统计/日志都放这里，可读写），
源码运行时指向脚本目录。二者都不会指向 PyInstaller 的临时解包目录。
"""
import ctypes
import json
import logging
import os
import pathlib
import shutil
import sys
import time

# 必须在任何 PyQt5 导入之前设置。
# 界面按 1440×810 逻辑像素排版，这里把缩放钉成 4/3，
# 屏幕上就是真实的 1920×1080，字体和所有控件同比例放大。
# （不设的话会被系统 150%/200% 缩放再放大一次。）
os.environ.setdefault("QT_SCALE_FACTOR", "1.3333")

FROZEN = bool(getattr(sys, "frozen", False))


def _app_dir():
    """可写数据目录：打包版为 exe 所在目录，源码版为脚本目录"""
    if FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _app_dir()
if not FROZEN and BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def setup_dpi():
    """进程 DPI 感知：保证截屏、鼠标坐标与界面都是物理像素"""
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """以管理员身份重新启动自身（游戏带 ACE 反查，不提权会被 UIPI 拦截）"""
    args = [arg for arg in sys.argv[1:] if arg != "--no-elevate"]
    params = " ".join(f'"{arg}"' for arg in args + ["--no-elevate"])
    executable = sys.executable
    if FROZEN:
        # 打包后 sys.executable 就是 exe 本身，直接重启，不要再拼脚本路径
        arg_line = params
    else:
        if executable.lower().endswith("python.exe"):
            pythonw = executable[:-4] + "w.exe"  # 用 pythonw，避免多留一个控制台
            if os.path.exists(pythonw):
                executable = pythonw
        arg_line = f'"{os.path.abspath(__file__)}" {params}'
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, arg_line, BASE_DIR, 1)
        return result > 32
    except Exception:
        return False


def load_config():
    """优先读 exe/脚本同目录的 config.json；打包版首次运行从内置副本释放一份"""
    target = os.path.join(BASE_DIR, "config.json")
    if not os.path.exists(target) and FROZEN:
        bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "config.json")
        if os.path.exists(bundled):
            try:
                shutil.copyfile(bundled, target)
            except OSError:
                pass
    with open(target, encoding="utf-8-sig") as file:
        return json.load(file)


def fatal(message):
    """启动期致命错误：打包版弹窗（无控制台），源码版打印"""
    print(f"[致命] {message}")
    if FROZEN:
        try:
            ctypes.windll.user32.MessageBoxW(
                None, str(message), "异环自动竞拍 · 启动失败", 0x10)
        except Exception:
            pass


def selftest():
    """打包自检：验证 numpy / opencv / onnxruntime / OCR 模型是否都能正常加载"""
    import numpy as np
    import cv2
    from ocr import OCREngine

    config = load_config()
    engine = OCREngine(config)
    image = np.full((90, 420, 3), 255, dtype=np.uint8)
    cv2.putText(image, "1,342,500", (12, 68), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 0, 0), 4)
    text = engine.read(image, [[0, 0], [420, 90]])
    ok = "1342" in text.replace(",", "").replace(" ", "")
    message = (f"numpy {np.__version__}\nopencv {cv2.__version__}\n"
               f"识别结果：{text!r}\n\n自检{'通过' if ok else '未通过（识别结果不符）'}")
    print(message)
    if FROZEN:
        try:
            ctypes.windll.user32.MessageBoxW(None, message, "异环自动竞拍 · 自检", 0x40)
        except Exception:
            pass
    return 0 if ok else 1


def main():
    setup_dpi()
    if "--selftest" in sys.argv:
        return selftest()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    logging.getLogger("RapidOCR").setLevel(logging.ERROR)

    if "--no-elevate" not in sys.argv and not is_admin():
        if relaunch_as_admin():
            return 0

    from bus import Command, ConfigHolder, Control
    from stats import Stats
    from ui import MainWindow, create_app
    from worker import BotWorker, ThreadLogHandler

    try:
        config = load_config()
    except Exception as error:
        fatal(f"读取 config.json 失败：{error}\n\n请确认 config.json 与本程序在同一目录。")
        return 1

    app = create_app()
    holder = ConfigHolder(config, pathlib.Path(BASE_DIR))
    control = Control()
    stats = Stats(os.path.join(BASE_DIR, "stats.json"))

    logger = logging.getLogger("yihuan")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.addHandler(ThreadLogHandler(control))

    window = MainWindow(holder, control, stats)
    window.show()
    window.log_panel.append(time.strftime("%H:%M:%S"),
                            "[界面] 准备就绪，点击「开始任务」启动挂机" if not is_admin()
                            else "[界面] 准备就绪（管理员权限），点击「开始任务」启动挂机")

    # 工作线程由主窗口按需拉起：开始 → 新建线程；停止后线程自然退出
    class Runtime:
        def __init__(self):
            self.worker = None

        def start(self):
            if self.worker is not None and self.worker.is_alive():
                return  # 已在运行
            self.worker = BotWorker(control, holder, stats)
            self.worker.start()

        def stop(self):
            control.send(Command.STOP)

        def shutdown(self):
            control.send(Command.STOP)
            if self.worker is not None:
                self.worker.join(timeout=3.0)

    runtime = Runtime()
    control.drain()
    window.attach_runtime(runtime)

    code = app.exec_()
    runtime.shutdown()
    stats.save()
    return code


if __name__ == "__main__":
    sys.exit(main())
