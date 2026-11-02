"""Live checks against Modulate's API. Skipped unless VELMA_API_KEY is set in the environment.

Reads fixtures from ../fixtures or fixtures/. Asserts structure only.
"""

import os
from pathlib import Path

import pytest

from velma_mcp import server

pytestmark = pytest.mark.skipif(
    not os.environ.get("VELMA_API_KEY"), reason="VELMA_API_KEY is not set"
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = next((p for p in (ROOT.parent / "fixtures", ROOT / "fixtures") if p.is_dir()), None)


@pytest.fixture(autouse=True)
def fixtures_dir(monkeypatch):
    if FIXTURES is None:
        pytest.skip("no fixtures folder found")
    monkeypatch.setenv("VELMA_MCP_BASE_PATH", str(FIXTURES))
    monkeypatch.setenv("VELMA_MCP_OUTPUT_MODE", "files")
    return FIXTURES


def need(name):
    if not (FIXTURES / name).is_file():
        pytest.skip(f"fixture {name} missing")
    return name


@pytest.mark.parametrize("name", ["synthetic-1.wav", "real-1.wav"])
async def test_live_synthetic(name):
    out = await server.detect_synthetic_voice(need(name))
    assert {"summary", "frames", "filename", "duration_ms"} <= out.keys()
    assert out["frames"]
    assert all(f["verdict"] in {"synthetic", "non-synthetic", "no-content"} for f in out["frames"])
    assert out["summary"]["majority_verdict"] in {"synthetic", "non-synthetic", "tie", None}


async def test_live_music():
    out = await server.detect_ai_music(need("music-1.wav"))
    assert out["primary_verdict"] in {"ai-vocal-music", "ai-instrumental", "not-ai-music"}
    assert {"duration_s", "latency_ms", "windows"} <= out.keys()


async def test_live_transcribe():
    out = await server.transcribe_audio(need("pii-speech.wav"))
    assert {"text", "duration_ms", "utterances"} <= out.keys()


async def test_live_redact():
    out = await server.redact_audio(need("pii-speech.wav"))
    assert {"text", "utterances", "redaction_ranges", "duration_ms"} <= out.keys()
    saved = Path(out["redacted_audio_path"])
    assert saved.is_file() and saved.stat().st_size > 0
    saved.unlink()


async def test_live_analyze_conversation():
    out = await server.analyze_conversation(need("pii-speech.wav"))
    assert {"summary", "topics", "behaviors_count", "raw"} <= out.keys()
    assert "clips" in out["raw"]
