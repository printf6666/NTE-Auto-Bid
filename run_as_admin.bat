@echo off
rem 以管理员身份启动异环自动竞拍（游戏带 ACE 反作弊以管理员运行，必须提权否则点击被 UIPI 拦截）
rem 用 pythonw 启动，不留黑色控制台窗口；界面里也可以直接点「开始任务」
setlocal
cd /d "%~dp0"

rem 优先用已装好 PyQt5 的解释器；找不到再退回 PATH 里的 pythonw
set "PY=D:\pytools\pythonw.exe"
if not exist "%PY%" (
    set "PY="
    for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do (
        if not defined PY set "PY=%%i"
    )
)

if not defined PY (
    echo [错误] 没找到 pythonw.exe，请先安装 Python 3 与 PyQt5。
    pause
    exit /b 1
)

echo 使用解释器: %PY%
powershell -NoProfile -Command "Start-Process -FilePath '%PY%' -ArgumentList '\"%~dp0main.py\"' -Verb RunAs"
endlocal
