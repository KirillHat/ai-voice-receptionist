"""Drive synthetic calls against a deployed receptionist instance.

Computes a valid Twilio signature using TWILIO_AUTH_TOKEN, opens the
ConversationRelay WebSocket on the live host, and replays a handful of
canonical scenarios so the dashboard has data to show.

Usage:
    .venv/bin/python scripts/seed_demo_calls.py \\
        --base https://ai-voice-production-eb9e.up.railway.app

The auth token is read from $TWILIO_AUTH_TOKEN or the project's
.env file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from pathlib import Path

import websockets
from twilio.request_validator import RequestValidator


SCENARIOS: list[dict] = [
    {
        "label": "Reservation, party of 4 (Olga)",
        "lang": "en-US",
        "turns": [
            "Hi, I'd like a table for four tomorrow at 8 pm",
            "My name is Olga",
            "Yes, that's correct",
        ],
    },
    {
        "label": "Private event, 15 guests (Maria)",
        "lang": "en-US",
        "turns": [
            "I'd like to plan a private event for fifteen people",
            "This is Maria",
            "Next Friday at seven pm",
            "Yes",
        ],
    },
    {
        "label": "Russian birthday (Анна)",
        "lang": "ru-RU",
        "turns": [
            "Здравствуйте, я бы хотела отметить день рождения у вас",
            "Меня зовут Анна",
            "Нас будет шестеро",
            "В субботу в восемь вечера",
            "Да, всё верно",
        ],
    },
    {
        "label": "Spanish reservation (Carlos)",
        "lang": "es-US",
        "turns": [
            "Hola, una reserva para cuatro personas mañana a las nueve",
            "Me llamo Carlos",
            "Sí, correcto",
        ],
    },
    {
        "label": "Menu question — tomahawk",
        "lang": "en-US",
        "turns": [
            "Do you have a tomahawk steak?",
        ],
    },
    {
        "label": "Allergy question — peanuts",
        "lang": "en-US",
        "turns": [
            "I have a peanut allergy, what can I have?",
        ],
    },
    {
        "label": "Hours question (FAQ)",
        "lang": "en-US",
        "turns": [
            "What time are you open today?",
        ],
    },
    {
        "label": "Takeout order (Daniel)",
        "lang": "en-US",
        "turns": [
            "Hi, I'd like to place a takeout order",
            "My name is Daniel",
            "Yes",
        ],
    },
]


def _load_dotenv_token() -> str | None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith("TWILIO_AUTH_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


async def _drain(ws, settle_seconds: float = 1.5) -> str:
    """Pull text tokens until WS goes quiet for ``settle_seconds``."""
    parts: list[str] = []
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=settle_seconds)
        except asyncio.TimeoutError:
            break
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if msg.get("type") == "text" and msg.get("token"):
            parts.append(msg["token"])
        if msg.get("type") == "language":
            continue
    return "".join(parts).strip()


async def run_one(base_url: str, scenario: dict, auth_token: str) -> None:
    label = scenario["label"]
    lang = scenario["lang"]
    turns = scenario["turns"]

    # Clean wss URL with no query params, signed against TWILIO_AUTH_TOKEN.
    https_base = base_url.rstrip("/")
    wss_url = (
        "wss" + https_base.removeprefix("https") + "/ws/conversationrelay"
    )
    https_for_sig = https_base + "/ws/conversationrelay"
    validator = RequestValidator(auth_token)
    signature = validator.compute_signature(https_for_sig, params={})

    headers = {"x-twilio-signature": signature}
    sid = f"CA{uuid.uuid4().hex[:30]}"
    phone = f"+1555{uuid.uuid4().hex[:7]}"

    print(f"\n=== {label} ===")
    print(f"  call_sid={sid}  phone={phone}  lang={lang}")
    async with websockets.connect(wss_url, additional_headers=headers) as ws:
        await ws.send(json.dumps({"type": "setup", "callSid": sid, "from": phone}))
        await asyncio.sleep(0.3)
        for turn in turns:
            print(f"  USER: {turn}")
            await ws.send(json.dumps({
                "type": "prompt", "voicePrompt": turn, "lang": lang, "last": True,
            }))
            reply = await _drain(ws)
            if reply:
                snippet = reply[:140] + ("…" if len(reply) > 140 else "")
                print(f"  BOT : {snippet}")
            else:
                print(f"  BOT : (no reply within timeout)")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="https://your-app.up.railway.app")
    parser.add_argument("--token", default=None, help="TWILIO_AUTH_TOKEN (else from env or .env)")
    parser.add_argument("--only", default=None, help="substring filter for scenario label")
    args = parser.parse_args()

    token = args.token or os.environ.get("TWILIO_AUTH_TOKEN") or _load_dotenv_token()
    if not token:
        raise SystemExit(
            "no auth token — pass --token, set TWILIO_AUTH_TOKEN, or add it to .env"
        )

    selected = [s for s in SCENARIOS if not args.only or args.only.lower() in s["label"].lower()]
    print(f"Running {len(selected)} scenario(s) against {args.base}")
    for scenario in selected:
        try:
            await run_one(args.base, scenario, token)
        except Exception as exc:
            print(f"  ERROR: {exc}")
        # Small gap between calls so analytics rows are clearly separated.
        await asyncio.sleep(0.5)
    print("\nDone. Open /dashboard to see the calls.")


if __name__ == "__main__":
    asyncio.run(main())
