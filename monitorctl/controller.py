"""后台控制器：串行化 DDC/CI 读写，避免阻塞界面。"""

from __future__ import annotations

import itertools
import queue
import threading
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from . import ddc


class _Bridge(QObject):
    done = Signal(object)
    failed = Signal(object)


class Controller(QObject):
    """所有 DDC 操作都在这一个后台线程里串行执行。

    * 写操作优先级更高，并且同一个 (显示器, VCP) 只保留最新值（合并抖动）。
    * 回调统一回到 Qt 主线程执行。
    """

    monitorScanned = Signal(object)     # List[Monitor]
    scanFailed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bridge = _Bridge(self)
        self.bridge.done.connect(self._on_done)
        self.bridge.failed.connect(self._on_failed)

        self.monitors: List[ddc.Monitor] = []
        self._queue: "queue.PriorityQueue" = queue.PriorityQueue()
        self._seq = itertools.count()
        self._pending_writes: Dict[Tuple[int, int], Tuple[ddc.Monitor, int, int]] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="ddc-worker", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ #
    def _submit(self, fn: Callable, callback: Optional[Callable], priority: int = 5) -> None:
        def job():
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                self.bridge.failed.emit((callback, exc))
            else:
                self.bridge.done.emit((callback, result))

        self._queue.put((priority, next(self._seq), job))

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                _prio, _seq, job = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            job()

    def _on_done(self, payload) -> None:
        callback, result = payload
        if callback:
            callback(result)

    def _on_failed(self, payload) -> None:
        callback, exc = payload
        if callback:
            callback(exc)

    # ------------------------------------------------------------------ #
    def scan(self, callback: Optional[Callable] = None) -> None:
        def task():
            for mon in self.monitors:
                mon.close()
            return ddc.enumerate_monitors(open_handles=True)

        def done(monitors):
            self.monitors = monitors
            self.monitorScanned.emit(monitors)
            if callback:
                callback(monitors)

        def failed(exc):
            self.scanFailed.emit(str(exc))
            if callback:
                callback([])

        self._submit(task, lambda r: done(r) if not isinstance(r, Exception) else failed(r), priority=0)

    # -- 读 -------------------------------------------------------------- #
    def read(self, mon: ddc.Monitor, code: int, callback: Callable) -> None:
        self._submit(lambda: mon.get_vcp(code), callback, priority=3)

    def read_many(self, mon: ddc.Monitor, codes: List[int], callback: Callable) -> None:
        def task():
            out = {}
            for code in codes:
                try:
                    out[code] = mon.get_vcp(code)
                except ddc.DDCError:
                    out[code] = None
            return out

        self._submit(task, callback, priority=4)

    # -- 写 -------------------------------------------------------------- #
    def write(self, mon: ddc.Monitor, code: int, value: int,
              callback: Optional[Callable] = None) -> None:
        """非阻塞写入；同一目标的高频调用会被合并为最后一次。"""
        key = (id(mon), code)
        self._pending_writes[key] = (mon, code, int(value))
        self._submit(lambda: self._flush(key), callback, priority=0)

    def _flush(self, key) -> Tuple[ddc.Monitor, int, int]:
        mon, code, value = self._pending_writes.pop(key)
        mon.set_vcp(code, value)
        return mon, code, value

    def write_now(self, mon: ddc.Monitor, code: int, value: int,
                  callback: Optional[Callable] = None) -> None:
        self._submit(lambda: (mon.set_vcp(code, value), (mon, code, value))[1],
                     callback, priority=0)

    # -- 组合操作 -------------------------------------------------------- #
    def call(self, fn: Callable, callback: Optional[Callable] = None,
             priority: int = 1) -> None:
        """在 DDC 线程里执行任意任务（用于批量/多步操作）。"""
        self._submit(fn, callback, priority=priority)

    def run_sequence(self, steps: List[Tuple[ddc.Monitor, int, int]],
                     callback: Optional[Callable] = None) -> None:
        """按顺序执行一组写入，返回 [(mon, code, value, error|None)]。"""

        def task():
            results = []
            for mon, code, value in steps:
                try:
                    mon.set_vcp(code, value)
                    results.append((mon, code, value, None))
                except ddc.DDCError as exc:
                    results.append((mon, code, value, str(exc)))
            return results

        self._submit(task, callback, priority=1)

    def shutdown(self) -> None:
        self._stop.set()
        for mon in self.monitors:
            try:
                mon.close()
            except Exception:
                pass
        self.monitors = []
