# -*- coding: utf-8 -*-
"""拼版选图导出工作台 — 程序入口。"""
import sys
import os
from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from config import APP_NAME
from style import build_app_qss
from ui import MainWindow


def _app_dir() -> Path:
    """程序所在目录：打包后为 exe 所在目录，开发时为源码目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _set_taskbar_icon(icon_path: Path):
    """用 Windows API 设置任务栏图标（解决开发环境下任务栏显示 Python 默认图标的问题）。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # Windows AppUserModelID 让任务栏把同一 app 归为一组
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "com.fomoesc.picpick.v5"
        )
        # 设置 exe 图标（仅打包后有效）
        if getattr(sys, "frozen", False):
            ctypes.windll.user32.SetWindowIconW(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
    except Exception:
        pass


def main():
    _set_taskbar_icon(None)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # 加载应用图标（同时用于任务栏和标题栏）
    icon_path = _app_dir() / "app_icon.ico"
    if not icon_path.exists():
        icon_path = _app_dir() / "app_icon.png"

    icon = QIcon()
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)

    # 设置默认中文字体，保证界面全中文正常显示
    app.setFont(QFont("Microsoft YaHei", 10))
    # 应用 v4 现代扁平化主题
    app.setStyleSheet(build_app_qss())
    win = MainWindow()

    # 确保 MainWindow 也使用图标（任务栏 + 标题栏）
    if not icon.isNull():
        win.setWindowIcon(icon)
        # Windows 任务栏强制刷新图标
        try:
            import ctypes
            hwnd = int(win.winId())
            WM_SETICON = 0x0080
            ICON_BIG = 1
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG,
                                              icon.pixmap(64, 64).toWinHICON())
        except Exception:
            pass

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
