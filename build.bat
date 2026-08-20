@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==== Building 拼版选图导出工作台 v5.0.1 ====
python -m PyInstaller "拼版选图导出工作台.spec" --clean --noconfirm
echo.
echo ==== Done. EXE is in dist\ folder ====
pause
