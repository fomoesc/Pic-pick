# -*- coding: utf-8 -*-
"""缩略图生成：把图片或 PDF 页转成指定尺寸的 QImage（供预览用）。

统一输出 QImage，是因为 QImage 可以在后台线程安全地创建，
再通过信号传回 GUI 线程后转 QPixmap 显示。

所有生成函数接受 size 参数（默认 THUMB_SIZE），支持运行时调整缩略图大小。
"""
from PySide6.QtGui import QImage
from PIL import Image, ImageOps, ImageDraw

from config import THUMB_SIZE
import pdf_render


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

    - GIF：只取第一帧（Image.open 默认停在第一帧）；
    - avif/webp：依赖 Pillow 支持；
    - 不支持的格式或损坏文件返回占位图，绝不抛出异常导致崩溃。
    """
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)  # 按 EXIF 旋转信息纠正方向
            rgb = _flatten_to_rgb(im)
            thumb = _thumb_pil(rgb, size)
            return pil_to_qimage(thumb)
    except Exception:
        return placeholder_qimage(size=size)


def make_pdf_thumb(pdf_path, page_index: int, size: int = THUMB_SIZE) -> QImage:
    """PDF 某页 → 缩略图 QImage。"""
    # 按页面尺寸计算精确 zoom，直接渲染成目标尺寸，避免先渲染大图再缩小
    img = pdf_render.render_pdf_page_fit(pdf_path, page_index, size)
    thumb = _thumb_pil(img, size)
    return pil_to_qimage(thumb)


def make_thumb(item, size: int = THUMB_SIZE) -> QImage:
    """按 MediaItem 类型生成缩略图。"""
    if item.kind == "image":
        return make_image_thumb(item.path, size)
    return make_pdf_thumb(item.path, item.page_index, size)
