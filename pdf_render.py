# -*- coding: utf-8 -*-
"""PDF 页渲染（基于 PyMuPDF）。

这里只负责把 PDF 的某一页渲染成 PIL 图像，
供「缩略图预览」和「导出为 JPG」两处共用。

超时渲染：复杂矢量 PDF（大量线条/曲线）的 get_pixmap() 可能耗时数十秒，
通过 threading + 超时机制避免阻塞 GUI。
"""
import threading
from PIL import Image
import pymupdf as fitz  # PyMuPDF

from config import PDF_EXPORT_ZOOM, PDF_MIN_LONG_SIDE, PDF_MIN_DPI

# 页数缓存：key=PDF 路径字符串，value=页数。避免重复打开同一个 PDF。
_page_count_cache = {}

# 超时渲染默认超时时间（秒）
DEFAULT_RENDER_TIMEOUT = 5


def get_pdf_page_count(pdf_path) -> int:
    """获取 PDF 的页数（带缓存）。"""
    key = str(pdf_path)
    if key not in _page_count_cache:
        doc = fitz.open(pdf_path)
        _page_count_cache[key] = doc.page_count
        doc.close()
    return _page_count_cache[key]


def calc_export_zoom(page_rect) -> float:
    """计算导出用的 zoom 系数。

    保证输出图片的最长边 ≥ PDF_MIN_LONG_SIDE（1200px），
    且 DPI ≥ PDF_MIN_DPI（180），确保清晰度。
    """
    min_zoom_by_size = PDF_MIN_LONG_SIDE / max(page_rect.width, page_rect.height)
    min_zoom_by_dpi = PDF_MIN_DPI / 72  # PDF 1pt = 1/72 inch
    return max(min_zoom_by_size, min_zoom_by_dpi, PDF_EXPORT_ZOOM)


def render_pdf_page(pdf_path, page_index: int, zoom: float = None) -> Image.Image:
    """把 PDF 的第 page_index 页渲染成 RGB PIL 图像。

    zoom 越大越清晰、像素尺寸也越大。
    如果未指定 zoom，自动计算（保底 1200px + 180 DPI）。
    """
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        if zoom is None:
            zoom = calc_export_zoom(page.rect)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return img
    finally:
        doc.close()


def render_pdf_page_fit(pdf_path, page_index: int, max_size: int) -> Image.Image:
    """渲染 PDF 页，使长边不超过 max_size 像素（用于缩略图，速度快）。"""
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        rect = page.rect
        zoom = max_size / max(rect.width, rect.height)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


def render_pdf_page_fit_with_timeout(pdf_path, page_index: int, max_size: int,
                                     timeout: float = DEFAULT_RENDER_TIMEOUT):
    """带超时的 PDF 缩略图渲染。

    返回 (Image.Image | None, bool)：
      - (image, False)：正常渲染完成
      - (None, True)：超时，未完成
    """
    result = [None]
    error = [None]

    def _render():
        try:
            result[0] = render_pdf_page_fit(pdf_path, page_index, max_size)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=_render, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        # 超时，渲染线程仍在后台运行（daemon 线程，进程退出时自动终止）
        return None, True

    if error[0]:
        return None, False

    return result[0], False
