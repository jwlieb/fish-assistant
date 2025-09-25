import asyncio
import pytest
from assistant.core.bus import Bus

@pytest.mark.asyncio
async def test_publish_subscribe():
    bus = Bus()
    got = []

    async def handler(evt):
        got.append(evt["x"])

    bus.subscribe("demo", handler)
    await bus.publish("demo", {"x": 1})
    await asyncio.sleep(0.01)
    assert got == [1]