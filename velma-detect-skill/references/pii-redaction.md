# PII/PHI redaction

Endpoint: `POST https://platform.modulate.ai/api/velma-2-pii-phi-redaction-batch`

It transcribes the audio, finds personal data (PII) and health data (PHI) in the transcript, removes it from the text, and silences the matching ranges in the audio.

## Request

```bash
mkdir -p out
curl -sS -X POST https://platform.modulate.ai/api/velma-2-pii-phi-redaction-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@call.wav" \
  -F "speaker_diarization=true" \
  -D out/headers.txt -o out/response.bin
python3 scripts/split_redaction.py out/headers.txt out/response.bin out/
```

Run the second line from the skill folder, or give the full path to `scripts/split_redaction.py`.

Form fields:

| Field | Default | Meaning |
| - | - | - |
| `upload_file` | required | Audio. `.aac .aiff .flac .mov .mp3 .mp4 .ogg .opus .wav .webm`. Max 100 MB |
| `speaker_diarization` | true | Adds a speaker number to each utterance |
| `start_redaction_padding_ms` | 100 | Extra silence before each redacted range |
| `end_redaction_padding_ms` | 0 | Extra silence after each redacted range |
| `language` | auto | ISO 639-1 hint, for example `en`. `en-US` is accepted, only `en` is used |

## Response

A successful reply is `multipart/form-data` with two parts:
- `metadata`: JSON.
- `audio`: the redacted MP3.

Do not pipe it to `jq`. Save it and split it. `scripts/split_redaction.py` reads the boundary from the saved `Content-Type` header, then writes `metadata.json` and `redacted.mp3` into the output folder. It prints one line for each file. If a part is missing it exits with an error and prints the part names it found.

On an error status (4xx or 5xx) the body is JSON `{"detail": "..."}`, not multipart. The script detects this, prints the `detail`, and exits non-zero.

`metadata.json` fields:

| Field | Meaning |
| - | - |
| `text` | Full redacted transcript |
| `duration_ms` | Audio length |
| `utterances[]` | `utterance_uuid`, redacted `text`, `start_ms`, `duration_ms`, `speaker`, `language` |
| `redaction_ranges` | List of `[start_ms, end_ms]`: the final merged and padded ranges silenced in the MP3 |

Tags in the text are empty markers: `<pii:CATEGORY></pii:CATEGORY>` for personal data, where CATEGORY is the entity type, and `<phi></phi>` for health data. The sensitive words are removed, not kept inside the tag.

Real result for `fixtures/pii-speech.wav` (made-up name, phone number and date of birth, 12.4 s):

```json
{"text": "Hello, my name is <pii:firstname></pii:firstname> <pii:lastname></pii:lastname>. You can reach me on <pii:phone></pii:phone>. My date of birth is the <pii:date_of_birth></pii:date_of_birth>",
 "redaction_ranges": [[1180, 2940], [3660, 8640], [9680, 12960]], "duration_ms": 12353}
```

Categories seen: `firstname`, `lastname`, `phone`, `date_of_birth`. Note the last range ends at 12960 ms, past the 12353 ms audio length, because of padding.

## Show the result

```bash
jq -r '.text' out/metadata.json
jq -c '.redaction_ranges' out/metadata.json
```

## Safety

- Redaction is automated. Missed or partial spans are possible.
- Tell the user to read the transcript and listen to the MP3 before sharing it.
- The original file is not changed. Do not delete it without asking.
- Redaction ranges are time-based. Padding can silence a little extra speech around a span.
- In a test, the silenced ranges were digital silence (about -91 dB). Transcribing the redacted MP3 still returned the word "John" for a silenced name, so a second transcription of redacted audio can guess words from the gaps. Judge leaks by listening, not by a second transcript.
- Need tags but not silence? Use transcription with `pii_phi_tagging=true`. It keeps the original text and wraps sensitive spans in tags.
