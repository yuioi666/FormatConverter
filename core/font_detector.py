"""
core/font_detector.py — 中文字体自动检测 (B5)

搜索优先级:
1. Windows 系统字体目录 (C:\\Windows\\Fonts\\)
2. 脚本同目录
3. 用户手动指定

注册 ReportLab 字体，提供全局访问。
"""

import os
from typing import Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 候选字体列表 ───────────────────────────────────────
# (显示名, 文件名, ReportLab 注册名)
CANDIDATES = [
    ("微软雅黑", "msyh.ttc"),
    ("微软雅黑 Bold", "msyhbd.ttc"),
    ("黑体", "simhei.ttf"),
    ("宋体", "simsun.ttc"),
    ("新宋体", "simsunb.ttf"),
    ("楷体", "simkai.ttf"),
    ("仿宋", "simfang.ttf"),
    ("Arial Unicode", "ArialUni.ttf"),
]

# 脚本所在目录
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)  # 项目根目录 (work1)


def _search_font(filename: str) -> Optional[str]:
    """在系统字体目录和项目目录中搜索字体文件"""
    # 1. Windows 系统字体目录
    sys_font_dir = r"C:\Windows\Fonts"
    sys_path = os.path.join(sys_font_dir, filename)
    if os.path.isfile(sys_path):
        return sys_path

    # 2. 项目根目录
    proj_path = os.path.join(_project_root, filename)
    if os.path.isfile(proj_path):
        return proj_path

    # 3. 脚本同目录
    local_path = os.path.join(_script_dir, filename)
    if os.path.isfile(local_path):
        return local_path

    # 4. 当前工作目录
    cwd_path = os.path.join(os.getcwd(), filename)
    if os.path.isfile(cwd_path):
        return cwd_path

    return None


def _search_any_font(fallback_name: str = "Helvetica") -> tuple[str, str]:
    """
    搜索可用的中文字体。
    返回: (注册名, 字体族名)
    """
    for display_name, filename in CANDIDATES:
        fp = _search_font(filename)
        if fp:
            try:
                # ttc 文件需要指定 subfont index
                if filename.endswith(".ttc"):
                    pdfmetrics.registerFont(TTFont(display_name, fp, subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont(display_name, fp))
                _registered_font_names.add(display_name)
                return display_name, display_name
            except Exception:
                continue

    # 全部失败，回退 Helvetica
    return fallback_name, fallback_name


# ── 全局状态 ────────────────────────────────────────────
_current_registered_name: str = "Helvetica"
_registered_font_names: set[str] = set()  # 记录已成功注册的字体名


def init_font() -> str:
    """
    初始化字体检测并注册。
    返回注册的字体名。
    """
    global _current_registered_name, _available_fonts, _registered_font_names

    font_name, _ = _search_any_font()
    _current_registered_name = font_name

    if font_name != "Helvetica":
        _registered_font_names.add(font_name)

    # 构建可用字体列表：记录 _search_any_font 过程中注册成功的字体
    _available_fonts = ["Helvetica (默认)"]
    for display_name, _ in CANDIDATES:
        if display_name in _registered_font_names:
            _available_fonts.append(display_name)

    return _current_registered_name


def get_current_font() -> str:
    """获取当前使用的字体名"""
    return _current_registered_name


def set_current_font(font_name: str):
    """由 GUI 设置当前字体"""
    global _current_registered_name
    # 去掉 " (默认)" 后缀
    clean_name = font_name.replace(" (默认)", "")
    if clean_name in _registered_font_names or clean_name == "Helvetica":
        _current_registered_name = clean_name


def get_available_fonts() -> list[str]:
    """获取可用字体列表"""
    return list(_available_fonts)