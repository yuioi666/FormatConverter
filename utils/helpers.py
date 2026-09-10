"""
utils/helpers.py — 通用工具函数
"""

import os
import time
import ctypes


# ── 屏幕 DPI 缩放 ─────────────────────────────────────
# 【关键】SetProcessDpiAwareness 必须在创建任何窗口前调用，
# 所以在模块级执行，而非放到函数内部。
DPI_INITIALIZED = False
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    DPI_INITIALIZED = True
except Exception:
    pass


def get_scale_factor() -> float:
    """获取系统 DPI 缩放比例，失败则返回 1.0"""
    if not DPI_INITIALIZED:
        return 1.0
    try:
        return ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    except Exception:
        return 1.0


def get_font_scale() -> float:
    """
    获取建议的字体缩放倍率。
    基于 DPI 缩放，在 1.0 ~ 2.0 之间，用缓增曲线避免字号过大。
    - 100% DPI → 1.00
    - 125% DPI → 1.10
    - 150% DPI → 1.25
    - 200% DPI → 1.50
    """
    sf = get_scale_factor()
    # 缓增: 比原始 DPI 比率增长慢一些，避免超大字号
    return max(1.0, 0.5 + sf * 0.5)


def scaled_font(family: str = "微软雅黑", size: int = 10,
                weight: str = "") -> tuple:
    """
    返回按 DPI 缩放后的字体元组 (family, scaled_size, [weight])。
    weight 可选: "" / "bold" / "italic" 等
    """
    scale = get_font_scale()
    scaled = max(1, int(size * scale))
    if weight:
        return (family, scaled, weight)
    return (family, scaled)


# ── 时间格式化 ─────────────────────────────────────────
def fmt_time(seconds: float) -> str:
    """将秒数格式化为 MM:SS"""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def fmt_time_verbose(seconds: float) -> str:
    """将秒数格式化为 已用 MM:SS | 预计剩余 MM:SS"""
    return fmt_time(seconds)


def fmt_now_timestamp() -> str:
    """返回 [HH:MM:SS] 格式的时间戳"""
    return time.strftime("[%H:%M:%S]", time.localtime())


# ── 路径工具 ───────────────────────────────────────────
def safe_basename(path: str) -> str:
    """安全的文件名提取，处理空路径"""
    return os.path.basename(path) if path else ""


def norm_path(path: str) -> str:
    """规范化路径"""
    return os.path.normpath(path)


def file_stem(path: str) -> str:
    """不含后缀的文件名"""
    return os.path.splitext(os.path.basename(path))[0]


def ext_lower(path: str) -> str:
    """返回小写扩展名"""
    _, ext = os.path.splitext(path)
    return ext.lower()