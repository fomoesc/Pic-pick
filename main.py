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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # 加载应用图标（同时用于任务栏和标题栏）
    icon_path = _app_dir() / "app_icon.ico"
    if not icon_path.exists():
        icon_path = _app_dir() / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 设置默认中文字体，保证界面全中文正常显示
    app.setFont(QFont("Microsoft YaHei", 10))
    # 应用 v4 现代扁平化主题
    app.setStyleSheet(build_app_qss())
    win = MainWindow()

    # 确保 MainWindow 也使用图标
    if icon_path.exists():
        win.setWindowIcon(QIcon(str(icon_path)))

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
