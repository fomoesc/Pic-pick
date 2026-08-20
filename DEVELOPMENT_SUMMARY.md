# 拼版选图导出工作台 — 开发过程总结与项目归档

> 版本：v5.0.0  
> 归档日期：2026-08-21  
> 归档人：星图软件工程师（小马）

---

## 一、项目概述

### 工具名称
**拼版选图导出工作台** (Batch Image Picker & Exporter)

### 版本
v5.0.0

### 用途
从大量纸模/拼版作品文件夹中**挑选图片 → 勾选 → 一键导出并自动重命名**，替代手工逐张复制、改名的重复劳动。

### 解决的核心问题
用户维护着数百个纸模作品文件夹（每个文件夹含几十张拼版图 + 部分 PDF），需要从中精选图片后按统一命名规则导出。手工操作极其繁琐，且容易出错（重命名遗漏、格式不一致等）。

### 目标用户场景
1. 用户选择"源文件夹"（包含多个作品子文件夹的根目录）
2. 程序扫描所有作品文件夹，左侧列出
3. 用户逐个点击文件夹，右侧按分组显示缩略图
4. 用户勾选需要的图片，可设定封面
5. 点击"开始导出"，自动按命名规则导出到输出目录

---

## 二、技术架构

### 技术栈选型及原因

| 组件 | 选型 | 选择原因 |
|------|------|----------|
| 语言 | Python 3.10+ | 用户团队无编程背景，Python生态成熟、打包简单 |
| GUI框架 | PySide6 (Qt6) | 跨平台、组件丰富、支持无边框窗口、自定义布局、QSS样式 |
| PDF处理 | PyMuPDF (fitz) | 渲染速度快，支持缩放系数控制，API简洁 |
| 图像处理 | Pillow | 格式全覆盖（含GIF动画、AVIF/WebP/EXIF旋转） |
| 打包 | PyInstaller | 单文件exe打包成熟，支持 --windowed 无控制台模式 |

### 模块依赖关系

```
main.py (入口)
  ├── config.py (常量)
  ├── style.py (QSS样式)
  └── ui.py (主窗口)
        ├── settings.py (配置持久化)
        ├── scanner.py (目录扫描)
        │     └── pdf_render.py (PDF页数查询)
        ├── thumbnail.py (缩略图生成)
        │     └── pdf_render.py (PDF页渲染)
        ├── exporter.py (导出逻辑)
        │     ├── pdf_render.py (PDF渲染)
        │     └── scanner.py (WorkFolder数据类)
        └── config.py (常量引用)
```

### 每个源文件的职责

#### 1. `main.py`（程序入口，22行）
- 创建 `QApplication`，设置中文字体（微软雅黑 10pt）
- 加载全局 QSS 样式表
- 创建并显示 `MainWindow`
- 启动事件循环

#### 2. `config.py`（配置常量，45行）
- 所有可调参数集中管理
- 关键常量：`IMAGE_EXTS`（10种图片扩展名）、`PDF_EXT`、`THUMB_SIZE`（200px）、`PDF_EXPORT_ZOOM`（2.0）、`EXPORT_JPEG_QUALITY`（92）、`MOUSE_GESTURE_THRESHOLD`（50px）
- `APP_NAME`、`APP_VERSION`（5.0.0）

#### 3. `scanner.py`（目录扫描，183行）
- **核心数据类**：`MediaItem`（可导出单元）、`MediaGroup`（展示分组）、`WorkFolder`（作品文件夹）
- **核心函数**：
  - `natural_key()` — 自然排序（page-1 < page-10）
  - `collect_media()` — 递归收集文件夹内所有图片和PDF
  - `build_groups()` — 按第一层子文件夹分组（v4新增）
  - `scan_source_dir()` — 列出源目录下第一层子目录
  - `is_folder_processed()` — 判断作品是否已导出过

#### 4. `pdf_render.py`（PDF页渲染，65行）
- `get_pdf_page_count()` — 获取PDF页数（带缓存）
- `render_pdf_page()` — 渲染PDF页为PIL图像（导出用，zoom=2.0）
- `render_pdf_page_fit()` — 渲染PDF页使长边不超过指定尺寸（缩略图用）

#### 5. `thumbnail.py`（缩略图生成，100行）
- `make_image_thumb()` — 图片→缩略图QImage（支持GIF第一帧、EXIF旋转、透明通道白底化）
- `make_pdf_thumb()` — PDF页→缩略图QImage
- `make_thumb()` — 按MediaItem类型分派
- `placeholder_qimage()` — 生成灰色占位图（文件损坏或格式不支持时使用）
- `pil_to_qimage()` — PIL图像转QImage（RGB888格式，copy保证数据独立）

#### 6. `exporter.py`（导出逻辑，108行）
- `export_all()` — 导出所有勾选项
  - 封面优先导出（文件名=文件夹名本身，无编号）
  - 其余按 `(1).ext`、`(2).ext` 递增编号
  - 图片原样复制（保留GIF动画、PNG透明等）
  - PDF渲染为JPG（144 DPI）
  - 同名文件跳过不覆盖
  - 返回 `(成功数, 跳过列表, 失败列表)`

#### 7. `ui.py`（图形界面，~1714行，项目最大文件）
- **后台任务类**：`ScanTask`、`LoadTask`、`ThumbTask`、`ExportTask`（均继承 `QRunnable`）
- **信号中心**：`WorkerSignals`（统一管理所有跨线程信号）
- **自定义控件**：
  - `ClickableLabel` — 可点击标签
  - `CircleCheckBox` — 圆形勾选框（自绘，品牌橙色）
  - `UniformGridLayout` — 统一网格布局（自动计算列数，等宽等高）
  - `TitleBar` — 自定义标题栏（橙色渐变背景，拖拽移动）
  - `SettingsDialog` — 设置对话框
  - `PreviewNavFilter` — 键盘/鼠标手势事件过滤器
  - `CollapsibleGroup` — 可折叠分组（带动画）
  - `ThumbWidget` — 缩略图卡片（封面按钮+勾选框叠放）
- **主窗口** `MainWindow`：无边框窗口，左右分栏，边缘拖拽缩放

#### 8. `style.py`（全局QSS样式，~300行）
- v4橙色扁平化主题
- 品牌色系：`#f97316`（主橙）、`#fb923c`（浅橙）、`#ea580c`（深橙）
- 圆角：卡片12px、输入框/按钮8px、药丸100px
- 阴影：`0 2px 8px rgba(0,0,0,0.06)`
- 运行时生成白色对勾PNG图标（用于QSS checkbox样式）

#### 9. `settings.py`（设置持久化，60行）
- `load()` — 读取config.json，缺失项用默认值补齐
- `save()` — 写入config.json，失败静默
- `app_dir()` — 自动检测exe目录或源码目录
- 默认配置项：鼠标手势、文件名显示、缩略图大小、记住路径、左侧比例

---

## 三、核心功能详解

### 1. 目录扫描机制

**扫描流程**：
1. 用户点击"开始扫描"，传入源目录路径
2. `ScanTask`（后台线程）调用 `scanner.scan_source_dir()` 列出第一层子目录
3. 对每个子目录调用 `collect_media()` 递归收集所有图片和PDF
4. 调用 `build_groups()` 按第一层子文件夹分组
5. 调用 `is_folder_processed()` 检查是否已导出过
6. 通过信号将结果传回GUI线程

**自然排序**：使用 `natural_key()` 函数，将字符串拆分为文本段和数字段，数字段按数值比较。例如 `page-2` 排在 `page-10` 前面。

**分组策略**：
- 有子文件夹 → 每个子文件夹一个 `MediaGroup`，根目录散落文件归入"根目录"分组
- 无子文件夹 → 返回空列表，UI走扁平展示

### 2. 缩略图系统

**生成流程**：
1. `ThumbTask`（后台线程）遍历当前文件夹的所有 `MediaItem`
2. 调用 `thumbnail.make_thumb()` 生成缩略图
3. 图片：Pillow打开 → EXIF旋转 → 透明通道白底化 → thumbnail缩放 → 转QImage
4. PDF：`render_pdf_page_fit()` 按长边限制渲染 → thumbnail缩放 → 转QImage
5. 通过信号传回GUI线程，`ThumbWidget.set_pixmap()` 显示

**缓存机制**：`thumb_cache` 字典以 `item_id` 为key缓存QImage，切回已加载文件夹时秒开。

**占位图处理**：文件损坏或格式不支持时，`placeholder_qimage()` 生成浅灰底+居中"无法预览"文字，绝不崩溃。

### 3. 勾选与封面系统

**勾选状态**：
- 存储在 `MainWindow.selection` 字典：`{item_id: bool}`
- 点击缩略图或勾选框均可切换
- 支持 `Ctrl+A` 全选、`Ctrl+Shift+A` 取消全选、`Space` 键切换当前悬停项

**封面系统**（v4新增）：
- 每个作品文件夹最多1张封面，存储在 `MainWindow.covers`：`{文件夹名: item_id}`
- 封面按钮点击逻辑：
  - 第一次点击 → 设为封面（同时自动勾选）
  - 再次点击同一张 → 取消封面（勾选保留）
  - 点击另一张 → 自动取消前一张封面，设为新封面
- 封面按钮互斥：有封面时仅封面按钮可见，无封面时全部可见

### 4. 导出系统

**命名规则**：
- 封面：`{文件夹名}.{扩展名}`（无编号，作为第一个文件）
- 其余：`{文件夹名} ({n}).{扩展名}`（从1开始递增）

**核心规则**：
- 图片原样复制（`shutil.copy2`），保留GIF动画、PNG透明、WebP/AVIF原格式
- PDF渲染为JPG（zoom=2.0，约144 DPI，quality=92）
- 同名文件跳过不覆盖，记录到跳过清单
- 封面无需勾选，设了即导出
- 导出前弹窗提醒漏选的文件夹

### 5. GUI架构

**窗口架构**：
- 无边框窗口（`Qt.FramelessWindowHint`）
- 自定义标题栏（橙色渐变背景，支持拖拽移动和双击最大化/还原）
- 窗口边缘拖拽缩放（6px检测区域，8方向光标提示）
- 左右分栏（`QSplitter`，左侧文件夹列表，右侧缩略图预览）

**线程模型**：
- `QThreadPool` 全局线程池管理所有后台任务
- `WorkerSignals` 统一信号中心，所有跨线程通信通过信号槽
- `generation` 机制防止旧任务结果覆盖新任务（过期任务自动忽略）

**布局系统**：
- `UniformGridLayout`：自定义QLayout，根据可用宽度自动计算列数（最少3列）
- 所有缩略图卡片等宽等高（`THUMB_DISPLAY_SIZE + 16` × `THUMB_DISPLAY_SIZE + 48`）
- 图片按比例缩放不裁切，居中显示

### 6. 键盘与鼠标手势

**键盘快捷键**（通过 `PreviewNavFilter` 事件过滤器）：
| 按键 | 功能 |
|------|------|
| ↑ / ↓ | 切换上一个/下一个文件夹 |
| PageUp / PageDown | 快速翻页（约10个文件夹） |
| Space | 勾选/取消当前悬停项 |
| C | 设为封面 |
| Esc | 取消封面 |
| Ctrl+A | 全选当前文件夹 |
| Ctrl+Shift+A | 取消全选 |

**鼠标手势**（默认关闭，可开启）：
- 按住右键上下拖动切换文件夹
- 拖动距离 ≥ 50px 才触发（防误触）
- 每次只触发一次（`_gt` 标志防止连续触发）

---

## 四、版本演进历史

### v1.0 — 基础版本
- 基本功能：扫描源目录 → 选择文件夹 → 勾选图片 → 导出重命名
- 支持 JPG/PNG/BMP 等常见格式
- 导出统一为 `.jpg` 格式
- 基础 GUI 布局

### v2.0 — 自然排序 + 导航
**关键改动**（根据 `test_v2.py`）：
- 实现自然排序（`natural_key()`），文件夹和文件按数值顺序排列
- 添加漏选统计（`_missed_folders()`）
- 添加导航按钮边界控制（prev/next 到达边界时禁用）
- 测试覆盖：自然排序正确性、collect_media排序、漏选统计、导航按钮边界

### v3.0 — 多格式支持 + 快捷键
**关键改动**（根据 `test_v3.py`）：
- 图片格式扩展至10种：`jpg/jpeg/png/gif/bmp/avif/webp/tif/tiff/jfif`
- GIF缩略图取第一帧，导出原样复制保留动画
- 导出扩展名跟随源文件（不再统一转JPG）
- 损坏文件返回占位图，不崩溃
- 键盘导航：方向键切换文件夹、PageUp/PageDown翻页
- 鼠标手势：右键拖动切换文件夹（可开关）
- 测试覆盖：10种格式识别、GIF帧验证、占位图生成、导出扩展名、手势开关

### v4.0 — 子文件夹分组 + 封面系统
**关键改动**（根据 `test_v4.py`）：
- 子文件夹分组展示（`build_groups()`）
- 封面功能（`covers` 字典、封面按钮互斥、跨文件夹保留）
- 封面导出规则：文件名=文件夹名本身、无编号、优先导出
- 漏选统计考虑封面（设封面的文件夹不算漏选）
- PDF页也显示封面按钮
- 折叠动画（`QPropertyAnimation`）
- 测试覆盖：build_groups分组、封面导出命名、封面互斥、跨文件夹保留、漏选统计

### v5.0 — UI重构 + 橙色主题
**关键改动**（根据 `test_v5.py` 和代码）：
- 工具名称统一为"拼版选图导出工作台"
- 橙色扁平化主题（`style.py` 重写）
- 无边框窗口 + 自定义标题栏
- 窗口边缘拖拽缩放
- 统一网格布局（`UniformGridLayout`）
- 圆形勾选框（`CircleCheckBox` 自绘）
- 消除缩略图白色覆盖层（背景改为透明）
- 封面按钮始终可见（`raise_()` 确保在最上层）
- 所有缩略图统一大小
- 文件夹勾选标记实时刷新
- 多个PDF分开显示（每个PDF一个可折叠区块）
- 测试覆盖：工具名称、PDF分离显示、封面自动勾选、复选框图标、标题栏按钮尺寸、窗口圆角遮罩

---

## 五、配置系统

### config.py 参数

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `IMAGE_EXTS` | 10种格式 | 支持的图片扩展名集合 |
| `PDF_EXT` | `.pdf` | PDF扩展名 |
| `THUMB_SIZE` | 200 | 缩略图基准尺寸（px） |
| `THUMB_COLS` | 4 | 每行缩略图列数（未使用，由UniformGridLayout动态计算） |
| `PDF_EXPORT_ZOOM` | 2.0 | PDF渲染缩放系数（≈144 DPI） |
| `EXPORT_JPEG_QUALITY` | 92 | 导出JPG质量（1-100） |
| `enable_mouse_gesture` | False | 鼠标手势开关（运行时变量） |
| `MOUSE_GESTURE_THRESHOLD` | 50 | 手势触发最小拖动距离（px） |
| `APP_NAME` | "拼版选图导出工作台" | 应用名称 |
| `APP_VERSION` | "5.0.0" | 版本号 |
| `COVER_BORDER_COLOR` | "#f59e0b" | 封面高亮边框颜色 |

### config.json 格式

```json
{
  "mouse_gesture": true,
  "show_filename": true,
  "thumb_size": 200,
  "remember_paths": true,
  "src_dir": "...",
  "out_dir": "...",
  "left_ratio": 0.21
}
```

### settings.py 持久化机制

- `app_dir()` 自动检测程序目录（`sys.frozen` 区分打包/开发环境）
- `load()` 读取 config.json，缺失项用 `DEFAULTS` 补齐，任何异常返回默认值
- `save()` 写入 config.json，失败静默（不崩溃）
- `THUMB_CHOICES = (150, 200, 250)` 缩略图尺寸可选值
- `left_ratio` 校验范围 0.05~0.8

---

## 六、已知问题与限制

### 来自 README.md 的已知限制
1. 缩略图首次查看某个文件夹时会边加载边显示，图片/PDF越多越慢
2. 导出为"原图复制+重命名"；PDF才重新渲染为JPG
3. 一次扫描结果对应一个源目录，换目录需重新扫描
4. 勾选状态保存在内存里，关闭程序后不保留
5. AVIF/WebP缩略图渲染依赖Pillow版本

### 从代码中发现的潜在问题

#### 🔴 重复方法定义（ui.py）
以下方法在 `MainWindow` 类中定义了**两次**（第二次定义覆盖第一次）：
- `goto_prev_folder()` — 出现在第~1230行和第~1340行
- `goto_next_folder()` — 同上
- `goto_page_up()` — 同上
- `goto_page_down()` — 同上
- `_on_search_changed()` — 同上
- `_matches_search()` — 同上
- `_on_zoom_changed()` — 同上

这意味着这些方法的最终行为取决于后定义的版本。虽然功能上等效，但这是明显的代码质量问题，表明ui.py经历了多次部分重写，存在合并遗留。

#### 🟡 辅助脚本残留
- `write_ui.py` 和 `_write_ui_p2.py` 是开发过程中用于生成/重写ui.py的临时脚本，包含了完整的旧版ui.py代码。这些文件已不再使用，建议归档或删除。

#### 🟡 线程安全
- `selection`、`covers`、`item_folder` 等共享字典在GUI线程和后台线程之间共享，虽然当前操作模式下不太会出现竞态（GUI线程写入，后台线程只读），但理论上线程不安全。

#### 🟡 缩略图缓存无上限
- `thumb_cache` 字典会持续增长，切换多个文件夹后内存占用可能较大。没有LRU淘汰机制。

#### 🟡 `config.py` 中的可变全局变量
- `enable_mouse_gesture` 是一个模块级可变变量（而非通过 `settings.py` 管理），与 `settings.mouse_gesture` 存在两套独立的状态。

---

## 七、打包与部署

### PyInstaller 打包流程

```bat
# build.bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==== Building 拼版选图导出工作台 ====
python -m PyInstaller --onefile --windowed --name "拼版选图导出工作台" --clean --noconfirm main.py
echo.
echo ==== Done. EXE is in dist\ folder ====
pause
```

**打包参数**：
- `--onefile` — 单文件打包
- `--windowed` — 无控制台窗口
- `--name` — 输出文件名
- `--clean` — 清理临时文件

### spec 文件配置
- 输出名：`拼版选图导出工作台_v5.0.0`
- `console=False` — 无控制台
- `upx=True` — 启用UPX压缩
- 无额外数据文件或隐藏导入

### 产物位置
- `dist\拼版选图导出工作台_v5.0.0.exe`（约95MB）

### 依赖清单

```
PySide6          # GUI框架
PyMuPDF (fitz)   # PDF渲染
Pillow           # 图像处理
PyInstaller      # 打包
```

---

## 八、代码质量观察

### 重复方法问题（需关注）

`ui.py` 中 `MainWindow` 类存在7组重复方法定义。这是项目最大的代码质量隐患。建议执行以下清理：

```python
# 需要删除的重复方法（保留较新的版本即可）：
# goto_prev_folder     (第~1340行附近的版本)
# goto_next_folder     (第~1340行附近的版本)
# goto_page_up         (第~1340行附近的版本)
# goto_page_down       (第~1340行附近的版本)
# _on_search_changed   (第~1340行附近的版本)
# _matches_search      (第~1340行附近的版本)
# _on_zoom_changed     (第~1340行附近的版本)
```

### 整体代码架构评价

**优点**：
- 模块职责清晰：scanner/thumbnail/exporter各司其职，ui.py专注界面
- 后台线程模型正确：QRunnable + 信号槽 + generation防过期
- 配置集中管理：config.py一个文件控制所有参数
- 样式分离：style.py独立管理QSS，方便换肤
- 防御性编程：缩略图生成和导出都有完善的异常处理
- 自然排序实现优雅，支持混合文本和数字

**待改进**：
- ui.py过于庞大（1714行），建议拆分为多个模块
- 存在重复方法定义
- 辅助脚本（write_ui.py）应清理
- 线程安全可以加强
- 缩略图缓存应加LRU限制

---

## 九、接手开发指南

### 如果需要添加新功能

1. **修改配置常量**：编辑 `config.py`，添加新常量
2. **修改UI样式**：编辑 `style.py` 中的 `build_app_qss()` 函数
3. **修改导出逻辑**：编辑 `exporter.py` 中的 `export_all()` 函数
4. **修改扫描逻辑**：编辑 `scanner.py` 中的相关函数
5. **修改界面布局**：编辑 `ui.py` 中 `MainWindow._build_ui()` 及相关方法

### 新增文件类型的处理流程

1. 在 `config.py` 的 `IMAGE_EXTS` 中添加扩展名
2. 在 `scanner.py` 的 `collect_media()` 中确保新格式被收集
3. 在 `thumbnail.py` 中确保Pillow能读取该格式（或添加占位图处理）
4. 在 `exporter.py` 的 `_target_ext()` 中确定导出扩展名

### 修改UI样式的入口

- 全局样式：`style.py` → `build_app_qss()`
- 控件内联样式：`ui.py` 中各控件的 `setStyleSheet()` 调用
- 配色常量：`ui.py` 顶部的 `BRAND`、`BRAND_LIGHT` 等变量

### 修改导出逻辑的入口

- 导出主函数：`exporter.py` → `export_all()`
- 命名规则：在 `export_all()` 中修改 `f"{f.name} ({n}){ext}"` 模板
- 跳过策略：修改 `_save()` 函数中的 `target.exists()` 判断

### 构建和测试

```bash
# 从源码运行
python main.py

# 运行核心测试
python test_core.py

# 运行GUI测试（offscreen）
python test_gui.py

# 运行v4版本测试
python test_v4.py

# 运行v5版本测试
python test_v5.py

# 打包为exe
build.bat
```

### 文件修改约束（重要）

根据项目约定，`ui.py` 和 `style.py` 可自由修改。但以下文件**不应修改**（除非有充分理由）：
- `config.py` — 配置常量
- `scanner.py` — 目录扫描核心逻辑
- `exporter.py` — 导出核心逻辑
- `thumbnail.py` — 缩略图生成
- `settings.py` — 设置持久化
- `pdf_render.py` — PDF渲染
- `main.py` — 程序入口

---

## 附录：项目文件清单

```
拼版选图导出工具/
├── main.py                      # 程序入口
├── config.py                    # 配置常量
├── scanner.py                   # 目录扫描
├── pdf_render.py                # PDF页渲染
├── thumbnail.py                 # 缩略图生成
├── exporter.py                  # 导出逻辑
├── ui.py                        # 图形界面（~1714行）
├── style.py                     # 全局QSS样式表
├── settings.py                  # 设置持久化
├── config.json                  # 运行时配置文件
├── build.bat                    # PyInstaller打包脚本
├── 拼版选图导出工作台.spec        # PyInstaller打包配置
├── README.md                    # 使用说明
├── DEVELOPMENT_SUMMARY.md       # 本文档（开发归档）
├── test_core.py                 # 核心功能测试
├── test_gui.py                  # GUI冒烟测试
├── test_v2.py                   # v2版本测试
├── test_v3.py                   # v3版本测试
├── test_v4.py                   # v4版本测试
├── test_v5.py                   # v5版本测试
├── write_ui.py                  # [辅助] UI生成脚本（已弃用）
├── _write_ui_p2.py              # [辅助] UI生成脚本第二部分（已弃用）
└── dist/
    └── 拼版选图导出工作台_v5.0.0.exe  # 打包产物
```

---

> **归档完成。** 如有任何疑问或需要进一步解释，请随时询问。
