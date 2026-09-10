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
from typing import Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from core.formats import format_cache
from utils.logger import logger


class TreeManager:
    """管理 Treeview 文件列表"""

    def __init__(self, tree: ttk.Treeview, master_check_var: tk.BooleanVar):
        self.tree = tree
        self.master_check_var = master_check_var
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
            p = os.path.normpath(p)
            if os.path.isdir(p):
                c, s = self._add_directory(p, exts, icon, tag)
                count += c
                skipped += s
            else:
                if self._is_duplicate(p):
                    skipped += 1
                    continue
                if self._match_ext(p, exts):
                    self._insert_row(p, icon, tag)
                    count += 1
                else:
                    skipped += 1

        if skipped > 0:
            logger.info(f"跳过 {skipped} 个文件（格式不匹配或重复）")

        return count

    def _add_directory(self, dir_path: str, exts: list[str],
                       icon: str, tag: tuple) -> tuple[int, int]:
        """递归添加目录中的匹配文件"""
        count = 0
        skipped = 0
        for root, _, files in os.walk(dir_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                if self._is_duplicate(fpath):
                    skipped += 1
                    continue
                if self._match_ext(fpath, exts):
                    self._insert_row(fpath, icon, tag)
                    count += 1
                else:
                    skipped += 1
        return count, skipped

    def _insert_row(self, path: str, icon: str, tag: tuple):
        """插入一行，记录映射"""
        path = os.path.normpath(path)
        iid = self.tree.insert("", tk.END,
                               values=(icon, path, "待处理", ""),
                               tags=tag)
        self.file_map[iid] = path
        self._path_to_iid[path] = iid

    def _is_duplicate(self, path: str) -> bool:
        """O(1) 查重"""
        return os.path.normpath(path) in self._path_to_iid

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
            path = self.file_map.pop(iid, "")
            if path:
                self._path_to_iid.pop(path, None)
            self.tree.delete(iid)

    def remove_completed(self):
        """删除状态为 完成/已删/出错/失败 的行"""
        to_delete = []
        for iid in self.tree.get_children():
            status = self.tree.item(iid, "values")[2]
            if status not in ("待处理", "处理中..."):
                to_delete.append(iid)
        for iid in to_delete:
            path = self.file_map.pop(iid, "")
            if path:
                self._path_to_iid.pop(path, None)
            self.tree.delete(iid)

    def clear_all(self):
        """清空全部"""
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.file_map.clear()
        self._path_to_iid.clear()

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
        self.tree.set(iid, "status", status)
        if info:
            self.tree.set(iid, "info", info)
        if tags:
            self.tree.item(iid, tags=(tags,))
        self.tree.see(iid)

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
        return result

    @property
    def item_count(self) -> int:
        return len(self.tree.get_children())