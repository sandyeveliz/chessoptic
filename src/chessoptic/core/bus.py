"""Minimal thread-safe publish/subscribe bus, typed by event class."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

Callback = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callback]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: type, callback: Callback) -> Callable[[], None]:
        """Register `callback` for `event_type` (and subclasses). Returns an unsubscribe fn."""
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)

        def unsubscribe() -> None:
            with self._lock:
                callbacks = self._subscribers.get(event_type, [])
                if callback in callbacks:
                    callbacks.remove(callback)

        return unsubscribe

    def publish(self, event: object) -> None:
        with self._lock:
            targets = [
                cb
                for cls in type(event).__mro__
                for cb in self._subscribers.get(cls, ())
                if cls is not object
            ]
        for cb in targets:
            try:
                cb(event)
            except Exception:
                log.exception("subscriber %r failed on %r", cb, event)
