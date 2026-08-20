# -*- coding: utf-8 -*-
"""GUI 冒烟测试（offscreen，不弹窗）。

验证：MainWindow 实例化 → 扫描结果构建列表 → 选中文件夹触发后台
LoadTask/ThumbTask → 事件循环处理信号 → 缩略图真实填充到 widget。
"""
import os
import sys
import io

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from ui import MainWindow
import scanner

SRC = r"F:\52纸模网\纸模型资源存储\已发布\[Answer-Angraf]\已上传"

app = QApplication([])
w = MainWindow()

# 同步扫描（测试用，不走线程）
folders = scanner.scan_source_dir(SRC)
for f in folders:
    f.images, f.pdfs = scanner.collect_media(f.path)
    f.is_processed = False

# 模拟扫描完成
w.on_scan_done(folders)
print("[GUI] 列表项数 =", w.folder_list.count())
print("[GUI] 首项文本 =", w.folder_list.item(0).text())

# 选中 Fuso（含图片 + PDF 两类）
target = None
for i in range(w.folder_list.count()):
    it = w.folder_list.item(i)
    if "Fuso A4" in it.text():
        target = it
        break
w.folder_list.setCurrentItem(target)
print("[GUI] 已选中:", target.text())


def check():
    filled = sum(1 for wid in w.thumb_widgets.values()
                 if wid.thumb.pixmap() is not None
                 and not wid.thumb.pixmap().isNull())
    print(f"[GUI] 缩略图缓存 = {len(w.thumb_cache)} 项")
    print(f"[GUI] 当前 widget = {len(w.thumb_widgets)} 个")
    print(f"[GUI] 已填充缩略图 = {filled} 个")
    app.quit()


QTimer.singleShot(9000, check)
app.exec()
print("GUI_TEST_DONE")
