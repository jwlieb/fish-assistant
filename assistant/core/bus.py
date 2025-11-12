"""Simple async pub/sub event bus"""

from collections import defaultdict
from typing import Any, Awaitable, Callable
import asyncio
import logging

Subscriber = Callable[[dict[str, Any]], Awaitable[None]]

class Bus:
    def __init__(self):
        self._subs: dict[str, list[Subscriber]] = defaultdict(list)
        self._log = logging.getLogger("bus")
    
    def subscribe(self, topic: str, fn: callable):
        self._subs[topic].append(fn)
        self._log.debug("subscribe: %s -> %s", topic, getattr(fn, "__name__", str(fn)))

    async def publish(self, topic, payload):
        self._log.info("publish: %s %s", topic, list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
        tasks = []
        for fn in self._subs.get(topic, []):
            try:
                tasks.append(asyncio.create_task(fn(payload)))
            except Exception as e:
                self._log.exception("error scheduling subscriber for %s: %s", topic, e)
                
        # Wait briefly for all direct subscribers to START their work
        await asyncio.gather(*tasks, return_exceptions=True) 

    def clear(self):
        self._subs.clear()