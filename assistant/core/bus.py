"""Simple async pub/sub event bus"""

from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, List
import asyncio
import logging

Subscriber = Callable[[Dict[str, Any]], Awaitable[None]]

class Bus:
    def __init__(self):
        self._subs: Dict[str, List[Subscriber]] = defaultdict(list)
        self._log = logging.getLogger("bus")
    
    def subscribe(self, topic: str, fn: callable):
        self._subs[topic].append(fn)
        subscriber_name = getattr(fn, "__name__", str(fn))
        self._log.info("subscribe: %s -> %s (total subscribers: %d)", topic, subscriber_name, len(self._subs[topic]))

    async def publish(self, topic, payload):
        subscribers = self._subs.get(topic, [])
        self._log.info("publish: %s -> %d subscribers %s", topic, len(subscribers), list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
        if not subscribers:
            self._log.warning("publish: No subscribers for topic %s", topic)
        tasks = []
        for fn in subscribers:
            try:
                self._log.debug("publish: Scheduling subscriber %s for topic %s", getattr(fn, "__name__", str(fn)), topic)
                tasks.append(asyncio.create_task(fn(payload)))
            except Exception as e:
                self._log.exception("error scheduling subscriber for %s: %s", topic, e)
                
        # Wait briefly for all direct subscribers to START their work
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._log.error("publish: Subscriber %d raised exception: %s", i, result, exc_info=result) 

    def clear(self):
        self._subs.clear()