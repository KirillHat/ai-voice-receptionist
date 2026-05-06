"""Bulk-transcribe recent Twilio calls and produce a real-call analysis report.

For every call we have a recording for, this script:
- downloads the MP3 (or reuses the cached file)
- runs OpenAI Whisper to get the verbatim transcript
- pulls the in-app transcript / captured fields from /analytics/calls
- pulls Twilio per-call notifications (TTS rejections, signature errors, etc.)
- writes everything to real_calls_report.md

Usage:
    python scripts/analyze_real_calls.py [--limit 6] [--min-duration 15]
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENV = dotenv_values(ROOT / ".env")
PROD_HTTP = "https://ai-voice-production-eb9e.up.railway.app"
RECORDINGS_DIR = ROOT / "recordings"
REPORT_PATH = ROOT / "real_calls_report.md"


def _fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _twilio_auth() -> str:
    sid = ENV.get("TWILIO_ACCOUNT_SID")
    tok = ENV.get("TWILIO_AUTH_TOKEN")
    if not sid or not tok:
        _fail("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN missing in .env")
    return base64.b64encode(f"{sid}:{tok}".encode()).decode()


def _twilio_get(path: str) -> dict:
    sid = ENV["TWILIO_ACCOUNT_SID"]
    auth = _twilio_auth()
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _list_calls(min_duration: int, limit: int) -> list[dict]:
    data = _twilio_get(f"/Calls.json?PageSize={limit * 2}")
    calls = data.get("calls", [])
    real = [c for c in calls if int(c.get("duration") or 0) >= min_duration]
    return real[:limit]


def _list_recordings(call_sid: str) -> list[dict]:
    data = _twilio_get(f"/Calls/{call_sid}/Recordings.json")
    return data.get("recordings", [])


def _list_notifications(call_sid: str) -> list[dict]:
    data = _twilio_get(f"/Calls/{call_sid}/Notifications.json")
    return data.get("notifications", [])


def _download_mp3(rec_sid: str) -> Path:
    sid = ENV["TWILIO_ACCOUNT_SID"]
    auth = _twilio_auth()
    RECORDINGS_DIR.mkdir(exist_ok=True)
    out = RECORDINGS_DIR / f"{rec_sid}.mp3"
    if out.exists() and out.stat().st_size > 0:
        return out
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Recordings/{rec_sid}.mp3"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=60) as r, open(out, "wb") as f:
        f.write(r.read())
    return out


def _whisper(mp3: Path) -> str:
    api_key = ENV.get("OPENAI_API_KEY")
    if not api_key:
        _fail("OPENAI_API_KEY missing in .env")
    boundary = "----whisper-boundary"
    parts: list[bytes] = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n')
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="response_format"\r\n\r\ntext\r\n')
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
        return r.read().decode().strip()


def _app_transcript(call_sid: str) -> dict | None:
    url = f"{PROD_HTTP}/analytics/calls/{urllib.parse.quote(call_sid)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _diagnose(whisper_text: str, detail: dict | None, notifs: list[dict]) -> list[str]:
    issues: list[str] = []
    lower = whisper_text.lower()

    # Twilio-side errors are facts, not heuristics.
    for n in notifs:
        code = n.get("error_code")
        if code in (None, "", "0"):
            continue
        msg = urllib.parse.unquote(n.get("message_text", ""))[:120]
        issues.append(f"Twilio error {code}: {msg}")

    # Heuristics on the verbatim transcript.
    if not whisper_text.strip():
        issues.append("Whisper returned an empty transcript (caller hung up immediately?)")
    if "trial account" in lower:
        issues.append("Twilio Trial disclaimer played — caller hit a non-paid call gate")

    # Common agent failure patterns we've seen in real calls.
    if "i did not catch that" in lower or "did not catch that" in lower:
        issues.append("Agent fell back to 'did not catch that' (STT noise / silence)")
    if lower.count("одну секунду") + lower.count("one moment") >= 3:
        issues.append("Holding phrase repeated 3+ times — LLM probably stalled")
    if "не говорил" in lower or "не говорила" in lower or "i didn't say" in lower:
        issues.append("Caller said the agent misheard them — likely field captured wrong")
    if "i did not say" in lower:
        issues.append("Caller said the agent misheard them")

    # Compare captured datetime against typical hour mistakes.
    if detail:
        dt = (detail.get("reservation_datetime") or "").lower()
        # 'семь часов вечера' should be 19:00 not 07:00
        if "семь" in lower and "вечера" in lower and "t07:" in dt:
            issues.append("Caller said 'семь часов вечера' but captured datetime is 07:00 (AM)")
        if (" pm" in lower or "evening" in lower) and ("t07:" in dt or "t08:" in dt):
            issues.append("Caller indicated PM but captured datetime looks like AM")

        if detail.get("intent") == "general" and ("reservation" in lower or "забронир" in lower):
            issues.append("Caller talked about a booking but intent was kept as 'general'")
        if (
            detail.get("party_size")
            and ("часов" in lower or "o'clock" in lower or "pm" in lower)
            and not any(c in lower for c in ("for ", "party of", "нас", "para ", "people"))
        ):
            issues.append(
                f"party_size={detail.get('party_size')} captured but caller's "
                f"speech was mostly about time — check for time-as-party hijack"
            )

    return issues


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--min-duration", type=int, default=15)
    args = p.parse_args()

    calls = _list_calls(args.min_duration, args.limit)
    if not calls:
        print("no real calls found")
        return 1

    sections: list[str] = []
    sections.append("# Real-call analysis\n")
    sections.append(f"- analyzed: **{len(calls)}** calls (>= {args.min_duration}s)")
    sections.append(f"- prod URL: {PROD_HTTP}\n")

    summary_rows: list[str] = []
    issue_count = 0

    for i, c in enumerate(calls, 1):
        sid = c["sid"]
        print(f"[{i}/{len(calls)}] {sid} ({c['duration']}s)…", flush=True)

        recs = _list_recordings(sid)
        notifs = _list_notifications(sid)
        detail = _app_transcript(sid)

        whisper_text = ""
        rec_sid = "—"
        if recs:
            rec_sid = recs[0]["sid"]
            try:
                mp3 = _download_mp3(rec_sid)
                whisper_text = _whisper(mp3)
            except Exception as exc:
                whisper_text = f"(Whisper failed: {exc!r})"

        issues = _diagnose(whisper_text, detail, notifs)
        issue_count += len(issues)
        ok = "✅" if not issues else "⚠️"

        date = c.get("date_created", "")[:25]
        intent = (detail or {}).get("intent") or "—"
        guest = (detail or {}).get("guest_name") or "—"
        party = (detail or {}).get("party_size") or "—"
        dt_field = (detail or {}).get("reservation_datetime") or "—"
        summary_rows.append(
            f"| {i} | {date} | {c['duration']}s | {ok} | {intent} | {guest} | "
            f"{party} | {dt_field} | {len(issues)} |"
        )

        sections.append(f"\n## {i}. {sid} — {ok}\n")
        sections.append(f"- date: {date}")
        sections.append(f"- duration: {c['duration']}s")
        sections.append(f"- recording: `{rec_sid}`")
        if detail:
            lead = detail.get("lead") or {}
            sections.append(
                f"- captured: intent=`{detail.get('intent')}` "
                f"name=`{detail.get('guest_name')}` "
                f"party=`{detail.get('party_size')}` "
                f"datetime=`{detail.get('reservation_datetime')}` "
                f"status=`{detail.get('status')}` "
                f"label=`{lead.get('qualification_label')}`"
            )
        else:
            sections.append("- captured: _(call session not found in prod DB — likely lost on container restart)_")

        if issues:
            sections.append("\n### Issues\n")
            for issue in issues:
                sections.append(f"- ⚠️ {issue}")
        else:
            sections.append("\n_No issues detected._")

        sections.append("\n### Whisper transcript\n")
        sections.append("```")
        sections.append(whisper_text or "(empty)")
        sections.append("```")

        if detail and detail.get("transcript"):
            sections.append("\n### Agent-side transcript (what the qualifier saw)\n")
            for entry in detail["transcript"]:
                role = entry.get("role", "?")
                marker = "👤" if role == "caller" else "🤖"
                sections.append(f"- {marker} {role}: {entry.get('text', '')}")

    out = "# Real-call analysis\n\n"
    out += f"- analyzed: **{len(calls)}** calls (>= {args.min_duration}s)\n"
    out += f"- total issues flagged: **{issue_count}**\n"
    out += f"- prod URL: {PROD_HTTP}\n\n"
    out += "## Summary\n\n"
    out += "| # | date | dur | result | intent | name | party | datetime | issues |\n"
    out += "|---|---|---|---|---|---|---|---|---|\n"
    out += "\n".join(summary_rows)
    out += "\n\n"
    out += "\n".join(sections[2:])

    REPORT_PATH.write_text(out)
    print(f"\nreport: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
