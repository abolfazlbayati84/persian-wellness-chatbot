from collections import deque
from threading import Lock
from typing import Any

_MAX_ITEMS = 200
_lock = Lock()
_items: deque[dict[str, Any]] = deque(maxlen=_MAX_ITEMS)


def add_trace(item: dict[str, Any]) -> None:
    with _lock:
        _items.append(item)


def list_traces(limit: int = 50, user_id: int | None = None) -> list[dict[str, Any]]:
    """Newest-last. If user_id is given, only that user's traces are returned."""
    limit = max(1, min(int(limit), _MAX_ITEMS))
    with _lock:
        data = list(_items)
    if user_id is not None:
        data = [d for d in data if d.get("user_id") == user_id]
    return data[-limit:]


def clear_traces(user_id: int | None = None) -> None:
    """Clears in-memory traces only. Never touches the messages table."""
    with _lock:
        if user_id is None:
            _items.clear()
            return
        kept = [d for d in _items if d.get("user_id") != user_id]
        _items.clear()
        _items.extend(kept)