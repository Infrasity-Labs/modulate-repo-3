"""Velma MCP server: five tools over stdio."""

from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from .client import json_body, parse_redaction_response, post_upload
from .config import load_settings
from .paths import SPEECH_EXTENSIONS, WIDE_EXTENSIONS, resolve_input

mcp = FastMCP("velma")

LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,3}([-_][A-Za-z0-9]+)*$")  # from the OpenAPI spec
MAX_RESOURCES = 10

_redacted: OrderedDict[str, bytes] = OrderedDict()


def _form(**fields: bool | str | None) -> dict[str, str]:
    """Keep only the fields the caller set. Booleans go as 'true' or 'false'."""
    out: dict[str, str] = {}
    for name, value in fields.items():
        if value is None:
            continue
        out[name] = ("true" if value else "false") if isinstance(value, bool) else value
    return out


def _check_language(language: str | None) -> None:
    if language is not None and not LANGUAGE_PATTERN.match(language):
        raise ToolError(
            f"Invalid language '{language}'. Use an ISO 639-1 code such as 'en' or 'fr' "
            "(a region suffix like 'en-US' is accepted)."
        )


@mcp.tool()
async def detect_synthetic_voice(file_path: str) -> dict[str, Any]:
    """Check one audio file for AI-generated (synthetic) speech, frame by frame.

    The result is a probability signal, not proof. The audio is uploaded to
    Modulate's Velma API. Works best on single-speaker clips of 4-60 seconds;
    clips under 0.5 seconds are rejected. Max 100 MB.

    file_path: path to the audio file, relative to VELMA_MCP_BASE_PATH or absolute
    inside it.
    """
    path = resolve_input(file_path, load_settings().base_path, WIDE_EXTENSIONS)
    response = await post_upload(
        "detect_synthetic_voice", "/api/velma-2-synthetic-voice-detection-batch", path
    )
    data = json_body(response)
    frames = data.get("frames") or []
    counts = {"synthetic": 0, "non-synthetic": 0, "no-content": 0}
    conf: dict[str, list[float]] = {"synthetic": [], "non-synthetic": []}
    for frame in frames:
        verdict = frame.get("verdict")
        if verdict in counts:
            counts[verdict] += 1
        if verdict in conf and isinstance(frame.get("confidence"), (int, float)):
            conf[verdict].append(float(frame["confidence"]))
    syn, non = counts["synthetic"], counts["non-synthetic"]
    if syn > non:
        majority = "synthetic"
    elif non > syn:
        majority = "non-synthetic"
    else:
        majority = "tie" if syn else None

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    return {
        "filename": data.get("filename"),
        "duration_ms": data.get("duration_ms"),
        "summary": {
            "duration_ms": data.get("duration_ms"),
            "frame_counts": counts,
            "synthetic_share_of_non_silent_frames": round(syn / (syn + non), 4) if syn + non else None,
            "mean_confidence_synthetic_frames": mean(conf["synthetic"]),
            "mean_confidence_non_synthetic_frames": mean(conf["non-synthetic"]),
            "majority_verdict": majority,
            "note": (
                "This is a probability signal from a model, not proof. "
                "majority_verdict counts frames that are not no-content; 'tie' means equal counts. "
                "Weigh it with other evidence."
            ),
        },
        "frames": frames,
    }


@mcp.tool()
async def detect_ai_music(file_path: str) -> dict[str, Any]:
    """Check one audio file for AI-generated music (vocals and instrumentals).

    The result is a probability signal, not proof. The audio is uploaded to
    Modulate's Velma API. Max 100 MB.

    file_path: path to the audio file, relative to VELMA_MCP_BASE_PATH or absolute
    inside it.
    """
    path = resolve_input(file_path, load_settings().base_path, WIDE_EXTENSIONS)
    response = await post_upload(
        "detect_ai_music", "/api/velma-2-ai-music-detection-batch", path
    )
    data = json_body(response)
    keys = (
        "filename", "duration_s", "primary_verdict", "vocal_percentage",
        "vocal_ai_percentage", "vocal_ai_confidence", "instrumental_percentage",
        "instrumental_ai_percentage", "instrumental_ai_confidence",
        "silence_percentage", "latency_ms",
    )  # fmt: skip
    out = {k: data.get(k) for k in keys}
    out["windows"] = data.get("windows") or []
    out["note"] = "This is a probability signal from a model, not proof."
    return out


def _save_audio_file(audio: bytes, source: Path, base_path: Path) -> Path:
    out_dir = base_path / "velma-output"
    out_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(5):
        target = out_dir / f"{source.stem}-redacted-{uuid.uuid4().hex[:8]}.mp3"
        try:
            with target.open("xb") as fh:  # "x" never overwrites
                fh.write(audio)
            return target
        except FileExistsError:
            continue
    raise ToolError("Could not pick a free output file name. Try again.")


def _store_audio(audio: bytes) -> str:
    rid = uuid.uuid4().hex
    _redacted[rid] = audio
    while len(_redacted) > MAX_RESOURCES:
        _redacted.popitem(last=False)
    return f"velma://redacted/{rid}"


@mcp.resource("velma://redacted/{id}", mime_type="audio/mpeg")
def redacted_audio(id: str) -> bytes:
    """Redacted MP3 produced by redact_audio (the last 10 are kept in memory)."""
    if id not in _redacted:
        raise ValueError("Unknown or expired redacted audio id.")
    return _redacted[id]


@mcp.tool()
async def redact_audio(
    file_path: str,
    language: str | None = None,
    speaker_diarization: bool | None = None,
) -> dict[str, Any]:
    """Transcribe an audio file and silence PII/PHI (names, numbers, health data) in text and audio.

    The audio is uploaded to Modulate's Velma API. Detection is automated and can
    miss items: always spot-check the redacted transcript and audio before sharing.
    Allowed formats: aac, aiff, flac, mov, mp3, mp4, ogg, opus, wav, webm. Max 100 MB.
    The redacted MP3 is saved under <VELMA_MCP_BASE_PATH>/velma-output/, or served as an MCP
    resource, or both, depending on VELMA_MCP_OUTPUT_MODE.

    file_path: path to the audio file, relative to VELMA_MCP_BASE_PATH or absolute inside it.
    language: optional ISO 639-1 hint such as 'en'. Omit to auto-detect.
    speaker_diarization: label speakers (API default is true). Omit to use the default.
    """
    settings = load_settings()
    _check_language(language)
    path = resolve_input(file_path, settings.base_path, SPEECH_EXTENSIONS)
    response = await post_upload(
        "redact_audio",
        "/api/velma-2-pii-phi-redaction-batch",
        path,
        _form(language=language, speaker_diarization=speaker_diarization),
    )
    metadata, audio = parse_redaction_response(response)
    out: dict[str, Any] = {
        "text": metadata.get("text"),
        "duration_ms": metadata.get("duration_ms"),
        "utterances": metadata.get("utterances") or [],
        "redaction_ranges": metadata.get("redaction_ranges") or [],
    }
    if settings.output_mode in ("files", "both"):
        out["redacted_audio_path"] = str(_save_audio_file(audio, path, settings.base_path))
    if settings.output_mode in ("resources", "both"):
        out["redacted_audio_resource"] = _store_audio(audio)
    out["note"] = (
        "Automated redaction can miss items. Spot-check the text and listen to the "
        "redacted audio before sharing it."
    )
    return out


@mcp.tool()
async def transcribe_audio(
    file_path: str,
    speaker_diarization: bool | None = None,
    emotion_signal: bool | None = None,
    accent_signal: bool | None = None,
    deepfake_signal: bool | None = None,
    pii_phi_tagging: bool | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Transcribe an audio file with Velma speech-to-text.

    The audio is uploaded to Modulate's Velma API. Optional per-utterance signals
    (emotion, accent, deepfake_score) are probability signals, not proof.
    Allowed formats: aac, aiff, flac, mp3, mp4, mov, ogg, opus, wav, webm. Max 100 MB.
    Options left unset use the API defaults.

    file_path: path to the audio file, relative to VELMA_MCP_BASE_PATH or absolute inside it.
    speaker_diarization: label speakers (API default true).
    emotion_signal: add an emotion label per utterance.
    accent_signal: add an accent label per utterance.
    deepfake_signal: add a deepfake_score (0 natural to 1 synthetic) per utterance.
    pii_phi_tagging: wrap PII/PHI in tags inside the text.
    language: optional ISO 639-1 hint such as 'en'. Omit to auto-detect.
    """
    _check_language(language)
    path = resolve_input(file_path, load_settings().base_path, SPEECH_EXTENSIONS)
    response = await post_upload(
        "transcribe_audio",
        "/api/velma-2-stt-batch",
        path,
        _form(
            speaker_diarization=speaker_diarization,
            emotion_signal=emotion_signal,
            accent_signal=accent_signal,
            deepfake_signal=deepfake_signal,
            pii_phi_tagging=pii_phi_tagging,
            language=language,
        ),
    )
    data = json_body(response)
    return {
        "text": data.get("text"),
        "duration_ms": data.get("duration_ms"),
        "utterances": data.get("utterances") or [],
    }


@mcp.tool()
async def analyze_conversation(file_path: str, config: str | None = None) -> dict[str, Any]:
    """Analyze a recorded conversation with Velma Triage: summary, topics, conversation type, behaviors.

    The audio is uploaded to Modulate's Velma API. Behavior and type picks are model
    judgments, not proof. Allowed formats: aac, aiff, flac, mp3, mp4, mov, ogg, opus, wav, webm.
    Max 100 MB. Returns a compact summary plus the full API response under 'raw'.

    file_path: path to the audio file, relative to VELMA_MCP_BASE_PATH or absolute inside it.
    config: 'default' (also used when omitted) or a JSON object string with a Velma Triage config.
    """
    path = resolve_input(file_path, load_settings().base_path, SPEECH_EXTENSIONS)
    if config is not None and config != "default":
        try:
            parsed = json.loads(config)
        except ValueError:
            raise ToolError("config must be 'default' or a valid JSON object string.") from None
        if not isinstance(parsed, dict):
            raise ToolError("config must be 'default' or a JSON object string.")
    response = await post_upload(
        "analyze_conversation", "/api/velma-2-batch", path, _form(config=config)
    )
    data = json_body(response)
    pick = data.get("conversation_type_pick") or {}
    behaviors = data.get("behaviors") or []
    return {
        "summary": data.get("summary"),
        "topics": data.get("topics") or [],
        "conversation_type": {"name": pick.get("name"), "confidence": pick.get("confidence")}
        if pick
        else None,
        "behaviors_count": len(behaviors),
        "behaviors_detected_count": sum(1 for b in behaviors if b.get("detected")),
        "duration_ms": data.get("duration_ms"),
        "model_version": data.get("model_version"),
        "raw": data,
    }


def main() -> None:
    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="velma-mcp %(levelname)s %(message)s"
    )
    for noisy in ("httpx", "mcp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        load_settings()
    except ToolError as exc:
        print(f"velma-mcp: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    mcp.run()


if __name__ == "__main__":
    main()
