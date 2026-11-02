# Deepfake detection (synthetic voice)

Endpoint: `POST https://platform.modulate.ai/api/velma-2-synthetic-voice-detection-batch`

## Request

```bash
curl -sS -X POST https://platform.modulate.ai/api/velma-2-synthetic-voice-detection-batch \
  -H "X-API-Key: $VELMA_API_KEY" \
  -F "upload_file=@clip.wav" > result.json
```

- Only field: `upload_file`. It must not be empty.
- Max 100 MB. Best on 4 to 60 second clips.
- Under 0.5 seconds returns 422. A clip shorter than one 4 second window is accepted and padded.
- Leading and trailing silence is excluded from analysis. Frame timestamps still match the original file.
- The model is described for single-speaker audio.
- Accepted extensions: about 96 formats, including `.wav .mp3 .flac .m4a .ogg .opus .webm .aac .aiff .mp4 .mov .amr .wma`. A bad extension returns 400 with the full list in `detail`.

## Response

```json
{
  "filename": "synthetic-1.wav",
  "frames": [
    {"start_time_ms": 0, "end_time_ms": 4000, "verdict": "synthetic", "confidence": 0.9717},
    {"start_time_ms": 4000, "end_time_ms": 8000, "verdict": "synthetic", "confidence": 0.9749},
    {"start_time_ms": 8000, "end_time_ms": 9334, "verdict": "synthetic", "confidence": 0.9693}
  ],
  "duration_ms": 9334
}
```

This is a real reply for a 9.3 second Piper text-to-speech clip. Frames are 4000 ms windows. The last frame is trimmed to the end of the audio.

| Field | Meaning |
| - | - |
| `verdict` | `synthetic`, `non-synthetic`, or `no-content` |
| `confidence` | 0 to 1, confidence in that verdict |
| `no-content` | Silent or unusable frame. Always confidence 1.0 |
| `duration_ms` | Total audio length |

`confidence` is not the probability the clip is fake. A `non-synthetic` frame at 0.97 means 97 percent confident the speech is natural. It does not mean a 3 percent chance of synthetic.

## Summarise

Per-frame timeline:

```bash
jq -r '.frames[] | "\(.start_time_ms)-\(.end_time_ms) ms  \(.verdict)  \(.confidence)"' result.json
```

Clip level, duration weighted, silence dropped:

```bash
jq '[.frames[] | select(.verdict != "no-content")] as $v
  | ($v | map(.end_time_ms - .start_time_ms) | add // 0) as $speech
  | ($v | map(select(.verdict == "synthetic") | .end_time_ms - .start_time_ms) | add // 0) as $syn
  | {duration_ms, frames: (.frames | length), speech_frames: ($v | length),
     synthetic_frames: ($v | map(select(.verdict == "synthetic")) | length),
     synthetic_share_of_speech: (if $speech == 0 then null else ($syn / $speech) end)}' result.json
```

If `speech_frames` is 0, report "inconclusive: no speech found".

## How to word the result

Wording templates (the numbers are placeholders, fill in the real ones):

Good:
- "7 of 8 speech frames (88 percent of speech time) were marked synthetic, with confidence from 0.81 to 0.99. This is a probability signal, not proof."
- "All speech frames were marked non-synthetic. That does not prove the audio is human."

Bad:
- "This is a deepfake."
- "98 percent chance this is fake." (confidence is not that.)

## Thresholds

The API defines none. Modulate's fraud-screening guide uses 0.5 of speech time as a starting point and says to tune it on labelled audio and your tolerance for false positives. Real calls carry hold music, IVR prompts and transfers, so partial shares are common.

## Limits to mention

- A synthetic verdict does not say anyone did something wrong. An AI assistant calling for a customer also reads as synthetic.
- Studio test clips do not match phone audio. Results on real calls may differ.
- For one score per utterance while transcribing, use `deepfake_signal=true` on the transcription endpoint. It gives `deepfake_score` from 0 (likely natural) to 1 (likely synthetic), and `null` for utterances under 0.5 seconds.
