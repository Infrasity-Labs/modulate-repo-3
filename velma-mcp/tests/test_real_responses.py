"""Replay responses captured from the live API (see tests/data/real/README.txt).

These catch shape drift that the spec-derived data in the other tests cannot:
real field values, real null handling, and the real multipart framing of the
redaction reply.
"""

import json

import pytest
import respx

from velma_mcp import server
from conftest import BASE, DATA

REAL = DATA / "real"


def real(name: str):
    return json.loads((REAL / name).read_text())


@pytest.fixture
def api():
    with respx.mock(assert_all_called=False) as router:
        yield router


async def test_real_synthetic_clip_summary(api, audio):
    api.post(BASE + "/api/velma-2-synthetic-voice-detection-batch").respond(
        200, json=real("svd_synthetic.json")
    )
    out = await server.detect_synthetic_voice("clip.wav")
    s = out["summary"]
    assert s["frame_counts"] == {"synthetic": 3, "non-synthetic": 0, "no-content": 0}
    assert s["synthetic_share_of_non_silent_frames"] == 1.0
    assert s["majority_verdict"] == "synthetic"
    assert out["duration_ms"] == 9334


async def test_real_human_clip_summary(api, audio):
    api.post(BASE + "/api/velma-2-synthetic-voice-detection-batch").respond(
        200, json=real("svd_real.json")
    )
    s = (await server.detect_synthetic_voice("clip.wav"))["summary"]
    assert s["synthetic_share_of_non_silent_frames"] == 0.0
    assert s["majority_verdict"] == "non-synthetic"


async def test_real_music_replies_pass_through(api, audio):
    route = api.post(BASE + "/api/velma-2-ai-music-detection-batch")
    route.respond(200, json=real("music_ai_vocal.json"))
    out = await server.detect_ai_music("clip.wav")
    assert out["primary_verdict"] == "ai-vocal-music"
    assert out["vocal_ai_percentage"] == 97.2
    route.respond(200, json=real("music_not_ai.json"))
    out = await server.detect_ai_music("clip.wav")
    assert out["primary_verdict"] == "not-ai-music"
    assert out["windows"] == real("music_not_ai.json")["windows"]


async def test_real_transcript_keeps_pii_tags_and_signals(api, audio):
    api.post(BASE + "/api/velma-2-stt-batch").respond(200, json=real("stt_pii.json"))
    out = await server.transcribe_audio(
        "clip.wav", emotion_signal=True, accent_signal=True,
        deepfake_signal=True, pii_phi_tagging=True,
    )  # fmt: skip
    first = out["utterances"][0]
    assert "<pii:firstname>Jonathan</pii:firstname>" in first["text"]
    assert (first["emotion"], first["accent"]) == ("Neutral", "American")
    assert 0 <= first["deepfake_score"] <= 1


async def test_real_triage_summary(api, audio):
    api.post(BASE + "/api/velma-2-batch").respond(200, json=real("triage_default.json"))
    out = await server.analyze_conversation("clip.wav")
    raw = real("triage_default.json")
    assert out["summary"] == raw["summary"]
    assert out["topics"] == raw["topics"]
    assert out["behaviors_detected_count"] == 1
    assert out["raw"] == raw


async def test_real_redaction_multipart_is_split_correctly(api, audio, env):
    ctype = (REAL / "redaction_content_type.txt").read_text().strip()
    body = (REAL / "redaction_multipart.bin").read_bytes()
    api.post(BASE + "/api/velma-2-pii-phi-redaction-batch").respond(
        200, content=body, headers={"content-type": ctype}
    )
    out = await server.redact_audio("clip.wav")
    assert "<pii:phone></pii:phone>" in out["text"]
    assert out["redaction_ranges"] == [[1180, 2940], [3660, 8640], [9680, 12960]]
    saved = list((env / "velma-output").glob("clip-redacted-*.mp3"))
    assert len(saved) == 1
    mp3 = saved[0].read_bytes()
    assert mp3.startswith(b"ID3") and len(mp3) == 1500
