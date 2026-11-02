# AI music detection

Endpoint: `POST https://platform.modulate.ai/api/velma-2-ai-music-detection-batch`

## Request

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-ai-music-detection-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@song.wav" > music.json
```

- Only field: `upload_file`. It must not be empty.
- Max 100 MB. Same list of about 96 extensions as deepfake detection.
- The spec gives no recommended clip length for this endpoint.

## Response fields

| Field | Meaning |
| - | - |
| `filename` | Name sent, or empty string |
| `duration_s` | Audio length in seconds |
| `primary_verdict` | `ai-vocal-music`, `ai-instrumental`, or `not-ai-music` |
| `vocal_percentage` | 0 to 100, share of the clip with vocals |
| `vocal_ai_percentage` | 0 to 100, AI-vocal score. Unscored windows count as zero but still count toward the clip length |
| `vocal_ai_confidence` | 0 to 1, average confidence over windows scored for AI vocals |
| `instrumental_percentage` | 0 to 100, share with instrumental content |
| `instrumental_ai_percentage` | 0 to 100, AI-instrumental score |
| `instrumental_ai_confidence` | 0 to 1, average confidence. 0 if no window was scored |
| `silence_percentage` | 0 to 100, share with neither |
| `windows[]` | Per-window detail: `start_time_ms`, `end_time_ms`, the percentages, and `vocal_ai_probability`, `instrumental_ai_probability` with their confidences |
| `latency_ms` | Inference time |

In `windows[]`, a probability is `null` when the window has too little vocal (or instrumental) content to score. A window can have both, one, or neither.

`ai-vocal-music` means AI music with a detected synthetic voice. `ai-instrumental` means AI instrumental music with no detectable synthetic voice. `not-ai-music` means the clip does not appear to contain AI-generated music.

## Summarise

```bash
jq '{primary_verdict, duration_s, vocal_ai_percentage, vocal_ai_confidence,
     instrumental_ai_percentage, instrumental_ai_confidence, silence_percentage,
     windows: (.windows | length)}' music.json
```

## How to word the result

- Template: "Primary verdict: not-ai-music. Vocal AI score X out of 100, instrumental AI score Y out of 100. This is a probability signal, not proof of origin."
- The docs give no threshold for the percentage scores. Do not invent one. Report the numbers and the verdict.
- A speech clip is not music. For speech, use the deepfake endpoint.
