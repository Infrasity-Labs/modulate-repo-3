# Transcription and conversation analysis

## Transcription

Endpoint: `POST https://platform.modulate.ai/api/velma-2-stt-batch`

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-stt-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@call.wav" \
  -F "speaker_diarization=true" \
  -F "emotion_signal=true" \
  -F "accent_signal=true" > transcript.json
```

Form fields:

| Field | Default | Meaning |
| - | - | - |
| `upload_file` | required | `.aac .aiff .flac .mp3 .mp4 .mov .ogg .opus .wav .webm`. Max 100 MB. Not empty |
| `speaker_diarization` | true | Speaker number on each utterance |
| `emotion_signal` | false | Emotion label per utterance |
| `accent_signal` | false | Accent label per utterance |
| `deepfake_signal` | false | `deepfake_score` per utterance |
| `pii_phi_tagging` | false | Wrap personal and health data in tags. Text is kept |
| `medical_domain` | false | Medical dictation mode for English. Adds some latency |
| `language` | auto | ISO 639-1 hint, for example `en` |
| `config` | none | JSON string. Same flags plus `custom_terms`. A field in `config` overrides the form field |

Custom vocabulary example:

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-stt-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@call.wav" \
  -F 'config={"custom_terms":["Modulate",{"term":"Velma","pronunciations":["VEL-muh"]}]};type=application/json'
```

Response:
- `text`: full transcript. May be empty if no speech was found.
- `duration_ms`: audio length.
- `utterances[]`: `utterance_uuid`, `text`, `start_ms`, `duration_ms`, `speaker` (1-indexed), `language` (per utterance), `emotion`, `accent`, `deepfake_score`.
- `emotion`, `accent` and `deepfake_score` are `null` when the matching flag is off. `deepfake_score` is also `null` when the utterance could not be analysed.
- Emotion values: Angry, Disgusted, Afraid, Happy, Neutral, Other, Sad, Surprised, Unknown.

Print a readable transcript:

```bash
jq -r '.utterances[] | "[\(.start_ms / 1000 | floor)s] speaker \(.speaker): \(.text)"' transcript.json
```

`deepfake_score` runs from 0 (likely natural) to 1 (likely synthetic). The docs give no threshold. Treat it as a probability signal, not proof.

## Conversation analysis (Velma Triage)

Endpoint: `POST https://platform.modulate.ai/api/velma-2-batch`

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@call.wav" \
  -F "config=default" > triage.json
```

- `upload_file`: `.aac .aiff .flac .mov .mp3 .mp4 .ogg .opus .wav .webm`, max 100 MB.
- `config`: the word `default`, or a JSON `BatchConfig`. When omitted, `default` is used.

Response fields:
- `duration_ms`, `model_version`.
- `clips[]`: transcript segments with `text`, `start_ms`, `duration_ms`, `speaker_label`, `language`, and optional `emotion`, `accent`, `deepfake_score`.
- `conversation_type_pick` and `participant_role_picks[]`: what kind of conversation, and who is who.
- `behaviors[]`: one entry per behaviour and speaker, with `behavior_name`, `speaker_label`, `detected`, `confidence`, `reasoning`.
- `topics[]`, `topic_sentiments[]`, `summary`.

A useful view:

```bash
jq '{summary, topics, conversation_type_pick, detected_behaviors: [.behaviors[] | select(.detected) | {behavior_name, speaker_label, confidence}]}' triage.json
```

The default config already evaluates some built-in behaviours. In a test on a one-speaker fable reading, `behaviors` held one entry, `Monologuing`, with `detected: true`. With `{"behaviors":["preset:complaints"]}` the same file returned an empty `behaviors` array. To evaluate your own list, pass a `BatchConfig` that names the behaviours. A behaviour can be a preset reference such as `preset:complaints`:

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@call.wav" \
  -F 'config={"behaviors":["preset:complaints"]};type=application/json'
```

List valid preset identifiers:

```bash
curl -sS https://platform.modulate.ai/api/velma-2-batch/list-presets -H "X-API-Key: $VELMA_API_KEY" | jq -r '.presets[] | "\(.identifier)\t\(.short_description)"'
```

Other `BatchConfig` flags: `produce_topics`, `produce_topic_sentiments`, `produce_summary` (all default true), `conversation_dynamics` (default false, adds `speakers` and `conversation_dynamics`), and `stt` options such as `custom_terms`. Custom `BehaviorDef` objects need `behavior_uuid`, `name`, `short_description` and `detailed_description`. Full schema: https://docs.modulate.ai/api-reference/velma/batch.md

A detected behaviour does not prove wrongdoing. Report `confidence` and `reasoning` as given.
