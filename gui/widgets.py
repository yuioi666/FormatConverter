"""
gui/widgets.py — 自定义 GUI 组件

包含：
- LogPanel: 可折叠日志面板 (B6)
- DragDropBanner: 拖拽提示区
"""

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from utils.logger import logger, LogEntry
from utils.helpers import scaled_font, get_font_scale


class LogPanel(ttk.Labelframe):
    """可折叠的日志面板 (B6)"""

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("text", "📋 处理日志")
        kwargs.setdefault("padding", 4)
        super().__init__(parent, **kwargs)

        self._visible = True
        self._max_lines = 200

        # 工具栏
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=X, pady=2)

        self._btn_toggle = ttk.Button(
            toolbar, text="▼ 折叠", bootstyle=SECONDARY, width=8,
            command=self._toggle,
        )
        self._btn_toggle.pack(side=LEFT, padx=2)

        ttk.Button(
            toolbar, text="清空", bootstyle="secondary-outline", width=6,
            command=self._clear,
        ).pack(side=LEFT, padx=2)

        ttk.Button(
            toolbar, text="复制", bootstyle="info-outline", width=6,
            command=self._copy_all,
        ).pack(side=LEFT, padx=2)

        # 日志文本框
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=BOTH, expand=True)

        self._text = tk.Text(
            text_frame,
            height=max(4, int(8 / get_font_scale())),  # 缩放行数，保持视觉高度
            wrap=tk.WORD,
            font=scaled_font("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            relief=tk.SUNKEN,
            borderwidth=1,
            state=tk.DISABLED,
        )
        self._text.pack(side=LEFT, fill=BOTH, expand=True)

        scroll = ttk.Scrollbar(text_frame, orient=VERTICAL, command=self._text.yview)
        scroll.pack(side=RIGHT, fill=Y)
        self._text.configure(yscrollcommand=scroll.set)

        # 注册日志回调
        logger.set_callback(self._on_log_entry)

        # 颜色标签
        self._text.tag_configure("INFO", foreground="#9cdcfe")
        self._text.tag_configure("SUCCESS", foreground="#4ec9b0")
        self._text.tag_configure("WARN", foreground="#ce9178")
        self._text.tag_configure("ERROR", foreground="#f44747")

    def _toggle(self):
        """折叠/展开"""
        if self._visible:
            self._text.pack_forget()
            self._btn_toggle.config(text="▶ 展开")
            self._visible = False
        else:
            self._text.pack(side=LEFT, fill=BOTH, expand=True)
            self._btn_toggle.config(text="▼ 折叠")
            self._visible = True

    def _clear(self):
        """清空日志"""
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)
        logger.clear()

    def _copy_all(self):
        """复制全部日志"""
        text = logger.to_text()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            # 不弹确认，直接静默复制

    def _on_log_entry(self, entry: LogEntry):
        """收到新日志条目"""
        try:
            self._text.config(state=tk.NORMAL)
            self._text.insert(tk.END, entry.format() + "\n", entry.level)

            # 限制行数
            line_count = int(self._text.index("end-1c").split(".")[0])
            if line_count > self._max_lines:
                self._text.delete("1.0", f"{line_count - self._max_lines + 1}.0")

            self._text.see(tk.END)
            self._text.config(state=tk.DISABLED)
        except Exception:
            pass

    def destroy(self):
        """清理回调"""
        logger.set_callback(None)
        super().destroy()


class DragDropBanner(ttk.Frame):
    """顶部拖拽提示区"""

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bootstyle", PRIMARY)
        super().__init__(parent, **kwargs)
        self.pack(fill=X)

        self.label = ttk.Label(
            self,
            text="📂 拖拽文件/文件夹至此 | 点击列表第一列可单独切换[自动删除]",
            font=scaled_font("微软雅黑", 10, "bold"),
            bootstyle=(INVERSE, PRIMARY),
        )
        self.label.pack(ipady=8)