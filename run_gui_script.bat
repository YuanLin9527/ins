@echo off
echo 直接运行Instagram监控工具(GUI版本)的Python脚本...
cd /d %~dp0
set PYTHONPATH=%PYTHONPATH%;%CD%\manual_deps
python instagram_monitor_gui.py > gui_script_output.log 2>&1
echo 程序退出，检查gui_script_output.log文件中的错误信息
pause 