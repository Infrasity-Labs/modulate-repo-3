"""Environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp.exceptions import ToolError

OUTPUT_MODES = ("files", "resources", "both")
DEFAULT_BASE_URL = "https://platform.modulate.ai"


@dataclass(frozen=True)
class Settings:
    base_path: Path
    output_mode: str
    api_base_url: str


def load_settings() -> Settings:
    mode = (os.environ.get("VELMA_MCP_OUTPUT_MODE") or "files").strip().lower()
    if mode not in OUTPUT_MODES:
        raise ToolError(
            f"Invalid VELMA_MCP_OUTPUT_MODE '{mode}'. Use one of: {', '.join(OUTPUT_MODES)}."
        )
    base = os.environ.get("VELMA_MCP_BASE_PATH") or "~/Desktop"
    url = (os.environ.get("VELMA_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return Settings(Path(base).expanduser().resolve(), mode, url)


def get_api_key() -> str:
    key = (os.environ.get("VELMA_API_KEY") or "").strip()
    if not key:
        raise ToolError(
            "VELMA_API_KEY is not set. Add it to the env block of your MCP client config."
        )
    return key
