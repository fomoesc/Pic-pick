# -*- coding: utf-8 -*-
"""导出逻辑。

把勾选的图按「{文件夹名} (n).{扩展名}」命名导出到输出目录；
若输出目录已存在同名文件则跳过（不覆盖），并记录到跳过清单。

v4 起支持「封面」：
- 每个作品文件夹最多 1 张封面（covers: {文件夹名: item_id}）；
- 封面图导出时文件名 = 文件夹名本身（无编号后缀），扩展名跟随源文件；
- 封面图优先导出（作为第一个文件），其余勾选图从 (1) 开始编号；
- 封面无需勾选，只要设了封面即导出。

- 普通图片：**原样复制**，目标扩展名跟随源文件扩展名（jpg/jpeg/png/gif/bmp/
  avif/webp/tif/tiff/jfif），从而保留 GIF 动画、PNG 透明、WebP/AVIF 原格式等；
- PDF：渲染成清晰的 JPG 再导出（约 144 DPI）。
"""
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional

from config import PDF_EXPORT_ZOOM, EXPORT_JPEG_QUALITY
import pdf_render
from scanner import WorkFolder


def _target_ext(it) -> str:
    """确定导出目标扩展名：图片跟随源文件扩展名，PDF 渲染为 jpg。"""
    if it.kind == "image":
        ext = it.path.suffix.lower()
        return ext if ext else ".jpg"
    return ".jpg"


def export_all(
    work_folders: List[WorkFolder],
    selection: Dict[str, bool],
    output_dir: str,
    covers: Optional[Dict[str, str]] = None,
    log: Callable[[str], None] = None,
    progress: Callable[[int, int], None] = None,
):
    """导出所有作品中被勾选的项（含封面）。

    返回 (成功数, 跳过列表, 失败列表)。
    跳过/失败列表元素为 (作品名, 项描述, 原因)。

    covers：{文件夹名: 封面 item_id}。封面无需勾选，设了即导出。
    """
    covers = covers or {}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 预构建每个作品的 items（含 PDF 页数），统计与导出共用一份
    folder_items = {f.name: f.ordered_items() for f in work_folders}

    def _should_export(f: WorkFolder, it) -> bool:
        if covers.get(f.name) == it.id:
            return True
        return bool(selection.get(it.id))

    total = sum(
        1 for f in work_folders for it in folder_items[f.name]
        if _should_export(f, it)
    )

    success = 0
    skipped: List[tuple] = []
    failed: List[tuple] = []
    done = 0

    def _emit_progress():
        nonlocal done
        done += 1
        if progress:
            progress(done, total)

    def _save(target: Path, it, name: str):
        nonlocal success
        if target.exists():
            skipped.append((name, it.label, "输出目录已存在同名文件"))
        else:
            try:
                if it.kind == "image":
                    # 原样复制：保留 GIF 动画 / PNG 透明 / WebP / AVIF 等原格式
                    shutil.copy2(it.path, target)
                else:
                    img = pdf_render.render_pdf_page(
                        it.path, it.page_index, PDF_EXPORT_ZOOM)
                    img.save(target, "JPEG", quality=EXPORT_JPEG_QUALITY)
                success += 1
                if log:
                    log(f"已导出：{target.name}")
            except Exception as e:
                failed.append((name, it.label, str(e)))
                if log:
                    log(f"导出失败：{it.label} — {e}")

    for f in work_folders:
        items = folder_items[f.name]
        cover_id = covers.get(f.name)

        # 1. 封面优先导出：文件名 = 文件夹名本身（无编号后缀）
        if cover_id:
            cover_item = next((it for it in items if it.id == cover_id), None)
            if cover_item is not None:
                ext = _target_ext(cover_item)
                target = out / f"{f.name}{ext}"
                _save(target, cover_item, f.name)
                _emit_progress()

        # 2. 其余勾选图（排除封面本身，避免重复导出），从 (1) 开始编号
        n = 1
        for it in items:
            if it.id == cover_id:
                continue
            if not selection.get(it.id):
                continue
            ext = _target_ext(it)
            target = out / f"{f.name} ({n}){ext}"
            _save(target, it, f.name)
            _emit_progress()
            n += 1

    return success, skipped, failed
