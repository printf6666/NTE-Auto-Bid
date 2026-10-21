# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置

构建：
    pyinstaller build.spec --noconfirm --clean

产物：dist/异环自动竞拍/异环自动竞拍.exe（onedir 目录模式）

选 onedir 而非 onefile 的原因：
- onefile 每次启动都要把 300MB+ 内容解压到临时目录，冷启动十几秒、占额外磁盘 IO
- onedir 启动快、内存占用低，更适合长时间挂机
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

APP_NAME = "异环自动竞拍"

# 设 BUILD_CONSOLE=1 可构建带控制台的调试版（能看到启动期报错），产物名加 -debug
DEBUG_BUILD = os.environ.get("BUILD_CONSOLE") == "1"
BUILD_NAME = APP_NAME + ("-debug" if DEBUG_BUILD else "")

# ---- conda 版 PyQt5 的 DLL 修复 -------------------------------------------
# 这套环境里 PyQt5 的 pyd 依赖 `Qt5Core_conda.dll` 这类带 _conda 后缀的名字，
# 而 DLL 实际放在 D:\pytools\Library\bin，PyInstaller 的默认 hook 解析不到，
# 会导致 Qt5/bin 为空、exe 启动即崩。这里显式收集整条依赖链。
CONDA_LIB = r"D:\pytools\Library\bin"
CONDA_ROOT = r"D:\pytools"

QT_DLLS = [
    # Qt 本体
    "Qt5Core_conda.dll", "Qt5Gui_conda.dll", "Qt5Widgets_conda.dll",
    "Qt5Svg_conda.dll", "Qt5PrintSupport_conda.dll",
    # Qt 间接依赖
    "icudt73.dll", "icuin73.dll", "icuuc73.dll",
    "libpng16.dll", "zlib.dll", "zstd.dll",
    "MSVCP140.dll", "MSVCP140_1.dll", "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
    # PIL（rapidocr.utils.vis_res 会导入）依赖的图像库
    "openjp2.dll", "tiff.dll", "libjpeg.dll",
    "libwebp.dll", "libwebpmux.dll", "libwebpdemux.dll", "lcms2.dll",
    # PyYAML 的 C 扩展
    "yaml.dll",
]

binaries = []
for name in QT_DLLS:
    path = os.path.join(CONDA_LIB, name)
    if os.path.exists(path):
        binaries.append((path, "."))
python3_dll = os.path.join(CONDA_ROOT, "python3.dll")
if os.path.exists(python3_dll):
    binaries.append((python3_dll, "."))

# rapidocr 的 onnx 模型、config.yaml 必须按原包结构一起带上
datas = [("config.json", ".")]
datas += collect_data_files("rapidocr", include_py_files=False)

binaries += collect_dynamic_libs("onnxruntime")

hiddenimports = []
hiddenimports += collect_submodules("rapidocr")
hiddenimports += [
    "onnxruntime",
    "onnxruntime.capi._pybind_state",
    "PyQt5.QtSvg",          # theme.py 用 QSvgRenderer 渲染图标
    "PyQt5.QtPrintSupport",  # QTextBrowser 依赖
    "mss",
]

# 明确排除用不到的大件，压缩体积、减少加载开销
excludes = [
    "tkinter", "matplotlib", "pandas", "scipy", "IPython", "jupyter",
    "notebook", "pytest",
    "PyQt5.QtWebEngine", "PyQt5.QtWebEngineCore", "PyQt5.QtWebEngineWidgets",
    "PyQt5.QtWebKit", "PyQt5.QtWebKitWidgets",
    "PyQt5.QtMultimedia", "PyQt5.QtMultimediaWidgets",
    "PyQt5.QtQuick", "PyQt5.QtQml", "PyQt5.QtQuickWidgets", "PyQt5.QtQuick3D",
    "PyQt5.Qt3DCore", "PyQt5.Qt3DRender", "PyQt5.Qt3DInput", "PyQt5.Qt3DLogic",
    "PyQt5.Qt3DAnimation", "PyQt5.Qt3DExtras",
    "PyQt5.QtCharts", "PyQt5.QtDataVisualization",
    "PyQt5.QtBluetooth", "PyQt5.QtNfc", "PyQt5.QtPositioning", "PyQt5.QtLocation",
    "PyQt5.QtSensors", "PyQt5.QtSerialPort", "PyQt5.QtWebSockets", "PyQt5.QtWebChannel",
    "PyQt5.QtDesigner", "PyQt5.QtHelp", "PyQt5.QtTest", "PyQt5.QtSql",
    "PyQt5.QtXmlPatterns", "PyQt5.QtNetworkAuth", "PyQt5.QtRemoteObjects",
    "PyQt5.QtTextToSpeech", "PyQt5.QtX11Extras",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# ---- 精简 conda 的 MKL -----------------------------------------------------
# numpy 只静态依赖 mkl_rt.2.dll，但 PyInstaller 把整套 MKL 内核（约 570MB）都收了。
# 只保留调度层 + 通用/常用内核，其余 AVX512/多线程变体去掉。
MKL_KEEP = {
    "mkl_rt.2.dll",            # 调度层，numpy 直接链接
    "mkl_core.2.dll",          # 核心
    "mkl_intel_thread.2.dll",  # 多线程内核
    "mkl_avx2.2.dll",          # 现代 CPU 主力内核
    "mkl_def.2.dll",           # 通用回退内核
}
a.binaries = [
    entry for entry in a.binaries
    if not (entry[0].lower().startswith("mkl_") and entry[0].lower() not in MKL_KEEP)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=BUILD_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=DEBUG_BUILD,    # 正式版无控制台，调试版保留
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=BUILD_NAME,
)
