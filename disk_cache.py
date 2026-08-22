# -*- coding: utf-8 -*-
"""磁盘缩略图缓存。

缓存目录：程序同级 .thumb_cache/
缓存文件命名：{md5(源路径)}_{mtime}_{size}.jpg
  - md5(源路径)：唯一标识源文件
  - mtime：源文件修改时间，用于失效检测
  - size：缩略图尺寸，不同尺寸分别缓存

读取流程：查缓存 → 命中且 mtime 一致 → 直接读取 JPEG → 转 QImage
写入流程：生成缩略图 → 转 PIL → 保存为 JPEG → 存入缓存目录

清理：用户手动清空 / 超过上限自动淘汰最旧文件
"""
import hashlib
import os
import time
from pathlib import Path
from typing import Optional

from PIL import Image

# 缓存目录名
CACHE_DIR_NAME = ".thumb_cache"
# 单个缓存文件最大 2MB（防止异常大文件）
MAX_CACHE_FILE_SIZE = 2 * 1024 * 1024
# 缓存文件最大数量上限（超过后淘汰最旧的）
MAX_CACHE_FILES = 2000


def _cache_dir() -> Path:
    """缓存目录：程序同级 .thumb_cache/"""
    app_dir = Path(__file__).resolve().parent
    d = app_dir / CACHE_DIR_NAME
    d.mkdir(exist_ok=True)
    return d


def _file_key(path, size: int) -> str:
    """生成缓存文件名的 key 部分。"""
    path_str = str(path) if not isinstance(path, str) else path
    path_hash = hashlib.md5(path_str.encode("utf-8")).hexdigest()[:12]
    try:
        mtime = int(os.path.getmtime(path))
    except Exception:
        mtime = 0
    return f"{path_hash}_{mtime}_{size}"


def get_cache(path, size: int) -> Optional[Path]:
    """查找磁盘缓存。

    返回缓存文件路径，如果命中且有效；否则返回 None。
    """
    key = _file_key(path, size)
    cache_dir = _cache_dir()
    for ext in (".jpg", ".jpeg", ".png"):
        candidate = cache_dir / f"{key}{ext}"
        if candidate.exists():
            # 二次校验 mtime（防止文件被外部修改）
            try:
                source_mtime = int(os.path.getmtime(path))
                # 从文件名解析 mtime
                parts = candidate.stem.split("_")
                cached_mtime = int(parts[1]) if len(parts) >= 2 else 0
                if source_mtime == cached_mtime:
                    return candidate
            except Exception:
                pass
    return None


def save_cache(path, size: int, img: Image.Image) -> Optional[Path]:
    """将 PIL Image 保存为磁盘缓存。

    返回保存的文件路径，失败返回 None。
    """
    try:
        key = _file_key(path, size)
        cache_dir = _cache_dir()
        cache_path = cache_dir / f"{key}.jpg"

        # 转为 RGB（JPEG 不支持 RGBA）
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.save(str(cache_path), "JPEG", quality=85, optimize=True)

        # 检查文件大小，过大的丢弃
        if cache_path.exists() and cache_path.stat().st_size > MAX_CACHE_FILE_SIZE:
            cache_path.unlink()
            return None

        # 淘汰旧缓存
        _evict_if_needed()

        return cache_path
    except Exception:
        return None


def clear_cache():
    """清空整个缓存目录。"""
    cache_dir = _cache_dir()
    if not cache_dir.exists():
        return
    for f in cache_dir.iterdir():
        if f.is_file():
            try:
                f.unlink()
            except Exception:
                pass


def get_cache_size() -> str:
    """返回缓存占用空间的可读字符串，如 '128.5 MB'。"""
    cache_dir = _cache_dir()
    if not cache_dir.exists():
        return "0 B"
    total = sum(f.stat().st_size for f in cache_dir.iterdir() if f.is_file())
    if total < 1024:
        return f"{total} B"
    elif total < 1024 * 1024:
        return f"{total / 1024:.1f} KB"
    elif total < 1024 * 1024 * 1024:
        return f"{total / 1024 / 1024:.1f} MB"
    else:
        return f"{total / 1024 / 1024 / 1024:.2f} GB"


def get_cache_count() -> int:
    """返回缓存文件数量。"""
    cache_dir = _cache_dir()
    if not cache_dir.exists():
        return 0
    return sum(1 for f in cache_dir.iterdir() if f.is_file())


def _evict_if_needed():
    """缓存文件超过上限时，淘汰最旧的文件。"""
    cache_dir = _cache_dir()
    if not cache_dir.exists():
        return
    files = [f for f in cache_dir.iterdir() if f.is_file()]
    if len(files) <= MAX_CACHE_FILES:
        return
    # 按修改时间排序，删除最旧的
    files.sort(key=lambda f: f.stat().st_mtime)
    to_remove = files[: len(files) - MAX_CACHE_FILES]
    for f in to_remove:
        try:
            f.unlink()
        except Exception:
            pass
