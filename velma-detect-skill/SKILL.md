---
name: velma-detect-skill
description: "Detects AI-generated (synthetic, deepfake, cloned) voices and AI-generated music, redacts personal data (PII/PHI) from audio, transcribes calls, and analyses conversations with Modulate's Velma API, using curl only. Use when the user asks whether a voice recording is a deepfake, synthetic or AI-generated voice or a voice clone, whether a song or music clip is AI-made, to remove or mask names, phone numbers or health details from a recording, to transcribe a call or meeting with speaker labels, emotion or accent, or to summarise a conversation. Keywords: deepfake, synthetic voice, AI voice detection, voice cloning, AI music detection, PII redaction, PHI, transcribe, Velma, Modulate."
license: MIT
compatibility: Requires curl and a VELMA_API_KEY environment variable
metadata:
  author: Infrasity Labs
  version: "0.1.0"
---

# Velma audio skill

Call Modulate's Velma batch API with `curl`. Five jobs: deepfake detection, AI music detection, PII/PHI redaction, transcription, conversation analysis. Base URL: `https://platform.modulate.ai`. Modulate owns the Velma API.

Use this skill when the user gives you an audio file (or a folder of them) and asks one of the questions in the decision tree below. Do not use it for streaming or live audio. Streaming exists but is not covered here.

## Setup

1. Get a key at https://platform.modulate.ai/signup-request. A free account includes starting credits. No credit card is needed to start.
2. Put the key in the shell: `export VELMA_API_KEY=...` or in a gitignored `.env` file that the user loads.
3. Check it is set without printing it: `[ -n "$VELMA_API_KEY" ] && echo set || echo missing`.

Rules for the key:
- Never paste the key into chat, a file you create, a commit, or a log.
- Never run `echo $VELMA_API_KEY`, `env`, `printenv`, or `curl -v`. They leak it.
- Always send it as `-H "X-API-Key: $VELMA_API_KEY"`. Never put it in a URL.

## Decision tree

| User asks | Endpoint | Reference |
| - | - | - |
| Is this voice fake, cloned, AI-generated? | `/api/velma-2-synthetic-voice-detection-batch` | `references/deepfake-detect.md` |
| Is this song or music clip AI-made? | `/api/velma-2-ai-music-detection-batch` | `references/ai-music-detect.md` |
| Remove names, numbers, health data from this recording | `/api/velma-2-pii-phi-redaction-batch` | `references/pii-redaction.md` |
| Transcribe this call (speakers, emotion, accent) | `/api/velma-2-stt-batch` | `references/transcribe.md` |
| Summarise this conversation, find topics or behaviours | `/api/velma-2-batch` | `references/transcribe.md` |
| Got an error or a limit | any | `references/errors-and-limits.md` |

All endpoints are `POST` with `multipart/form-data`. The file goes in the field `upload_file`.

## Deepfake detection

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-synthetic-voice-detection-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@clip.wav" > result.json
```

Response fields that matter:
- `frames[]`: one entry per analysis window, in order. Each has `start_time_ms`, `end_time_ms`, `verdict`, `confidence`.
- `verdict`: `synthetic` (likely AI speech), `non-synthetic` (likely natural speech), `no-content` (silence).
- `confidence`: 0 to 1. It is confidence in the verdict given. It is not the chance the audio is fake.
- `duration_ms`: length of the audio.

Summarise the frames. Drop `no-content`, weight by frame length, report the synthetic share of speech:

```bash
jq '[.frames[] | select(.verdict != "no-content")] as $v
  | ($v | map(.end_time_ms - .start_time_ms) | add // 0) as $speech
  | ($v | map(select(.verdict == "synthetic") | .end_time_ms - .start_time_ms) | add // 0) as $syn
  | {duration_ms, frames: (.frames | length), speech_frames: ($v | length),
     synthetic_frames: ($v | map(select(.verdict == "synthetic")) | length),
     synthetic_share_of_speech: (if $speech == 0 then null else ($syn / $speech) end)}' result.json
```

## AI music detection

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-ai-music-detection-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@song.wav" > music.json
```

- `primary_verdict`: `ai-vocal-music`, `ai-instrumental`, or `not-ai-music`.
- `vocal_ai_percentage` and `instrumental_ai_percentage`: 0 to 100 AI scores for each layer.
- `vocal_ai_confidence` and `instrumental_ai_confidence`: 0 to 1 average confidence over scored windows.
- `vocal_percentage`, `instrumental_percentage`, `silence_percentage`: how much of the clip is each kind of content.
- `windows[]`: per-window detail. Probabilities are `null` when a window has too little vocal or instrumental content to score.

## PII/PHI redaction

The reply is multipart, not plain JSON. Save headers and body, then split them with the bundled script:

```bash
mkdir -p out
curl -sS -X POST https://platform.modulate.ai/api/velma-2-pii-phi-redaction-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@call.wav" \
  -F "speaker_diarization=true" \
  -D out/headers.txt -o out/response.bin
python3 scripts/split_redaction.py out/headers.txt out/response.bin out/
```

The script writes `out/metadata.json` and `out/redacted.mp3`. Optional form fields: `start_redaction_padding_ms` (default 100), `end_redaction_padding_ms` (default 0), `language` (ISO 639-1 hint such as `en`).

In `metadata.json`:
- `text`: redacted transcript. Sensitive spans become empty tags: `<pii:CATEGORY></pii:CATEGORY>` for personal data and `<phi></phi>` for health data.
- `utterances[]`: redacted text per utterance with `start_ms`, `duration_ms`, `speaker`, `language`.
- `redaction_ranges`: `[start_ms, end_ms]` pairs that were silenced in the MP3.

Redaction is automated. Always tell the user to spot-check the transcript and listen to the audio before sharing it.

## Transcription

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-stt-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@call.wav" \
  -F "speaker_diarization=true" > transcript.json
```

- `text`: full transcript. `duration_ms`: audio length.
- `utterances[]`: `text`, `start_ms`, `duration_ms`, `speaker`, `language`, and three optional signals.
- Optional boolean form fields, all default false except diarization: `emotion_signal`, `accent_signal`, `deepfake_signal`, `pii_phi_tagging`, `medical_domain`. Optional `language` hint.
- `deepfake_signal=true` adds a `deepfake_score` (0 = likely natural, 1 = likely synthetic) per utterance. For a deepfake question, prefer the dedicated deepfake endpoint above.

## Conversation analysis (Velma Triage)

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@call.wav" \
  -F "config=default" > triage.json
```

Read `summary`, `topics`, `conversation_type_pick`, `participant_role_picks`, `behaviors`, `topic_sentiments`. Custom behaviours need a JSON `config`. See `references/transcribe.md`.

## Reading scores

- Report what the API returned: verdicts, confidences, the synthetic share. Do not invent a pass or fail line.
- The docs give no official threshold. Their fraud-screening guide uses 0.5 of speech time as a starting point and says to tune it on your own labelled audio. If you quote 0.5, say it is a starting point, not an API value.
- A mixed result is normal. Calls carry hold music, IVR prompts, and transfers.
- Always say the result is a probability signal, not proof. Do not call someone a fraudster or a clip fake on this evidence alone.
- A synthetic voice is not wrongdoing. An AI assistant calling on someone's behalf also reads as synthetic.

## Input rules

- Max file size is 100 MB for every endpoint. Over that, the API returns 413.
- Deepfake detection: best on 4 to 60 second clips. Under 0.5 seconds returns 422. It expects a single speaker.
- Deepfake and AI music accept about 96 extensions (wav, mp3, flac, m4a, ogg, opus, webm, aac, aiff, mp4, mov and more).
- Redaction, transcription and conversation analysis accept only `.aac .aiff .flac .mov .mp3 .mp4 .ogg .opus .wav .webm`.
- For a long file, ask the user first, then cut a clip with ffmpeg: `ffmpeg -ss 0 -t 60 -i long.wav -c copy clip.wav`.

## Workflows

Screen one recording:
1. Check the file exists and is under 100 MB.
2. Tell the user the audio will be uploaded to Modulate's API. Wait for a yes if the audio is sensitive.
3. Run the deepfake curl, then the jq summary.
4. Report the share of speech marked synthetic, the confidence range, and the time ranges of synthetic frames. Add the probability-signal caveat.

Screen a folder, one at a time. The default limit is 3 requests in flight per model. A sequential loop stays under it:

```bash
mkdir -p results
for f in clips/*.wav; do
  out="results/$(basename "$f").json"
  for attempt in 1 2 3 4 5; do
    code=$(curl -sS -o "$out" -w "%{http_code}" -X POST \
      https://platform.modulate.ai/api/velma-2-synthetic-voice-detection-batch \
      -H "X-API-Key: $VELMA_API_KEY" -F "upload_file=@$f")
    if [ "$code" = "429" ] && grep -q "Concurrent request limit" "$out"; then
      sleep $((2 ** attempt)); continue
    fi
    break
  done
  echo "$code $f"
done
```

Redact, then transcribe: redact first, then send `out/redacted.mp3` to the transcription endpoint. Redaction output is MP3, which transcription accepts. The silenced gaps can make the second transcript guess or drop words, so use it for structure, not as proof of what was removed.

## Errors

Errors are JSON: `{"detail": "..."}`. Details are in `references/errors-and-limits.md`.

| Status | Do this |
| - | - |
| 400 | File empty, wrong format, or undecodable. Check the extension and play the file. |
| 401 | Key missing or invalid. Check `VELMA_API_KEY` is set. Never print it. |
| 403 | Key valid but not allowed, or no access to this model. Tell the user to contact Modulate. |
| 413 | File over 100 MB. Offer to cut a clip. |
| 422 | Audio too short, or `upload_file` missing. |
| 429 | Read `detail`. "Concurrent request limit" means wait and retry with backoff. "Insufficient credits" and "Monthly usage limit" mean stop. Never loop hot. |
| 500, 502, 504 | Server side. Retry later with backoff. Stop after a few tries. |

## Red flags and safety

- Do not upload audio the user has no right to share. Ask if unsure.
- Tell the user the audio leaves their machine and goes to Modulate's API. Per the Velma FAQ, self-service accounts are enrolled in model improvement unless they opt out with Modulate.
- Redacted output must be spot-checked. Missed spans are possible.
- Never print the key. Never use `curl -v`.
- Do not treat a detection result as proof of fraud, identity, or authorship.
- Streaming (WebSocket) endpoints are not covered by this skill.
