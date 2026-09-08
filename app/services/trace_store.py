from collections import deque
from threading import Lock
from typing import Any

_MAX_ITEMS = 200
_lock = Lock()
_items = deque(maxlen=_MAX_ITEMS)


def add_trace(item: dict[str, Any]) -> None:
    with _lock:
        _items.append(item)


def list_traces(limit: int = 50) -> list[dict[str, Any]]:
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200
    with _lock:
        data = list(_items)
    return data[-limit:]


def clear_traces() -> None:
    with _lock:
        _items.clear()