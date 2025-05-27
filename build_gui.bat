@echo off
echo ===== 开始打包Instagram监控工具(GUI版本) =====

echo 1. 安装必要依赖...
pip install pyinstaller matplotlib pycryptodome pywin32 requests plyer instagrapi

echo 2. 清理旧的打包文件...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del instagram_monitor_gui.spec 2>nul

echo 3. 开始打包...
python -m PyInstaller --onefile --windowed instagram_monitor_gui.py ^
    --hidden-import=instagrapi ^
    --hidden-import=tzdata

echo 4. 复制额外资源文件...
if not exist "dist" mkdir dist
copy browser_cookie_extractor.py dist\ 2>nul
copy instagram_monitor.py dist\ 2>nul

echo 5. 创建示例Cookie文件...
echo 正在创建示例Cookie文件，供测试使用...
(
echo [
echo   {
echo     "name": "sessionid",
echo     "value": "替换为真实会话ID",
echo     "domain": ".instagram.com",
echo     "path": "/"
echo   },
echo   {
echo     "name": "csrftoken",
echo     "value": "替换为真实CSRF令牌",
echo     "domain": ".instagram.com", 
echo     "path": "/"
echo   },
echo   {
echo     "name": "ds_user_id",
echo     "value": "替换为真实用户ID",
echo     "domain": ".instagram.com",
echo     "path": "/"
echo   }
echo ]
) > dist\example_cookie.json

echo ===== 打包完成! =====
echo 可执行文件位于: dist\instagram_monitor_gui.exe
echo. 