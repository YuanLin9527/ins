@echo off
echo 以控制台模式测试Instagram监控工具(GUI版本)...
cd dist
start cmd /k "echo 正在启动GUI应用程序... && instagram_monitor_gui.exe"
echo 请查看新打开的命令窗口中的输出信息
pause 