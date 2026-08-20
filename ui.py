# -*- coding: utf-8 -*-
"""拼版选图导出工作台 — 图形界面（PySide6）v4.0 橙色主题。

修复清单（2026-08-21）：
1. 消除缩略图上的半透明白色覆盖层（thumb_area背景改为透明）
2. 封面按钮始终可见（raise_确保在最上层）
3. 所有缩略图统一大小（ThumbWidget固定尺寸 + UniformGridLayout）
4. 文件夹勾选标记始终刷新（每次selection/covers变更后调用_refresh_folder_badges）
"""
import os, math

from PySide6.QtCore import (
    Qt, QObject, QRunnable, QThreadPool, Signal, QEvent, QPoint, QPointF,
    QRect, QRectF, QSize, QPropertyAnimation, QTimer,
)
from PySide6.QtGui import (
    QImage, QPixmap, QFont, QPainter, QColor, QPen, QBrush, QCursor,
    QPainterPath, QRegion, QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QListWidget, QListWidgetItem,
    QScrollArea, QCheckBox, QTextEdit, QProgressBar, QSplitter, QMessageBox,
    QFrame, QDialog, QComboBox, QLayout, QAbstractButton,
    QSlider, QSizePolicy, QSpacerItem,
)

from config import (
    APP_NAME, APP_VERSION, THUMB_SIZE, THUMB_COLS,
    MOUSE_GESTURE_THRESHOLD, COVER_BORDER_COLOR,
)
import settings
import scanner
from scanner import WorkFolder
import thumbnail as thumb
import exporter

# ── 配色常量 ──
BRAND = "#f97316"
BRAND_LIGHT = "#fb923c"
BRAND_DARK = "#ea580c"
BRAND_BG = "#FFF7ED"
BRAND_BORDER = "#FDBA74"
COVER_COLOR = "#f59e0b"
TEXT = "#1f2937"
TEXT_MUTED = "#6b7280"
PANEL = "#ffffff"
BORDER = "#e5e7eb"
BG = "#F5F6FA"
HOVER_BG = "#FFF7ED"

# ── 缩略图显示区统一尺寸 ──
THUMB_DISPLAY_SIZE = 160


# ═══════════════════════ 后台任务 ═══════════════════════

class WorkerSignals(QObject):
    scan_progress = Signal(int, int)
    scan_done = Signal(object)
    scan_error = Signal(str)
    load_ready = Signal(int, str, object, object)
    thumb_ready = Signal(int, str, object)
    load_done = Signal(int, str)
    export_log = Signal(str)
    export_progress = Signal(int, int)
    export_done = Signal(int, object, object)
    export_error = Signal(str)


class ScanTask(QRunnable):
    def __init__(self, source_dir, output_dir, signals):
        super().__init__()
        self.source_dir = source_dir
        self.output_dir = output_dir
        self.signals = signals
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            folders = scanner.scan_source_dir(self.source_dir)
            total = len(folders)
            for i, f in enumerate(folders):
                if self._cancelled:
                    return
                f.images, f.pdfs = scanner.collect_media(f.path)
                f.groups = scanner.build_groups(f.path)
                f.is_processed = scanner.is_folder_processed(f.name, self.output_dir)
                self.signals.scan_progress.emit(i + 1, total)
            self.signals.scan_done.emit(folders)
        except Exception as e:
            self.signals.scan_error.emit(str(e))


class LoadTask(QRunnable):
    def __init__(self, generation, folder, signals):
        super().__init__()
        self.generation = generation
        self.folder = folder
        self.signals = signals
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        if self._cancelled:
            return
        try:
            items = self.folder.ordered_items()
            groups = self.folder.groups
            self.signals.load_ready.emit(self.generation, self.folder.name, items, groups)
        except Exception:
            self.signals.load_done.emit(self.generation, self.folder.name)


class ThumbTask(QRunnable):
    def __init__(self, generation, items, signals, thumb_size=THUMB_SIZE):
        super().__init__()
        self.generation = generation
        self.items = items
        self.signals = signals
        self.thumb_size = thumb_size
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        for item in self.items:
            if self._cancelled:
                return
            try:
                qimg = thumb.make_thumb(item, self.thumb_size)
                self.signals.thumb_ready.emit(self.generation, item.id, qimg)
            except Exception:
                pass


class ExportTask(QRunnable):
    def __init__(self, work_folders, selection, output_dir, signals, covers=None):
        super().__init__()
        self.work_folders = work_folders
        self.selection = selection
        self.output_dir = output_dir
        self.signals = signals
        self.covers = covers or {}

    def run(self):
        try:
            def log(s):
                self.signals.export_log.emit(s)
            def prog(d, t):
                self.signals.export_progress.emit(d, t)
            success, skipped, failed = exporter.export_all(
                self.work_folders, self.selection, self.output_dir,
                self.covers, log, prog)
            self.signals.export_done.emit(success, skipped, failed)
        except Exception as e:
            self.signals.export_error.emit(str(e))


# ═══════════════════════ 基础控件 ═══════════════════════

class ClickableLabel(QLabel):
    """可点击标签 — 背景完全透明，绝不遮挡缩略图。"""
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CircleCheckBox(QAbstractButton):
    SIZE = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background:transparent; border:none;")

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(2, 2, -2, -2)
        if self.isChecked():
            p.setBrush(QColor(BRAND))
            p.setPen(QPen(QColor(BRAND), 2))
            p.drawEllipse(r)
            pen = QPen(QColor("white"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            cx, cy = self.width() / 2.0, self.height() / 2.0
            p.drawLine(QPointF(cx - 4.5, cy + 0.5), QPointF(cx - 1.5, cy + 3.5))
            p.drawLine(QPointF(cx - 1.5, cy + 3.5), QPointF(cx + 4.5, cy - 3.0))
        else:
            p.setBrush(QColor(255, 255, 255, 240))
            p.setPen(QPen(QColor("#d1d5db"), 2))
            p.drawEllipse(r)


# ═══════════════════════ 统一网格布局 ═══════════════════════

class UniformGridLayout(QLayout):
    """统一网格布局：所有单元格等宽等高。

    根据可用宽度自动计算列数，每列宽度一致，
    保证JPG和PDF缩略图大小完全一致。
    """
    def __init__(self, parent=None, margin=8, spacing=8, min_cols=3):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []
        self._min_cols = min_cols

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Horizontal

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do_layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._do_layout(r, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        return QSize(200, 200)

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        available_w = rect.width() - margins.left() - margins.right()
        if not self._items:
            return 0
        spacing = self.spacing()
        # 固定单元格尺寸
        cell_w = THUMB_DISPLAY_SIZE + 16
        cell_h = THUMB_DISPLAY_SIZE + 48
        # 计算列数
        cols = max(self._min_cols, (available_w + spacing) // (cell_w + spacing))
        cols = min(cols, len(self._items))
        x = margins.left()
        y = margins.top()
        for i, item in enumerate(self._items):
            col = i % cols
            if col == 0 and i > 0:
                x = margins.left()
                y += cell_h + spacing
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(cell_w, cell_h)))
            x += cell_w + spacing
        return y + cell_h + margins.bottom() - rect.y()


# ═══════════════════════ 标题栏 ═══════════════════════

class TitleBar(QFrame):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(56)
        self._drag_pos = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 8, 0)
        lay.setSpacing(8)
        # 应用图标（优先加载 PNG/ICO，回退到文字图标）
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(28, 28)
        self._icon_label.setAlignment(Qt.AlignCenter)
        icon_loaded = False
        for icon_name in ("app_icon.png", "app_icon.ico"):
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name)
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path).scaled(
                    24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._icon_label.setPixmap(pixmap)
                icon_loaded = True
                break
        if not icon_loaded:
            self._icon_label.setText("拼")
            self._icon_label.setStyleSheet(
                "font-size:14px; font-weight:bold; background:rgba(255,255,255,0.2); "
                "color:#ffffff; border-radius:6px;")
        lay.addWidget(self._icon_label)
        self.title_label = QLabel(APP_NAME)
        self.title_label.setStyleSheet(
            "color:#ffffff; font-weight:bold; font-size:15px; background:transparent;")
        lay.addWidget(self.title_label)
        sub = QLabel("高效拼版 · 批量处理 · 一键导出")
        sub.setStyleSheet("color:rgba(255,255,255,0.8); font-size:12px; background:transparent;")
        lay.addWidget(sub)
        lay.addStretch(1)
        self.min_btn = self._mk_btn("\u2014", "最小化")
        self.min_btn.clicked.connect(self._window.showMinimized)
        lay.addWidget(self.min_btn)
        self.max_btn = self._mk_btn("\u25a1", "最大化")
        self.max_btn.clicked.connect(self._toggle_max)
        lay.addWidget(self.max_btn)
        self.close_btn = self._mk_btn("\u2715", "关闭", danger=True)
        self.close_btn.clicked.connect(self._window.close)
        lay.addWidget(self.close_btn)

    def _mk_btn(self, text, tip, danger=False):
        b = QPushButton(text)
        b.setObjectName("titleClose" if danger else "titleBtn")
        b.setFixedSize(36, 32)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        return b

    def _toggle_max(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self._sync_max_btn()

    def _sync_max_btn(self):
        self.max_btn.setText("\u2550" if self._window.isMaximized() else "\u25a1")
        self.max_btn.setToolTip("还原" if self._window.isMaximized() else "最大化")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos and (e.buttons() & Qt.LeftButton):
            if not self._window.isMaximized():
                self._window.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._toggle_max()
            e.accept()
        else:
            super().mouseDoubleClickEvent(e)


# ═══════════════════════ 设置对话框 ═══════════════════════

class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("设置")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        self.chk_gesture = QCheckBox("启用鼠标手势（右键上下拖动切换文件夹）")
        self.chk_gesture.setChecked(bool(cfg.get("mouse_gesture", False)))
        lay.addWidget(self.chk_gesture)
        self.chk_name = QCheckBox("缩略图下方显示文件名")
        self.chk_name.setChecked(bool(cfg.get("show_filename", True)))
        lay.addWidget(self.chk_name)
        self.chk_remember = QCheckBox("记住上次打开的源 / 输出路径")
        self.chk_remember.setChecked(bool(cfg.get("remember_paths", True)))
        lay.addWidget(self.chk_remember)
        sr = QHBoxLayout()
        sr.addWidget(QLabel("缩略图大小："))
        self.combo_thumb = QComboBox()
        for v in settings.THUMB_CHOICES:
            self.combo_thumb.addItem(f"{v} x {v} px", v)
        idx = self.combo_thumb.findData(cfg.get("thumb_size", 200))
        if idx >= 0:
            self.combo_thumb.setCurrentIndex(idx)
        sr.addWidget(self.combo_thumb)
        sr.addStretch(1)
        lay.addLayout(sr)
        tip = QLabel(
            "键盘快捷键：\n  Up/Down  切换文件夹\n  PageUp/Down  快速翻页\n"
            "  Space  勾选/取消\n  C  设为封面\n  Esc  取消封面\n"
            "  Ctrl+A  全选\n  Ctrl+Shift+A  取消全选")
        tip.setStyleSheet(
            "color:#6b7280; background:#f8fafc; border:1px solid #e5e7eb; "
            "border-radius:8px; padding:10px; font-size:12px;")
        lay.addWidget(tip)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("确定")
        ok.setObjectName("primaryBtn")
        ok.setDefault(True)
        cancel = QPushButton("取消")
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def accept(self):
        self.cfg["mouse_gesture"] = self.chk_gesture.isChecked()
        self.cfg["show_filename"] = self.chk_name.isChecked()
        self.cfg["remember_paths"] = self.chk_remember.isChecked()
        self.cfg["thumb_size"] = self.combo_thumb.currentData()
        super().accept()


# ═══════════════════════ 键盘/手势过滤器 ═══════════════════════

class PreviewNavFilter(QObject):
    def __init__(self, window):
        super().__init__()
        self._w = window
        self._th = MOUSE_GESTURE_THRESHOLD
        self._gp = False
        self._gy = 0.0
        self._gt = False

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.KeyPress:
            k = event.key()
            if k == Qt.Key_Up:
                self._w.goto_prev_folder(); return True
            if k == Qt.Key_Down:
                self._w.goto_next_folder(); return True
            if k == Qt.Key_PageUp:
                self._w.goto_page_up(); return True
            if k == Qt.Key_PageDown:
                self._w.goto_page_down(); return True
            m = event.modifiers()
            ctrl = bool(m & Qt.ControlModifier)
            if k == Qt.Key_Space:
                self._w.toggle_hover_item(); return True
            if k == Qt.Key_C and not ctrl:
                self._w.set_hover_item_cover(); return True
            if k == Qt.Key_Escape:
                self._w.cancel_current_cover(); return True
            if k == Qt.Key_A and ctrl and bool(m & Qt.ShiftModifier):
                self._w.deselect_all_current(); return True
            if k == Qt.Key_A and ctrl:
                self._w.select_all_current(); return True
            return False
        if not self._w.mouse_gesture_enabled:
            return False
        if t == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            self._gp = True
            self._gy = event.globalPosition().y()
            self._gt = False
        elif t == QEvent.MouseMove and self._gp and not self._gt:
            dy = event.globalPosition().y() - self._gy
            if dy >= self._th:
                self._w.goto_next_folder(); self._gt = True
            elif dy <= -self._th:
                self._w.goto_prev_folder(); self._gt = True
        elif t == QEvent.MouseButtonRelease and event.button() == Qt.RightButton:
            self._gp = False
        return False


# ═══════════════════════ 可折叠分组 ═══════════════════════

class CollapsibleGroup(QWidget):
    def __init__(self, title, icon="", parent=None):
        super().__init__(parent)
        self._title = title
        self._icon = icon
        self._expanded = True
        self._anim = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 2)
        outer.setSpacing(0)
        self.header = QPushButton()
        self.header.setObjectName("groupHeader")
        self.header.setCheckable(True)
        self.header.setChecked(True)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.toggled.connect(self._on_toggle)
        outer.addWidget(self.header)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(8, 4, 8, 4)
        self.body_layout.setSpacing(6)
        outer.addWidget(self.body)
        self._sync()

    def _sync(self):
        a = "v" if self._expanded else ">"
        self.header.setText(f"{a}  {self._icon}  {self._title}")
        self.body.setVisible(self._expanded)

    def _on_toggle(self, checked):
        self._expanded = checked
        if self._anim:
            self._anim.stop()
        if self._expanded:
            self.body.setVisible(True)
            self.body.setMaximumHeight(0)
            target = max(self.body.sizeHint().height(), 100)
            a = QPropertyAnimation(self.body, b"maximumHeight", self)
            a.setDuration(150)
            a.setStartValue(0)
            a.setEndValue(target)
            a.finished.connect(lambda: self.body.setMaximumHeight(16777215))
            a.start()
            self._anim = a
        else:
            current_h = self.body.height()
            a = QPropertyAnimation(self.body, b"maximumHeight", self)
            a.setDuration(150)
            a.setStartValue(current_h)
            a.setEndValue(0)
            a.finished.connect(lambda: self.body.setVisible(False))
            a.start()
            self._anim = a
        self._sync()


# ═══════════════════════ 缩略图卡片（核心修复） ═══════════════════════

class ThumbWidget(QFrame):
    """缩略图卡片 — 修复版。

    修复内容：
    1. thumb_area 背景透明，消除白色覆盖层
    2. 封面按钮 raise_() 确保始终可见
    3. 固定尺寸，所有卡片大小一致
    4. 勾选框右上角，封面按钮左上角，互不遮挡
    """
    toggled = Signal(str, bool)
    cover_clicked = Signal(str, str)
    hovered = Signal(object)

    def __init__(self, item_id, label, folder_name, is_image,
                 cover_export_name="", pixmap=None, thumb_size=THUMB_SIZE,
                 show_name=True, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.folder_name = folder_name
        self.is_image = is_image
        self.cover_export_name = cover_export_name
        self.thumb_size = thumb_size
        self._is_cover = False
        self._checked = False
        self._pixmap = None
        self.setObjectName("thumbCard")

        # ── 主布局 ──
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 2)
        lay.setSpacing(2)

        # ── 缩略图容器（QWidget，透明背景，叠放图片+按钮+勾选） ──
        self.thumb_container = QWidget()
        self.thumb_container.setFixedSize(THUMB_DISPLAY_SIZE + 8, THUMB_DISPLAY_SIZE + 8)
        self.thumb_container.setStyleSheet(
            f"background:transparent; border:1px solid {BORDER}; border-radius:8px;")

        # 图片标签（背景透明，不遮挡任何东西）
        self.thumb = ClickableLabel()
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setFixedSize(THUMB_DISPLAY_SIZE + 8, THUMB_DISPLAY_SIZE + 8)
        self.thumb.setStyleSheet("background:transparent; border:none;")
        self.thumb.setParent(self.thumb_container)
        self.thumb.move(0, 0)

        # 封面按钮（叠在缩略图左上角，raise_确保在最上层）
        self.cover_btn = QPushButton("封面")
        self.cover_btn.setObjectName("coverBtn")
        self.cover_btn.setCursor(Qt.PointingHandCursor)
        self.cover_btn.setStyleSheet(
            "background:rgba(255,255,255,0.92); color:#9ca3af; font-size:11px; "
            "padding:2px 6px; border-radius:4px; border:1px solid #e5e7eb;")
        self.cover_btn.setParent(self.thumb_container)
        self.cover_btn.move(4, 4)
        self.cover_btn.raise_()
        self.cover_label = self.cover_btn

        # 勾选框（叠在缩略图右上角，raise_确保在最上层）
        self.check = CircleCheckBox()
        self.check.setParent(self.thumb_container)
        self.check.raise_()
        self._update_check_pos()

        lay.addWidget(self.thumb_container, 0, Qt.AlignHCenter)

        # ── 文件名标签 ──
        self.name = QLabel(label)
        self.name.setWordWrap(True)
        self.name.setMaximumHeight(28)
        self.name.setMinimumHeight(18)
        self.name.setToolTip(label)
        f = QFont()
        f.setPointSize(8)
        self.name.setFont(f)
        self.name.setStyleSheet(f"color:{TEXT_MUTED}; background:transparent;")
        self.name.setVisible(show_name)
        lay.addWidget(self.name)

        # 封面备注
        self.cover_note = QLabel("")
        self.cover_note.setAlignment(Qt.AlignCenter)
        self.cover_note.setStyleSheet(f"color:{COVER_COLOR}; font-size:11px; padding-top:2px; background:transparent;")
        self.cover_note.setVisible(False)
        lay.addWidget(self.cover_note)

        # ── 信号连接 ──
        self.check.toggled.connect(self._on_check)
        self.thumb.clicked.connect(self._on_thumb_click)
        self.cover_btn.clicked.connect(self._on_cover_click)

        self._hovered = False
        self.thumb.setAttribute(Qt.WA_Hover)
        self.thumb.installEventFilter(self)
        self.setAttribute(Qt.WA_Hover)

        if pixmap is not None:
            self.set_pixmap(pixmap)

    def _update_check_pos(self):
        """将勾选框定位到缩略图区域右上角。"""
        tw = self.thumb_container.width()
        self.check.move(tw - self.check.width() - 2, 2)

    def _on_thumb_click(self):
        """点击缩略图区域 = 勾选/取消勾选。"""
        self.check.setChecked(not self.check.isChecked())

    def _on_check(self, checked):
        self._checked = checked
        self._apply_border()
        self.toggled.emit(self.item_id, checked)

    def _on_cover_click(self):
        """封面按钮被点击。"""
        self.cover_clicked.emit(self.folder_name, self.item_id)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            if not self._hovered:
                self._hovered = True
                self.hovered.emit(self.item_id)
        elif event.type() == QEvent.Leave:
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                if self._hovered:
                    self._hovered = False
                    self.hovered.emit(None)
        return super().eventFilter(obj, event)

    def set_checked(self, checked):
        self._checked = checked
        self.check.blockSignals(True)
        self.check.setChecked(checked)
        self.check.blockSignals(False)
        self._apply_border()

    def set_cover(self, active):
        self._is_cover = active
        if active:
            self.cover_btn.setText("封面")
            self.cover_btn.setStyleSheet(
                "background:rgba(249,115,22,0.9); color:#fff; font-size:11px; "
                "padding:2px 6px; border-radius:4px; border:1px solid rgba(249,115,22,0.9); font-weight:bold;")
        else:
            self.cover_btn.setText("封面")
            self.cover_btn.setStyleSheet(
                "background:rgba(255,255,255,0.92); color:#9ca3af; font-size:11px; "
                "padding:2px 6px; border-radius:4px; border:1px solid #e5e7eb;")
        # 关键：每次设置封面状态后，确保按钮在最上层
        self.cover_btn.raise_()
        self._apply_border()
        self._update_cover_note()

    def _apply_border(self):
        """更新缩略图区域的边框样式。"""
        if self._is_cover:
            border_style = f"border:2px solid {BRAND};"
        elif self._checked:
            border_style = f"border:1.5px solid {BRAND};"
        else:
            border_style = f"border:1px solid {BORDER};"
        self.thumb_container.setStyleSheet(
            f"background:transparent; {border_style} border-radius:8px;")

    def _update_cover_note(self):
        if self._is_cover and self.cover_export_name:
            self.cover_note.setText(f"导出: {self.cover_export_name}")
            self.cover_note.setVisible(True)
        else:
            self.cover_note.setText("")
            self.cover_note.setVisible(False)

    def set_cover_visible(self, visible):
        self.cover_label.setVisible(visible)

    def set_pixmap(self, pixmap):
        """设置缩略图 — 按比例缩放不裁切，居中显示，无覆盖层。"""
        self._pixmap = pixmap
        area_w = self.thumb.width() - 4
        area_h = self.thumb.height() - 4
        if area_w < 20 or area_h < 20:
            area_w = THUMB_DISPLAY_SIZE
            area_h = THUMB_DISPLAY_SIZE
        scaled = pixmap.scaled(area_w, area_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumb.setPixmap(scaled)
        self._update_check_pos()
        self.cover_btn.raise_()

    def sizeHint(self):
        return QSize(THUMB_DISPLAY_SIZE + 16, THUMB_DISPLAY_SIZE + 48)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap:
            self.set_pixmap(self._pixmap)
        self._update_check_pos()
        self.cover_btn.raise_()


# ═══════════════════════ 主窗口 ═══════════════════════

class MainWindow(QMainWindow):

    _EDGE = 6

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1500, 900)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        self._drag_edge = None
        self._drag_pos = None
        self.work_folders = []
        self.selection = {}
        self.covers = {}
        self.item_folder = {}
        self.thumb_cache = {}
        self.generation = 0
        self.current_load_task = None
        self.thumb_widgets = {}
        self.hover_item_id = None
        self.all_items_current = []
        self.threadpool = QThreadPool.globalInstance()
        self.signals = WorkerSignals()
        self._connect_signals()
        self.settings_cfg = settings.load()
        self.mouse_gesture_enabled = bool(self.settings_cfg.get("mouse_gesture", False))
        self._build_ui()
        self._apply_remembered_paths()

    def _connect_signals(self):
        s = self.signals
        s.scan_progress.connect(self.on_scan_progress)
        s.scan_done.connect(self.on_scan_done)
        s.scan_error.connect(self.on_scan_error)
        s.load_ready.connect(self.on_load_ready)
        s.thumb_ready.connect(self.on_thumb_ready)
        s.export_log.connect(self.on_export_log)
        s.export_progress.connect(self.on_export_progress)
        s.export_done.connect(self.on_export_done)
        s.export_error.connect(self.on_export_error)

    # ═══════════════════════ 窗口边缘缩放 ═══════════════════════

    def _edge_at(self, pos):
        e = self._EDGE
        r = self.rect()
        l = pos.x() < e
        ri = pos.x() > r.width() - e
        t = pos.y() < e
        b = pos.y() > r.height() - e
        return l, ri, t, b

    def _cursor_for_edge(self, pos):
        l, ri, t, b = self._edge_at(pos)
        if l and t:
            return Qt.SizeFDiagCursor
        elif ri and t:
            return Qt.SizeBDiagCursor
        elif l and b:
            return Qt.SizeBDiagCursor
        elif ri and b:
            return Qt.SizeFDiagCursor
        elif l:
            return Qt.SizeHorCursor
        elif ri:
            return Qt.SizeHorCursor
        elif t:
            return Qt.SizeVerCursor
        elif b:
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            l, ri, t, b = self._edge_at(pos)
            if l or ri or t or b:
                self._drag_edge = (l, ri, t, b)
                self._drag_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        if self._drag_edge and (event.buttons() & Qt.LeftButton):
            cur_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
            diff = cur_pos - self._drag_pos
            l, ri, t, b = self._drag_edge
            geom = self.geometry()
            if l:
                geom.setLeft(geom.left() + diff.x())
            if ri:
                geom.setRight(geom.right() + diff.x())
            if t:
                geom.setTop(geom.top() + diff.y())
            if b:
                geom.setBottom(geom.bottom() + diff.y())
            if geom.width() > 200 and geom.height() > 200:
                self.setGeometry(geom)
            self._drag_pos = cur_pos
            event.accept()
        else:
            self.setCursor(self._cursor_for_edge(pos))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_edge = None
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    # ═══════════════════════ UI 构建 ═══════════════════════

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        self.title_bar = TitleBar(self)
        ml.addWidget(self.title_bar)
        self._build_toolbar(ml)
        content = QSplitter(Qt.Horizontal)
        content.setHandleWidth(1)
        self.splitter = content
        self._build_left_panel(content)
        self._build_right_panel(content)
        content.addWidget(self.left_frame)
        content.addWidget(self.right_frame)
        content.setStretchFactor(0, 0)
        content.setStretchFactor(1, 1)
        lr = self.settings_cfg.get("left_ratio", 0.21)
        QTimer.singleShot(0, lambda: self._set_splitter_ratio(lr))
        ml.addWidget(content, 1)
        self._build_status_bar(ml)
        self._build_log_area(ml)
        self.nav_filter = PreviewNavFilter(self)
        self.installEventFilter(self.nav_filter)

    def _set_splitter_ratio(self, ratio):
        total = self.splitter.width()
        if total > 50:
            self.splitter.setSizes([int(total * ratio), int(total * (1 - ratio))])

    def _build_toolbar(self, ml):
        tb = QFrame()
        tb.setStyleSheet(f"QFrame{{background:{PANEL}; border-bottom:1px solid {BORDER};}}")
        lay = QHBoxLayout(tb)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(10)
        for lbl_text in ("来源文件夹",):
            sl = QLabel(lbl_text)
            sl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
            lay.addWidget(sl)
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("选择包含作品文件夹的源目录...")
        lay.addWidget(self.src_edit, 1)
        lay.addWidget(QPushButton("浏览"))
        self.src_edit.parent().findChild(QPushButton).clicked.connect(self._browse_src)
        sl2 = QLabel("输出文件夹")
        sl2.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
        lay.addWidget(sl2)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("导出图片保存的位置...")
        lay.addWidget(self.out_edit, 1)
        b2 = QPushButton("浏览")
        b2.clicked.connect(self._browse_out)
        lay.addWidget(b2)
        lay.addSpacing(16)
        sb = QPushButton("设置")
        sb.setObjectName("textBtn")
        sb.clicked.connect(self._open_settings)
        lay.addWidget(sb)
        ob = QPushButton("打开输出")
        ob.setObjectName("textBtn")
        ob.clicked.connect(self._open_output_folder)
        lay.addWidget(ob)
        lay.addStretch(1)
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setObjectName("primaryBtn")
        self.scan_btn.clicked.connect(self._start_scan)
        lay.addWidget(self.scan_btn)
        ml.addWidget(tb)

    def _build_left_panel(self, parent):
        self.left_frame = QFrame()
        self.left_frame.setStyleSheet(f"QFrame{{background:{PANEL}; border-right:1px solid {BORDER};}}")
        ll = QVBoxLayout(self.left_frame)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        hdr = QLabel("  文件夹")
        hdr.setStyleSheet(f"color:{TEXT}; font-weight:bold; font-size:14px; padding:14px 12px 10px 12px; background:{PANEL}; border-bottom:1px solid {BORDER};")
        ll.addWidget(hdr)
        self.folder_list = QListWidget()
        self.folder_list.setStyleSheet(
            f"QListWidget{{background:{PANEL}; border:none; outline:none;}}"
            f"QListWidget::item{{padding:8px 14px; border-radius:8px; margin:2px 10px; min-height:28px; max-height:36px;}}"
            f"QListWidget::item:hover{{background:{HOVER_BG};}}"
            f"QListWidget::item:selected{{background:{BRAND}; color:#ffffff;}}")
        self.folder_list.currentRowChanged.connect(self._on_folder_selected)
        ll.addWidget(self.folder_list, 1)

    def _build_right_panel(self, parent):
        self.right_frame = QFrame()
        rl = QVBoxLayout(self.right_frame)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.preview_header = QLabel("  请选择文件夹")
        self.preview_header.setStyleSheet(f"color:{TEXT}; font-weight:bold; font-size:14px; padding:12px 16px 8px 16px; background:{PANEL};")
        rl.addWidget(self.preview_header)
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setStyleSheet("QScrollArea{border:none; background:transparent;}")
        self.preview_container = QWidget()
        self.preview_container.setStyleSheet(f"background:{BG};")
        self.preview_inner = QVBoxLayout(self.preview_container)
        self.preview_inner.setContentsMargins(16, 16, 16, 16)
        self.preview_inner.setSpacing(8)
        self.preview_scroll.setWidget(self.preview_container)
        rl.addWidget(self.preview_scroll, 1)

    def _build_status_bar(self, ml):
        sb = QFrame()
        sb.setObjectName("appStatusBar")
        sb.setStyleSheet(f"QFrame#appStatusBar{{background:{PANEL}; border-top:1px solid {BORDER};}}")
        sb.setFixedHeight(52)
        lay = QHBoxLayout(sb)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(16)
        # 状态图标 + 文字
        self.scan_status_icon = QLabel("●")
        self.scan_status_icon.setStyleSheet(f"color:{TEXT_MUTED}; font-size:14px; background:transparent;")
        lay.addWidget(self.scan_status_icon)
        self.scan_status_text = QLabel("就绪")
        self.scan_status_text.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:bold; background:transparent;")
        lay.addWidget(self.scan_status_text)
        self.scan_status_detail = QLabel("")
        self.scan_status_detail.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; background:transparent;")
        lay.addWidget(self.scan_status_detail)
        lay.addStretch(1)
        # 已选择 + 预计导出
        self.sel_count_label = QLabel("已选 0 页")
        self.sel_count_label.setStyleSheet(f"color:{BRAND}; font-size:13px; font-weight:bold; background:transparent;")
        lay.addWidget(self.sel_count_label)
        self.export_count_label = QLabel("预计导出: 0 张")
        self.export_count_label.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; background:transparent;")
        lay.addWidget(self.export_count_label)
        # 清空按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setFixedWidth(56)
        self.clear_btn.clicked.connect(self._clear_selection)
        lay.addWidget(self.clear_btn)
        # 分隔
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(24)
        sep.setStyleSheet(f"color:{BORDER};")
        lay.addWidget(sep)
        # 导航按钮
        self.prev_btn = QPushButton("< 上一个")
        self.prev_btn.setObjectName("navBtn")
        self.prev_btn.setFixedWidth(90)
        self.prev_btn.clicked.connect(self.goto_prev_folder)
        lay.addWidget(self.prev_btn)
        self.next_btn = QPushButton("下一个 >")
        self.next_btn.setObjectName("navBtn")
        self.next_btn.setFixedWidth(90)
        self.next_btn.clicked.connect(self.goto_next_folder)
        lay.addWidget(self.next_btn)
        # 导出按钮
        self.export_btn = QPushButton("开始导出")
        self.export_btn.setObjectName("primaryBtn")
        self.export_btn.setFixedWidth(120)
        self.export_btn.clicked.connect(self._start_export)
        self.export_btn.setEnabled(False)
        lay.addWidget(self.export_btn)
        ml.addWidget(sb)

    def _build_log_area(self, ml):
        self.log_container = QWidget()
        log_lay = QVBoxLayout(self.log_container)
        log_lay.setContentsMargins(12, 0, 12, 4)
        log_lay.setSpacing(0)
        self.log_header = QPushButton("日志  >")
        self.log_header.setObjectName("logHeader")
        self.log_header.setCursor(Qt.PointingHandCursor)
        self.log_header.clicked.connect(self._toggle_log)
        log_lay.addWidget(self.log_header)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(120)
        self.log_area.setVisible(False)
        log_lay.addWidget(self.log_area)
        self._log_expanded = False
        ml.addWidget(self.log_container)

    def _toggle_log(self):
        self._log_expanded = not self._log_expanded
        self.log_area.setVisible(self._log_expanded)
        self.log_header.setText("日志  v" if self._log_expanded else "日志  >")

    # ═══════════════════════ 浏览/设置/打开输出 ═══════════════════════

    def _browse_src(self):
        d = QFileDialog.getExistingDirectory(self, "选择来源文件夹", self.src_edit.text())
        if d:
            self.src_edit.setText(d)

    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出文件夹", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    def _open_settings(self):
        dlg = SettingsDialog(self.settings_cfg, self)
        if dlg.exec() == QDialog.Accepted:
            self._apply_settings()

    def _apply_settings(self):
        self.mouse_gesture_enabled = bool(self.settings_cfg.get("mouse_gesture", False))
        settings.save(self.settings_cfg)
        self._regenerate_thumbs()

    def _regenerate_thumbs(self):
        if not self.all_items_current:
            return
        self.generation += 1
        gen = self.generation
        task = ThumbTask(gen, self.all_items_current, self.signals, self.settings_cfg.get("thumb_size", THUMB_SIZE))
        self.threadpool.start(task)

    def _open_output_folder(self):
        out = self.out_edit.text().strip()
        if not out:
            QMessageBox.information(self, "提示", "请先设置输出文件夹。")
            return
        if not os.path.isdir(out):
            QMessageBox.warning(self, "提示", f"输出文件夹不存在：{out}")
            return
        if hasattr(os, 'startfile'):
            os.startfile(out)
        else:
            os.system(f'open "{out}"')

    def _apply_remembered_paths(self):
        if not self.settings_cfg.get("remember_paths", True):
            return
        src = self.settings_cfg.get("src_dir", "")
        out = self.settings_cfg.get("out_dir", "")
        if src and os.path.isdir(src):
            self.src_edit.setText(src)
        if out and os.path.isdir(out):
            self.out_edit.setText(out)

    def _remember_paths(self):
        self.settings_cfg["src_dir"] = self.src_edit.text().strip()
        self.settings_cfg["out_dir"] = self.out_edit.text().strip()
        settings.save(self.settings_cfg)

    # ═══════════════════════ 扫描 ═══════════════════════

    def _start_scan(self):
        src = self.src_edit.text().strip()
        if not src or not os.path.isdir(src):
            QMessageBox.warning(self, "提示", "请选择有效的来源文件夹。")
            return
        self._remember_paths()
        self.scan_btn.setEnabled(False)
        self.scan_status_icon.setStyleSheet(f"color:#f59e0b; font-size:20px; font-weight:bold; background:transparent;")
        self.scan_status_icon.setText("●")
        self.scan_status_text.setText("扫描中...")
        self.scan_status_detail.setText("")
        self.folder_list.clear()
        self.work_folders = []
        self.selection.clear()
        self.covers.clear()
        self.item_folder.clear()
        self.thumb_cache.clear()
        self.thumb_widgets.clear()
        self.all_items_current = []
        self.hover_item_id = None
        self.generation += 1
        self._clear_preview()
        self.preview_header.setText("  扫描中...")
        task = ScanTask(src, self.out_edit.text().strip(), self.signals)
        self.threadpool.start(task)

    def on_scan_progress(self, current, total):
        self.scan_status_detail.setText(f"{current} / {total}")

    def on_scan_done(self, folders):
        self.work_folders = folders
        self.scan_btn.setEnabled(True)
        self.scan_status_icon.setStyleSheet(f"color:#16a34a; font-size:20px; font-weight:bold; background:transparent;")
        self.scan_status_icon.setText("●")
        total_items = sum(f.image_count + f.pdf_count for f in folders)
        self.scan_status_text.setText("扫描完成")
        self.scan_status_detail.setText(f"找到 {len(folders)} 个文件夹，共 {total_items} 项")
        self._populate_folder_list()
        self._remember_paths()

    def on_scan_error(self, msg):
        self.scan_btn.setEnabled(True)
        self.scan_status_icon.setStyleSheet(f"color:#dc2626; font-size:20px; font-weight:bold; background:transparent;")
        self.scan_status_icon.setText("●")
        self.scan_status_text.setText("扫描失败")
        self.scan_status_detail.setText(msg[:60])
        QMessageBox.warning(self, "扫描失败", msg)

    def _populate_folder_list(self):
        """填充左侧文件夹列表，显示勾选标记。"""
        self.folder_list.clear()
        for i, f in enumerate(self.work_folders):
            total = f.image_count + f.pdf_count
            # 勾选状态标记
            has_sel = f.name in self.selection and any(self.selection.values())
            has_cover = f.name in self.covers and self.covers.get(f.name)
            if has_cover and has_sel:
                badge = "[✓]"
            elif has_sel:
                badge = "[●]"
            elif has_cover:
                badge = "[★]"
            else:
                badge = "   "
            item = QListWidgetItem(f"{badge} {i + 1}.  {f.name}")
            item.setData(Qt.UserRole, i)
            self.folder_list.addItem(item)
        if self.work_folders:
            self.folder_list.setCurrentRow(0)

    def _refresh_folder_badges(self):
        """刷新左侧文件夹列表的勾选状态指示。"""
        for i, f in enumerate(self.work_folders):
            item = self.folder_list.item(i)
            if not item:
                continue
            has_sel = f.name in self.selection and self.selection.get(f.name, False)
            has_cover = f.name in self.covers and self.covers.get(f.name)
            if has_cover and has_sel:
                badge = "[✓]"
            elif has_sel:
                badge = "[●]"
            elif has_cover:
                badge = "[★]"
            else:
                badge = "   "
            item.setText(f"{badge} {i + 1}.  {f.name}")

    def _missed_folders(self):
        return [f for f in self.work_folders
                if not f.is_processed and f.name not in self.selection
                and f.name not in self.covers]

    def _check_missed_folders(self):
        return [f.name for f in self.work_folders
                if not f.is_processed
                and not self.selection.get(f.name, False)
                and not self.covers.get(f.name)]

    # ═══════════════════════ 文件夹选择 → 加载预览 ═══════════════════════

    def _on_folder_selected(self, row):
        if row < 0 or row >= len(self.work_folders):
            return
        self._load_folder(self.work_folders[row])

    def _load_folder(self, folder):
        self.generation += 1
        self._clear_preview()
        self.preview_header.setText(f"  加载中：{folder.name}...")
        self.scan_status_text.setText(f"加载中：{folder.name}")
        self.scan_status_detail.setText("")
        if self.current_load_task:
            self.current_load_task.cancel()
        task = LoadTask(self.generation, folder, self.signals)
        self.current_load_task = task
        self.threadpool.start(task)

    def on_load_ready(self, gen, name, items, groups):
        if gen != self.generation:
            return
        self.all_items_current = items
        folder = next((f for f in self.work_folders if f.name == name), None)
        if folder:
            for it in items:
                self.item_folder[it.id] = folder
        total_count = len(items)
        self.preview_header.setText(f"{name}（{total_count} 项）")
        self.scan_status_text.setText("扫描完成")
        self.scan_status_detail.setText(f"找到 {total_count} 项")
        self._clear_preview()
        if groups:
            self._build_grouped_preview(groups)
        else:
            self._build_flat_preview(items)
        self.preview_container.updateGeometry()
        self.preview_scroll.updateGeometry()
        thumb_size = self.settings_cfg.get("thumb_size", THUMB_SIZE)
        task = ThumbTask(gen, items, self.signals, thumb_size)
        self.threadpool.start(task)
        self._update_sel_count()

    def _build_grouped_preview(self, groups):
        """按分组构建预览：图片和PDF分开，每个PDF独立区块。"""
        for grp in groups:
            grp_items = grp.ordered_items()
            if not grp_items:
                continue
            item_count = len(grp_items)
            grp_title = f"{grp.name}（{item_count} 项）"
            cg = CollapsibleGroup(grp_title)
            images = [it for it in grp_items if it.kind == "image"]
            pdfs = [it for it in grp_items if it.kind == "pdf"]
            pdf_groups = {}
            for it in pdfs:
                key = str(it.path)
                if key not in pdf_groups:
                    pdf_groups[key] = []
                pdf_groups[key].append(it)

            inner_layout = QVBoxLayout()
            inner_layout.setContentsMargins(0, 0, 0, 0)
            inner_layout.setSpacing(8)

            # 图片区
            if images:
                img_grid = UniformGridLayout(margin=6, spacing=8)
                for it in images:
                    card = self._make_thumb_widget(it)
                    img_grid.addWidget(card)
                img_widget = QWidget()
                img_widget.setStyleSheet(f"background:{BG};")
                img_lay = QVBoxLayout(img_widget)
                img_lay.setContentsMargins(0, 0, 0, 0)
                img_lay.addLayout(img_grid)
                inner_layout.addWidget(img_widget)

            # PDF区块
            for pdf_path, pdf_items in pdf_groups.items():
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{BORDER};")
                sep.setContentsMargins(20, 4, 20, 4)
                inner_layout.addWidget(sep)
                pdf_name = pdf_items[0].path.name if pdf_items else "PDF"
                pdf_title = QLabel(f"{pdf_name}（{len(pdf_items)} 页）")
                pdf_title.setStyleSheet(
                    f"color:{TEXT_MUTED}; font-size:11px; font-weight:bold; "
                    f"padding:4px 12px; background:{PANEL};")
                inner_layout.addWidget(pdf_title)
                pdf_grid = UniformGridLayout(margin=6, spacing=8)
                for it in pdf_items:
                    card = self._make_thumb_widget(it)
                    pdf_grid.addWidget(card)
                pdf_widget = QWidget()
                pdf_widget.setStyleSheet(f"background:{BG};")
                pdf_lay = QVBoxLayout(pdf_widget)
                pdf_lay.setContentsMargins(0, 0, 0, 0)
                pdf_lay.addLayout(pdf_grid)
                inner_layout.addWidget(pdf_widget)

            cg.body_layout.addLayout(inner_layout)
            self.preview_inner.addWidget(cg)

    def _build_flat_preview(self, items):
        """无分组时扁平展示。"""
        images = [it for it in items if it.kind == "image"]
        pdfs = [it for it in items if it.kind == "pdf"]
        pdf_groups = {}
        for it in pdfs:
            key = str(it.path)
            if key not in pdf_groups:
                pdf_groups[key] = []
            pdf_groups[key].append(it)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        if images:
            img_grid = UniformGridLayout(margin=8, spacing=10)
            for it in images:
                card = self._make_thumb_widget(it)
                img_grid.addWidget(card)
            img_widget = QWidget()
            img_widget.setStyleSheet(f"background:{BG};")
            img_layout = QVBoxLayout(img_widget)
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.addLayout(img_grid)
            main_layout.addWidget(img_widget)

        for pdf_path, pdf_items in pdf_groups.items():
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{BORDER};")
            sep.setContentsMargins(20, 4, 20, 4)
            main_layout.addWidget(sep)
            pdf_name = pdf_items[0].path.name if pdf_items else "PDF"
            pdf_title = QLabel(f"{pdf_name}（{len(pdf_items)} 页）")
            pdf_title.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:11px; font-weight:bold; "
                f"padding:4px 12px; background:{PANEL};")
            main_layout.addWidget(pdf_title)
            pdf_grid = UniformGridLayout(margin=8, spacing=10)
            for it in pdf_items:
                card = self._make_thumb_widget(it)
                pdf_grid.addWidget(card)
            pdf_widget = QWidget()
            pdf_widget.setStyleSheet(f"background:{BG};")
            pdf_layout = QVBoxLayout(pdf_widget)
            pdf_layout.setContentsMargins(0, 0, 0, 0)
            pdf_layout.addLayout(pdf_grid)
            main_layout.addWidget(pdf_widget)

        main_layout.addStretch(1)
        container = QWidget()
        container.setStyleSheet(f"background:{BG};")
        container.setLayout(main_layout)
        self.preview_inner.addWidget(container)

    def on_load_done(self, gen, name):
        if gen != self.generation:
            return
        self.scan_status_text.setText(f"{name}：加载失败")

    def _make_thumb_widget(self, item):
        show_name = self.settings_cfg.get("show_filename", True)
        folder = self.item_folder.get(item.id)
        fname = folder.name if folder else ""
        cover_exp = fname if (fname and self.covers.get(fname) == item.id) else ""
        w = ThumbWidget(
            item.id, item.label, fname, item.kind == "image",
            cover_export_name=cover_exp,
            thumb_size=self.settings_cfg.get("thumb_size", THUMB_SIZE),
            show_name=show_name)
        if self.selection.get(item.id, False):
            w.set_checked(True)
        if self.covers.get(fname) == item.id:
            w.set_cover(True)
        w.toggled.connect(self._on_item_toggled)
        w.cover_clicked.connect(self._on_cover_label_clicked)
        w.hovered.connect(self._on_thumb_hover)
        self.thumb_widgets[item.id] = w
        return w

    def _clear_preview(self):
        while self.preview_inner.count():
            child = self.preview_inner.takeAt(0)
            w = child.widget()
            if w:
                w.deleteLater()
            else:
                sub = child.layout()
                if sub:
                    while sub.count():
                        sc = sub.takeAt(0)
                        sw = sc.widget()
                        if sw:
                            sw.deleteLater()

    # ═══════════════════════ 缩略图就绪 ═══════════════════════

    def on_thumb_ready(self, gen, item_id, qimg):
        if gen != self.generation:
            return
        self.thumb_cache[item_id] = qimg
        w = self.thumb_widgets.get(item_id)
        if w:
            w.set_pixmap(QPixmap.fromImage(qimg))

    # ═══════════════════════ 勾选/封面/全选 ═══════════════════════

    def _on_item_toggled(self, item_id, checked):
        self.selection[item_id] = checked
        self._update_sel_count()
        self._refresh_folder_badges()

    def _on_select_all(self, checked):
        for item in self.all_items_current:
            self.selection[item.id] = checked
            w = self.thumb_widgets.get(item.id)
            if w:
                w.set_checked(checked)
        self._update_sel_count()
        self._refresh_folder_badges()

    def _on_cover_label_clicked(self, folder_name, item_id):
        if self.covers.get(folder_name) == item_id:
            # 取消封面
            del self.covers[folder_name]
            w = self.thumb_widgets.get(item_id)
            if w:
                w.set_cover(False)
            self._sync_cover_buttons(folder_name)
        else:
            # 设置封面
            old_id = self.covers.get(folder_name)
            if old_id:
                ow = self.thumb_widgets.get(old_id)
                if ow:
                    ow.set_cover(False)
            self.covers[folder_name] = item_id
            w = self.thumb_widgets.get(item_id)
            if w:
                w.set_cover(True)
            self._sync_cover_buttons(folder_name)
        self._update_sel_count()
        self._refresh_folder_badges()

    # 测试用公开别名
    on_cover_clicked = _on_cover_label_clicked

    def _sync_cover_buttons(self, folder_name):
        """同步封面按钮可见性：有封面时仅封面按钮可见，无封面时全部可见。"""
        has_cover = folder_name in self.covers
        for it in self.all_items_current:
            w = self.thumb_widgets.get(it.id)
            if not w:
                continue
            folder = self.item_folder.get(it.id)
            if folder and folder.name == folder_name:
                if has_cover:
                    w.cover_btn.setVisible(self.covers.get(folder_name) == it.id)
                else:
                    w.cover_btn.setVisible(True)

    def select_all_current(self):
        for item in self.all_items_current:
            self.selection[item.id] = True
            w = self.thumb_widgets.get(item.id)
            if w:
                w.set_checked(True)
        self._update_sel_count()
        self._refresh_folder_badges()

    def deselect_all_current(self):
        for item in self.all_items_current:
            self.selection[item.id] = False
            w = self.thumb_widgets.get(item.id)
            if w:
                w.set_checked(False)
        self._update_sel_count()
        self._refresh_folder_badges()

    def _clear_selection(self):
        self.deselect_all_current()

    def _update_sel_count(self):
        sel = sum(1 for v in self.selection.values() if v)
        cover_count = sum(1 for v in self.covers.values() if v)
        self.sel_count_label.setText(f"已选择 {sel + cover_count} 页")
        self.export_count_label.setText(f"预计导出：{sel + cover_count} 张")
        self.export_btn.setEnabled(sel + cover_count > 0)

    # ═══════════════════════ 悬停导航 ═══════════════════════

    def _on_thumb_hover(self, item_id):
        self.hover_item_id = item_id

    def toggle_hover_item(self):
        if self.hover_item_id:
            w = self.thumb_widgets.get(self.hover_item_id)
            if w:
                w.set_checked(not w._checked)

    def set_hover_item_cover(self):
        if not self.hover_item_id:
            return
        item = self._find_item_by_id(self.hover_item_id)
        if item:
            folder = self.item_folder.get(item.id)
            if folder:
                self._on_cover_label_clicked(folder.name, item.id)

    def cancel_current_cover(self):
        if not self.hover_item_id:
            return
        item = self._find_item_by_id(self.hover_item_id)
        if item:
            folder = self.item_folder.get(item.id)
            if folder and self.covers.get(folder.name) == item.id:
                del self.covers[folder.name]
                w = self.thumb_widgets.get(item.id)
                if w:
                    w.set_cover(False)
                self._update_sel_count()
                self._refresh_folder_badges()

    def _find_item_by_id(self, item_id):
        for it in self.all_items_current:
            if it.id == item_id:
                return it
        return None

    # ═══════════════════════ 文件夹导航 ═══════════════════════

    def goto_prev_folder(self):
        row = self.folder_list.currentRow()
        if row > 0:
            self.folder_list.setCurrentRow(row - 1)

    def goto_next_folder(self):
        row = self.folder_list.currentRow()
        if row < self.folder_list.count() - 1:
            self.folder_list.setCurrentRow(row + 1)

    def goto_page_up(self):
        sb = self.preview_scroll.verticalScrollBar()
        sb.setValue(sb.value() - sb.pageStep())

    def goto_page_down(self):
        sb = self.preview_scroll.verticalScrollBar()
        sb.setValue(sb.value() + sb.pageStep())

    # ═══════════════════════ 搜索/缩放 ═══════════════════════

    def _on_search_changed(self, text):
        import re
        text = text.strip().lower()
        for item in self.all_items_current:
            w = self.thumb_widgets.get(item.id)
            if not w:
                continue
            if not text:
                w.setVisible(True)
                continue
            w.setVisible(self._matches_search(item, text))

    def _matches_search(self, item, query):
        import re
        label_lower = item.label.lower()
        if query in label_lower:
            return True
        try:
            m = re.search(r'第(\d+)页', item.label)
            if m:
                page_num = int(m.group(1))
                for part in query.split(','):
                    part = part.strip()
                    if '-' in part:
                        lo, hi = part.split('-', 1)
                        if int(lo) <= page_num <= int(hi):
                            return True
                    elif part.isdigit() and int(part) == page_num:
                        return True
        except Exception:
            pass
        return False

    def _on_zoom_changed(self, value):
        self._regenerate_thumbs()

    # ═══════════════════════ 导出 ═══════════════════════

    def _start_export(self):
        out = self.out_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "提示", "请先设置输出文件夹。")
            return
        sel_count = sum(1 for v in self.selection.values() if v)
        cover_count = sum(1 for v in self.covers.values() if v)
        if sel_count + cover_count == 0:
            QMessageBox.information(self, "提示", "没有勾选任何项目。")
            return
        missed = self._check_missed_folders()
        if missed:
            names = ", ".join(missed[:8])
            extra = f"\n...还有 {len(missed) - 8} 个" if len(missed) > 8 else ""
            reply = QMessageBox.question(
                self, "漏选提醒",
                f"以下文件夹尚未勾选或设置封面：\n{names}{extra}\n\n仍然继续导出？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        self.export_btn.setEnabled(False)
        self.scan_status_icon.setStyleSheet(f"color:#f59e0b; font-size:20px; font-weight:bold; background:transparent;")
        self.scan_status_icon.setText("\u27f3")
        self.scan_status_text.setText("导出中...")
        self.scan_status_detail.setText("")
        task = ExportTask(self.work_folders, self.selection, out, self.signals, self.covers)
        self.threadpool.start(task)

    def on_export_log(self, msg):
        self.log_area.append(msg)

    def on_export_progress(self, current, total):
        pct = int(current / total * 100) if total > 0 else 0
        self.scan_status_detail.setText(f"{current}/{total} ({pct}%)")

    def on_export_done(self, success, skipped, failed):
        self.export_btn.setEnabled(True)
        self.scan_status_icon.setStyleSheet(f"color:#16a34a; font-size:20px; font-weight:bold; background:transparent;")
        self.scan_status_icon.setText("\u2714")
        parts = [f"成功 {success}"]
        if skipped:
            parts.append(f"跳过 {len(skipped)}")
        if failed:
            parts.append(f"失败 {len(failed)}")
        self.scan_status_text.setText("导出完成")
        self.scan_status_detail.setText("，".join(parts))
        for f in self.work_folders:
            f.is_processed = scanner.is_folder_processed(f.name, self.out_edit.text().strip())
        self._populate_folder_list()
        msg = f"导出完成！成功 {success} 张"
        if skipped:
            msg += f"，跳过 {len(skipped)} 张（同名文件已存在）"
        if failed:
            msg += f"，失败 {len(failed)} 张"
        QMessageBox.information(self, "导出完成", msg)

    def on_export_error(self, msg):
        self.export_btn.setEnabled(True)
        self.scan_status_icon.setStyleSheet(f"color:#dc2626; font-size:20px; font-weight:bold; background:transparent;")
        self.scan_status_icon.setText("\u2715")
        self.scan_status_text.setText("导出失败")
        self.scan_status_detail.setText(msg[:60])
        QMessageBox.warning(self, "导出失败", msg)
