@echo off
echo 开始测试Instagram监控工具(GUI版本)...
cd dist
instagram_monitor_gui.exe > gui_output.log 2>&1
echo 程序退出，检查gui_output.log文件中的错误信息
pause 