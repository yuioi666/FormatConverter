"""
gui/app.py — 主窗口 GUI 类

整合所有组件：
- TreeManager（文件列表 + B2 右键菜单）
- LogPanel（B6 日志面板）
- DragDropBanner（拖拽提示）
- 引擎对接（status callbacks + B1 停止按钮）
"""

import os
import time
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip

# tkinterdnd2 — 拖拽功能
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    # 降级：没有 dnd 也能运行

from core.formats import (
    CONVERSION_CHOICES,
    format_cache,
    get_conversion_mode,
    get_target_formats,
)
from core.engine import engine, Task
from core.font_detector import init_font, get_available_fonts, set_current_font
from utils.helpers import (
    get_scale_factor,
    get_font_scale,
    scaled_font,
    fmt_time,
    resource_path,
)
from utils.logger import logger
from gui.tree_manager import TreeManager
from gui.widgets import LogPanel, DragDropBanner
from version import __version__

# ── 主窗口 ─────────────────────────────────────────────
class App(TkinterDnD.Tk if HAS_DND else tk.Tk):
    """全能文档格式工厂 — 主应用"""

    def __init__(self):
        super().__init__()
        self.title(f"全能文档格式工厂 v{__version__}")
        try:
            self.iconbitmap(resource_path("assets/format-converter-icon.ico"))
        except (OSError, tk.TclError):
            # 图标缺失不应阻止应用启动。
            pass
        ScaleFactor = get_scale_factor()
        w, h = int(1080 * ScaleFactor), int(780 * ScaleFactor)
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(int(900 * ScaleFactor), int(660 * ScaleFactor))
        self.style = ttk.Style("cosmo")

        # ── 全局字体缩放 ──
        fs = get_font_scale()
        base_font = ("微软雅黑", max(1, int(10 * fs)))
        self.style.configure('.', font=base_font)
        self.style.configure('TButton', font=("微软雅黑", max(1, int(9 * fs))))
        self.style.configure('TLabel', font=base_font)
        self.style.configure('TCombobox', font=base_font)
        self.style.configure(
            'Treeview',
            font=("微软雅黑", max(1, int(9 * fs))),
            rowheight=max(26, int(30 * fs)),
        )
        self.style.configure('Treeview.Heading', font=("微软雅黑", max(1, int(9 * fs)), 'bold'))
        self.style.configure('TLabelframe.Label', font=("微软雅黑", max(1, int(9 * fs)), 'bold'))
        self.style.configure('TCheckbutton', font=base_font)
        self.style.configure('TRadiobutton', font=base_font)
        self.style.configure('TSpinbox', font=base_font)

        # 保存字体缩放供子组件使用
        self.font_scale = fs

        # 初始化字体检测 (B5)
        init_font()

        # 内部状态
        self._timer_active = False
        self._active_task_iids: set[str] = set()
        self._ui_events = queue.SimpleQueue()

        # ── 构建 UI ──
        self._build_ui()

        # ── 设置引擎回调 ──
        self._setup_engine_callbacks()

        # ── 注册转换函数 ──
        self._register_converter_funcs()

        # 后台转换线程只写入队列，由 GUI 主线程统一处理界面更新。
        self.after(50, self._drain_ui_events)

        # ── 拖拽注册 ──
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self._on_drop)

        # 启动定时器
        self._start_timer()

        # 初始日志
        logger.info("程序启动，准备就绪")

    # ══════════════════════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        """构建完整界面"""
        header = ttk.Frame(self, padding=(14, 10, 14, 2))
        header.pack(fill=X)
        ttk.Label(
            header, text="文档格式转换",
            font=scaled_font("微软雅黑", 16, "bold"),
        ).pack(side=LEFT)
        ttk.Label(
            header, text=f"v{__version__}", bootstyle="secondary",
            font=scaled_font("微软雅黑", 9),
        ).pack(side=LEFT, padx=8, pady=(5, 0))

        # 1. 转换配置
        self._build_config_panel()

        # 2. 拖放与文件列表
        self._drag_banner = DragDropBanner(self)
        self._drag_banner.pack(fill=X, padx=14, pady=(2, 8))
        self._drag_banner.set_formats(
            self.source_format_var.get(), self.target_format_var.get(),
        )
        self._build_file_list()

        # 3. 执行控制
        self._build_toolbar()

        # 4. 日志与状态栏
        self._log_panel = LogPanel(self)
        self._log_panel.pack(fill=X, padx=14, pady=(0, 5))
        self._build_statusbar()

    def _build_config_panel(self):
        """转换配置区域"""
        sets = ttk.Labelframe(self, text="1  设置转换方式", padding=(12, 8))
        sets.pack(fill=X, padx=14, pady=(4, 8))
        sets.columnconfigure(0, weight=1)
        sets.columnconfigure(2, weight=1)
        sets.columnconfigure(4, weight=1)
        sets.columnconfigure(6, weight=1)

        source_formats = list(CONVERSION_CHOICES)
        initial_source = source_formats[0]
        initial_targets = get_target_formats(initial_source)

        ttk.Label(sets, text="转换前格式").grid(
            row=0, column=0, sticky=W, padx=(0, 6), pady=(0, 3),
        )
        self.source_format_var = tk.StringVar(value=initial_source)
        self.source_format_combo = ttk.Combobox(
            sets,
            textvariable=self.source_format_var,
            values=source_formats,
            state="readonly",
            width=15,
        )
        self.source_format_combo.grid(row=1, column=0, sticky=EW, padx=(0, 8))
        self.source_format_combo.bind(
            "<<ComboboxSelected>>", self._on_source_format_change,
        )

        ttk.Label(
            sets, text="→", bootstyle="primary",
            font=scaled_font("微软雅黑", 15, "bold"),
        ).grid(row=1, column=1, padx=(0, 8))
        ttk.Label(sets, text="转换后格式").grid(
            row=0, column=2, sticky=W, padx=(0, 6), pady=(0, 3),
        )
        self.target_format_var = tk.StringVar(value=initial_targets[0])
        self.target_format_combo = ttk.Combobox(
            sets,
            textvariable=self.target_format_var,
            values=initial_targets,
            state="readonly",
            width=18,
        )
        self.target_format_combo.grid(row=1, column=2, sticky=EW, padx=(0, 4))
        self.target_format_combo.bind(
            "<<ComboboxSelected>>", self._on_target_format_change,
        )

        self.mode_var = tk.StringVar(value=get_conversion_mode(
            initial_source, initial_targets[0],
        ))
        format_cache.set_mode(self.mode_var.get())

        # 帮助提示
        help_frame = ttk.Frame(sets)
        help_frame.grid(row=1, column=3, sticky=W, padx=(0, 14))
        self._help_icon(help_frame, "功能说明：\n• Office转PDF：调用本地Office\n• PDF转Word：大量数学公式/矩阵会较慢\n• 合并模式：按列表顺序合并")

        self.quality_label = ttk.Label(
            sets, text="输出质量",
        )
        self.quality_label.grid(row=0, column=4, sticky=W, pady=(0, 3))
        self.quality_var = tk.StringVar(value="臻享画质 (Ultra)")
        self.quality_combo = ttk.Combobox(
            sets, textvariable=self.quality_var,
            values=["臻享画质 (Ultra)", "标准均衡 (Standard)", "极速预览 (Speed)"],
            state="readonly", width=20, bootstyle="info",
        )
        self.quality_combo.grid(row=1, column=4, sticky=EW, padx=(0, 4))
        quality_help = ttk.Frame(sets)
        quality_help.grid(row=1, column=5, sticky=W, padx=(0, 14))
        self._help_icon(quality_help, "• 臻享：打印级清晰度\n• 标准：日常办公\n• 极速：屏幕预览，生成最快")

        # B5: 字体选择
        self.font_label = ttk.Label(sets, text="TXT 转 PDF 字体")
        self.font_label.grid(row=0, column=6, sticky=W, pady=(0, 3))
        fonts = get_available_fonts()
        self.font_var = tk.StringVar(value=fonts[0] if fonts else "Helvetica (默认)")
        self.font_combo = ttk.Combobox(
            sets, textvariable=self.font_var,
            values=fonts, state="readonly", width=18, bootstyle="secondary",
        )
        self.font_combo.grid(row=1, column=6, sticky=EW, padx=(0, 4))
        self.font_combo.bind("<<ComboboxSelected>>", self._on_font_change)
        font_help = ttk.Frame(sets)
        font_help.grid(row=1, column=7, sticky=W)
        self._help_icon(font_help, "仅 TXT 转 PDF 时生效，自动检测系统可用中文字体")

        # 统一切换自动删除
        self.master_del_var = tk.BooleanVar(value=False)
        cb_del = ttk.Checkbutton(
            sets, text="转换成功后删除源文件",
            variable=self.master_del_var,
            command=self._on_toggle_all_del,
            bootstyle="round-toggle",
        )
        cb_del.grid(row=1, column=8, sticky=E, padx=(16, 0))

        ttk.Separator(sets).grid(
            row=2, column=0, columnspan=9, sticky=EW, pady=(10, 8),
        )
        r2 = ttk.Frame(sets)
        r2.grid(row=3, column=0, columnspan=9, sticky=EW)
        r2.columnconfigure(4, weight=1)

        ttk.Label(r2, text="输出位置").grid(row=0, column=0, sticky=W, padx=(0, 10))
        self.out_mode = tk.StringVar(value="origin")
        ttk.Radiobutton(
            r2, text="原文件夹", variable=self.out_mode,
            value="origin", command=self._toggle_path,
        ).grid(row=0, column=1, sticky=W, padx=(0, 8))
        ttk.Radiobutton(
            r2, text="指定目录:", variable=self.out_mode,
            value="custom", command=self._toggle_path,
        ).grid(row=0, column=2, sticky=W, padx=(0, 6))
        self.custom_path_var = tk.StringVar()
        self.entry_path = ttk.Entry(r2, textvariable=self.custom_path_var, state=DISABLED)
        self.entry_path.grid(row=0, column=4, sticky=EW, padx=(0, 6))
        self.btn_browse = ttk.Button(
            r2, text="浏览", width=7, state=DISABLED,
            command=self._browse_path, bootstyle=OUTLINE,
        )
        self.btn_browse.grid(row=0, column=5, sticky=E)
        self._update_quality_state()
        self._update_font_state()

    def _build_file_list(self):
        """文件列表区"""
        section = ttk.Labelframe(self, text="2  待处理任务", padding=(8, 6))
        section.pack(fill=BOTH, expand=True, padx=14, pady=(0, 8))

        list_tools = ttk.Frame(section)
        list_tools.pack(fill=X, pady=(0, 6))

        self.task_count_var = tk.StringVar(value="暂无任务")
        ttk.Label(
            list_tools, textvariable=self.task_count_var, bootstyle="secondary",
        ).pack(side=LEFT, padx=(2, 12))
        ttk.Label(
            list_tools, text="右键可调整顺序或删除任务",
            bootstyle="secondary",
            font=scaled_font("微软雅黑", 8),
        ).pack(side=LEFT)

        ttk.Button(
            list_tools, text="清空", bootstyle="secondary-outline",
            command=self._clear_list, width=7,
        ).pack(side=RIGHT, padx=(4, 0))
        ttk.Button(
            list_tools, text="清除已完成", bootstyle="secondary-outline",
            command=self._remove_completed, width=11,
        ).pack(side=RIGHT, padx=4)
        ttk.Button(
            list_tools, text="添加文件夹", bootstyle="info-outline",
            command=self._add_folder, width=10,
        ).pack(side=RIGHT, padx=4)
        ttk.Button(
            list_tools, text="添加文件", bootstyle=INFO,
            command=self._add_files, width=9,
        ).pack(side=RIGHT, padx=4)

        list_frame = ttk.Frame(section)
        list_frame.pack(fill=BOTH, expand=True)

        cols = ("del", "path", "status", "info")
        self.tree = ttk.Treeview(
            list_frame, columns=cols,
            show="headings", selectmode="extended",
        )

        self.tree.heading("del", text="删除源文件", anchor=CENTER)
        self.tree.heading("path", text="文件名称 / 路径")
        self.tree.heading("status", text="状态")
        self.tree.heading("info", text="耗时/备注")

        self.tree.column("del", width=105, anchor=CENTER, stretch=False)
        self.tree.column("path", width=480)
        self.tree.column("status", width=105, anchor=CENTER, stretch=False)
        self.tree.column("info", width=190, anchor=CENTER)

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.tag_configure("checked", foreground="red")
        self.tree.tag_configure("processing", foreground="#007bff")
        self.tree.tag_configure("success", foreground="#28a745")
        self.tree.tag_configure("deleted", foreground="#6c757d")
        self.tree.tag_configure("failed", foreground="#dc3545")

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.tree.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=sb.set)

        # 初始化 TreeManager
        self.tree_mgr = TreeManager(
            self.tree, self.master_del_var, on_change=self._update_task_count,
        )

    def _build_toolbar(self):
        """底部执行控制区。"""
        tool = ttk.Labelframe(self, text="3  开始转换", padding=(10, 8))
        tool.pack(fill=X, padx=14, pady=(0, 8))

        progress_frame = ttk.Frame(tool)
        progress_frame.pack(side=LEFT, fill=X, expand=True, padx=(0, 18))
        progress_header = ttk.Frame(progress_frame)
        progress_header.pack(fill=X, pady=(0, 4))
        ttk.Label(progress_header, text="总进度").pack(side=LEFT)
        self.progress_text_var = tk.StringVar(value="0 / 0")
        ttk.Label(
            progress_header, textvariable=self.progress_text_var,
            bootstyle="secondary",
        ).pack(side=RIGHT)
        self.progress = ttk.Progressbar(
            progress_frame, orient=HORIZONTAL, mode='determinate',
            bootstyle="success-striped",
        )
        self.progress.pack(fill=X)

        # B1: 停止按钮
        self.btn_stop = ttk.Button(
            tool, text="停止", bootstyle="danger-outline",
            state=DISABLED, command=self._stop, width=8,
        )
        self.btn_stop.pack(side=RIGHT, padx=(6, 0), ipady=3)

        # 暂停按钮
        self.btn_pause = ttk.Button(
            tool, text="暂停", bootstyle="warning-outline",
            state=DISABLED, command=self._toggle_pause, width=8,
        )
        self.btn_pause.pack(side=RIGHT, padx=6, ipady=3)

        # 开始按钮
        self.btn_start = ttk.Button(
            tool, text="开始转换", bootstyle=SUCCESS,
            command=self._start_conversion, width=14,
        )
        self.btn_start.pack(side=RIGHT, ipadx=8, ipady=5)

    def _build_statusbar(self):
        """底部状态栏"""
        status_bar = ttk.Frame(self)
        status_bar.pack(side=BOTTOM, fill=X, padx=14, pady=(0, 5))

        self.status_var = tk.StringVar(value="准备就绪")
        self.time_var = tk.StringVar(value="")

        ttk.Label(
            status_bar, textvariable=self.status_var,
            font=scaled_font("微软雅黑", 8), foreground="gray",
        ).pack(side=LEFT)
        ttk.Label(
            status_bar, textvariable=self.time_var,
            font=scaled_font("Consolas", 9, "bold"), foreground="#007bff",
        ).pack(side=RIGHT)

    # ══════════════════════════════════════════════════════
    #  引擎对接
    # ══════════════════════════════════════════════════════

    def _register_converter_funcs(self):
        """注册所有转换函数到引擎"""
        from core.office_com import (
            word_to_pdf, excel_to_pdf, ppt_to_pdf,
            word_to_txt, excel_to_csv,
        )
        from core.pdf_tools import (
            pdf_to_word, pdf_to_images, pdf_to_txt,
            txt_to_pdf, pdf_merge, pdf_compress,
        )
        from core.image_tools import (
            image_to_pdf, image_merge_pdf, image_convert,
        )

        engine.set_converter_funcs({
            # Office → PDF
            "Word 转 PDF": word_to_pdf,
            "Excel 转 PDF": excel_to_pdf,
            "PPT 转 PDF": ppt_to_pdf,

            # PDF 处理
            "PDF 转 Word": pdf_to_word,
            "PDF 转 TXT": pdf_to_txt,
            "PDF 转 图片": pdf_to_images,
            "PDF 合并": pdf_merge,
            "PDF 压缩": pdf_compress,

            # 图片处理
            "图片 转 PDF": image_to_pdf,
            "图片 合并 PDF": image_merge_pdf,
            "图片格式转换": image_convert,

            # 纯文本
            "TXT 转 PDF": txt_to_pdf,
            "Word 转 TXT": word_to_txt,
            "Excel 转 CSV": excel_to_csv,
        })

    def _setup_engine_callbacks(self):
        """设置引擎回调，更新 GUI"""

        def on_start(task: Task):
            self._post_ui_event(handle_start, task)

        def handle_start(task: Task):
            self.tree_mgr.update_status(
                task.iid, "处理中...", tags="processing",
            )
            self.status_var.set(f"正在处理: {task.basename}")

        def on_success(task: Task):
            self._post_ui_event(handle_success, task)

        def handle_success(task: Task):
            info_str = f"耗时 {task.cost:.1f}s"
            if task.is_multi:
                # 多文件合并：标记所有源文件为完成
                merge_name = os.path.basename(task.out_path)
                for src_path in task.input_files:
                    # 查找对应的 iid
                    for iid, fp in self.tree_mgr.file_map.items():
                        if os.path.normpath(fp) == os.path.normpath(src_path):
                            self.tree_mgr.update_status(
                                iid, "完成", f"合并→{merge_name}", tags="success",
                            )
                            break
                # 再标记第一个（合并主力）
                self.tree_mgr.update_status(
                    task.iid, "完成", info_str, tags="success",
                )
            elif task.source_deleted:
                self.tree_mgr.update_status(
                    task.iid, "已删", info_str + " (清理)", tags="deleted",
                )
            elif task.need_delete:
                self.tree_mgr.update_status(
                    task.iid,
                    "完成",
                    info_str + "（源文件删除失败）",
                    tags="success",
                )
            else:
                self.tree_mgr.update_status(
                    task.iid, "完成", info_str, tags="success",
                )

        def on_fail(task: Task, reason: str):
            self._post_ui_event(handle_fail, task, reason)

        def handle_fail(task: Task, reason: str):
            if task.is_multi:
                source_keys = {
                    os.path.normcase(os.path.abspath(path))
                    for path in task.input_files
                }
                for iid, path in self.tree_mgr.file_map.items():
                    if os.path.normcase(os.path.abspath(path)) in source_keys:
                        self.tree_mgr.update_status(
                            iid, "失败", reason, tags="failed",
                        )
            else:
                self.tree_mgr.update_status(
                    task.iid, "失败", reason, tags="failed",
                )

        def on_progress(current: int, total: int):
            self._post_ui_event(handle_progress, current, total)

        def handle_progress(current: int, total: int):
            self.progress['value'] = current
            self.progress['maximum'] = total
            self.progress_text_var.set(f"{current} / {total}")

        def on_finish():
            self._post_ui_event(self._conversion_finished)

        engine.callbacks.on_start = on_start
        engine.callbacks.on_success = on_success
        engine.callbacks.on_fail = on_fail
        engine.callbacks.on_progress = on_progress
        engine.callbacks.on_finish = on_finish

    def _post_ui_event(self, callback, *args):
        """允许工作线程安全投递 GUI 操作。"""
        self._ui_events.put((callback, args))

    def _drain_ui_events(self):
        """在 Tk 主线程依次执行后台线程投递的界面操作。"""
        try:
            while True:
                callback, args = self._ui_events.get_nowait()
                callback(*args)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(50, self._drain_ui_events)

    # ══════════════════════════════════════════════════════
    #  用户操作
    # ══════════════════════════════════════════════════════

    def _on_mode_change(self, event=None):
        """模式切换时更新格式缓存"""
        mode = self.mode_var.get()
        format_cache.set_mode(mode)
        if hasattr(self, "tree_mgr"):
            self.tree_mgr.apply_extension_filter(format_cache.exts_in)
        self._update_quality_state()
        self._update_font_state()
        if hasattr(self, "_drag_banner"):
            self._drag_banner.set_formats(
                self.source_format_var.get(), self.target_format_var.get(),
            )
        logger.info(f"切换到模式: {mode}")

    def _on_source_format_change(self, event=None):
        """源格式变化时，只展示其支持的目标格式。"""
        targets = get_target_formats(self.source_format_var.get())
        self.target_format_combo.config(values=targets)
        self.target_format_var.set(targets[0] if targets else "")
        self._on_target_format_change()

    def _on_target_format_change(self, event=None):
        """根据源格式和目标格式同步内部转换模式。"""
        mode = get_conversion_mode(
            self.source_format_var.get(),
            self.target_format_var.get(),
        )
        if not mode:
            return
        self.mode_var.set(mode)
        self._on_mode_change()

    def _update_quality_state(self):
        """仅在转换实现真正使用画质参数时启用选项。"""
        if format_cache.uses_quality():
            self.quality_combo.config(state="readonly")
            self.quality_label.config(foreground="")
        else:
            self.quality_combo.config(state=DISABLED)
            self.quality_label.config(foreground="gray")

    def _update_font_state(self):
        """字体仅影响 TXT 转 PDF，其他模式下避免造成误解。"""
        enabled = self.mode_var.get() == "TXT 转 PDF"
        self.font_combo.config(state="readonly" if enabled else DISABLED)
        self.font_label.config(foreground="" if enabled else "gray")

    def _on_font_change(self, event=None):
        """字体切换 (B5)"""
        name = self.font_var.get()
        set_current_font(name)
        logger.info(f"切换字体: {name}")

    def _on_toggle_all_del(self):
        """统一切换自动删除"""
        self.tree_mgr.toggle_all_flags()

    def _toggle_path(self):
        """切换输出路径模式"""
        state = tk.NORMAL if self.out_mode.get() == "custom" else tk.DISABLED
        self.entry_path.config(state=state)
        self.btn_browse.config(state=state)

    def _browse_path(self):
        p = filedialog.askdirectory()
        if p:
            self.custom_path_var.set(p)

    def _on_tree_click(self, event):
        """点击树列表第一列切换删除标记"""
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            if col == "#1":
                iid = self.tree.identify_row(event.y)
                if iid:
                    self.tree_mgr.toggle_delete_flag(iid)

    def _on_drop(self, event):
        """按当前转换模式递归识别拖入的文件或文件夹。"""
        files = self.tk.splitlist(event.data)
        count = self.tree_mgr.add_files(list(files))
        if count > 0:
            self.status_var.set(f"已添加 {count} 个文件")
        else:
            self.status_var.set("未找到与当前转换模式匹配的新文件")

    def _add_files(self):
        """文件对话框添加文件"""
        exts = format_cache.exts_in
        ft = [("Files", " ".join([f"*{e}" for e in exts]))] if exts else []
        fs = filedialog.askopenfilenames(filetypes=ft)
        if fs:
            count = self.tree_mgr.add_files(list(fs))
            self.status_var.set(f"已添加 {count} 个文件")

    def _add_folder(self):
        """添加文件夹"""
        d = filedialog.askdirectory()
        if d:
            count = self.tree_mgr.add_files([d])
            self.status_var.set(f"已添加 {count} 个文件")

    def _clear_list(self):
        """清空列表"""
        if engine.is_running:
            messagebox.showwarning("提示", "转换进行中，不能清空任务列表")
            return
        self.tree_mgr.clear_all()
        self.progress['value'] = 0
        self.progress_text_var.set("0 / 0")
        self.time_var.set("")

    def _remove_completed(self):
        """清理已结束任务，保留待处理和格式不匹配项。"""
        self.tree_mgr.remove_completed()
        self.status_var.set("已清除完成的任务")

    def _update_task_count(self):
        """刷新任务数与待处理数。"""
        if not hasattr(self, "tree") or not hasattr(self, "task_count_var"):
            return
        items = self.tree.get_children()
        if not items:
            self.task_count_var.set("暂无任务")
            return
        pending = sum(
            self.tree.set(iid, "status") == "待处理" for iid in items
        )
        self.task_count_var.set(f"共 {len(items)} 项  ·  待处理 {pending} 项")

    # ══════════════════════════════════════════════════════
    #  转换控制
    # ══════════════════════════════════════════════════════

    def _start_conversion(self):
        """开始转换"""
        # 先按当前模式刷新缓存和待办兼容状态。
        format_cache.set_mode(self.mode_var.get())
        self.tree_mgr.apply_extension_filter(format_cache.exts_in)
        pending = self.tree_mgr.get_pending_items()
        if not pending:
            messagebox.showinfo("提示", "没有待处理的文件")
            return

        if self.out_mode.get() == "custom" and not self.custom_path_var.get():
            messagebox.showerror("错误", "请选择输出路径")
            return

        mode = self.mode_var.get()
        quality = self.quality_var.get()
        use_custom = self.out_mode.get() == "custom"
        custom_folder = self.custom_path_var.get()

        # ── 多文件合并模式（PDF合并 / 图片合并） ────────
        if format_cache.is_multi_input():
            self._start_multi_merge(pending, mode, quality, use_custom, custom_folder)
            return

        # ── 普通模式：每个文件一个任务 ──────────────────
        tasks: list[Task] = []
        reserved_outputs: set[str] = set()
        for iid, file_path, need_delete in pending:
            out_path = format_cache.get_output_path(
                file_path,
                custom_folder,
                use_custom,
                reserved_paths=reserved_outputs,
            )
            task = Task(
                iid=iid, file_path=file_path,
                mode=mode, quality=quality,
                out_path=out_path, need_delete=need_delete,
            )
            tasks.append(task)

        self._launch_engine(tasks, len(tasks))

    def _start_multi_merge(self, pending, mode, quality, use_custom, custom_folder):
        """多文件合并模式的启动逻辑"""
        # 收集所有匹配的源文件
        source_paths = [fp for _, fp, _ in pending]
        if not source_paths:
            messagebox.showinfo("提示", "没有可合并的文件")
            return

        # 输出路径：使用第一个文件的名称
        first_path = source_paths[0]
        out_path = format_cache.get_output_path(
            first_path, custom_folder, use_custom,
        )

        # 创建单个合并任务，source_paths 存储在 input_files 中
        # iid 使用第一个文件，但后续回调会标记所有文件
        first_iid = pending[0][0]
        merge_task = Task(
            iid=first_iid, file_path=first_path,
            mode=mode, quality=quality,
            out_path=out_path, need_delete=False,
            input_files=source_paths,
        )

        self._launch_engine([merge_task], len(source_paths))
        logger.info(f"📎 合并模式: {len(source_paths)} 个文件 → {os.path.basename(out_path)}")

    def _launch_engine(self, tasks: list[Task], total_items: int):
        """启动引擎并更新 UI"""
        if not engine.start(tasks):
            messagebox.showwarning("提示", "转换引擎仍在运行，请稍后再试")
            return

        active_paths = {
            os.path.normcase(os.path.abspath(path))
            for task in tasks
            for path in (task.input_files or [task.file_path])
        }
        self._active_task_iids = {
            iid for iid, path in self.tree_mgr.file_map.items()
            if os.path.normcase(os.path.abspath(path)) in active_paths
        }

        self.btn_start.config(state=DISABLED)
        self.btn_pause.config(state=NORMAL, text="暂停", bootstyle="warning-outline")
        self.btn_stop.config(state=NORMAL)
        self.progress['value'] = 0
        self.progress['maximum'] = total_items
        self.progress_text_var.set(f"0 / {total_items}")

        self._timer_active = True
        self.status_var.set(f"开始转换 {total_items} 个文件...")

        mode = self.mode_var.get()
        logger.info(f"🚀 开始转换 {total_items} 个文件（模式: {mode}）")

    def _toggle_pause(self):
        """暂停/继续"""
        if engine.is_paused:
            engine.resume()
            self.btn_pause.config(text="暂停", bootstyle="warning-outline")
            self.status_var.set("任务继续...")
        else:
            engine.pause()
            self.btn_pause.config(text="继续", bootstyle="success-outline")
            self.status_var.set("任务已暂停")

    def _stop(self):
        """B1: 停止转换"""
        engine.stop()
        self.btn_stop.config(state=DISABLED)
        self.status_var.set("正在停止...")
        logger.info("用户点击停止")

    def _conversion_finished(self):
        """转换完成/停止后的清理"""
        self._timer_active = False
        self.btn_start.config(state=NORMAL)
        self.btn_pause.config(
            state=DISABLED, text="暂停", bootstyle="warning-outline",
        )
        self.btn_stop.config(state=DISABLED)
        self.status_var.set("任务完成")
        total = engine.elapsed
        self.time_var.set(f"总耗时: {int(total)}秒")

        # 检查失败项
        failed = 0
        for iid in self._active_task_iids:
            if hasattr(self.tree, "exists") and not self.tree.exists(iid):
                continue
            if self.tree.item(iid, "values")[2] in ("失败", "出错"):
                failed += 1

        if engine.last_run_stopped:
            messagebox.showinfo("已停止", "转换已停止，未处理的任务仍保留在列表中")
        elif failed > 0:
            messagebox.showwarning("完成", f"转换完成，{failed} 个文件失败，请查看日志")
        else:
            messagebox.showinfo("完成", "所有文件处理完毕！")

    # ══════════════════════════════════════════════════════
    #  定时器
    # ══════════════════════════════════════════════════════

    def _start_timer(self):
        """启动定时器"""
        self._timer_active = True
        self._timer_tick()

    def _timer_tick(self):
        """每秒更新计时器"""
        if not self._timer_active:
            return

        if engine.is_running:
            elapsed = engine.elapsed
            done = engine.completed_tasks
            total = engine.total_tasks

            time_str = f"已用: {fmt_time(elapsed)}"

            if done > 0 and total > 0:
                avg = elapsed / done
                remain = int(avg * (total - done))
                time_str += f" | 预计剩余: {fmt_time(remain)}"
            elif done == 0 and total > 0:
                time_str += " | 计算中..."

            self.time_var.set(time_str)

        self.after(1000, self._timer_tick)

    # ══════════════════════════════════════════════════════
    #  工具方法
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _help_icon(parent, text: str):
        """创建帮助图标"""
        btn = ttk.Label(
            parent, text="[?]", font=scaled_font("Arial", 9, "bold"),
            foreground="#17a2b8", cursor="hand2",
        )
        btn.pack(side=LEFT, padx=2)
        ToolTip(btn, text=text, bootstyle=(INFO, INVERSE))
