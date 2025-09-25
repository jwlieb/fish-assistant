"""Simple async pub/sub event bus"""

from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, List
import asyncio

Subscriber = Callable[[Dict[str, Any]], Awaitable[None]]

class Bus:
    def __init__(self):
        self._subs: Dict[str, List[Subscriber]] = defaultdict(list)
    
    def subscribe(self, topic: str, fn: callable):
        self._subs[topic].append(fn)

    async def publish(self, topic, payload):
        for fn in self._subs.get(topic, []):
            asyncio.create_task(fn(payload))

    def clear(self):
        self._subs.clear()