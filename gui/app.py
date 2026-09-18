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
import threading
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

from core.formats import FORMAT_MAP, ALL_MODES, format_cache
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
        w, h = int(950 * ScaleFactor), int(850 * ScaleFactor)
        self.geometry(f"{w}x{h}")
        self.style = ttk.Style("cosmo")

        # ── 全局字体缩放 ──
        fs = get_font_scale()
        base_font = ("微软雅黑", max(1, int(10 * fs)))
        self.style.configure('.', font=base_font)
        self.style.configure('TButton', font=("微软雅黑", max(1, int(9 * fs))))
        self.style.configure('TLabel', font=base_font)
        self.style.configure('TCombobox', font=base_font)
        self.style.configure('Treeview', font=("微软雅黑", max(1, int(9 * fs))))
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

        # ── 构建 UI ──
        self._build_ui()

        # ── 设置引擎回调 ──
        self._setup_engine_callbacks()

        # ── 注册转换函数 ──
        self._register_converter_funcs()

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
        # 1. 顶部拖拽区
        self._drag_banner = DragDropBanner(self)

        # 2. 转换配置
        self._build_config_panel()

        # 3. 文件列表
        self._build_file_list()

        # 4. 底部工具栏
        self._build_toolbar()

        # 5. 日志面板 (B6)
        self._log_panel = LogPanel(self)
        self._log_panel.pack(fill=BOTH, padx=10, pady=(0, 5))

        # 6. 状态栏
        self._build_statusbar()

    def _build_config_panel(self):
        """转换配置区域"""
        sets = ttk.Labelframe(self, text="转换配置", padding=12)
        sets.pack(fill=X, padx=10, pady=5)

        # 行1：模式 + 画质 + 字体 + 自动删除
        r1 = ttk.Frame(sets)
        r1.pack(fill=X, pady=2)

        ttk.Label(r1, text="转换模式:").pack(side=LEFT)
        self.mode_var = tk.StringVar(value=ALL_MODES[0])
        self.mode_combo = ttk.Combobox(
            r1, textvariable=self.mode_var,
            values=ALL_MODES, state="readonly", width=24,
        )
        self.mode_combo.pack(side=LEFT, padx=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        # 帮助提示
        self._help_icon(r1, "功能说明：\n• Office转PDF：调用本地Office\n• PDF转Word：⚠️大量数学公式/矩阵会非常慢\n• 图片转PDF：无损合并\n• PDF合并：选择多个PDF合并为一个\n• PDF压缩：降低图片DPI减小体积")

        ttk.Label(r1, text="画质引擎:", padding=(10, 0, 0, 0)).pack(side=LEFT)
        self.quality_var = tk.StringVar(value="臻享画质 (Ultra)")
        ttk.Combobox(
            r1, textvariable=self.quality_var,
            values=["臻享画质 (Ultra)", "标准均衡 (Standard)", "极速预览 (Speed)"],
            state="readonly", width=18, bootstyle="info",
        ).pack(side=LEFT, padx=5)
        self._help_icon(r1, "• 臻享(Ultra)：打印级清晰度\n• 标准(Std)：日常办公\n• 极速(Speed)：屏幕预览，生成最快")

        # B5: 字体选择
        ttk.Label(r1, text="字体:", padding=(10, 0, 0, 0)).pack(side=LEFT)
        fonts = get_available_fonts()
        self.font_var = tk.StringVar(value=fonts[0] if fonts else "Helvetica (默认)")
        self.font_combo = ttk.Combobox(
            r1, textvariable=self.font_var,
            values=fonts, state="readonly", width=14, bootstyle="secondary",
        )
        self.font_combo.pack(side=LEFT, padx=3)
        self.font_combo.bind("<<ComboboxSelected>>", self._on_font_change)
        self._help_icon(r1, "TXT→PDF 时使用的中文字体，自动检测系统可用字体")

        # 统一切换自动删除
        self.master_del_var = tk.BooleanVar(value=False)
        cb_del = ttk.Checkbutton(
            r1, text="默认[完成后自动删除]",
            variable=self.master_del_var,
            command=self._on_toggle_all_del,
            bootstyle="round-toggle",
        )
        cb_del.pack(side=RIGHT, padx=5)

        # 行2：输出路径
        r2 = ttk.Frame(sets)
        r2.pack(fill=X, pady=6)

        ttk.Label(r2, text="输出路径:").pack(side=LEFT)
        self.out_mode = tk.StringVar(value="origin")
        ttk.Radiobutton(
            r2, text="原文件夹", variable=self.out_mode,
            value="origin", command=self._toggle_path,
        ).pack(side=LEFT, padx=5)
        ttk.Radiobutton(
            r2, text="指定目录:", variable=self.out_mode,
            value="custom", command=self._toggle_path,
        ).pack(side=LEFT, padx=5)
        self.custom_path_var = tk.StringVar()
        self.entry_path = ttk.Entry(r2, textvariable=self.custom_path_var, state=DISABLED)
        self.entry_path.pack(side=LEFT, fill=X, expand=True, padx=5)
        self.btn_browse = ttk.Button(
            r2, text="...", width=4, state=DISABLED,
            command=self._browse_path, bootstyle=OUTLINE,
        )
        self.btn_browse.pack(side=LEFT)

    def _build_file_list(self):
        """文件列表区"""
        list_frame = ttk.Frame(self, padding=5)
        list_frame.pack(fill=BOTH, expand=True, padx=10)

        cols = ("del", "path", "status", "info")
        self.tree = ttk.Treeview(
            list_frame, columns=cols,
            show="headings", selectmode="extended",
        )

        self.tree.heading("del", text="自动删除?", anchor=CENTER)
        self.tree.heading("path", text="文件名称 / 路径")
        self.tree.heading("status", text="状态")
        self.tree.heading("info", text="耗时/备注")

        self.tree.column("del", width=80, anchor=CENTER, stretch=False)
        self.tree.column("path", width=400)
        self.tree.column("status", width=100, anchor=CENTER)
        self.tree.column("info", width=150, anchor=CENTER)

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
        self.tree_mgr = TreeManager(self.tree, self.master_del_var)

    def _build_toolbar(self):
        """底部工具栏（含 B1 停止按钮）"""
        tool = ttk.Frame(self, padding=10)
        tool.pack(fill=X)

        ttk.Button(tool, text="+ 文件", bootstyle=INFO,
                   command=self._add_files).pack(side=LEFT, padx=2)
        ttk.Button(tool, text="+ 文件夹", bootstyle=INFO,
                   command=self._add_folder).pack(side=LEFT, padx=2)
        ttk.Button(tool, text="清空列表", bootstyle=SECONDARY,
                   command=self._clear_list).pack(side=LEFT, padx=10)

        self.progress = ttk.Progressbar(tool, orient=HORIZONTAL, mode='determinate')
        self.progress.pack(side=LEFT, fill=X, expand=True, padx=20)

        # B1: 停止按钮
        self.btn_stop = ttk.Button(tool, text="⏹ 停止", bootstyle=DANGER,
                                   state=DISABLED, command=self._stop)
        self.btn_stop.pack(side=RIGHT, padx=3)

        # 暂停按钮
        self.btn_pause = ttk.Button(tool, text="⏸ 暂停", bootstyle=WARNING,
                                    state=DISABLED, command=self._toggle_pause)
        self.btn_pause.pack(side=RIGHT, padx=3)

        # 开始按钮
        self.btn_start = ttk.Button(tool, text="🚀 开始转换", bootstyle=SUCCESS,
                                    command=self._start_conversion)
        self.btn_start.pack(side=RIGHT, ipadx=15)

    def _build_statusbar(self):
        """底部状态栏"""
        status_bar = ttk.Frame(self)
        status_bar.pack(side=BOTTOM, fill=X, padx=10, pady=3)

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
            "PDF 合并": self._do_pdf_merge,
            "PDF 压缩": pdf_compress,

            # 图片处理
            "图片 转 PDF": image_to_pdf,
            "图片 合并 PDF": self._do_image_merge,
            "图片格式转换": image_convert,

            # 纯文本
            "TXT 转 PDF": txt_to_pdf,
            "Word 转 TXT": word_to_txt,
            "Excel 转 CSV": excel_to_csv,
        })

    def _setup_engine_callbacks(self):
        """设置引擎回调，更新 GUI"""

        def on_start(task: Task):
            self.tree_mgr.update_status(
                task.iid, "处理中...", tags="processing",
            )
            self.status_var.set(f"正在处理: {task.basename}")

        def on_success(task: Task):
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
            elif task.need_delete:
                self.tree_mgr.update_status(
                    task.iid, "已删", info_str + " (清理)", tags="deleted",
                )
            else:
                self.tree_mgr.update_status(
                    task.iid, "完成", info_str, tags="success",
                )

        def on_fail(task: Task, reason: str):
            self.tree_mgr.update_status(
                task.iid, "失败", reason, tags="failed",
            )

        def on_progress(current: int, total: int):
            self.progress['value'] = current
            self.progress['maximum'] = total

        def on_finish():
            self._conversion_finished()

        engine.callbacks.on_start = on_start
        engine.callbacks.on_success = on_success
        engine.callbacks.on_fail = on_fail
        engine.callbacks.on_progress = on_progress
        engine.callbacks.on_finish = on_finish

    # ══════════════════════════════════════════════════════
    #  用户操作
    # ══════════════════════════════════════════════════════

    def _on_mode_change(self, event=None):
        """模式切换时更新格式缓存"""
        mode = self.mode_var.get()
        format_cache.set_mode(mode)
        logger.info(f"切换到模式: {mode}")

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
        """拖拽文件"""
        files = self.tk.splitlist(event.data)
        count = self.tree_mgr.add_files(list(files))
        if count > 0:
            self.status_var.set(f"已添加 {count} 个文件")

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
        self.tree_mgr.clear_all()
        self.progress['value'] = 0
        self.time_var.set("")

    # ══════════════════════════════════════════════════════
    #  转换控制
    # ══════════════════════════════════════════════════════

    def _start_conversion(self):
        """开始转换"""
        pending = self.tree_mgr.get_pending_items()
        if not pending:
            messagebox.showinfo("提示", "没有待处理的文件")
            return

        if self.out_mode.get() == "custom" and not self.custom_path_var.get():
            messagebox.showerror("错误", "请选择输出路径")
            return

        # 确保格式缓存是最新的
        format_cache.set_mode(self.mode_var.get())

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
        for iid, file_path, need_delete in pending:
            out_path = format_cache.get_output_path(
                file_path, custom_folder, use_custom,
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
        self.btn_start.config(state=DISABLED)
        self.btn_pause.config(state=NORMAL, text="⏸ 暂停", bootstyle=WARNING)
        self.btn_stop.config(state=NORMAL)
        self.progress['value'] = 0
        self.progress['maximum'] = total_items

        engine.start(tasks)
        self._timer_active = True
        self.status_var.set(f"开始转换 {total_items} 个文件...")

        mode = self.mode_var.get()
        logger.info(f"🚀 开始转换 {total_items} 个文件（模式: {mode}）")

    def _toggle_pause(self):
        """暂停/继续"""
        if engine.is_paused:
            engine.resume()
            self.btn_pause.config(text="⏸ 暂停", bootstyle=WARNING)
            self.status_var.set("任务继续...")
        else:
            engine.pause()
            self.btn_pause.config(text="▶ 继续", bootstyle=SUCCESS)
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
        self.btn_pause.config(state=DISABLED, text="⏸ 暂停")
        self.btn_stop.config(state=DISABLED)
        self.status_var.set("任务完成")
        total = engine.elapsed
        self.time_var.set(f"总耗时: {int(total)}秒")

        # 检查失败项
        failed = 0
        for iid in self.tree.get_children():
            if self.tree.item(iid, "values")[2] in ("失败", "出错"):
                failed += 1

        if failed > 0:
            messagebox.showwarning("完成", f"转换完成，{failed} 个文件失败，请查看日志")
        else:
            messagebox.showinfo("完成", "所有文件处理完毕！")

    # ══════════════════════════════════════════════════════
    #  特殊多文件转换 (B4)
    # ══════════════════════════════════════════════════════

    def _do_pdf_merge(self, task: Task, app=None) -> bool:
        """
        PDF 合并 (B4)
        使用 task.input_files 中的所有 PDF 进行合并。
        """
        try:
            import fitz

            pdf_paths = [p for p in task.input_files if p.lower().endswith('.pdf')]
            if not pdf_paths:
                logger.error("没有可合并的 PDF 文件")
                return False

            out_doc = fitz.open()
            for pdf_path in pdf_paths:
                src = fitz.open(pdf_path)
                out_doc.insert_pdf(src)
                src.close()

            out_doc.save(task.out_path, deflate=True)
            out_doc.close()

            logger.info(f"✅ 合并 {len(pdf_paths)} 个 PDF → {task.out_path}")
            return True
        except Exception as e:
            logger.error(f"PDF 合并失败: {e}")
            return False

    def _do_image_merge(self, task: Task, app=None) -> bool:
        """
        多图片合并为单 PDF (B4)
        使用 task.input_files 中的所有图片。
        """
        try:
            from PIL import Image

            img_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
            img_paths = [
                p for p in task.input_files
                if os.path.splitext(p)[1].lower() in img_exts
            ]

            if not img_paths:
                logger.error("没有可合并的图片")
                return False

            images = []
            for img_path in img_paths:
                img = Image.open(img_path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)

            if images:
                images[0].save(
                    task.out_path, "PDF",
                    save_all=True,
                    append_images=images[1:],
                )

            # 关闭所有图片
            for img in images:
                img.close()

            logger.info(f"✅ 合并 {len(images)} 张图片 → {task.out_path}")
            return True
        except Exception as e:
            logger.error(f"图片合并 PDF 失败: {e}")
            return False

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
