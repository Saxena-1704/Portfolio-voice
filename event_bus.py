from collections import defaultdict
from typing import Callable, Any


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str, handler: Callable) -> None:
        self._handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        self._handlers[event].remove(handler)

    async def emit(self, event: str, **data: Any) -> None:
        for handler in self._handlers.get(event, []):
            await handler(event=event, data=data)
