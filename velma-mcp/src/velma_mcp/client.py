"""HTTP client for the Velma batch API, with error mapping."""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from email.message import Message
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp.exceptions import ToolError
from python_multipart.multipart import MultipartParser

from .config import get_api_key, load_settings

log = logging.getLogger("velma_mcp")

MAX_CONCURRENCY = 3  # Default per-model concurrency from the docs.
TIMEOUT = httpx.Timeout(connect=15.0, read=300.0, write=300.0, pool=60.0)

_semaphore: asyncio.Semaphore | None = None
_semaphore_loop: asyncio.AbstractEventLoop | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore, _semaphore_loop
    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore_loop is not loop:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        _semaphore_loop = loop
    return _semaphore


def scrub(text: str, key: str) -> str:
    return text.replace(key, "***") if key else text


def _detail_text(response: httpx.Response) -> str:
    """Return the `detail` of an error body as text. It can be a string or a list."""
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:300]
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail.strip()
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(p) for p in item.get("loc", []))
                msg = str(item.get("msg", ""))
                parts.append(f"{loc}: {msg}" if loc else msg)
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return response.text.strip()[:300]


def error_message(status: int, detail: str) -> str:
    """Build a short readable message for an HTTP error status."""
    d = detail.rstrip(".") or "no detail given"
    low = detail.lower()
    if status == 429:
        if "concurrent" in low:
            return (
                f"Velma is busy (429): {d}. Wait a moment for running requests to finish, "
                "then try again."
            )
        if "insufficient credits" in low:
            return f"Velma account is out of credits (429): {d}. Do not retry. Add credits first."
        if "monthly" in low:
            return (
                f"Velma monthly usage limit reached (429): {d}. Do not retry "
                "until the limit resets or is raised."
            )
        return f"Velma refused the request (429): {d}."
    if status == 401:
        return f"Velma rejected the API key (401): {d}. Check VELMA_API_KEY."
    if status == 403:
        return (
            f"Velma refused the request (403): {d}. "
            "The key may not have access to this model."
        )
    if status == 400:
        return f"Velma rejected the request (400): {d}."
    if status == 413:
        return f"The file is too large for Velma (413): {d}. The limit is 100 MB."
    if status == 422:
        return f"Velma could not process the input (422): {d}."
    if status == 504:
        return f"Velma timed out (504): {d}. Try again, or use a shorter file."
    if status in (500, 502):
        return f"Velma server error ({status}): {d}. Try again later."
    return f"Unexpected response from Velma ({status}): {d}."


async def post_upload(
    tool: str,
    endpoint: str,
    file: Path,
    fields: dict[str, str] | None = None,
) -> httpx.Response:
    """POST a file as `upload_file` plus string form fields. Return a 200 response."""
    key = get_api_key()
    url = load_settings().api_base_url + endpoint
    mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    try:
        async with _get_semaphore():
            async with httpx.AsyncClient(timeout=TIMEOUT) as http:
                with file.open("rb") as fh:
                    response = await http.post(
                        url,
                        headers={"X-API-Key": key},
                        data=fields or {},
                        files={"upload_file": (file.name, fh, mime)},
                    )
    except httpx.TimeoutException:
        log.warning("tool=%s timeout", tool)
        raise ToolError(
            "The request to Velma timed out. The file may be long. "
            "Try a shorter file or try again."
        ) from None
    except httpx.TransportError as exc:
        log.warning("tool=%s transport_error=%s", tool, type(exc).__name__)
        raise ToolError(
            f"Could not reach Velma ({type(exc).__name__}). Check your network and VELMA_API_BASE_URL."
        ) from None
    except OSError as exc:
        raise ToolError(f"Could not read the file ({type(exc).__name__}).") from None
    log.info("tool=%s status=%s", tool, response.status_code)
    if response.status_code != 200:
        msg = error_message(response.status_code, _detail_text(response))
        raise ToolError(scrub(msg, key))
    return response


def json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        raise ToolError("Velma returned a response that is not valid JSON.") from None
    if not isinstance(body, dict):
        raise ToolError("Velma returned an unexpected JSON shape.")
    return body


def parse_redaction_response(response: httpx.Response) -> tuple[dict[str, Any], bytes]:
    """Split the multipart 200 response into (metadata, mp3 bytes)."""
    header = Message()
    header["content-type"] = response.headers.get("content-type", "")
    boundary = header.get_boundary()
    if not boundary:
        raise ToolError("Velma redaction response had no multipart boundary.")

    parts: list[tuple[str | None, bytearray]] = []
    state: dict[str, Any] = {"field": b"", "value": b"", "headers": {}}

    def on_part_begin() -> None:
        state["headers"] = {}
        parts.append((None, bytearray()))

    def on_header_field(data: bytes, start: int, end: int) -> None:
        state["field"] += data[start:end]

    def on_header_value(data: bytes, start: int, end: int) -> None:
        state["value"] += data[start:end]

    def on_header_end() -> None:
        name = state["field"].decode("latin-1").strip().lower()
        state["headers"][name] = state["value"].decode("latin-1")
        state["field"] = b""
        state["value"] = b""

    def on_headers_finished() -> None:
        disposition = Message()
        disposition["content-disposition"] = state["headers"].get("content-disposition", "")
        name = disposition.get_param("name", header="content-disposition")
        parts[-1] = (str(name).lower() if name else None, parts[-1][1])

    def on_part_data(data: bytes, start: int, end: int) -> None:
        parts[-1][1].extend(data[start:end])

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
        },
    )
    try:
        parser.write(response.content)
        parser.finalize()
    except Exception:
        raise ToolError("Velma redaction response could not be parsed as multipart.") from None

    by_name = {name: bytes(data) for name, data in parts if name}
    if "metadata" not in by_name:
        raise ToolError("Velma redaction response is missing the 'metadata' part.")
    if "audio" not in by_name:
        raise ToolError("Velma redaction response is missing the 'audio' part.")
    try:
        metadata = json.loads(by_name["metadata"])
    except ValueError:
        raise ToolError("Velma redaction 'metadata' part is not valid JSON.") from None
    if not isinstance(metadata, dict):
        raise ToolError("Velma redaction 'metadata' part has an unexpected shape.")
    return metadata, by_name["audio"]
