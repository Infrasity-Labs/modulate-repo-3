![Velma Agent Tools: an agent skill and an MCP server for Modulate's Velma voice AI](./docs/images/banner.png)

# Velma Agent Tools

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-spec%20valid-brightgreen.svg)](https://agentskills.io/specification)
[![MCP](https://img.shields.io/badge/MCP-stdio-black.svg)](https://modelcontextprotocol.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)

Give your AI agent [Modulate's Velma](https://docs.modulate.ai) voice AI. Ask it "is this voice fake?", "is this song AI-made?", "remove personal data from this call" or "transcribe this meeting", and it calls the Velma API for you.

This repo has two ways to do that. Both cover the same five batch endpoints, so pick the one that fits your agent.

Modulate owns the Velma API and its trademarks. This is an independent integration prepared by Infrasity Labs for Modulate.

## Pick one

| | [`velma-detect-skill`](./velma-detect-skill) | [`velma-mcp`](./velma-mcp) |
| - | - | - |
| What it is | An Agent Skill: `SKILL.md` plus references | A local MCP server in Python |
| How the agent calls Velma | Runs `curl` from the skill's instructions | Calls typed tools |
| Runs anything? | No, just instructions | Yes, a local stdio process |
| Works with | Claude Code, Cursor, Gemini CLI and other skill readers | Claude Desktop, Claude Code, Cursor, Windsurf and other MCP clients |
| Needs | `curl` (`jq` and `ffmpeg` optional) | `uv` and Python 3.10+ |
| Guards | Safety rules in the instructions | Files readable only under a base folder, key scrubbed from errors |

You can use both. They do not depend on each other.

## What they do

| Job | Endpoint | MCP tool |
| - | - | - |
| Is this voice fake, cloned or AI-generated? | `POST /api/velma-2-synthetic-voice-detection-batch` | `detect_synthetic_voice` |
| Is this music AI-made? | `POST /api/velma-2-ai-music-detection-batch` | `detect_ai_music` |
| Remove personal data (PII/PHI) from a recording | `POST /api/velma-2-pii-phi-redaction-batch` | `redact_audio` |
| Transcribe a call, with speakers, emotion, accent | `POST /api/velma-2-stt-batch` | `transcribe_audio` |
| Summarise a conversation, find topics and behaviours | `POST /api/velma-2-batch` | `analyze_conversation` |

Streaming (WebSocket) endpoints are not covered yet.

## Quickstart

1. Get a key at https://platform.modulate.ai/signup-request. New accounts get free credits. Then export it, and never commit it:

```bash
export VELMA_API_KEY=your-key-here
```

2. Install the skill, the MCP server, or both:

```bash
# Skill: copy it into your agent's skills folder
cp -R velma-detect-skill .claude/skills/

# MCP server, from this checkout (use `uvx velma-mcp` once it is published)
claude mcp add velma -e VELMA_API_KEY=<your-key> -- uvx --from "$PWD/velma-mcp" velma-mcp
```

Once published, `npx skills add <owner>/velma-agent-tools` installs the skill. Config for Claude Desktop, Cursor and Windsurf is in the [MCP README](./velma-mcp/README.md).

3. Ask your agent, for example:
   - "Is `fixtures/synthetic-1.wav` a deepfake?"
   - "Redact the names and phone numbers from `fixtures/pii-speech.wav`."
   - "Transcribe `call.wav` with speaker labels and emotion."

## See it in action

Four chats with the MCP server, using the clips in `fixtures/`. The numbers, transcripts and tags in each reply come from real runs against the live API. The chat window around them is a mock-up.

<table>
<tr>
<td width="50%"><img src="./docs/images/claude-deepfake-check.png" alt="Chat: Claude calls detect_synthetic_voice on a text-to-speech clip and a human clip and compares the verdicts"><br><sub>Deepfake check: <code>detect_synthetic_voice</code></sub></td>
<td width="50%"><img src="./docs/images/claude-redact-audio.png" alt="Chat: Claude calls redact_audio and shows the transcript with the name, phone number and date of birth removed"><br><sub>Redaction: <code>redact_audio</code></sub></td>
</tr>
<tr>
<td width="50%"><img src="./docs/images/claude-ai-music.png" alt="Chat: Claude calls detect_ai_music on an opera recording and gets not-ai-music"><br><sub>AI music check: <code>detect_ai_music</code></sub></td>
<td width="50%"><img src="./docs/images/claude-transcribe-analyze.png" alt="Chat: Claude calls transcribe_audio and analyze_conversation"><br><sub>Transcribe and summarise: <code>transcribe_audio</code>, <code>analyze_conversation</code></sub></td>
</tr>
</table>

The images are rendered from the HTML in [`docs/images/src/`](./docs/images/src).

## Results on the bundled clips

Run on 2026-11-02 against the live API.

| Clip | Result | Confidence |
| - | - | - |
| `fixtures/synthetic-1.wav` (text-to-speech) | 3 of 3 deepfake frames synthetic | 0.969 to 0.975 |
| `fixtures/real-2.wav` (human reading) | 3 of 3 deepfake frames non-synthetic | 0.912 to 0.922 |
| `fixtures/pii-speech.wav` (made-up name, phone, date of birth) | All three spans tagged and silenced | n/a |

Results are probability signals, not proof. A few short studio-style clips are not a benchmark. Sources and licences for every clip are in [`fixtures/SOURCES.md`](./fixtures/SOURCES.md).

## Repo layout

```text
velma-agent-tools/
  fixtures/            shared test clips and their sources
  velma-detect-skill/  SKILL.md, references/, scripts/, evals/
  velma-mcp/           src/, tests/, pyproject.toml
  .github/workflows/   skill validation and MCP tests
```

## Develop

```bash
skills-ref validate ./velma-detect-skill        # skill format check
./velma-detect-skill/evals/run_trigger_eval.sh  # 12 trigger prompts, needs the claude CLI
cd velma-mcp && uv run pytest                   # live tests run only with VELMA_API_KEY set
```

See [`CHANGELOG.md`](./CHANGELOG.md) for what is in each release.

## Privacy and safety

- Every call uploads audio to Modulate's API. Per Modulate's FAQ, self-service accounts are enrolled in model improvement unless they opt out with Modulate. Do not send audio you may not share.
- The API key lives only in your environment or a gitignored `.env`. Neither project logs it.
- Spot-check redacted output before sharing it.

## Links

- [Velma docs](https://docs.modulate.ai), [authentication and limits](https://docs.modulate.ai/guides/authentication.md), [troubleshooting](https://docs.modulate.ai/guides/troubleshooting.md)
- [Agent Skills specification](https://agentskills.io/specification), [Model Context Protocol](https://modelcontextprotocol.io)

## Licence

MIT. Copyright (c) 2026 Infrasity Labs. See [`LICENSE`](./LICENSE).
