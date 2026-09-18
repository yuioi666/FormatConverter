"""
core/formats.py — 格式定义 + 缓存查询

将 FORMAT_MAP 统一管理，提供 O(1) 缓存查询。
新增格式 (B4) 全部集成在此。
"""

import os

# ── 格式定义 ─────────────────────────────────────────────
# 结构: { "分类": { "模式名": ([输入扩展名列表], 输出扩展名, 可选项) } }
# 第三个元素为可选 dict:
#   multi_input: True 表示该模式支持多文件输入（如 PDF 合并）
#   output_is_dir: True 表示输出是目录（如 PDF 转图片）

FORMAT_MAP = {
    "Office → PDF": {
        "Word 转 PDF": ([".docx", ".doc"], ".pdf", {"uses_quality": True}),
        "Excel 转 PDF": ([".xlsx", ".xls"], ".pdf", {"uses_quality": True}),
        "PPT 转 PDF": ([".pptx", ".ppt"], ".pdf"),
    },
    "PDF 处理": {
        "PDF 转 Word": ([".pdf"], ".docx"),
        "PDF 转 TXT": ([".pdf"], ".txt"),
        "PDF 转 图片": ([".pdf"], ".png", {
            "output_is_dir": True,
            "uses_quality": True,
        }),
        "PDF 合并": ([".pdf"], ".pdf", {
            "multi_input": True,
            "output_suffix": "_merged",
        }),
        "PDF 压缩": ([".pdf"], ".pdf", {
            "uses_quality": True,
            "output_suffix": "_compressed",
        }),
    },
    "图片处理": {
        "图片 转 PDF": ([".jpg", ".jpeg", ".png", ".bmp", ".webp"], ".pdf", {
            "uses_quality": True,
        }),
        "图片 合并 PDF": ([".jpg", ".jpeg", ".png", ".bmp", ".webp"], ".pdf", {"multi_input": True}),
        "图片格式转换": ([".jpg", ".jpeg", ".png", ".bmp", ".webp"], ".png", {
            "output_suffix": "_converted",
        }),
    },
    "纯文本": {
        "TXT 转 PDF": ([".txt"], ".pdf"),
        "Word 转 TXT": ([".docx", ".doc"], ".txt"),
        "Excel 转 CSV": ([".xlsx", ".xls"], ".csv"),
    },
}

# GUI 中使用“转换前格式 + 转换后格式”组合映射到内部转换模式。
# 同格式存在不同操作时，在目标名称中明确标注，避免歧义。
CONVERSION_CHOICES: dict[str, dict[str, str]] = {
    "Word": {
        "PDF": "Word 转 PDF",
        "TXT": "Word 转 TXT",
    },
    "Excel": {
        "PDF": "Excel 转 PDF",
        "CSV": "Excel 转 CSV",
    },
    "PowerPoint": {
        "PDF": "PPT 转 PDF",
    },
    "PDF": {
        "Word": "PDF 转 Word",
        "TXT": "PDF 转 TXT",
        "图片": "PDF 转 图片",
        "PDF（合并）": "PDF 合并",
        "PDF（压缩）": "PDF 压缩",
    },
    "图片": {
        "PDF（逐个转换）": "图片 转 PDF",
        "PDF（合并）": "图片 合并 PDF",
        "PNG": "图片格式转换",
    },
    "TXT": {
        "PDF": "TXT 转 PDF",
    },
}


def get_target_formats(source_format: str) -> list[str]:
    """返回指定源格式支持的目标格式/操作。"""
    return list(CONVERSION_CHOICES.get(source_format, {}))


def get_conversion_mode(source_format: str, target_format: str) -> str:
    """将两个格式选择转换为内部模式名。"""
    return CONVERSION_CHOICES.get(source_format, {}).get(target_format, "")

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
        self._exts_in = []
        self._ext_out = ""
        self._mode_info = {}

        for cat in FORMAT_MAP.values():
            if mode in cat:
                entry = cat[mode]
                # 必须复制，不能让缓存直接引用并修改 FORMAT_MAP 的全局列表。
                self._exts_in = list(entry[0])
                self._ext_out = entry[1]
                self._mode_info = dict(entry[2]) if len(entry) > 2 else {}
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

    def uses_quality(self) -> bool:
        """当前转换模式是否实际使用画质参数。"""
        return self._mode_info.get("uses_quality", False)

    def get_output_path(self, in_path: str, custom_folder: str = "",
                        use_custom: bool = False,
                        reserved_paths: set[str] | None = None) -> str:
        """
        根据输入路径和当前模式计算输出路径。
        返回输出文件完整路径或目录路径。
        """
        from utils.helpers import file_stem

        name = file_stem(in_path)
        folder = custom_folder if use_custom else os.path.dirname(in_path)
        folder = os.path.abspath(folder or os.curdir)
        os.makedirs(folder, exist_ok=True)

        if self.is_output_dir():
            # PDF 转图片：输出到子目录
            sub = os.path.join(folder, f"{name}_Img")
            sub = self._unique_path(
                sub, is_dir=True, reserved_paths=reserved_paths,
            )
            os.makedirs(sub)
            self._reserve_path(sub, reserved_paths)
            return sub

        suffix = self._mode_info.get("output_suffix", "")
        output_path = os.path.join(folder, name + suffix + self._ext_out)

        # 永远不允许转换结果覆盖正在读取的源文件。
        if os.path.normcase(os.path.abspath(output_path)) == os.path.normcase(os.path.abspath(in_path)):
            output_path = os.path.join(folder, name + "_converted" + self._ext_out)
        output_path = self._unique_path(
            output_path, reserved_paths=reserved_paths,
        )
        self._reserve_path(output_path, reserved_paths)
        return output_path

    @staticmethod
    def _unique_path(path: str, is_dir: bool = False,
                     reserved_paths: set[str] | None = None) -> str:
        """避免覆盖已有结果，必要时追加递增编号。"""
        reserved_paths = reserved_paths or set()
        path_key = os.path.normcase(os.path.abspath(path))
        if not os.path.exists(path) and path_key not in reserved_paths:
            return path
        folder, filename = os.path.split(path)
        stem, ext = (filename, "") if is_dir else os.path.splitext(filename)
        index = 1
        while True:
            candidate = os.path.join(folder, f"{stem}_{index}{ext}")
            candidate_key = os.path.normcase(os.path.abspath(candidate))
            if not os.path.exists(candidate) and candidate_key not in reserved_paths:
                return candidate
            index += 1

    @staticmethod
    def _reserve_path(path: str, reserved_paths: set[str] | None):
        if reserved_paths is not None:
            reserved_paths.add(os.path.normcase(os.path.abspath(path)))

    def get_file_filter(self) -> list:
        """返回 filedialog 文件过滤器"""
        exts = self._exts_in
        if not exts:
            return []
        pattern = " ".join(f"*{e}" for e in exts)
        return [("Files", pattern)]


# 全局单例
format_cache = FormatCache()
