# -*- coding: utf-8 -*-
"""v2 自测：自然排序 / 漏选统计 / 导航按钮边界（offscreen，不弹窗）。"""
import os
import sys
import io
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ---------- 1. 自然排序（纯函数） ----------
from scanner import natural_key, collect_media, scan_source_dir, WorkFolder

print("=== 1. 自然排序 ===")
names = ["page-1", "page-10", "page-2", "page-11", "page-12",
         "page-3", "page-20", "page-9"]
got = sorted(names, key=natural_key)
expect = ["page-1", "page-2", "page-3", "page-9", "page-10",
          "page-11", "page-12", "page-20"]
print("文件自然排序:", got)
assert got == expect, f"自然排序错误: {got}"

folders = ["[Angraf 105]", "[Angraf 101]", "[Angraf 200]",
           "[Angraf 11]", "[Angraf 2]"]
got2 = sorted(folders, key=natural_key)
expect2 = ["[Angraf 2]", "[Angraf 11]", "[Angraf 101]", "[Angraf 105]", "[Angraf 200]"]
print("文件夹自然排序:", got2)
assert got2 == expect2, f"文件夹自然排序错误: {got2}"

# 边界：数字与文本混合不抛 TypeError
mixed = ["page-1", "page-x", "page-2"]
print("混合排序:", sorted(mixed, key=natural_key))
assert sorted(mixed, key=natural_key) == ["page-1", "page-2", "page-x"]

# ---------- 2. collect_media / scan_source_dir 真实文件场景 ----------
print("\n=== 2. collect_media / scan_source_dir 场景 ===")
tmp = tempfile.mkdtemp(prefix="v2_natsort_")
src = Path(tmp) / "src"
out = Path(tmp) / "out"
# 构造一个作品文件夹，内含 page-1..page-12.jpg（乱序创建）
work = src / "MyWork"
work.mkdir(parents=True)
for n in [10, 2, 1, 12, 3, 11, 9, 8, 7, 6, 5, 4]:
    (work / f"page-{n}.jpg").write_bytes(b"x")
img, pdf = collect_media(work)
got_names = [p.name for p in img]
expect_names = [f"page-{n}.jpg" for n in range(1, 13)]
print("collect_media 排序:", got_names)
assert got_names == expect_names, f"collect_media 排序错误: {got_names}"

# 构造多个带数字的文件夹，验证 scan_source_dir 排序
for name in ["[Angraf 105]", "[Angraf 101]", "[Angraf 2]", "[Angraf 11]"]:
    (src / name).mkdir()
scan_names = [f.name for f in scan_source_dir(str(src))]
print("scan_source_dir 排序:", scan_names)
assert scan_names == ["[Angraf 2]", "[Angraf 11]", "[Angraf 101]", "[Angraf 105]", "MyWork"], \
    f"scan 排序错误: {scan_names}"

# ---------- 3. 漏选统计 + 导航按钮边界 ----------
print("\n=== 3. 漏选统计 + 导航按钮边界 ===")
from PySide6.QtWidgets import QApplication
from ui import MainWindow

app = QApplication([])
w = MainWindow()

folders = []
for name in ["A", "B", "C", "D"]:
    f = WorkFolder(name=name, path=Path("F:/fake") / name)
    f.is_processed = False
    folders.append(f)
# 模拟 C 已处理
folders[2].is_processed = True
w.on_scan_done(folders)
print("列表项数 =", w.folder_list.count())
assert w.folder_list.count() == 4

# 模拟 on_load_ready 填充 item_folder：每个文件夹 3 项
for f in folders:
    for i in range(3):
        w.item_folder[f"img:{f.path}/page-{i}.jpg"] = f.name

# 勾选 A、B 各 1 项（C、D 完全没勾）
w.selection[f"img:{folders[0].path}/page-0.jpg"] = True
w.selection[f"img:{folders[1].path}/page-0.jpg"] = True
w._update_count_label()

missed = w._missed_folders()
missed_names = [f.name for f in missed]
print("漏选文件夹 =", missed_names)
assert missed_names == ["C", "D"], f"漏选统计错误: {missed_names}"
print("漏选弹窗中 C 的已处理标注 =", missed[0].is_processed, "(应为 True)")
assert missed[0].is_processed is True

# 全部勾选后应无漏选
for f in folders:
    w.selection[f"img:{f.path}/page-0.jpg"] = True
assert w._missed_folders() == [], "全勾选后应无漏选"
print("全勾选后漏选 = []  (正确)")

# 导航按钮边界
print("\n导航按钮初始状态: prev =", w.prev_btn.isEnabled(),
      ", next =", w.next_btn.isEnabled(), "(应均为 False)")
assert not w.prev_btn.isEnabled() and not w.next_btn.isEnabled()

w.folder_list.setCurrentRow(0)
print("选中第 0 项: prev =", w.prev_btn.isEnabled(),
      ", next =", w.next_btn.isEnabled(), "(prev=False, next=True)")
assert not w.prev_btn.isEnabled() and w.next_btn.isEnabled()

w.goto_next_folder()
w.goto_next_folder()
w.goto_next_folder()
print("连点 3 次 next → row =", w.folder_list.currentRow(), "(应为 3，最后一项)")
assert w.folder_list.currentRow() == 3
print("最后一项: prev =", w.prev_btn.isEnabled(),
      ", next =", w.next_btn.isEnabled(), "(prev=True, next=False)")
assert w.prev_btn.isEnabled() and not w.next_btn.isEnabled()

w.goto_next_folder()  # 越界点击应无效果
print("越界点 next 后 row =", w.folder_list.currentRow(), "(仍应为 3)")
assert w.folder_list.currentRow() == 3

w.goto_prev_folder()
print("点 prev → row =", w.folder_list.currentRow(), "(应为 2)")
assert w.folder_list.currentRow() == 2

# 等待后台线程任务收尾，避免退出时信号源被销毁的噪音
w.threadpool.waitForDone(5000)

print("\nALL_V2_TESTS_PASSED")
