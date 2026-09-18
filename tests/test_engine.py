import threading
import unittest

from core.engine import ConversionEngine, Task


def make_task(name: str = "input.pdf") -> Task:
    return Task(
        iid=name,
        file_path=name,
        mode="测试转换",
        quality="标准均衡 (Standard)",
        out_path=name + ".txt",
        need_delete=False,
    )


class ConversionEngineTests(unittest.TestCase):
    def test_engine_can_run_two_consecutive_batches(self):
        engine = ConversionEngine()
        converted = []
        finished = threading.Event()

        def convert(task, app):
            converted.append(task.file_path)
            return True

        engine.set_converter_funcs({"测试转换": convert})
        engine.callbacks.on_finish = finished.set

        self.assertTrue(engine.start([make_task("first")]))
        self.assertTrue(finished.wait(3))
        self.assertFalse(engine.is_running)

        finished.clear()
        self.assertTrue(engine.start([make_task("second")]))
        self.assertTrue(finished.wait(3))
        self.assertFalse(engine.is_running)
        self.assertEqual(converted, ["first", "second"])

    def test_failed_task_still_advances_progress(self):
        engine = ConversionEngine()
        finished = threading.Event()
        progress = []

        def fail(task, app):
            task.error = "expected failure"
            return False

        engine.set_converter_funcs({"测试转换": fail})
        engine.callbacks.on_progress = lambda current, total: progress.append(
            (current, total)
        )
        engine.callbacks.on_finish = finished.set

        self.assertTrue(engine.start([make_task()]))
        self.assertTrue(finished.wait(3))
        self.assertEqual(progress, [(1, 1)])

    def test_failed_source_deletion_is_not_reported_as_deleted(self):
        engine = ConversionEngine()
        finished = threading.Event()
        task = make_task("file-that-does-not-exist.pdf")
        task.need_delete = True

        engine.set_converter_funcs({"测试转换": lambda _task, _app: True})
        engine.callbacks.on_finish = finished.set

        self.assertTrue(engine.start([task]))
        self.assertTrue(finished.wait(3))
        self.assertFalse(task.source_deleted)


if __name__ == "__main__":
    unittest.main()
