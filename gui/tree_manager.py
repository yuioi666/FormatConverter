"""
gui/tree_manager.py — Treeview 文件列表管理

负责：
- 文件添加/去重（B3）
- 删除标记切换
- 右键菜单（B2）
- 批量操作
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from core.formats import format_cache
from utils.logger import logger


class TreeManager:
    """管理 Treeview 文件列表"""

    def __init__(self, tree: ttk.Treeview, master_check_var: tk.BooleanVar,
                 on_change: Optional[Callable[[], None]] = None):
        self.tree = tree
        self.master_check_var = master_check_var
        self.on_change = on_change
        self.file_map: dict[str, str] = {}  # iid → file_path
        self._path_to_iid: dict[str, str] = {}  # file_path → iid（用于 O(1) 去重）

        # 绑定右键菜单
        self._create_context_menu()
        tree.bind("<Button-3>", self._on_right_click)

    # ── 添加文件 ────────────────────────────────────────
    def add_files(self, paths: list[str]) -> int:
        """
        添加文件到列表，自动去重。
        返回实际添加的数量。
        """
        exts = format_cache.exts_in
        if not exts:
            return 0

        is_checked = self.master_check_var.get()
        icon = "☑ 是" if is_checked else "☐ 否"
        tag = ("checked",) if is_checked else ()

        count = 0
        skipped = 0

        for p in paths:
            p = os.path.abspath(os.path.normpath(p))
            if os.path.isdir(p):
                c, s = self._add_directory(p, exts, icon, tag)
                count += c
                skipped += s
            else:
                if not self._match_ext(p, exts):
                    skipped += 1
                    continue
                existing_iid = self._get_existing_iid(p)
                if existing_iid:
                    if self._requeue_completed(existing_iid, icon, tag):
                        count += 1
                    else:
                        skipped += 1
                    continue
                self._insert_row(p, icon, tag)
                count += 1

        if skipped > 0:
            logger.info(f"跳过 {skipped} 个文件（格式不匹配或重复）")

        self._notify_change()
        return count

    def _notify_change(self):
        """通知界面刷新任务统计。"""
        callback = getattr(self, "on_change", None)
        if callback:
            callback()

    def _add_directory(self, dir_path: str, exts: list[str],
                       icon: str, tag: tuple) -> tuple[int, int]:
        """递归添加目录中的匹配文件"""
        count = 0
        skipped = 0
        for root, dirs, files in os.walk(dir_path):
            dirs.sort(key=str.casefold)
            for fname in sorted(files, key=str.casefold):
                fpath = os.path.join(root, fname)
                if not self._match_ext(fpath, exts):
                    skipped += 1
                    continue
                existing_iid = self._get_existing_iid(fpath)
                if existing_iid:
                    if self._requeue_completed(existing_iid, icon, tag):
                        count += 1
                    else:
                        skipped += 1
                    continue
                self._insert_row(fpath, icon, tag)
                count += 1
        return count, skipped

    def _insert_row(self, path: str, icon: str, tag: tuple):
        """插入一行，记录映射"""
        path = os.path.abspath(os.path.normpath(path))
        iid = self.tree.insert("", tk.END,
                               values=(icon, path, "待处理", ""),
                               tags=tag)
        self.file_map[iid] = path
        self._path_to_iid[self._path_key(path)] = iid

    @staticmethod
    def _path_key(path: str) -> str:
        """用于 Windows 路径查重的规范键。"""
        return os.path.normcase(os.path.abspath(os.path.normpath(path)))

    def _get_existing_iid(self, path: str) -> Optional[str]:
        return self._path_to_iid.get(self._path_key(path))

    def _requeue_completed(self, iid: str, icon: str, tag: tuple) -> bool:
        """再次添加已完成文件时，将原行恢复为待处理。"""
        status = self.tree.set(iid, "status")
        path = self.file_map.get(iid, "")
        if status in ("待处理", "处理中...") or not os.path.isfile(path):
            return False
        self.tree.set(iid, "del", icon)
        self.tree.set(iid, "status", "待处理")
        self.tree.set(iid, "info", "")
        self.tree.item(iid, tags=tag)
        self.tree.see(iid)
        return True

    @staticmethod
    def _match_ext(path: str, exts: list[str]) -> bool:
        """检查扩展名是否匹配"""
        _, ext = os.path.splitext(path)
        return ext.lower() in exts

    # ── 删除标记 ────────────────────────────────────────
    def toggle_delete_flag(self, iid: str):
        """切换单行的自动删除标记"""
        curr = self.tree.item(iid, "values")[2]  # status column
        if curr not in ("待处理",):
            return

        curr_val = self.tree.set(iid, "#1")  # "del" 列是第1列
        if "☐" in curr_val:
            self.tree.set(iid, "#1", "☑ 是")
            self.tree.item(iid, tags=("checked",))
        else:
            self.tree.set(iid, "#1", "☐ 否")
            self.tree.item(iid, tags=())

    def toggle_all_flags(self):
        """统一切换所有行删除标记"""
        val = self.master_check_var.get()
        icon = "☑ 是" if val else "☐ 否"
        for iid in self.tree.get_children():
            curr = self.tree.item(iid, "values")[2]
            if curr in ("待处理",):
                self.tree.set(iid, "#1", icon)
                if val:
                    self.tree.item(iid, tags=("checked",))
                else:
                    self.tree.item(iid, tags=())

    # ── 删除行 ──────────────────────────────────────────
    def remove_selected(self):
        """删除选中的行"""
        selected = self.tree.selection()
        for iid in selected:
            if self.tree.set(iid, "status") == "处理中...":
                continue
            path = self.file_map.pop(iid, "")
            if path:
                self._path_to_iid.pop(self._path_key(path), None)
            self.tree.delete(iid)
        self._notify_change()

    def remove_completed(self):
        """删除状态为 完成/已删/出错/失败 的行"""
        to_delete = []
        for iid in self.tree.get_children():
            status = self.tree.item(iid, "values")[2]
            if status not in ("待处理", "处理中...", "格式不匹配"):
                to_delete.append(iid)
        for iid in to_delete:
            path = self.file_map.pop(iid, "")
            if path:
                self._path_to_iid.pop(self._path_key(path), None)
            self.tree.delete(iid)
        self._notify_change()

    def clear_all(self):
        """清空全部"""
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.file_map.clear()
        self._path_to_iid.clear()
        self._notify_change()

    def move_up(self):
        """选中的行上移"""
        selected = self.tree.selection()
        for iid in selected:
            idx = self.tree.index(iid)
            if idx > 0:
                self.tree.move(iid, "", idx - 1)

    def move_down(self):
        """选中的行下移"""
        selected = self.tree.selection()
        for iid in reversed(selected):
            idx = self.tree.index(iid)
            children = self.tree.get_children()
            if idx < len(children) - 1:
                self.tree.move(iid, "", idx + 1)

    # ── 状态更新 ────────────────────────────────────────
    def update_status(self, iid: str, status: str, info: str = "", tags: str = ""):
        """更新单行状态"""
        if hasattr(self.tree, "exists") and not self.tree.exists(iid):
            return
        self.tree.set(iid, "status", status)
        if info:
            self.tree.set(iid, "info", info)
        if tags:
            self.tree.item(iid, tags=(tags,))
        self.tree.see(iid)
        self._notify_change()

    def apply_extension_filter(self, exts: list[str]):
        """根据当前模式标记待办文件，切回兼容模式时自动恢复。"""
        for iid in self.tree.get_children():
            status = self.tree.set(iid, "status")
            if status not in ("待处理", "格式不匹配"):
                continue
            path = self.file_map.get(iid, "")
            if self._match_ext(path, exts):
                self.tree.set(iid, "status", "待处理")
                self.tree.set(iid, "info", "")
            else:
                self.tree.set(iid, "status", "格式不匹配")
                self.tree.set(iid, "info", "不适用于当前转换模式")
        self._notify_change()

    # ── 右键菜单 (B2) ──────────────────────────────────
    def _create_context_menu(self):
        self._menu = tk.Menu(self.tree, tearoff=0)
        self._menu.add_command(label="删除选中行", command=self.remove_selected)
        self._menu.add_command(label="清除已完成", command=self.remove_completed)
        self._menu.add_separator()
        self._menu.add_command(label="上移一行", command=self.move_up)
        self._menu.add_command(label="下移一行", command=self.move_down)
        self._menu.add_separator()
        self._menu.add_command(label="全选", command=self.select_all)
        self._menu.add_command(label="全部切换[自动删除]",
                               command=self._toggle_context_flags)

    def select_all(self):
        """全选"""
        self.tree.selection_set(self.tree.get_children())

    def _toggle_context_flags(self):
        """右键菜单中的切换删除标记"""
        for iid in self.tree.get_children():
            curr = self.tree.item(iid, "values")[2]
            if curr in ("待处理",):
                cv = self.tree.set(iid, "#1")
                if "☑" in cv:
                    self.tree.set(iid, "#1", "☐ 否")
                    self.tree.item(iid, tags=())
                else:
                    self.tree.set(iid, "#1", "☑ 是")
                    self.tree.item(iid, tags=("checked",))

    def _on_right_click(self, event):
        """右键弹出菜单"""
        iid = self.tree.identify_row(event.y)
        if iid:
            # 如果没选中该行，选中它
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    # ── 查询 ────────────────────────────────────────────
    def get_pending_items(self) -> list[tuple[str, str, bool]]:
        """
        返回待处理的文件列表。
        每个元素: (iid, file_path, need_delete)
        """
        result = []
        for iid in self.tree.get_children():
            status = self.tree.item(iid, "values")[2]
            if status in ("待处理",):
                path = self.file_map.get(iid, "")
                if path and os.path.isfile(path):
                    need_delete = "☑" in self.tree.item(iid, "values")[0]
                    result.append((iid, path, need_delete))
                elif path:
                    self.update_status(iid, "文件不存在", "请重新添加文件", tags="failed")
        return result

    @property
    def item_count(self) -> int:
        return len(self.tree.get_children())
