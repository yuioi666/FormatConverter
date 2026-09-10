"""
core/engine.py — 队列式转换引擎

采用生产者-消费者模式：
- 主线程（GUI）调用 submit() 提交任务到 Queue
- 一个工作线程从 Queue 取任务，通过回调通知进度
- 支持暂停（Event）/ 停止（flag）
"""

import os
import time
import threading
import queue
from typing import Callable, Optional

from utils.logger import logger
from core.formats import FORMAT_MAP, format_cache

# ── 任务数据类型 ───────────────────────────────────────
class Task:
    def __init__(self, iid: str, file_path: str, mode: str,
                 quality: str, out_path: str, need_delete: bool,
                 input_files: Optional[list[str]] = None):
        self.iid = iid
        self.file_path = os.path.normpath(file_path)
        self.mode = mode
        self.quality = quality
        self.out_path = out_path
        self.need_delete = need_delete
        # 多文件合并模式：存储所有源文件路径
        self.input_files = input_files or []
        self.start_time = 0.0
        self.cost = 0.0

    @property
    def basename(self) -> str:
        return os.path.basename(self.file_path)

    @property
    def is_multi(self) -> bool:
        return len(self.input_files) > 1


# ── 回调类型 ────────────────────────────────────────────
class TaskCallbacks:
    def __init__(self):
        self.on_start: Optional[Callable[[Task], None]] = None
        self.on_success: Optional[Callable[[Task], None]] = None
        self.on_fail: Optional[Callable[[Task, str], None]] = None
        self.on_progress: Optional[Callable[[int, int], None]] = None  # current, total
        self.on_finish: Optional[Callable[[], None]] = None


# ── 转换引擎 ────────────────────────────────────────────
class ConversionEngine:
    """非阻塞队列式转换引擎"""

    def __init__(self):
        self._queue: queue.Queue[Task] = queue.Queue()
        self._worker: Optional[threading.Thread] = None

        # 控制标志
        self._stop_flag = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # 默认允许运行

        self._running = False
        self._total_tasks = 0
        self._completed_tasks = 0
        self._start_timestamp = 0.0
        self._pause_timestamp = 0.0
        self._total_pause_duration = 0.0

        self.callbacks = TaskCallbacks()

        # 导入转换函数引用（延迟赋值）
        self._converter_funcs = None

    # ── 公开属性 ────────────────────────────────────────
    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    @property
    def pause_event(self) -> threading.Event:
        return self._pause_event

    @property
    def total_tasks(self) -> int:
        return self._total_tasks

    @property
    def completed_tasks(self) -> int:
        return self._completed_tasks

    def set_converter_funcs(self, funcs):
        """
        设置转换函数字典。
        funcs = {
            'Word 转 PDF': callable(task, app),
            'Excel 转 PDF': callable(task, app),
            ...
        }
        由外部注入以解耦循环导入。
        """
        self._converter_funcs = funcs

    # ── 控制方法 ────────────────────────────────────────
    def start(self, tasks: list[Task]):
        """启动转换任务队列"""
        if self._running:
            return

        self._stop_flag = False
        self._pause_event.set()
        self._running = True
        self._completed_tasks = 0
        self._total_tasks = len(tasks)
        self._total_pause_duration = 0.0

        # 清空旧队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        for t in tasks:
            self._queue.put(t)

        self._start_timestamp = time.time()

        logger.info(f"🚀 开始转换: {self._total_tasks} 个文件")

        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def stop(self):
        """请求停止（当前文件处理完即停）"""
        self._stop_flag = True
        self._pause_event.set()  # 如果处于暂停状态，解除暂停以便 worker 检测到 stop
        logger.info("⏹ 已请求停止转换")

    def pause(self):
        """暂停"""
        if not self._running:
            return
        self._pause_event.clear()
        self._pause_timestamp = time.time()
        logger.info("⏸ 转换已暂停")

    def resume(self):
        """继续"""
        if not self._running:
            return
        self._pause_event.set()
        self._total_pause_duration += (time.time() - self._pause_timestamp)
        logger.info("▶ 转换继续")

    @property
    def elapsed(self) -> float:
        """返回实际已运行时长（不含暂停）"""
        if not self._start_timestamp:
            return 0.0
        return time.time() - self._start_timestamp - self._total_pause_duration

    # ── 工作线程 ────────────────────────────────────────
    def _worker_loop(self):
        """工作线程主循环"""
        import comtypes.client as comclient
        from core.formats import FORMAT_MAP

        mode = None  # 将在第一个任务中确定
        is_office = False
        app = None

        try:
            # 确定模式
            if not self._queue.empty():
                first_task = self._queue.queue[0]
                mode = first_task.mode
                is_office = mode in FORMAT_MAP.get("Office → PDF", {})

                if is_office:
                    comclient.CoInitialize()
                    try:
                        if "Word" in mode:
                            app = comclient.CreateObject("Word.Application")
                        elif "Excel" in mode:
                            app = comclient.CreateObject("Excel.Application")
                        elif "PPT" in mode:
                            app = comclient.CreateObject("Powerpoint.Application")
                        if app:
                            app.Visible = False
                    except Exception as e:
                        logger.error(f"无法启动 Office 应用: {e}")
                        app = None

            while not self._queue.empty() and not self._stop_flag:
                # 暂停检测
                self._pause_event.wait()

                if self._stop_flag:
                    break

                task = self._queue.get()
                task.start_time = time.time()

                # 通知开始
                if self.callbacks.on_start:
                    self.callbacks.on_start(task)

                try:
                    success = self._convert_single(task, app, is_office)
                except Exception as e:
                    logger.error(f"{task.basename}: 转换异常 — {e}")
                    success = False

                task.cost = time.time() - task.start_time

                if success:
                    self._completed_tasks += 1
                    if task.need_delete:
                        self._try_delete_source(task)

                    if self.callbacks.on_success:
                        self.callbacks.on_success(task)

                    msg = f"✅ {task.basename} → 完成 ({task.cost:.1f}s)"
                    if task.need_delete:
                        msg += " [已删除源文件]"
                    logger.success(msg)
                else:
                    if self.callbacks.on_fail:
                        self.callbacks.on_fail(task, "转换失败")

                    logger.error(f"❌ {task.basename} → 转换失败 ({task.cost:.1f}s)")

                # 进度通知
                if self.callbacks.on_progress:
                    self.callbacks.on_progress(self._completed_tasks, self._total_tasks)

        finally:
            # 清理 COM
            if app:
                try:
                    app.Quit()
                except Exception:
                    pass
            if is_office:
                try:
                    comclient.CoUninitialize()
                except Exception:
                    pass

            self._running = False
            self._stop_flag = False

            if self.callbacks.on_finish:
                self.callbacks.on_finish()

            total_time = time.time() - self._start_timestamp - self._total_pause_duration
            logger.info(f"🏁 任务全部完成，总耗时 {total_time:.1f}秒")

    def _convert_single(self, task: Task, app, is_office: bool):
        """执行单个文件转换"""
        if self._converter_funcs is None:
            logger.error("转换函数未设置")
            return False

        converter_map = self._converter_funcs
        mode = task.mode

        if mode in converter_map:
            return converter_map[mode](task, app)

        # 兼容旧式回调
        logger.error(f"未知转换模式: {mode}")
        return False

    @staticmethod
    def _try_delete_source(task: Task):
        """尝试删除源文件"""
        try:
            os.remove(task.file_path)
        except Exception:
            pass


# 全局单例
engine = ConversionEngine()