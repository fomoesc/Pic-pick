# -*- coding: utf-8 -*-
"""v3 自测：图片格式扩展 + 文件夹快速切换（键盘/手势）。

覆盖：
  1. 格式识别（10 种扩展名全集）
  2. GIF 缩略图取第一帧、导出原样复制保留动画（.gif 扩展名）
  3. avif/webp/bmp/tif/jfif 缩略图不崩溃
  4. 损坏文件返回占位图、不崩溃
  5. 导出扩展名跟随源文件
  6. 方向键切换 + PageUp/PageDown 翻页
  7. 右键拖动手势：默认关闭不触发，开启后触发
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
from PySide6.QtCore import QEvent, Qt, QPointF
from PySide6.QtGui import QKeyEvent, QMouseEvent, QImage

import scanner
import exporter
import thumbnail
from scanner import WorkFolder, collect_media

tmp = Path(tempfile.mkdtemp(prefix="v3_"))
print("临时目录:", tmp)

# ---------- 1. 构造 10 种格式样例 ----------
work = tmp / "Demo"
work.mkdir()

def make_sample():
    base = Image.new("RGB", (80, 80), (200, 30, 30))
    # 各格式（用 PIL 能保存的）
    base.save(work / "a.jpg", "JPEG")
    base.save(work / "b.jpeg", "JPEG")
    base.save(work / "c.png", "PNG")
    base.save(work / "d.bmp", "BMP")
    base.save(work / "e.webp", "WEBP")
    base.save(work / "f.tif", "TIFF")
    base.save(work / "g.tiff", "TIFF")
    base.save(work / "h.jfif", "JPEG")  # jfif 本质是 JPEG
    base.save(work / "i.avif", "AVIF")
    # GIF 动画：2 帧（第 1 帧红、第 2 帧蓝）
    f1 = Image.new("RGB", (80, 80), (255, 0, 0))
    f2 = Image.new("RGB", (80, 80), (0, 0, 255))
    f1.save(work / "j.gif", save_all=True, append_images=[f2], duration=100, loop=0)

make_sample()

print("\n=== 1. 格式识别 ===")
imgs, pdfs = collect_media(work)
got_exts = sorted(p.suffix.lower() for p in imgs)
print("识别到的扩展名:", got_exts)
expect_exts = ['.avif', '.bmp', '.gif', '.jfif', '.jpeg', '.jpg', '.png', '.tif', '.tiff', '.webp']
assert got_exts == expect_exts, f"格式识别错误: {got_exts}"

# ---------- 2. GIF 缩略图取第一帧 ----------
print("\n=== 2. GIF 缩略图第一帧 ===")
gif_path = work / "j.gif"
qimg = thumbnail.make_image_thumb(gif_path)
assert not qimg.isNull(), "gif 缩略图为空"
print("gif 缩略图尺寸:", qimg.width(), "x", qimg.height())

def center_rgb(qi: QImage):
    qi = qi.convertToFormat(QImage.Format_RGB888)
    c = qi.pixel(qi.width() // 2, qi.height() // 2)
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)

r, g, b = center_rgb(qimg)
print("gif 缩略图中心像素 RGB:", (r, g, b), "(第一帧应为红)")
assert r > 200 and g < 80 and b < 80, f"gif 未取第一帧（红），得到 {(r,g,b)}"

# ---------- 3. 各格式缩略图不崩溃 ----------
print("\n=== 3. 各格式缩略图不崩溃 ===")
for p in sorted(work.iterdir()):
    q = thumbnail.make_image_thumb(p)
    assert not q.isNull(), f"{p.name} 缩略图为空"
print("全部", len(list(work.iterdir())), "个格式缩略图生成成功，无崩溃")

# ---------- 4. 损坏文件返回占位图 ----------
print("\n=== 4. 损坏文件占位图 ===")
bad = work / "bad.jpg"
bad.write_bytes(b"not a real image")
qb = thumbnail.make_image_thumb(bad)
assert not qb.isNull(), "损坏文件应返回占位图而非空"
qb = qb.convertToFormat(QImage.Format_RGB888)
c = qb.pixel(3, 3)  # 左上角角落，避开居中文字
pr, pg, pb = ((c >> 16) & 255, (c >> 8) & 255, c & 255)
print("损坏文件占位图角落 RGB:", (pr, pg, pb), "(应为浅灰 ~238)")
assert pr >= 230 and pg >= 230 and pb >= 230, "占位图应是浅灰底"
bad.unlink()

# ---------- 5. 导出扩展名跟随源文件 + GIF 保留动画 ----------
print("\n=== 5. 导出扩展名 + GIF 动画保留 ===")
out = tmp / "out"
f = WorkFolder(name="Demo", path=work)
f.images, f.pdfs = collect_media(work)
items = f.ordered_items()
sel = {it.id: True for it in items}
success, skipped, failed = exporter.export_all([f], sel, str(out))
print("导出成功数:", success, "跳过:", len(skipped), "失败:", len(failed))
assert success == 10 and not skipped and not failed, f"导出异常: 成功{success} 跳过{len(skipped)} 失败{len(failed)}"

out_files = list(out.iterdir())
out_names = [p.name for p in out_files]
print("导出文件名:")
for n in sorted(out_names, key=scanner.natural_key):
    print("  ", n)
# 验证扩展名逐一对应（图片在前按自然排序，扩展名跟随源文件）
expect_names = [
    "Demo (1).jpg", "Demo (2).jpeg", "Demo (3).png", "Demo (4).bmp",
    "Demo (5).webp", "Demo (6).tif", "Demo (7).tiff", "Demo (8).jfif",
    "Demo (9).avif", "Demo (10).gif",
]
assert set(out_names) == set(expect_names), f"导出文件集合不符: {set(out_names)}"
for name in expect_names:
    assert (out / name).exists(), f"缺少 {name}"

# 验证 gif 原样复制、保留 2 帧动画
gif_out = out / "Demo (10).gif"
with Image.open(gif_out) as g:
    n_frames = getattr(g, "n_frames", 1)
print("导出的 gif 帧数:", n_frames, "(应为 2，保留动画)")
assert n_frames == 2, "gif 导出后丢失动画帧"

# 再次导出 → 全部跳过（按实际扩展名判断同名）
success2, skipped2, _ = exporter.export_all([f], sel, str(out))
print("二次导出: 成功", success2, "跳过", len(skipped2))
assert success2 == 0 and len(skipped2) == 10, "同名跳过应按各格式扩展名判断"

# ---------- 6. 方向键 + 翻页 + 手势 ----------
print("\n=== 6. 键盘导航 + 翻页 ===")
from PySide6.QtWidgets import QApplication
from ui import MainWindow, PreviewNavFilter

app = QApplication([])
w = MainWindow()

folders = [WorkFolder(name=f"F{i}", path=Path("F:/x") / f"F{i}") for i in range(15)]
w.on_scan_done(folders)
w.folder_list.setCurrentRow(5)
print("初始 row =", w.folder_list.currentRow())

# 右侧预览区过滤器：方向键
flt = w.preview_filter
ev_down = QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier)
ret = flt.eventFilter(None, ev_down)
print("过滤器 Down 返回值:", ret, "(应 True=已拦截), row =", w.folder_list.currentRow(), "(应 6)")
assert ret is True and w.folder_list.currentRow() == 6

ev_up = QKeyEvent(QEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
flt.eventFilter(None, ev_up)
print("过滤器 Up 后 row =", w.folder_list.currentRow(), "(应 5)")
assert w.folder_list.currentRow() == 5

# PageDown / PageUp
flt.eventFilter(None, QKeyEvent(QEvent.KeyPress, Qt.Key_PageDown, Qt.NoModifier))
print("PageDown 后 row =", w.folder_list.currentRow(), "(应 15-1=14，越界 clamp)")
assert w.folder_list.currentRow() == 14
flt.eventFilter(None, QKeyEvent(QEvent.KeyPress, Qt.Key_PageUp, Qt.NoModifier))
print("PageUp 后 row =", w.folder_list.currentRow(), "(应 14-10=4)")
assert w.folder_list.currentRow() == 4

# 主窗口 keyPressEvent 兜底（方向键）
w.folder_list.setCurrentRow(4)
w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier))
print("keyPressEvent Down 后 row =", w.folder_list.currentRow(), "(应 5)")
assert w.folder_list.currentRow() == 5

# ---------- 7. 手势开关逻辑 ----------
print("\n=== 7. 右键拖动手势开关 ===")
w.folder_list.setCurrentRow(7)

def m_press(y):
    return QMouseEvent(QEvent.MouseButtonPress, QPointF(10, y), QPointF(10, y),
                       Qt.RightButton, Qt.RightButton, Qt.NoModifier)

def m_move(y):
    return QMouseEvent(QEvent.MouseMove, QPointF(10, y), QPointF(10, y),
                       Qt.NoButton, Qt.RightButton, Qt.NoModifier)

def m_release(y):
    return QMouseEvent(QEvent.MouseButtonRelease, QPointF(10, y), QPointF(10, y),
                       Qt.RightButton, Qt.NoButton, Qt.NoModifier)

# 默认关闭：拖动不触发
w.mouse_gesture_enabled = False
flt.eventFilter(None, m_press(100))
flt.eventFilter(None, m_move(160))   # 向下 60px > 50 阈值
flt.eventFilter(None, m_release(160))
print("手势关闭时拖动后 row =", w.folder_list.currentRow(), "(应仍 7)")
assert w.folder_list.currentRow() == 7, "默认关闭不应触发手势"

# 开启：向下拖 → 下一个
w.mouse_gesture_enabled = True
flt.eventFilter(None, m_press(100))
flt.eventFilter(None, m_move(160))
flt.eventFilter(None, m_release(160))
print("开启后向下拖 row =", w.folder_list.currentRow(), "(应 8)")
assert w.folder_list.currentRow() == 8

# 开启：向上拖 → 上一个
flt.eventFilter(None, m_press(200))
flt.eventFilter(None, m_move(140))   # 向上 60px
flt.eventFilter(None, m_release(140))
print("开启后向上拖 row =", w.folder_list.currentRow(), "(应 7)")
assert w.folder_list.currentRow() == 7

# 未达阈值不触发
flt.eventFilter(None, m_press(100))
flt.eventFilter(None, m_move(130))   # 仅 30px < 50
flt.eventFilter(None, m_release(130))
print("未达阈值(30px)拖动后 row =", w.folder_list.currentRow(), "(应仍 7)")
assert w.folder_list.currentRow() == 7

w.threadpool.waitForDone(5000)

shutil.rmtree(tmp, ignore_errors=True)
print("\nALL_V3_TESTS_PASSED")
