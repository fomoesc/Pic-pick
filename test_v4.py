# -*- coding: utf-8 -*-
"""v4 自测：子文件夹分组展示 + 封面功能 + UI 逻辑。

覆盖：
  1. build_groups：有子文件夹分组 / 根目录散落归「根目录」/ 无子文件夹扁平
  2. 封面导出：文件名=文件夹名、无编号、扩展名跟随、去重、只导封面
  3. UI 分组展示：子文件夹区块 + 折叠
  4. 封面按钮互斥 + 跨文件夹保留
  5. 漏选统计考虑封面
  6. PDF 页不显示封面按钮
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
import exporter
from scanner import WorkFolder

tmp = Path(tempfile.mkdtemp(prefix="v4_"))
print("临时目录:", tmp)

# ---------- 1. build_groups ----------
print("\n=== 1. build_groups 分组 ===")
work = tmp / "Demo"
(work / "SubA").mkdir(parents=True)
(work / "SubB").mkdir(parents=True)
red = Image.new("RGB", (60, 60), (200, 30, 30))
blue = Image.new("RGB", (60, 60), (30, 30, 200))
green = Image.new("RGB", (60, 60), (30, 200, 30))
red.save(work / "SubA" / "page-2.jpg")
blue.save(work / "SubA" / "page-1.jpg")
green.save(work / "SubB" / "a.jpg")
Image.new("RGB", (60, 60), (90, 90, 90)).save(work / "root.jpg")  # 根目录散落

# 生成一个单页 PDF 放入 SubB
pdf_doc = fitz.open()
pdf_doc.new_page()
pdf_doc.save(str(work / "SubB" / "manual.pdf"))
pdf_doc.close()

groups = scanner.build_groups(work)
names = [g.name for g in groups]
print("分组:", names)
assert names == ["SubA", "SubB", "根目录"], f"分组名错误: {names}"
assert groups[0].image_count == 2
assert groups[1].image_count == 1 and groups[1].pdf_count == 1 and groups[1].pdf_page_count == 1
assert groups[2].image_count == 1 and groups[2].name == "根目录"
print("分组正确 ✓")

# 无子文件夹 → 空列表
flat = tmp / "Flat"
flat.mkdir()
red.save(flat / "x.jpg")
assert scanner.build_groups(flat) == []
print("无子文件夹返回空（扁平模式）✓")

# ---------- 2. 封面导出 ----------
print("\n=== 2. 封面导出 ===")
out = tmp / "out"
f = WorkFolder(name="Demo", path=work)
f.images, f.pdfs = scanner.collect_media(work)
f.groups = groups
items = f.ordered_items()
img_items = [it for it in items if it.kind == "image"]
cover_id = next(it.id for it in img_items if it.path.name == "page-1.jpg")
sel = {it.id: True for it in img_items if it.path.name == "root.jpg"}
covers = {"Demo": cover_id}

success, skipped, failed = exporter.export_all([f], sel, str(out), covers=covers)
out_names = sorted(p.name for p in out.iterdir())
print("导出:", out_names)
assert "Demo.jpg" in out_names and "Demo (1).jpg" in out_names and len(out_names) == 2
print("封面命名 + 编号正确 ✓")

# 只设封面不勾其他 → 只导封面
out2 = tmp / "out2"
exporter.export_all([f], {}, str(out2), covers=covers)
assert sorted(p.name for p in out2.iterdir()) == ["Demo.jpg"]
print("只导封面正确 ✓")

# 全勾选（含封面）→ 封面去重
out3 = tmp / "out3"
sel3 = {it.id: True for it in items}
exporter.export_all([f], sel3, str(out3), covers=covers)
# 封面 1 + 其余（page-2, a, root, pdf页）共 5
assert len(list(out3.iterdir())) == 5, f"应 5 张: {sorted(p.name for p in out3.iterdir())}"
print("封面去重正确 ✓")

# ---------- 3~6. UI ----------
print("\n=== 3. UI 分组展示 + 封面 ===")
from PySide6.QtWidgets import QApplication
from ui import MainWindow, CollapsibleGroup

app = QApplication([])
w = MainWindow()

# 载入带分组的 Demo
w.work_folders = [f]
w.generation = 1
w.item_folder = {}
w.on_load_ready(1, "Demo", items, f.groups)

# 验证分组区块数量
colls = []
for i in range(w.preview_inner.count()):
    wid = w.preview_inner.itemAt(i).widget()
    if isinstance(wid, CollapsibleGroup):
        colls.append(wid)
print("分组区块数:", len(colls), "(应 3)")
assert len(colls) == 3, f"应 3 个分组区块: {len(colls)}"
print("标题文本:", [c.header.text() for c in colls])

# 验证 thumb_widgets 数量 = 图片 4 + pdf 1 页 = 5
print("thumb_widgets 数:", len(w.thumb_widgets), "(应 5)")
assert len(w.thumb_widgets) == 5

# 验证折叠：点标题后 body 隐藏
first = colls[0]
assert first._expanded is True
first.header.setChecked(False)
assert first._expanded is False and first.body.isHidden()
first.header.setChecked(True)
assert first._expanded is True and not first.body.isHidden()
print("折叠/展开正常 ✓")

# ---------- 4. 封面互斥 + 跨文件夹保留 ----------
print("\n=== 4. 封面互斥 + 跨文件夹保留 ===")
# 第一张图片设为封面
img_ids = [it.id for it in img_items]
w.on_cover_clicked("Demo", img_ids[0])
assert w.covers.get("Demo") == img_ids[0]
print("设封面 1:", img_ids[0].split(":")[-1])

# 设第二张 → 取消第一张
w.on_cover_clicked("Demo", img_ids[1])
assert w.covers.get("Demo") == img_ids[1]
# 第一张 widget 的封面状态应为 False
w0 = w.thumb_widgets.get(img_ids[0])
w1 = w.thumb_widgets.get(img_ids[1])
assert w0._is_cover is False and w1._is_cover is True
print("互斥：封面已从", img_ids[0].split(":")[-1], "切到", img_ids[1].split(":")[-1], "✓")

# 点同一张 → 取消封面
w.on_cover_clicked("Demo", img_ids[1])
assert "Demo" not in w.covers
assert w1._is_cover is False
print("点已选封面取消 ✓")

# 跨文件夹保留：再建一个文件夹 B
workB = tmp / "DemoB"
workB.mkdir()
Image.new("RGB", (60, 60), (10, 20, 30)).save(workB / "b1.jpg")
Image.new("RGB", (60, 60), (40, 50, 60)).save(workB / "b2.jpg")
fB = WorkFolder(name="DemoB", path=workB)
fB.images, fB.pdfs = scanner.collect_media(workB)
fB.groups = scanner.build_groups(workB)
itemsB = fB.ordered_items()

w.work_folders = [f, fB]
w.generation = 2
w.on_load_ready(2, "DemoB", itemsB, fB.groups)

w.on_cover_clicked("Demo", img_ids[0])   # 给 Demo 设封面
w.on_cover_clicked("DemoB", itemsB[0].id)  # 给 DemoB 设封面
assert w.covers.get("Demo") == img_ids[0]
assert w.covers.get("DemoB") == itemsB[0].id
print("跨文件夹封面保留: Demo ->", img_ids[0].split(":")[-1],
      ", DemoB ->", itemsB[0].path.name, "✓")

# ---------- 5. 漏选统计考虑封面 ----------
print("\n=== 5. 漏选统计考虑封面 ===")
# 清空勾选，只保留封面
w.selection = {}
missed = w._missed_folders()
missed_names = [x.name for x in missed]
print("漏选(仅封面):", missed_names)
# Demo 和 DemoB 都设了封面，均不算漏
assert missed_names == [], f"设封面的文件夹不应漏选: {missed_names}"
# 取消一个封面，则那个文件夹应漏选
w.covers.pop("DemoB", None)
missed2 = [x.name for x in w._missed_folders()]
print("漏选(取消DemoB封面):", missed2)
assert missed2 == ["DemoB"], f"应漏 DemoB: {missed2}"
print("漏选统计正确 ✓")

# ---------- 6. PDF 页与图片均有封面按钮 ----------
print("\n=== 6. PDF 页与图片均有封面按钮 ===")
# 清空所有封面，确保初始状态全部显示按钮
w.covers = {}
w.generation = 3
w.on_load_ready(3, "Demo", items, f.groups)
pdf_widget = None
for it in items:
    if it.kind == "pdf":
        pdf_widget = w.thumb_widgets.get(it.id)
        break
assert pdf_widget is not None
assert pdf_widget.cover_btn.isHidden() is False, "PDF 页应显示封面按钮"
img_widget = w.thumb_widgets.get(img_items[0].id)
assert img_widget.cover_btn.isHidden() is False, "图片应显示封面按钮"
print("PDF 页与图片均有封面按钮 ✓")

# ---------- 7. 封面互斥：选中后其他按钮隐藏，取消后恢复 ----------
print("\n=== 7. 封面互斥 ===")
# 设 PDF 页为封面
pdf_id = next(it.id for it in items if it.kind == "pdf")
w.on_cover_clicked("Demo", pdf_id)
assert w.covers.get("Demo") == pdf_id
# 封面那张按钮应可见，其余（含图片）按钮应隐藏
for it in items:
    wdg = w.thumb_widgets.get(it.id)
    if it.id == pdf_id:
        assert wdg.cover_btn.isHidden() is False, "封面 PDF 页按钮应可见"
        assert wdg._is_cover is True
    else:
        assert wdg.cover_btn.isHidden() is True, f"{it.label} 的封面按钮应隐藏"
print("选 PDF 页为封面后，仅封面按钮可见，其余隐藏 ✓")

# 取消封面 → 所有按钮恢复显示
w.on_cover_clicked("Demo", pdf_id)
assert "Demo" not in w.covers
for it in items:
    wdg = w.thumb_widgets.get(it.id)
    assert wdg.cover_btn.isHidden() is False, f"取消封面后 {it.label} 的按钮应恢复显示"
print("取消封面后所有按钮恢复显示 ✓")

# ---------- 8. PDF 页设为封面 → 导出文件名 = 文件夹名.jpg ----------
print("\n=== 8. PDF 页封面导出 ===")
out4 = tmp / "out4"
w.on_cover_clicked("Demo", pdf_id)  # 设 PDF 页为封面
covers_pdf = {"Demo": pdf_id}
# 不勾选任何项，只导封面
exporter.export_all([f], {}, str(out4), covers=covers_pdf)
pdf_cover_names = sorted(p.name for p in out4.iterdir())
print("PDF 封面导出:", pdf_cover_names)
assert pdf_cover_names == ["Demo.jpg"], f"PDF 封面应导出为 Demo.jpg: {pdf_cover_names}"
# 校验导出的是 jpg 图片
from PIL import Image as _Img
with _Img.open(out4 / "Demo.jpg") as _im:
    assert _im.format == "JPEG", f"应为 JPEG: {_im.format}"
print("PDF 页封面导出文件名 = Demo.jpg（JPEG）✓")
# 恢复：清空封面
w.on_cover_clicked("Demo", pdf_id)

w.threadpool.waitForDone(5000)

shutil.rmtree(tmp, ignore_errors=True)
print("\nALL_V4_TESTS_PASSED")
