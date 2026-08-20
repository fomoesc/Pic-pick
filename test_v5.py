# -*- coding: utf-8 -*-
"""v5 自测：6 项小优化。

覆盖：
  1. 工具名称（APP_NAME）
  2. 多个 PDF 分开显示（每个 PDF 文件一个可折叠区块）
  3. 设封面自动勾选 / 取消封面勾选保留
  4. 复选框对勾图标（QSS image + PNG 生成）
  5. 标题栏按钮尺寸统一
  6. 窗口透明背景（圆角前置条件）
"""
import os
import sys
import io
import tempfile
import shutil
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from PIL import Image
import pymupdf as fitz

import scanner
from scanner import WorkFolder

tmp = Path(tempfile.mkdtemp(prefix="v5_"))
print("临时目录:", tmp)

# ---------- 1. 工具名称 ----------
print("\n=== 1. 工具名称 ===")
import config
assert config.APP_NAME == "拼版选图导出工作台", config.APP_NAME
print("APP_NAME =", config.APP_NAME, "✓")

# ---------- 准备：1 个作品文件夹，含 1 图 + 2 个多页 PDF ----------
work = tmp / "Demo"
work.mkdir()
Image.new("RGB", (60, 60), (200, 30, 30)).save(work / "a.jpg")

pdf1 = fitz.open()
pdf1.new_page(); pdf1.new_page()          # 2 页
pdf1.save(str(work / "file1.pdf"))
pdf1.close()
pdf2 = fitz.open()
pdf2.new_page()                            # 1 页
pdf2.save(str(work / "file2.pdf"))
pdf2.close()

f = WorkFolder(name="Demo", path=work)
f.images, f.pdfs = scanner.collect_media(work)
f.groups = scanner.build_groups(work)      # 无子文件夹 → []
items = f.ordered_items()

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication
from ui import MainWindow, CollapsibleGroup

app = QApplication([])
w = MainWindow()

# ---------- 2. 多个 PDF 分开显示 ----------
print("\n=== 2. 多个 PDF 分开显示 ===")
pdf_items = [it for it in items if it.kind == "pdf"]
split = w._pdf_items_by_file(pdf_items)
print("按文件拆分:", [(name, cnt) for name, cnt, _ in split])
assert len(split) == 2, f"应 2 个 PDF 文件: {len(split)}"
assert split[0][0] == "file1.pdf" and split[0][1] == 2
assert split[1][0] == "file2.pdf" and split[1][1] == 1
print("_pdf_items_by_file 正确 ✓")

# 扁平展示（无子文件夹）
w.work_folders = [f]
w.generation = 1
w.item_folder = {}
w.on_load_ready(1, "Demo", items, f.groups)

colls = []
for i in range(w.preview_layout.count()):
    wid = w.preview_layout.itemAt(i).widget()
    if isinstance(wid, CollapsibleGroup):
        colls.append(wid)
print("扁平模式 PDF 折叠区块数:", len(colls), "(应 2)")
print("区块标题:", [c.header.text() for c in colls])
assert len(colls) == 2, f"扁平模式应有 2 个 PDF 区块: {len(colls)}"
assert "file1.pdf（2页）" in colls[0].header.text()
assert "file2.pdf（1页）" in colls[1].header.text()
print("扁平模式每个 PDF 一个区块 ✓")

# ---------- 3. 设封面自动勾选 / 取消保留勾选 ----------
print("\n=== 3. 封面自动勾选 ===")
img_items = [it for it in items if it.kind == "image"]
img_id = img_items[0].id
w.on_cover_clicked("Demo", img_id)
assert w.covers.get("Demo") == img_id
assert w.selection.get(img_id) is True, "设封面应自动勾选"
w0 = w.thumb_widgets.get(img_id)
assert w0._checked is True and w0.check.isChecked() is True
print("设封面自动勾选 ✓")

w.on_cover_clicked("Demo", img_id)   # 再点同一张 → 取消封面
assert "Demo" not in w.covers
assert w.selection.get(img_id) is True, "取消封面后勾选应保留"
assert w0._checked is True, "取消封面后 widget 勾选应保留"
print("取消封面勾选保留 ✓")

# ---------- 4. 复选框对勾图标 ----------
print("\n=== 4. 复选框对勾图标 ===")
from style import build_app_qss
import style as _style
qss = build_app_qss()
assert "image: url(" in qss, "QSS 应含对勾 image url"
assert "pbb_check.png" in qss
assert "QFrame#appStatusBar" in qss
icon_path = Path(_style._CHECK_ICON_PATH)
assert icon_path.exists(), f"对勾图标应已生成: {icon_path}"
print("对勾图标已生成:", _style._CHECK_ICON_PATH, "✓")

# ---------- 5. 标题栏按钮尺寸统一 ----------
print("\n=== 5. 标题栏按钮尺寸 ===")
tb = w.title_bar
sizes = [(b.width(), b.height()) for b in (tb.min_btn, tb.max_btn, tb.close_btn)]
print("按钮尺寸 (宽, 高):", sizes)
assert tb.min_btn.width() == 36 and tb.min_btn.height() == 32
assert tb.max_btn.width() == 36 and tb.max_btn.height() == 32
assert tb.close_btn.width() == 36 and tb.close_btn.height() == 32
print("三按钮尺寸统一为 36×32 ✓")

# ---------- 6. 窗口圆角遮罩 ----------
print("\n=== 6. 窗口圆角遮罩 ===")
assert not w.mask().isEmpty(), "setMask 圆角遮罩应已设置"
mask = w.mask()
W, H = w.width(), w.height()
# 四角应在圆角外（mask 不含），中心应在圆角内
assert not mask.contains(QPoint(0, 0)), "左上角应在圆角外"
assert not mask.contains(QPoint(W - 1, 0)), "右上角应在圆角外"
assert not mask.contains(QPoint(0, H - 1)), "左下角应在圆角外"
assert not mask.contains(QPoint(W - 1, H - 1)), "右下角应在圆角外"
assert mask.contains(QPoint(W // 2, H // 2)), "中心应在圆角内"
assert w.centralWidget().objectName() == "rootContainer"
print("setMask 圆角几何正确（四角在圆角外、中心在圆角内）✓")

w.threadpool.waitForDone(5000)
shutil.rmtree(tmp, ignore_errors=True)
print("\nALL_V5_TESTS_PASSED")
