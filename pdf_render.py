# -*- coding: utf-8 -*-
"""PDF 页渲染（基于 PyMuPDF）。

这里只负责把 PDF 的某一页渲染成 PIL 图像，
供「缩略图预览」和「导出为 JPG」两处共用。
"""
from PIL import Image
import pymupdf as fitz  # PyMuPDF

from config import PDF_EXPORT_ZOOM

# 页数缓存：key=PDF 路径字符串，value=页数。避免重复打开同一个 PDF。
_page_count_cache = {}


def get_pdf_page_count(pdf_path) -> int:
    """获取 PDF 的页数（带缓存）。"""
    key = str(pdf_path)
    if key not in _page_count_cache:
        doc = fitz.open(pdf_path)
        _page_count_cache[key] = doc.page_count
        doc.close()
    return _page_count_cache[key]


def render_pdf_page(pdf_path, page_index: int, zoom: float = PDF_EXPORT_ZOOM) -> Image.Image:
    """把 PDF 的第 page_index 页渲染成 RGB PIL 图像。

    zoom 越大越清晰、像素尺寸也越大。
    """
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
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
