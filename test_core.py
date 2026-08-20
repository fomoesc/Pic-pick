# -*- coding: utf-8 -*-
"""核心链路自测（不启动 GUI）。

覆盖：扫描 → ordered_items（含 PDF 页数）→ 图片/PDF 缩略图
      → PDF 页渲染 → 导出命名 → 跳过同名文件 → 已处理判定。
导出使用临时目录，不污染真实输出目录。
"""
import sys
import io
import tempfile
import shutil
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import scanner
import pdf_render
import thumbnail
import exporter
from config import PDF_EXPORT_ZOOM

SRC = r"F:\52纸模网\纸模型资源存储\已发布\[Answer-Angraf]\已上传"

# 1. 扫描
folders = scanner.scan_source_dir(SRC)
print(f"[扫描] 作品文件夹数 = {len(folders)}")
total_img = 0
total_pdf = 0
for f in folders:
    f.images, f.pdfs = scanner.collect_media(f.path)
    total_img += len(f.images)
    total_pdf += len(f.pdfs)
print(f"[扫描] 图片总数 = {total_img}, PDF 总数 = {total_pdf}")

# 2. 找到 Fuso 混合样例
fuso = next(f for f in folders if "Fuso A4" in f.name)
print(f"[样例] {fuso.name}: 图片 {len(fuso.images)} 张, PDF {len(fuso.pdfs)} 个")

# 3. ordered_items（含 PDF 页数）
items = fuso.ordered_items()
img_items = [i for i in items if i.kind == "image"]
pdf_items = [i for i in items if i.kind == "pdf"]
print(f"[items] 共 {len(items)} 项：图片 {len(img_items)}，PDF 页 {len(pdf_items)}")

# 4. 图片缩略图
qimg = thumbnail.make_thumb(img_items[0])
print(f"[缩略图] 图片缩略图尺寸 = {qimg.width()}x{qimg.height()}")

# 5. PDF 缩略图
qimg2 = thumbnail.make_thumb(pdf_items[0])
print(f"[缩略图] PDF 页缩略图尺寸 = {qimg2.width()}x{qimg2.height()}")

# 6. PDF 页渲染（导出尺寸）
pil = pdf_render.render_pdf_page(pdf_items[0].path, pdf_items[0].page_index, PDF_EXPORT_ZOOM)
print(f"[PDF渲染] 导出尺寸 = {pil.size}")

# 7. 导出测试（临时目录），勾选前 3 项（图 + 图 + PDF 页）
tmp = tempfile.mkdtemp(prefix="test_export_")
selection = {it.id: True for it in items[:3]}
success, skipped, failed = exporter.export_all([fuso], selection, tmp)
print(f"[导出1] 成功 {success}, 跳过 {len(skipped)}, 失败 {len(failed)}")
for p in sorted(Path(tmp).iterdir()):
    print("    生成:", p.name, p.stat().st_size, "bytes")

# 8. 跳过测试：再次导出同样勾选，应全部跳过
success2, skipped2, failed2 = exporter.export_all([fuso], selection, tmp)
print(f"[导出2] 成功 {success2}, 跳过 {len(skipped2)}, 失败 {len(failed2)}")
for name, label, reason in skipped2:
    print("    跳过:", name, "|", label, "|", reason)

# 9. 已处理判定
print("[已处理]", fuso.name, "->", scanner.is_folder_processed(fuso.name, tmp))

shutil.rmtree(tmp, ignore_errors=True)
print("TEST_DONE")
