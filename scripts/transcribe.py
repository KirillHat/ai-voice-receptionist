"""Transcribe a call recording with Whisper and merge with the in-app transcript.

Usage:
    python scripts/transcribe.py <call_sid_or_recording_sid_or_mp3_path>

Env vars used (read from project .env automatically):
    OPENAI_API_KEY        — required, used for Whisper
    TWILIO_ACCOUNT_SID    — used to download recordings via Twilio API
    TWILIO_AUTH_TOKEN     — used to download recordings via Twilio API
    APP_BASE_URL          — used to fetch the in-app transcript (defaults to prod)
"""

from __future__ import annotations

import base64
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV = dotenv_values(ROOT / ".env")

PROD_URL = ENV.get("APP_BASE_URL") or "https://ai-voice-production-eb9e.up.railway.app"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def twilio_basic_auth() -> str:
    sid = ENV.get("TWILIO_ACCOUNT_SID")
    tok = ENV.get("TWILIO_AUTH_TOKEN")
    if not sid or not tok:
        fail("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN missing in .env")
    return base64.b64encode(f"{sid}:{tok}".encode()).decode()


def http_get_json(url: str, *, basic_auth: str | None = None) -> dict:
    headers: dict[str, str] = {}
    if basic_auth:
        headers["Authorization"] = f"Basic {basic_auth}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as r:
        return json.loads(r.read().decode())


def find_recording_for_call(call_sid: str) -> tuple[str, Path]:
    sid = ENV["TWILIO_ACCOUNT_SID"]
    auth = twilio_basic_auth()
    data = http_get_json(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls/{call_sid}/Recordings.json",
        basic_auth=auth,
    )
    recs = data.get("recordings", [])
    if not recs:
        fail(f"no recordings for call {call_sid}")
    rec_sid = recs[0]["sid"]
    return rec_sid, download_recording(rec_sid)


def download_recording(rec_sid: str) -> Path:
    sid = ENV["TWILIO_ACCOUNT_SID"]
    auth = twilio_basic_auth()
    out_dir = ROOT / "recordings"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{rec_sid}.mp3"
    if out.exists() and out.stat().st_size > 0:
        return out
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Recordings/{rec_sid}.mp3"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req) as r, open(out, "wb") as f:
        f.write(r.read())
    return out


def whisper_transcribe(mp3: Path) -> dict:
    """Send the MP3 to OpenAI's audio transcription endpoint."""
    api_key = ENV.get("OPENAI_API_KEY")
    if not api_key:
        fail("OPENAI_API_KEY missing in .env")

    boundary = "----whisper-boundary-1"
    parts: list[bytes] = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n')
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="response_format"\r\n\r\nverbose_json\r\n')
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{mp3.name}"\r\n'.encode()
    )
    parts.append(b"Content-Type: audio/mpeg\r\n\r\n")
    parts.append(mp3.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def fetch_app_transcript(call_sid: str) -> dict | None:
    try:
        return http_get_json(
            f"{PROD_URL.rstrip('/')}/analytics/calls/{urllib.parse.quote(call_sid)}"
        )
    except Exception as exc:
        print(f"(could not fetch app transcript: {exc})", file=sys.stderr)
        return None


def main() -> None:
    if len(sys.argv) < 2:
        fail("usage: python scripts/transcribe.py <call_sid|recording_sid|path.mp3>")
    arg = sys.argv[1]

    call_sid: str | None = None
    if arg.startswith("CA"):
        call_sid = arg
        _, mp3 = find_recording_for_call(arg)
    elif arg.startswith("RE"):
        mp3 = download_recording(arg)
    else:
        mp3 = Path(arg)
        if not mp3.exists():
            fail(f"file not found: {mp3}")

    print(f"=== Whisper transcription of {mp3.name} ===")
    result = whisper_transcribe(mp3)
    print()
    print(result.get("text", "(empty)"))

    if call_sid is None:
        return

    print()
    print(f"=== App transcript for {call_sid} (what the agent saw) ===")
    detail = fetch_app_transcript(call_sid)
    if not detail:
        return
    for entry in detail.get("transcript", []):
        role = entry.get("role", "?")
        text = entry.get("text", "")
        marker = "👤" if role == "caller" else "🤖"
        print(f"  {marker} {role:>9}: {text}")
    print()
    lead = detail.get("lead")
    if lead:
        print(f"  → lead: {json.dumps(lead, ensure_ascii=False)}")
    print(f"  → status: {detail.get('status')}")


if __name__ == "__main__":
    main()
