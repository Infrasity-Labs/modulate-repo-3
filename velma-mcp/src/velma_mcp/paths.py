"""Input file sandbox and validation."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp.exceptions import ToolError

MAX_UPLOAD_BYTES = 100 * 1024 * 1024

# Synthetic voice and AI music endpoints (same list in both specs).
WIDE_EXTENSIONS = frozenset(
    [
        ".3g2", ".3ga", ".3gp", ".3gpp", ".8svx", ".aa3", ".aac", ".ac3", ".act", ".adts",
        ".aif", ".aifc", ".aiff", ".alac", ".amb", ".amr", ".ape", ".asf", ".at3", ".au",
        ".avi", ".avr", ".awb", ".bwf", ".c2", ".caf", ".dss", ".dts", ".dtshd", ".eac3",
        ".ec3", ".f4a", ".f4b", ".flac", ".flv", ".gsm", ".iff", ".m2a", ".m2ts", ".m4a",
        ".m4b", ".m4r", ".m4v", ".mka", ".mkv", ".mlp", ".mmf", ".mov", ".mp+", ".mp1",
        ".mp2", ".mp3", ".mp4", ".mpa", ".mpc", ".mpeg", ".mpg", ".mpga", ".mpp", ".mts",
        ".mxf", ".nist", ".oga", ".ogg", ".ogx", ".oma", ".omg", ".opus", ".paf", ".pvf",
        ".qcp", ".ra", ".rf64", ".rka", ".rm", ".rmvb", ".sf", ".shn", ".snd", ".sph",
        ".svx", ".tak", ".thd", ".ts", ".tta", ".vob", ".voc", ".vqf", ".w64", ".wav",
        ".wave", ".weba", ".webm", ".wma", ".wmv", ".wv",
    ]
)

# STT, redaction and Velma Triage endpoints.
SPEECH_EXTENSIONS = frozenset(
    [".aac", ".aiff", ".flac", ".mov", ".mp3", ".mp4", ".ogg", ".opus", ".wav", ".webm"]
)


def resolve_input(file_path: str, base_path: Path, allowed: frozenset[str]) -> Path:
    """Return the resolved path of a safe, uploadable file or raise ToolError."""
    if not file_path or not file_path.strip():
        raise ToolError("file_path is empty.")
    candidate = Path(file_path).expanduser()
    if not candidate.is_absolute():
        candidate = base_path / candidate
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError):
        raise ToolError("file_path could not be resolved.") from None
    base = base_path.resolve()
    if not resolved.is_relative_to(base):
        raise ToolError(
            f"file_path is outside the allowed folder. Files must be inside {base} "
            "(set VELMA_MCP_BASE_PATH to change it)."
        )
    if not resolved.exists():
        raise ToolError(f"File not found: {resolved}")
    if not resolved.is_file():
        raise ToolError(f"Not a regular file: {resolved}")
    suffix = resolved.suffix.lower()
    if suffix not in allowed:
        raise ToolError(
            f"Unsupported file extension '{suffix}'. Allowed for this tool: "
            + ", ".join(sorted(allowed))
            + "."
        )
    size = resolved.stat().st_size
    if size == 0:
        raise ToolError(f"File is empty: {resolved}")
    if size > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ToolError(f"File is too large ({size} bytes). The maximum is {limit_mb} MB.")
    return resolved
