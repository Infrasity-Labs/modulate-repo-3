#!/usr/bin/env python3
"""Split a Velma redaction response into metadata.json and redacted.mp3.

Usage: split_redaction.py HEADERS_FILE BODY_FILE OUT_DIR

HEADERS_FILE comes from `curl -D`. BODY_FILE comes from `curl -o`.
Standard library only. Python 3.8 or newer.
"""
import email
import email.policy
import json
import pathlib
import sys


def last_header_block(text):
    blocks = [b for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return blocks[-1].split("\n") if blocks else []


def main(argv):
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    headers_path, body_path, out_dir = map(pathlib.Path, argv[1:])
    lines = last_header_block(headers_path.read_text(errors="replace"))
    status = lines[0].split()[1] if lines and len(lines[0].split()) > 1 else "?"
    content_type = ""
    for line in lines[1:]:
        if line.lower().startswith("content-type:"):
            content_type = line.split(":", 1)[1].strip()
    body = body_path.read_bytes()

    if status != "200" or not content_type.lower().startswith("multipart/"):
        try:
            detail = json.loads(body).get("detail", body[:200])
        except (ValueError, AttributeError):
            detail = body[:200].decode("utf-8", "replace")
        print("HTTP %s: %s" % (status, detail), file=sys.stderr)
        return 1

    raw = b"MIME-Version: 1.0\r\nContent-Type: " + content_type.encode() + b"\r\n\r\n" + body
    message = email.message_from_bytes(raw, policy=email.policy.HTTP)
    parts = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        parts[name] = part.get_payload(decode=True)

    if "metadata" not in parts or "audio" not in parts:
        print("Expected parts 'metadata' and 'audio'. Found: %s" % sorted(map(str, parts)), file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metadata.json").write_bytes(parts["metadata"])
    (out_dir / "redacted.mp3").write_bytes(parts["audio"])
    print("wrote %s (%d bytes)" % (out_dir / "metadata.json", len(parts["metadata"])))
    print("wrote %s (%d bytes)" % (out_dir / "redacted.mp3", len(parts["audio"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
