# Changelog

## 0.1.0

First release. Both projects share this version.

velma-detect-skill
- One skill covering deepfake detection, AI music detection, PII/PHI redaction, transcription and conversation analysis with `curl`.
- References for each endpoint, plus errors and limits.
- `scripts/split_redaction.py` to split the multipart redaction reply.
- 12 trigger prompts (8 should load the skill, 4 should not) and a Claude Code runner.

velma-mcp
- Five tools: `detect_synthetic_voice`, `detect_ai_music`, `redact_audio`, `transcribe_audio`, `analyze_conversation`.
- Input files limited to `VELMA_MCP_BASE_PATH`. Path escapes and symlink escapes are rejected.
- Redacted audio saved as a file, served as an MCP resource, or both (`VELMA_MCP_OUTPUT_MODE`).
- HTTP errors mapped to short messages. The API key is never included in errors or logs.

Both: batch endpoints only. Streaming is not covered yet.
