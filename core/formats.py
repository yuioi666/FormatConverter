"""
core/formats.py — 格式定义 + 缓存查询

将 FORMAT_MAP 统一管理，提供 O(1) 缓存查询。
新增格式 (B4) 全部集成在此。
"""

from typing import Optional

# ── 格式定义 ─────────────────────────────────────────────
# 结构: { "分类": { "模式名": ([输入扩展名列表], 输出扩展名, 可选项) } }
# 第三个元素为可选 dict:
#   multi_input: True 表示该模式支持多文件输入（如 PDF 合并）
#   output_is_dir: True 表示输出是目录（如 PDF 转图片）

FORMAT_MAP = {
    "Office → PDF": {
        "Word 转 PDF": ([".docx", ".doc"], ".pdf"),
        "Excel 转 PDF": ([".xlsx", ".xls"], ".pdf"),
        "PPT 转 PDF": ([".pptx", ".ppt"], ".pdf"),
    },
    "PDF 处理": {
        "PDF 转 Word": ([".pdf"], ".docx"),
        "PDF 转 TXT": ([".pdf"], ".txt"),
        "PDF 转 图片": ([".pdf"], ".png", {"output_is_dir": True}),
        "PDF 合并": ([".pdf"], ".pdf", {"multi_input": True}),
        "PDF 压缩": ([".pdf"], ".pdf"),
    },
    "图片处理": {
        "图片 转 PDF": ([".jpg", ".jpeg", ".png", ".bmp", ".webp"], ".pdf"),
        "图片 合并 PDF": ([".jpg", ".jpeg", ".png", ".bmp", ".webp"], ".pdf", {"multi_input": True}),
        "图片格式转换": ([".jpg", ".jpeg", ".png", ".bmp", ".webp"], ".png"),
    },
    "纯文本": {
        "TXT 转 PDF": ([".txt"], ".pdf"),
        "Word 转 TXT": ([".docx", ".doc"], ".txt"),
        "Excel 转 CSV": ([".xlsx", ".xls"], ".csv"),
    },
}

# ── 扁平索引（用于 ComboBox） ──────────────────────────
ALL_MODES: list[str] = []
for cat in FORMAT_MAP.values():
    ALL_MODES.extend(cat.keys())


class FormatCache:
    """格式查询缓存，模式切换时重建"""

    def __init__(self):
        self._current_mode: str = ""
        self._exts_in: list[str] = []
        self._ext_out: str = ""
        self._mode_info: dict = {}

    def set_mode(self, mode: str):
        """设置当前模式，重建缓存"""
        if mode == self._current_mode:
            return
        self._current_mode = mode
        self._exts_in.clear()
        self._ext_out = ""
        self._mode_info = {}

        for cat in FORMAT_MAP.values():
            if mode in cat:
                entry = cat[mode]
                self._exts_in = entry[0]
                self._ext_out = entry[1]
                self._mode_info = entry[2] if len(entry) > 2 else {}
                break

    @property
    def exts_in(self) -> list[str]:
        return self._exts_in

    @property
    def ext_out(self) -> str:
        return self._ext_out

    @property
    def mode_info(self) -> dict:
        return self._mode_info

    def is_valid_ext(self, path: str) -> bool:
        """判断文件扩展名是否匹配当前模式的输入格式"""
        from utils.helpers import ext_lower
        return ext_lower(path) in self._exts_in

    def is_multi_input(self) -> bool:
        return self._mode_info.get("multi_input", False)

    def is_output_dir(self) -> bool:
        return self._mode_info.get("output_is_dir", False)

    def get_output_path(self, in_path: str, custom_folder: str = "",
                        use_custom: bool = False) -> str:
        """
        根据输入路径和当前模式计算输出路径。
        返回输出文件完整路径或目录路径。
        """
        import os
        from utils.helpers import file_stem

        name = file_stem(in_path)
        folder = custom_folder if use_custom else os.path.dirname(in_path)

        if self.is_output_dir():
            # PDF 转图片：输出到子目录
            sub = os.path.join(folder, f"{name}_Img")
            if not os.path.exists(sub):
                os.makedirs(sub)
            return sub

        return os.path.join(folder, name + self._ext_out)

    def get_file_filter(self) -> list:
        """返回 filedialog 文件过滤器"""
        exts = self._exts_in
        if not exts:
            return []
        pattern = " ".join(f"*{e}" for e in exts)
        return [("Files", pattern)]


# 全局单例
format_cache = FormatCache()