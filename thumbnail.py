# -*- coding: utf-8 -*-
"""缩略图生成：把图片或 PDF 页转成指定尺寸的 QImage（供预览用）。

统一输出 QImage，是因为 QImage 可以在后台线程安全地创建，
再通过信号传回 GUI 线程后转 QPixmap 显示。

所有生成函数接受 size 参数（默认 THUMB_SIZE），支持运行时调整缩略图大小。

磁盘缓存：生成的缩略图保存到 .thumb_cache/ 目录，下次直接读取，跳过原图解码。
"""
from PySide6.QtGui import QImage
from PIL import Image, ImageOps, ImageDraw

from config import THUMB_SIZE
import pdf_render
import disk_cache


def pil_to_qimage(img: Image.Image) -> QImage:
    """PIL 图像 → QImage。"""
    img = img.convert("RGB")
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
    return qimg.copy()  # copy 使数据独立于 bytes 缓冲


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    """把任意模式的图转成「白底 RGB」，透明区域显示为白色。

    用于 GIF（P 模式）、带透明通道的 PNG/WebP、灰度图等，保证缩略图好看且不黑底。
    """
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        return bg.convert("RGB")
    return img.convert("RGB")


def _thumb_pil(img: Image.Image, size: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((size, size), Image.LANCZOS)
    return img


def _qimage_from_cache(cache_path) -> QImage:
    """从磁盘缓存文件读取并转为 QImage。"""
    qimg = QImage(str(cache_path))
    if not qimg.isNull():
        return qimg
    return None


def placeholder_qimage(text: str = "无法预览", size: int = THUMB_SIZE) -> QImage:
    """生成一张占位缩略图：浅灰底 + 居中提示文字。

    用于不支持的格式（如缺少 avif 插件时）或损坏文件，保证缩略图区有反馈且不崩溃。
    """
    img = Image.new("RGB", (size, size), (238, 238, 238))
    d = ImageDraw.Draw(img)
    lines = text.split("\n")
    line_h = 16
    total_h = line_h * len(lines)
    y = (size - total_h) // 2
    for line in lines:
        try:
            w = d.textlength(line)
        except Exception:
            w = len(line) * 8
        d.text(((size - w) // 2, y), line, fill=(150, 150, 150))
        y += line_h
    return pil_to_qimage(img)


def make_image_thumb(path, size: int = THUMB_SIZE) -> QImage:
    """图片文件 → 缩略图 QImage。

    - 先查磁盘缓存，命中直接返回；
    - 大图（>2000px）先降采样到中间尺寸再缩略，减少内存和 CPU 开销；
    - GIF：只取第一帧；损坏文件返回占位图。
    """
    # 查磁盘缓存
    cached = disk_cache.get_cache(path, size)
    if cached:
        qimg = _qimage_from_cache(cached)
        if qimg:
            return qimg

    try:
        with Image.open(path) as im:
            # EXIF 旋转（部分 JPG 的 EXIF 数据异常，跳过不影响显示）
            try:
                im = ImageOps.exif_transpose(im)
            except Exception:
                pass
            rgb = _flatten_to_rgb(im)
            # 大图快速降采样：先缩到中间尺寸（保持比例），再做最终缩略
            w, h = rgb.size
            if max(w, h) > 2000:
                scale = (size * 4) / max(w, h)
                new_w = int(w * scale)
                new_h = int(h * scale)
                rgb = rgb.resize((new_w, new_h), Image.LANCZOS)
            thumb = _thumb_pil(rgb, size)
            # 写入磁盘缓存
            disk_cache.save_cache(path, size, thumb)
            return pil_to_qimage(thumb)
    except Exception:
        return placeholder_qimage(size=size)


def make_pdf_thumb(pdf_path, page_index: int, size: int = THUMB_SIZE) -> QImage:
    """PDF 某页 → 缩略图 QImage。

    - 先查磁盘缓存，命中直接返回；
    - 未命中则带超时渲染（防止复杂矢量PDF卡死GUI）；
    - 超时返回占位图。
    """
    # PDF 缓存 key 需要包含页索引
    cache_key = f"{pdf_path}_p{page_index}"
    cached = disk_cache.get_cache(cache_key, size)
    if cached:
        qimg = _qimage_from_cache(cached)
        if qimg:
            return qimg

    # 带超时渲染（防止复杂矢量PDF卡死）
    img, timed_out = pdf_render.render_pdf_page_fit_with_timeout(
        pdf_path, page_index, size, timeout=5)
    if timed_out or img is None:
        return placeholder_qimage(text="加载中…", size=size)

    thumb = _thumb_pil(img, size)
    # 写入磁盘缓存（用含页索引的 key）
    disk_cache.save_cache(cache_key, size, thumb)
    return pil_to_qimage(thumb)


def make_thumb(item, size: int = THUMB_SIZE) -> QImage:
    """按 MediaItem 类型生成缩略图。"""
    if item.kind == "image":
        return make_image_thumb(item.path, size)
    return make_pdf_thumb(item.path, item.page_index, size)
