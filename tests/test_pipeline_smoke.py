import asyncio
import pytest

from assistant.core.bus import Bus
from assistant.core.router import Router
from assistant.core.nlu.nlu import NLU
from assistant.core.contracts import (
    STTTranscript,
    NLUIntent,
    SkillRequest,
    SkillResponse,
    TTSRequest,
    PlaybackStart,
    PlaybackEnd,
)

pytestmark = pytest.mark.asyncio

async def test_pipeline_smoke():
    bus = Bus()
    router = Router(bus)  # subscribes to nlu.intent and skill.response
    router.register_intent("unknown", "echo")  # route unknown intents to echo skill
    nlu = NLU(bus)
    await nlu.start()  # subscribe to stt.transcript

    # capture published events
    captures = []  # list[tuple[str, dict]]

    async def capture(topic):
        async def _fn(payload):
            captures.append((topic, payload))
        return _fn

    # Subscribe to topics we want to observe
    bus.subscribe("nlu.intent", await capture("nlu.intent"))
    bus.subscribe("skill.request", await capture("skill.request"))
    bus.subscribe("tts.request", await capture("tts.request"))
    bus.subscribe("audio.playback.start", await capture("audio.playback.start"))
    bus.subscribe("audio.playback.end", await capture("audio.playback.end"))

    # echo skill: replies with say="You said: <text>" 
    async def echo_skill(payload: dict):
        req = SkillRequest(**payload)  # light validation
        said = req.payload.get("original_text", "").strip()
        resp = SkillResponse(skill=req.skill, say=f"You said: {said}")
        # keep the same trace/correlation id
        resp.corr_id = req.corr_id
        await bus.publish(resp.topic, resp.dict())

    bus.subscribe("skill.request", echo_skill)

    # TTS + playback: turns TTSRequest into playback start/end quickly 
    async def fake_tts_and_playback(payload: dict):
        tts = TTSRequest(**payload)
        start = PlaybackStart(wav_path="in-memory://dummy.wav")
        start.corr_id = tts.corr_id
        end = PlaybackEnd(wav_path=start.wav_path, ok=True)
        end.corr_id = tts.corr_id

        await bus.publish(start.topic, start.dict())
        # tiny delay to simulate playback time
        await asyncio.sleep(0.001)
        await bus.publish(end.topic, end.dict())

    bus.subscribe("tts.request", fake_tts_and_playback)

    # kick off the pipeline with stt.transcript (full pipeline test)
    stt_event = STTTranscript(text="hello fish")
    await bus.publish(stt_event.topic, stt_event.dict())

    # wait for the expected sequence 
    expected_topics = [
        "nlu.intent",
        "skill.request",
        "tts.request",
        "audio.playback.start",
        "audio.playback.end",
    ]

    await _wait_for_topics(captures, expected_topics, timeout=1.0)

    # Assert order
    got_topics = [t for (t, _) in captures[: len(expected_topics)]]
    assert got_topics == expected_topics

    # Assert corr_id consistency end-to-end
    corr_ids = [payload["corr_id"] for (_, payload) in captures[: len(expected_topics)]]
    assert all(c == corr_ids[0] for c in corr_ids), "corr_id should propagate across the chain"

    # Assert NLU classified correctly
    nlu_payload = captures[0][1]
    assert nlu_payload["intent"] == "smalltalk" or nlu_payload["intent"] == "unknown"
    assert nlu_payload["original_text"] == "hello fish"

    # (Optional) print a human-friendly path for the test log
    path_str = " → ".join(got_topics)
    print(f"pipeline path: {path_str}")


# helpers

async def _wait_for_topics(captures, expected_topics, timeout=1.0):
    """Poll until we see at least the expected number of captured events in order."""
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        if len(captures) >= len(expected_topics):
            # Check ordering of just the first N we care about.
            got = [t for (t, _) in captures[: len(expected_topics)]]
            if got == expected_topics:
                return
        await asyncio.sleep(0.001)
    raise AssertionError(f"did not observe expected topics in time; got {[t for (t, _) in captures]}")
