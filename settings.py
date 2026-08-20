# -*- coding: utf-8 -*-
"""设置持久化：读写 config.json。

配置文件位置：
    - 打包成 exe 后：与 exe 同目录；
    - 开发环境：与源码同目录（用 sys.frozen 区分）。

所有设置项集中在此，读写失败一律静默（不崩溃、不影响程序运行）。
"""
import json
import sys
from pathlib import Path


def app_dir() -> Path:
    """程序所在目录：打包后为 exe 所在目录，开发时为源码目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = app_dir() / "config.json"

# 缩略图尺寸可选值
THUMB_CHOICES = (150, 200, 250)

# 默认配置（缺失项自动补全）
DEFAULTS = {
    "mouse_gesture": False,   # 鼠标手势：右键拖动切换文件夹
    "show_filename": True,    # 缩略图下方是否显示文件名
    "thumb_size": 200,        # 缩略图尺寸（150 / 200 / 250）
    "remember_paths": True,   # 下次启动自动填充上次的源/输出路径
    "src_dir": "",            # 记住的源目录
    "out_dir": "",            # 记住的输出目录
    "left_ratio": 0.21,       # 左侧列表占左右分栏的宽度比例（0~1）
}


def load() -> dict:
    """读取配置；缺失项用默认值补齐，任何异常都返回默认值。"""
    cfg = dict(DEFAULTS)
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    except Exception:
        pass
    # 校验 thumb_size 合法性
    if cfg.get("thumb_size") not in THUMB_CHOICES:
        cfg["thumb_size"] = 200
    # 校验 left_ratio 取值范围
    try:
        lr = float(cfg.get("left_ratio", 0.21))
        if not (0.05 <= lr <= 0.8):
            lr = 0.21
        cfg["left_ratio"] = lr
    except Exception:
        cfg["left_ratio"] = 0.21
    return cfg


def save(cfg: dict):
    """写入配置；失败静默（目录只读、磁盘满等不影响运行）。"""
    try:
        CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
