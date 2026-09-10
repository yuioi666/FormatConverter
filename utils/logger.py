"""
utils/logger.py — 内存环形缓冲区日志系统 (B6)
"""

import time
from collections import deque
from typing import Callable, Optional


class LogLevel:
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


class LogEntry:
    """单条日志记录"""

    def __init__(self, level: str, message: str):
        self.timestamp = time.time()
        self.time_str = time.strftime("[%H:%M:%S]", time.localtime())
        self.level = level
        self.message = message

    def format(self) -> str:
        return f"{self.time_str} [{self.level}] {self.message}"


class LogBuffer:
    """线程安全的环形缓冲区日志"""

    def __init__(self, maxlen: int = 500):
        self._buffer: deque[LogEntry] = deque(maxlen=maxlen)
        self._maxlen = maxlen
        self._on_append: Optional[Callable[[LogEntry], None]] = None

    def set_callback(self, cb: Callable[[LogEntry], None]):
        """设置新日志回调（用于 GUI 刷新）"""
        self._on_append = cb

    def append(self, level: str, message: str):
        entry = LogEntry(level, message)
        self._buffer.append(entry)
        if self._on_append:
            try:
                self._on_append(entry)
            except Exception:
                pass  # 避免回调异常影响主逻辑

    def info(self, message: str):
        self.append(LogLevel.INFO, message)

    def warn(self, message: str):
        self.append(LogLevel.WARN, message)

    def error(self, message: str):
        self.append(LogLevel.ERROR, message)

    def success(self, message: str):
        self.append(LogLevel.SUCCESS, message)

    def get_all(self) -> list[LogEntry]:
        return list(self._buffer)

    def get_recent(self, n: int = 50) -> list[LogEntry]:
        return list(self._buffer)[-n:]

    def clear(self):
        self._buffer.clear()

    def to_text(self) -> str:
        return "\n".join(e.format() for e in self._buffer)

    @property
    def count(self) -> int:
        return len(self._buffer)


# 全局单例
logger = LogBuffer()