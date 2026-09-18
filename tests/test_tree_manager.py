import os
import tempfile
import unittest

from core.formats import format_cache
from gui.tree_manager import TreeManager


class FakeBooleanVar:
    def get(self):
        return False


class FakeTree:
    def __init__(self):
        self.rows = {}
        self.next_id = 1

    def insert(self, _parent, _position, values, tags=()):
        iid = str(self.next_id)
        self.next_id += 1
        self.rows[iid] = {"values": list(values), "tags": tuple(tags)}
        return iid

    def set(self, iid, column, value=None):
        indexes = {"del": 0, "path": 1, "status": 2, "info": 3,
                   "#1": 0}
        index = indexes[column]
        if value is None:
            return self.rows[iid]["values"][index]
        self.rows[iid]["values"][index] = value

    def item(self, iid, option=None, **kwargs):
        if "tags" in kwargs:
            self.rows[iid]["tags"] = tuple(kwargs["tags"])
        if option == "values":
            return tuple(self.rows[iid]["values"])
        return self.rows[iid]

    def get_children(self):
        return tuple(self.rows)

    def see(self, _iid):
        pass


def make_manager() -> TreeManager:
    manager = TreeManager.__new__(TreeManager)
    manager.tree = FakeTree()
    manager.master_check_var = FakeBooleanVar()
    manager.file_map = {}
    manager._path_to_iid = {}
    return manager


class TreeManagerTests(unittest.TestCase):
    def test_completed_file_can_be_queued_again(self):
        format_cache.set_mode("PDF 转 TXT")
        manager = make_manager()

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sample.pdf")
            open(path, "wb").close()

            self.assertEqual(manager.add_files([path]), 1)
            iid = next(iter(manager.file_map))
            manager.update_status(iid, "完成", "done", tags="success")

            self.assertEqual(manager.add_files([path]), 1)
            self.assertEqual(manager.tree.set(iid, "status"), "待处理")
            self.assertEqual(manager.tree.set(iid, "info"), "")

    def test_mode_filter_marks_incompatible_pending_file(self):
        format_cache.set_mode("PDF 转 TXT")
        manager = make_manager()

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sample.pdf")
            open(path, "wb").close()
            manager.add_files([path])
            iid = next(iter(manager.file_map))

            manager.apply_extension_filter([".docx", ".doc"])
            self.assertEqual(manager.tree.set(iid, "status"), "格式不匹配")
            manager.apply_extension_filter([".pdf"])
            self.assertEqual(manager.tree.set(iid, "status"), "待处理")

    def test_incompatible_completed_file_is_not_requeued(self):
        format_cache.set_mode("PDF 转 TXT")
        manager = make_manager()

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sample.pdf")
            open(path, "wb").close()
            manager.add_files([path])
            iid = next(iter(manager.file_map))
            manager.update_status(iid, "完成")

            format_cache.set_mode("Word 转 TXT")
            self.assertEqual(manager.add_files([path]), 0)
            self.assertEqual(manager.tree.set(iid, "status"), "完成")


if __name__ == "__main__":
    unittest.main()
