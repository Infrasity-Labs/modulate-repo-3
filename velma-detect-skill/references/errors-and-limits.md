# Errors and limits

Every error body is JSON: `{"detail": "..."}`. Exception: a 422 from a missing field has `detail` as a list of `{loc, msg, type}` objects.

Show the status and the `detail` text. Never show request headers.

## See the status code

```bash
code=$(curl -sS -o out.json -w "%{http_code}" -X POST <url> -H "X-API-Key: $VELMA_API_KEY" -F "upload_file=@clip.wav")
echo "$code"; jq -r '.detail' out.json
```

Never use `curl -v`. It prints request headers, including the key. `-D file` saves only response headers and is safe.

## By status code

| Status | Typical `detail` | Fix |
| - | - | - |
| 400 | `Unsupported file format. Supported formats: ...` | Use a listed extension. Convert with ffmpeg if needed |
| 400 | `The uploaded file is empty.` | Check the path. Check the file is not 0 bytes |
| 400 | `No decodable audio stream was found in the file.` / `The audio file appears to be corrupted or truncated.` | Play the file. Re-export it |
| 400 | `Invalid language='english'. Expected an ISO 639-1 language code (e.g. 'en', 'fr').` | Use a code like `en` |
| 401 | `Missing API key.` | The header was not sent. Check `VELMA_API_KEY` is exported in this shell |
| 401 | `Invalid API key.` | Key is wrong, revoked or rotated. Ask the user to check the dashboard. Do not print the key |
| 403 | `This request is not permitted.` / `This API key does not have access to this model.` | The organization lacks access. Contact Modulate |
| 413 | `The uploaded file is too large.` | Over 100 MB. Offer to cut a clip |
| 422 | `The audio is too short to analyze.` | Deepfake detection needs 0.5 seconds or more |
| 422 | list with `"loc": ["body", "upload_file"]` | The `upload_file` field is missing. Use `-F "upload_file=@path"` |
| 429 | `Concurrent request limit reached. Please retry after your in-flight requests complete.` | Wait, then retry with backoff |
| 429 | `Insufficient credits.` | Stop. Credits must be added |
| 429 | `Monthly usage limit reached.` | Stop. Wait for the next billing cycle or a raised limit |
| 500 | `Internal server error` | Retry later. Stop after a few tries |
| 502 | `Unable to complete the request. Please try again.` | Retry with backoff. Documented for AI music detection and Multilingual Fast Transcription batch |
| 504 | `The request timed out. Please try again.` | Retry with backoff. Try a shorter clip |

Match on the `detail` text for 429, not on the status alone.

## Limits

- Concurrency: 3 requests in flight per model by default. Reaching the cap on one model does not affect another.
- Credits are separate from concurrency. An out-of-credits request is rejected whatever the load.
- Max file size: 100 MB on every batch endpoint.
- Deepfake detection: under 0.5 seconds is rejected. 4 to 60 seconds is the recommended range.
- To raise a concurrency cap, the user contacts Modulate with the model name and expected traffic. See https://docs.modulate.ai/support.md

## Backoff rule

Only the concurrency 429 is worth retrying.

```bash
for attempt in 1 2 3 4 5; do
  code=$(curl -sS -o out.json -w "%{http_code}" -X POST <url> -H "X-API-Key: $VELMA_API_KEY" -F "upload_file=@clip.wav")
  if [ "$code" = "429" ] && grep -q "Concurrent request limit" out.json; then
    sleep $((2 ** attempt)); continue
  fi
  break
done
```

Rules:
- Never retry in a tight loop.
- Never retry credit or monthly 429s. Tell the user.
- Cap tries at 5. Then report the last status and `detail`.
- When processing many files, run one at a time, or at most 3 together.

## Still stuck

Docs: https://docs.modulate.ai/guides/troubleshooting.md. Support: support@modulate.ai.
