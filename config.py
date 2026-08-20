# -*- coding: utf-8 -*-
"""拼版选图导出工作台 — 配置常量

所有可调参数集中在这里，方便以后修改。
"""

# ---- 文件类型 ----
# 支持的图片扩展名（小写，含点）—— 常见格式全集
IMAGE_EXTS = (
    '.jpg', '.jpeg', '.png', '.gif', '.bmp',
    '.avif', '.webp', '.tif', '.tiff', '.jfif',
)

# PDF 扩展名
PDF_EXT = '.pdf'

# ---- 预览缩略图 ----
# 缩略图尺寸（像素，正方形显示区域）
THUMB_SIZE = 200
# 每行缩略图列数
THUMB_COLS = 4

# ---- PDF 导出 ----
# PDF 页渲染成图片时的缩放系数（2.0 ≈ 144 DPI，A4 宽约 1190px，贴合"1200px"目录语义）
PDF_EXPORT_ZOOM = 2.0
# 导出的 JPG 质量（1-100）
EXPORT_JPEG_QUALITY = 92

# ---- 鼠标手势（右键拖动切换文件夹）----
# 手势开关通过 settings.py 持久化管理（config.json → mouse_gesture）
# 触发手势的最小垂直拖动距离（像素），超过该距离才切换，防止轻微抖动误触
MOUSE_GESTURE_THRESHOLD = 50

# ---- 应用 ----
APP_NAME = "拼版选图导出工作台"
APP_VERSION = "5.0.1"

# ---- 封面 ----
# 封面缩略图高亮边框颜色（金色）
COVER_BORDER_COLOR = "#f59e0b"
