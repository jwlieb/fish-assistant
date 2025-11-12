import pytest
from assistant.core.nlu.rules import RulesNLU

pytestmark = pytest.mark.asyncio

@pytest.fixture
def nlu():
    return RulesNLU()

async def test_joke_intent(nlu):
    result = await nlu.classify("tell me a joke")
    assert result.intent == "joke"
    assert result.confidence == 0.9
    assert result.original_text == "tell me a joke"
    assert result.entities == {}

async def test_joke_variations(nlu):
    test_cases = [
        "make me laugh",
        "I want a funny story",
        "joke please",
    ]
    for text in test_cases:
        result = await nlu.classify(text)
        assert result.intent == "joke", f"Failed for: {text}"

async def test_time_intent(nlu):
    result = await nlu.classify("what's the time")
    assert result.intent == "time"
    assert result.confidence == 0.8
    assert result.entities == {}

async def test_time_variations(nlu):
    test_cases = [
        "what is the time",
        "time",
        "time in new york",
    ]
    for text in test_cases:
        result = await nlu.classify(text)
        assert result.intent == "time", f"Failed for: {text}"

async def test_timer_intent_with_duration(nlu):
    result = await nlu.classify("set a timer for 5 minutes")
    assert result.intent == "timer"
    assert result.confidence == 0.85
    assert "duration" in result.entities
    assert result.entities["duration"]["seconds"] == 300

async def test_timer_duration_parsing(nlu):
    test_cases = [
        ("timer for 30 seconds", 30),
        ("set timer for 2 hours", 7200),
        ("alarm in 10 min", 600),
        ("start timer in 1 hour 30 minutes", 5400),
    ]
    for text, expected_seconds in test_cases:
        result = await nlu.classify(text)
        assert result.intent == "timer", f"Failed for: {text}"
        assert result.entities["duration"]["seconds"] == expected_seconds, f"Failed for: {text}"

async def test_timer_intent_without_duration(nlu):
    result = await nlu.classify("set a timer")
    assert result.intent == "timer"
    assert result.confidence == 0.6  # lower confidence without duration
    assert "duration" not in result.entities

async def test_weather_intent(nlu):
    result = await nlu.classify("what's the weather")
    assert result.intent == "weather"
    assert result.confidence == 0.8
    assert result.entities == {}

async def test_weather_variations(nlu):
    test_cases = [
        "temperature",
        "forecast for tomorrow",
        "weather today",
    ]
    for text in test_cases:
        result = await nlu.classify(text)
        assert result.intent == "weather", f"Failed for: {text}"

async def test_music_intent(nlu):
    result = await nlu.classify("play music")
    assert result.intent == "music"
    assert result.confidence == 0.7
    assert result.entities == {}

async def test_music_variations(nlu):
    test_cases = [
        "play a song",
        "music please",
        "playlist",
    ]
    for text in test_cases:
        result = await nlu.classify(text)
        assert result.intent == "music", f"Failed for: {text}"

async def test_smalltalk_intent(nlu):
    result = await nlu.classify("hello")
    assert result.intent == "smalltalk"
    assert result.confidence == 0.5
    assert result.entities == {}

async def test_smalltalk_variations(nlu):
    test_cases = [
        "hi there",
        "hey fish",
        "thanks",
        "bye",
    ]
    for text in test_cases:
        result = await nlu.classify(text)
        assert result.intent == "smalltalk", f"Failed for: {text}"

async def test_unknown_intent(nlu):
    result = await nlu.classify("random gibberish text")
    assert result.intent == "unknown"
    assert result.confidence == 0.1
    assert result.entities == {}

async def test_intent_priority_order(nlu):
    # Joke should match before other patterns
    result = await nlu.classify("tell me a joke about the weather")
    assert result.intent == "joke"  # joke pattern matches first
    
    # Timer should match before time
    result = await nlu.classify("set timer for 5 minutes")
    assert result.intent == "timer"

async def test_original_text_preserved(nlu):
    text = "  set timer for 10 seconds  "
    result = await nlu.classify(text)
    assert result.original_text == text.strip()

async def test_empty_text(nlu):
    result = await nlu.classify("")
    assert result.intent == "unknown"
    assert result.confidence == 0.1

async def test_whitespace_handling(nlu):
    result = await nlu.classify("   what's the time   ")
    assert result.intent == "time"
    assert result.original_text == "what's the time"

