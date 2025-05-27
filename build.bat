@echo off
echo ===== 开始打包Instagram监控工具 =====

echo 1. 安装PyInstaller...
pip install pyinstaller

echo 2. 清理旧的打包文件...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del instagram_monitor.spec 2>nul

echo 3. 开始打包...
python -m PyInstaller --onefile ^
    --add-data "manual_deps;manual_deps" ^
    --add-data "mock_instagrapi.py;." ^
    --hidden-import=plyer.platforms.win.notification ^
    --hidden-import=configparser ^
    --hidden-import=threading ^
    --name=instagram_monitor instagram_monitor.py

echo 4. 复制额外资源文件...
if not exist "dist" mkdir dist
if not exist "dist\manual_deps\instagrapi" mkdir "dist\manual_deps\instagrapi"
copy mock_instagrapi.py dist\ 2>nul
xcopy /s /y manual_deps dist\manual_deps\ 2>nul

echo ===== 打包完成! =====
echo 可执行文件位于: dist\instagram_monitor.exe
echo. 