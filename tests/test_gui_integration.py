"""可选的隐藏 GUI 集成测试。

运行：
    $env:FORMATCONVERTER_GUI_TESTS = "1"
    python -m unittest tests.test_gui_integration -v
"""

import os
import tempfile
import time
import unittest
from unittest import mock

import fitz

from core.engine import engine
from gui.app import App


GUI_TESTS_ENABLED = os.environ.get("FORMATCONVERTER_GUI_TESTS") == "1"


@unittest.skipUnless(GUI_TESTS_ENABLED, "需要显式启用隐藏 GUI 测试")
class GuiIntegrationTests(unittest.TestCase):
    def wait_for_batch(self, app, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            app.update()
            if not engine.is_running and app.btn_start.instate(["!disabled"]):
                return
            time.sleep(0.02)
        self.fail("GUI 转换批次超时")

    def test_folder_add_and_two_consecutive_batches(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch(
            "gui.app.messagebox.showinfo"
        ), mock.patch("gui.app.messagebox.showwarning"), mock.patch(
            "gui.app.messagebox.showerror"
        ):
            source = os.path.join(folder, "sample.pdf")
            with fitz.open() as document:
                page = document.new_page()
                page.insert_text((72, 72), "FormatConverter GUI integration")
                document.save(source)

            app = App()
            app.withdraw()
            try:
                self.assertFalse(app._log_panel._visible)
                self.assertEqual(str(app.font_combo.cget("state")), "disabled")

                app.source_format_var.set("PDF")
                app._on_source_format_change()
                app.target_format_var.set("TXT")
                app._on_target_format_change()

                self.assertEqual(app.tree_mgr.add_files([folder]), 1)
                self.assertIn("1", app.task_count_var.get())
                iid = next(iter(app.tree_mgr.file_map))
                app._start_conversion()
                self.wait_for_batch(app)
                self.assertEqual(app.tree.set(iid, "status"), "完成")
                self.assertTrue(os.path.isfile(os.path.join(folder, "sample.txt")))

                self.assertEqual(app.tree_mgr.add_files([source]), 1)
                self.assertEqual(app.tree.set(iid, "status"), "待处理")
                app._start_conversion()
                self.wait_for_batch(app)
                self.assertEqual(app.tree.set(iid, "status"), "完成")
                self.assertTrue(os.path.isfile(os.path.join(folder, "sample_1.txt")))

                app.source_format_var.set("TXT")
                app._on_source_format_change()
                self.assertEqual(str(app.font_combo.cget("state")), "readonly")
            finally:
                if engine.is_running:
                    engine.stop()
                app.destroy()


if __name__ == "__main__":
    unittest.main()
