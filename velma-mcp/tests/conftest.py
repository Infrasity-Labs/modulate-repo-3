import json
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"
KEY = "test-key-SECRET-12345"
BASE = "https://platform.modulate.ai"


def load(name: str):
    data = json.loads((DATA / name).read_text())
    data.pop("_comment", None)
    return data


@pytest.fixture(autouse=True)
def env(request, monkeypatch, tmp_path):
    if request.module.__name__.endswith("test_live"):
        return tmp_path  # live tests use the real environment
    monkeypatch.setenv("VELMA_API_KEY", KEY)
    monkeypatch.setenv("VELMA_MCP_BASE_PATH", str(tmp_path))
    monkeypatch.delenv("VELMA_MCP_OUTPUT_MODE", raising=False)
    monkeypatch.delenv("VELMA_API_BASE_URL", raising=False)
    return tmp_path


@pytest.fixture
def audio(tmp_path):
    p = tmp_path / "clip.wav"
    p.write_bytes(b"RIFF0000WAVEfmt fake audio")
    return p


def multipart_body(metadata: dict, mp3: bytes, boundary: str = "velmaBOUNDARY42"):
    crlf = b"\r\n"
    body = (
        b"--" + boundary.encode() + crlf
        + b'Content-Disposition: form-data; name="metadata"' + crlf
        + b"Content-Type: application/json" + crlf + crlf
        + json.dumps(metadata).encode() + crlf
        + b"--" + boundary.encode() + crlf
        + b'Content-Disposition: form-data; name="audio"; filename="redacted.mp3"' + crlf
        + b"Content-Type: audio/mpeg" + crlf + crlf
        + mp3 + crlf
        + b"--" + boundary.encode() + b"--" + crlf
    )
    return body, f"multipart/form-data; boundary={boundary}"


# Binary on purpose: NULs, CRLF, and a boundary-like string inside the payload.
MP3 = b"ID3\x00\x01\r\n--not-the-boundary\r\n\xff\xfb\x90\x00" + bytes(range(256)) + b"\r\n"
