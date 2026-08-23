# -*- coding: utf-8 -*-
"""扫描源目录，构建作品文件夹列表与可导出项。

实际目录结构：
    源目录/
        [作品文件夹]/
            [子文件夹]/
                图片(jpg...) 和 PDF
                （可能还有更深嵌套）
            散落的图片/PDF（可选）

所以：源目录第一层子目录 = 一个"作品"；作品内部递归收集所有图片和 PDF。

v4 起，作品文件夹内部可按「第一层子文件夹」分组展示（见 build_groups）。
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from config import IMAGE_EXTS, PDF_EXT
import pdf_render


def natural_key(text: str):
    """自然排序 key：识别字符串中的数字段并按数值比较，其余按小写字典序。

    例如 page-1, page-2, ..., page-10, page-11 会按数值顺序排列，
    而不是字典序（page-10 会排在 page-2 前面）。

    每个片段打包为 (类别, 值) 元组：数字段为 (0, 整数值)，文本段为 (1, 小写文本)，
    从而避免同一位置 int 与 str 直接比较时抛出 TypeError。
    """
    key = []
    for part in re.split(r"(\d+)", text):
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return key


@dataclass
class MediaItem:
    """一个可勾选 / 可导出的单元：一张图片，或 PDF 的一页。"""
    id: str                # 全局唯一标识（用作勾选状态、缩略图缓存的 key）
    kind: str              # 'image' 或 'pdf'
    path: Path             # 源文件路径
    page_index: int = 0    # 仅 PDF 有意义：页索引（从 0 开始）
    label: str = ""        # 显示名


def _ordered_items(images: List[Path], pdfs: List[Path]) -> List[MediaItem]:
    """按「图序」构建可导出项：图片（按文件名排序）在前，PDF（按 文件名→页序）在后。"""
    items: List[MediaItem] = []
    for p in images:
        items.append(MediaItem(
            id=f"img:{p}", kind="image", path=p, label=p.name))
    for p in pdfs:
        try:
            count = pdf_render.get_pdf_page_count(p)
        except Exception:
            count = 1
        for i in range(count):
            items.append(MediaItem(
                id=f"pdf:{p}:{i}", kind="pdf", path=p,
                page_index=i, label=f"{p.name} 第{i + 1}页"))
    return items


def _pdf_page_total(pdfs: List[Path]) -> int:
    """统计一组 PDF 的总页数（用于分组标题展示）。"""
    total = 0
    for p in pdfs:
        try:
            total += pdf_render.get_pdf_page_count(p)
        except Exception:
            total += 1
    return total


@dataclass
class MediaGroup:
    """一个展示分组：作品文件夹下的一个子文件夹，或根目录散落文件。

    name 为子文件夹名；根目录散落文件的分组名为「根目录」。
    """
    name: str
    images: List[Path] = field(default_factory=list)
    pdfs: List[Path] = field(default_factory=list)

    def ordered_items(self) -> List[MediaItem]:
        return _ordered_items(self.images, self.pdfs)

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def pdf_count(self) -> int:
        return len(self.pdfs)

    @property
    def pdf_page_count(self) -> int:
        return _pdf_page_total(self.pdfs)


@dataclass
class WorkFolder:
    """一个作品文件夹。"""
    name: str
    path: Path
    images: List[Path] = field(default_factory=list)
    pdfs: List[Path] = field(default_factory=list)
    groups: List[MediaGroup] = field(default_factory=list)
    is_processed: bool = False

    def ordered_items(self) -> List[MediaItem]:
        """返回全部可导出项（扁平，图片在前 PDF 在后）。"""
        return _ordered_items(self.images, self.pdfs)

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def pdf_count(self) -> int:
        return len(self.pdfs)


def collect_media(folder_path: Path):
    """递归收集文件夹下所有图片与 PDF 文件（各自按自然排序）。"""
    images: List[Path] = []
    pdfs: List[Path] = []
    for root, _dirs, files in os.walk(folder_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            fp = Path(root) / f
            if ext in IMAGE_EXTS:
                images.append(fp)
            elif ext == PDF_EXT:
                pdfs.append(fp)
    images.sort(key=lambda p: natural_key(p.name))
    pdfs.sort(key=lambda p: natural_key(p.name))
    return images, pdfs


def build_groups(folder_path: Path) -> List[MediaGroup]:
    """按子文件夹构建展示分组。

    规则：
    - 文件夹下没有任何子文件夹 → 返回空列表（UI 走扁平展示）；
    - 有子文件夹 → 递归深入：如果某个子文件夹内部还有子文件夹，
      则用其内部子文件夹作为分组（而非把所有文件混在一起）；
    - 同名子文件夹自动跳过（常见纸模目录结构）；
    - 根目录散落的图片/PDF 归入「根目录」分组。
    """
    return _build_groups_recursive(folder_path)


def _build_groups_recursive(folder_path: Path) -> List[MediaGroup]:
    """递归构建分组。"""
    try:
        entries = sorted(os.scandir(folder_path), key=lambda e: natural_key(e.name))
    except Exception:
        return []

    subdirs = [e for e in entries if e.is_dir()]
    if not subdirs:
        return []

    # 跳过同名子文件夹（常见纸模结构：作品文件夹/同名子文件夹/...）
    if len(subdirs) == 1 and subdirs[0].name == folder_path.name:
        return _build_groups_recursive(Path(subdirs[0].path))

    # 检查每个子文件夹是否有内部子文件夹
    groups: List[MediaGroup] = []
    root_imgs, root_pdfs = _collect_files_from_entries(entries)

    for sub in subdirs:
        sub_path = Path(sub.path)
        try:
            inner_entries = sorted(os.scandir(sub_path), key=lambda e: natural_key(e.name))
        except Exception:
            inner_entries = []
        inner_subdirs = [e for e in inner_entries if e.is_dir()]

        if inner_subdirs:
            # 该子文件夹有内部子文件夹 → 递归深入，用内部子文件夹作为分组
            inner_groups = _build_groups_recursive(sub_path)
            for ig in inner_groups:
                # 在分组名前加上父文件夹名，形成路径感
                ig.name = f"{sub.name} / {ig.name}"
                groups.append(ig)
            # 也收集该子文件夹根目录散落的文件
            sub_imgs, sub_pdfs = _collect_files_from_entries(inner_entries)
            if sub_imgs or sub_pdfs:
                groups.append(MediaGroup(name=sub.name, images=sub_imgs, pdfs=sub_pdfs))
        else:
            # 该子文件夹没有内部子文件夹 → 直接作为分组
            imgs, pdfs = collect_media(sub_path)
            if imgs or pdfs:
                groups.append(MediaGroup(name=sub.name, images=imgs, pdfs=pdfs))

    # 根目录散落文件
    if root_imgs or root_pdfs:
        groups.append(MediaGroup(name="根目录", images=root_imgs, pdfs=root_pdfs))

    return groups


def _collect_files_from_entries(entries):
    """从目录条目列表中收集散落的图片和 PDF。"""
    imgs: List[Path] = []
    pdfs: List[Path] = []
    for e in entries:
        if not e.is_file():
            continue
        ext = os.path.splitext(e.name)[1].lower()
        fp = Path(e.path)
        if ext in IMAGE_EXTS:
            imgs.append(fp)
        elif ext == PDF_EXT:
            pdfs.append(fp)
    imgs.sort(key=lambda p: natural_key(p.name))
    pdfs.sort(key=lambda p: natural_key(p.name))
    return imgs, pdfs


def _build_subdir_groups(subdirs) -> List[MediaGroup]:
    """为每个子文件夹创建分组。"""
    groups: List[MediaGroup] = []
    for sub in subdirs:
        imgs, pdfs = collect_media(Path(sub.path))
        if imgs or pdfs:
            groups.append(MediaGroup(name=sub.name, images=imgs, pdfs=pdfs))
    return groups


def scan_source_dir(source_dir: str) -> List[WorkFolder]:
    """列出源目录下第一层子目录作为作品文件夹，忽略文件（如 zip）。

    文件夹按自然排序（如 [Angraf 101] < [Angraf 105] < [Angraf 200]）。
    """
    folders: List[WorkFolder] = []
    try:
        entries = sorted(os.scandir(source_dir), key=lambda e: natural_key(e.name))
    except Exception as e:
        raise RuntimeError(f"无法访问源目录：{source_dir}\n{e}")
    for entry in entries:
        if entry.is_dir():
            folders.append(WorkFolder(name=entry.name, path=Path(entry.path)))
    return folders


def is_folder_processed(name: str, output_dir) -> bool:
    """判断作品是否「已处理」：输出目录下存在以「{文件夹名} (」开头的文件。"""
    if not output_dir:
        return False
    out = Path(output_dir)
    if not out.is_dir():
        return False
    prefix = f"{name} ("
    try:
        for f in out.iterdir():
            if f.is_file() and f.name.startswith(prefix):
                return True
    except Exception:
        return False
    return False
