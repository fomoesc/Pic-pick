# -*- coding: utf-8 -*-
"""拼版选图导出工作台 — 程序入口。"""
import sys
import os
from pathlib import Path

# Windows: 在创建 QApplication 之前设置 AppUserModelID，确保任务栏图标正确分组
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "com.fomoesc.picpick"
        )
    except Exception:
        pass

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from config import APP_NAME
from style import build_app_qss
from ui import MainWindow


def _find_icon() -> Path | None:
    """查找应用图标文件（ICO 优先，PNG 回退）。

    打包后：图标嵌入在 exe 资源中，同时作为数据文件解压到 sys._MEIPASS。
    开发时：图标在源码目录。
    """
    candidates = ["app_icon.ico", "app_icon.png"]

    # PyInstaller 打包后的临时解压目录
    if getattr(sys, "frozen", False):
        meipass = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else None
        exe_dir = Path(sys.executable).resolve().parent
        search_dirs = [d for d in [meipass, exe_dir] if d]
    else:
        search_dirs = [Path(__file__).resolve().parent]

    for d in search_dirs:
        for name in candidates:
            p = d / name
            if p.exists():
                return p
    return None


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # 加载图标
    icon_path = _find_icon()
    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))

    # 设置默认中文字体
    app.setFont(QFont("Microsoft YaHei", 10))
    # 应用橙色主题
    app.setStyleSheet(build_app_qss())

    win = MainWindow()

    # 再次设置窗口图标（确保任务栏 + 标题栏都显示）
    if icon_path:
        icon = QIcon(str(icon_path))
        win.setWindowIcon(icon)

        # Windows: 通过 Win32 API 强制发送 WM_SETICON 消息
        # 解决 PySide6 在某些 Win10/11 版本上任务栏图标不刷新的问题
        try:
            import ctypes
            hwnd = int(win.winId())
            hicon = int(icon.pixmap(64, 64).toWinHICON())
            # WM_SETICON = 0x0080, ICON_BIG = 1, ICON_SMALL = 0
            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
        except Exception:
            pass

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
