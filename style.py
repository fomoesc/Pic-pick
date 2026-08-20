# -*- coding: utf-8 -*-
"""全局样式表（QSS）— v4.0 橙色主题。

配色：橙色 #f97316 品牌色，浅灰白底 #F5F6FA
圆角：12px 卡片、8px 输入框/按钮
阴影：0 2px 8px rgba(0,0,0,0.06)
字体：微软雅黑 + Segoe UI
"""

import tempfile
from pathlib import Path

# 对勾图标缓存路径
_CHECK_ICON_PATH = None

# ---- 调色板 ----
BG = "#F5F6FA"                  # 主背景（浅灰白）
PANEL = "#ffffff"               # 面板/卡片背景（纯白）
TEXT = "#1f2937"                 # 主文字
TEXT_MUTED = "#6b7280"           # 次要文字
BORDER = "#e5e7eb"              # 边框
HOVER_BG = "#FFF7ED"            # 悬停背景（浅橙色）

# 品牌色系：橙色
BRAND = "#f97316"               # 主品牌色
BRAND_LIGHT = "#fb923c"         # 浅橙（hover 等场景）
BRAND_DARK = "#ea580c"          # 深橙（pressed 等场景）
BRAND_BG = "#FFF7ED"            # 浅橙背景
BRAND_BORDER = "#FDBA74"        # 橙色边框

COVER = "#f59e0b"               # 封面金色（保留）
SUCCESS = "#16a34a"             # 成功绿
DANGER = "#dc2626"              # 危险红

# 卡片阴影
CARD_SHADOW_RADIUS = 8
CARD_SHADOW_OFFSET = (0, 2)
CARD_SHADOW_COLOR = "rgba(0,0,0,0.06)"

# 圆角
RADIUS_CARD = 12                # 卡片圆角
RADIUS_INPUT = 8                # 输入框/按钮圆角
RADIUS_PILL = 100               # 药丸形状（大圆角）


def _ensure_check_icon() -> str:
    """生成白色对勾 PNG（16×16 透明底），返回其文件路径。"""
    global _CHECK_ICON_PATH
    if _CHECK_ICON_PATH is not None:
        return _CHECK_ICON_PATH
    from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
    from PySide6.QtCore import QPointF, Qt
    pm = QPixmap(16, 16)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor("white"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.drawLine(QPointF(3.5, 8.5), QPointF(7.0, 11.5))
    p.drawLine(QPointF(7.0, 11.5), QPointF(12.5, 4.5))
    p.end()
    path = Path(tempfile.gettempdir()) / "pbb_check.png"
    pm.save(str(path), "PNG")
    _CHECK_ICON_PATH = path.as_posix()
    return _CHECK_ICON_PATH


def build_app_qss() -> str:
    """返回完整 QSS（含运行时生成的对勾图标），需在 QApplication 创建后调用。"""
    check_icon = _ensure_check_icon()
    return f"""
/* ===== 全局基础 ===== */
QMainWindow {{
    background: {BG};
}}
QDialog {{
    background: {BG};
}}
QWidget {{
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QLabel {{
    color: {TEXT};
    background: transparent;
}}

/* ===== 按钮（通用） ===== */
QPushButton {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 6px 14px;
    min-height: 20px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: {HOVER_BG};
    border-color: {BRAND_BORDER};
}}
QPushButton:pressed {{
    background: {BRAND_BG};
}}
QPushButton:disabled {{
    color: #b0b7c0;
    background: #f3f4f6;
    border-color: {BORDER};
}}

/* 主操作按钮（橙色背景白字） */
QPushButton#primaryBtn {{
    background: {BRAND};
    border: 1px solid {BRAND};
    color: #ffffff;
    font-weight: bold;
}}
QPushButton#primaryBtn:hover {{
    background: {BRAND_LIGHT};
    border-color: {BRAND_LIGHT};
}}
QPushButton#primaryBtn:pressed {{
    background: {BRAND_DARK};
    border-color: {BRAND_DARK};
}}
QPushButton#primaryBtn:disabled {{
    background: {BRAND_BORDER};
    border-color: {BRAND_BORDER};
    color: #ffffff;
}}

/* 灰色文字按钮（设置、打开输出等） */
QPushButton#textBtn {{
    background: transparent;
    border: none;
    color: {TEXT_MUTED};
    padding: 4px 8px;
}}
QPushButton#textBtn:hover {{
    color: {BRAND};
    background: {BRAND_BG};
}}

/* ===== 输入框 ===== */
QLineEdit {{
    background: #F0F1F5;
    border: 1px solid transparent;
    border-radius: {RADIUS_INPUT}px;
    padding: 6px 10px;
    selection-background-color: {BRAND};
    selection-color: #ffffff;
    color: {TEXT};
}}
QLineEdit:focus {{
    border-color: {BRAND};
    background: {PANEL};
}}
QLineEdit:hover {{
    border-color: {BRAND_BORDER};
}}

/* ===== 左侧文件夹列表 ===== */
QListWidget {{
    background: transparent;
    border: none;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 8px;
    margin: 2px 4px;
    min-height: 36px;
}}
QListWidget::item:hover {{
    background: {HOVER_BG};
}}
QListWidget::item:selected {{
    background: {BRAND};
    color: #ffffff;
}}

/* ===== 滚动区 ===== */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #d1d5db;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #9ca3af;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #d1d5db;
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #9ca3af;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ===== 进度条 ===== */
QProgressBar {{
    background: #E8EAF0;
    border: none;
    border-radius: 6px;
    text-align: center;
    color: {TEXT_MUTED};
    font-size: 11px;
    height: 14px;
}}
QProgressBar::chunk {{
    background: {BRAND};
    border-radius: 6px;
}}

/* ===== 日志区 ===== */
QTextEdit {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
    padding: 6px 8px;
    font-family: "Consolas", "Microsoft YaHei", monospace;
    font-size: 12px;
    color: {TEXT};
}}

/* ===== 复选框 ===== */
QCheckBox {{
    spacing: 6px;
    color: {TEXT};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid #d1d5db;
    border-radius: 4px;
    background: {PANEL};
}}
QCheckBox::indicator:hover {{
    border-color: {BRAND};
}}
QCheckBox::indicator:checked {{
    background: {BRAND};
    border-color: {BRAND};
    image: url({check_icon});
}}

/* ===== 分割条 ===== */
QSplitter::handle {{
    background: {BORDER};
    width: 1px;
}}
QSplitter::handle:hover {{
    background: {BRAND_BORDER};
}}

/* ===== 状态栏 ===== */
QFrame#appStatusBar {{
    background: {PANEL};
    border: none;
    border-top: 1px solid {BORDER};
}}
QFrame#appStatusBar QLabel {{
    color: {TEXT_MUTED};
}}

/* ===== 菜单栏 ===== */
QMenuBar {{
    background: {PANEL};
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item {{
    padding: 5px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {HOVER_BG};
}}
QMenu {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background: {HOVER_BG};
}}

/* ===== 缩略图卡片 ===== */
QFrame#thumbCard {{
    background: {PANEL};
    border: 2px solid transparent;
    border-radius: {RADIUS_CARD}px;
}}
QFrame#thumbCard:hover {{
    border-color: {BRAND_BORDER};
}}

/* ===== 分组标题（可折叠）===== */
QPushButton#groupHeader {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 8px 12px;
    text-align: left;
    font-weight: bold;
    font-size: 13px;
    color: {TEXT};
}}
QPushButton#groupHeader:hover {{
    background: {HOVER_BG};
    border-color: {BRAND_BORDER};
}}

/* ===== 日志折叠标题 ===== */
QPushButton#logHeader {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 5px 12px;
    text-align: left;
    font-weight: bold;
    font-size: 12px;
    color: {TEXT_MUTED};
}}
QPushButton#logHeader:hover {{
    background: {HOVER_BG};
    border-color: {BRAND_BORDER};
}}

/* ===== 封面按钮 ===== */
QPushButton#coverBtn {{
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px 7px;
    font-size: 11px;
    color: {TEXT_MUTED};
    min-height: 16px;
}}
QPushButton#coverBtn:hover {{
    border-color: {COVER};
    color: {COVER};
    background: #fffbeb;
}}
QPushButton#coverBtn[active="true"] {{
    background: {COVER};
    border-color: {COVER};
    color: #ffffff;
    font-weight: bold;
}}

/* ===== 自定义标题栏（橙色渐变背景） ===== */
QFrame#titleBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {BRAND}, stop:1 {BRAND_LIGHT});
    border: none;
}}
QFrame#titleBar QLabel {{
    background: transparent;
    color: #ffffff;
}}
QPushButton#titleBtn {{
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: 14px;
}}
QPushButton#titleBtn:hover {{
    background: rgba(255, 255, 255, 0.2);
    border-radius: 0;
}}
QPushButton#titleClose {{
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: 14px;
}}
QPushButton#titleClose:hover {{
    background: #dc2626;
    border-radius: 0;
}}

/* ===== 提示标签（占位/空态） ===== */
QLabel#mutedTip {{
    color: {TEXT_MUTED};
}}

/* ===== 清空按钮（灰色背景） ===== */
QPushButton#clearBtn {{
    background: #E5E7EB;
    border: 1px solid {BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 4px 8px;
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: bold;
}}
QPushButton#clearBtn:hover {{
    background: #D1D5DB;
    border-color: {BRAND_BORDER};
}}
QPushButton#clearBtn:pressed {{
    background: #B0B7C0;
}}

/* ===== 工具提示 ===== */
QToolTip {{
    background: #1f2937;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}}

/* ===== 导航按钮（灰色描边） ===== */
QPushButton#navBtn {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 6px 16px;
    color: {TEXT};
}}
QPushButton#navBtn:hover {{
    background: {HOVER_BG};
    border-color: {BRAND_BORDER};
}}
QPushButton#navBtn:pressed {{
    background: {BRAND_BG};
}}
QPushButton#navBtn:disabled {{
    color: #d1d5db;
    background: #f9fafb;
    border-color: {BORDER};
}}
"""
