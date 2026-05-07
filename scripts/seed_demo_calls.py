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
    # === Reservations (EN) — 8 ===
    {"label": "Reservation 4 guests (Olga)", "lang": "en-US",
     "turns": ["Hi, I'd like a table for four tomorrow at 8 pm",
               "My name is Olga", "Yes, that's correct"]},
    {"label": "Reservation 2 guests (James)", "lang": "en-US",
     "turns": ["A table for two on Saturday at seven pm please",
               "I'm James", "Yes"]},
    {"label": "Reservation 6 guests (Sophia)", "lang": "en-US",
     "turns": ["Hi, can I book a table for six tomorrow at nine pm",
               "Sophia", "Correct"]},
    {"label": "Reservation 3 guests anniversary (Daniel)", "lang": "en-US",
     "turns": ["I'd like a reservation for three on Friday at 8",
               "It's our anniversary, name is Daniel", "Yes that's right"]},
    {"label": "Reservation kids high chair (Lucas)", "lang": "en-US",
     "turns": ["A table for two adults and one child tomorrow at seven",
               "My name is Lucas", "Yes"]},
    {"label": "Reservation late dinner (Emma)", "lang": "en-US",
     "turns": ["Can I get a table at 10:30 pm tonight for two",
               "Emma", "That's correct"]},
    {"label": "Reservation gluten-free pasta (Hannah)", "lang": "en-US",
     "turns": ["Hi, table for two tomorrow at 8 with gluten-free pasta",
               "I'm Hannah", "Yes"]},
    {"label": "Reservation window seat (Michael)", "lang": "en-US",
     "turns": ["I'd like a table for four tomorrow at 7:30 pm by the window",
               "Michael", "Yes"]},

    # === Private events (EN) — 4 ===
    {"label": "Private event 15 guests HOT (Maria)", "lang": "en-US",
     "turns": ["I'd like to plan a private event for fifteen people",
               "This is Maria", "Next Friday at seven pm", "Yes"]},
    {"label": "Private event birthday (Emily)", "lang": "en-US",
     "turns": ["Hi, I want to book a table for my birthday",
               "I'm Emily", "Saturday at eight, party of four", "Yes"]},
    {"label": "Private event 8 (Sophia)", "lang": "en-US",
     "turns": ["Private dinner for eight on Friday at seven",
               "Sophia", "Yes"]},
    {"label": "Private event 25 corporate HOT (David)", "lang": "en-US",
     "turns": ["We're planning a corporate dinner for 25",
               "David from Goldman Sachs", "Next Thursday at 7:30 pm", "Yes"]},

    # === Takeout (EN/ES) — 3 ===
    {"label": "Takeout order (Daniel)", "lang": "en-US",
     "turns": ["Hi, I'd like to place a takeout order",
               "My name is Daniel", "Yes"]},
    {"label": "Takeout pickup at 7 (Olivia)", "lang": "en-US",
     "turns": ["Takeout please, pickup at 7 pm",
               "Olivia", "Yes"]},
    {"label": "Spanish takeout (Carlos)", "lang": "es-US",
     "turns": ["Hola, quisiera ordenar comida para llevar",
               "Me llamo Carlos", "Sí"]},

    # === Spanish (ES) — 3 ===
    {"label": "Spanish reservation 4 (Sofia)", "lang": "es-US",
     "turns": ["Hola, una reserva para cuatro personas mañana a las nueve",
               "Me llamo Sofia", "Sí, correcto"]},
    {"label": "Spanish reservation 2 (Diego)", "lang": "es-US",
     "turns": ["Quisiera reservar mesa para dos el sábado a las ocho",
               "Soy Diego", "Sí"]},
    {"label": "Spanish allergy (Lucia)", "lang": "es-US",
     "turns": ["Tengo alergia a los mariscos, ¿qué pueden ofrecer?"]},

    # === Russian (RU) — 4 ===
    {"label": "Russian birthday 6 (Анна)", "lang": "ru-RU",
     "turns": ["Здравствуйте, я бы хотела отметить день рождения у вас",
               "Меня зовут Анна", "Нас будет шестеро",
               "В субботу в восемь вечера", "Да, всё верно"]},
    {"label": "Russian reservation 4 (Кирилл)", "lang": "ru-RU",
     "turns": ["Здравствуйте, столик на четверых завтра в восемь вечера",
               "Меня зовут Кирилл", "Да, всё верно"]},
    {"label": "Russian reservation 2 (Игорь)", "lang": "ru-RU",
     "turns": ["Хочу забронировать столик",
               "Меня зовут Игорь", "Нас будет двое",
               "На пятницу в семь вечера", "Да"]},
    {"label": "Russian hours (faq)", "lang": "ru-RU",
     "turns": ["Во сколько вы сегодня открыты?"]},

    # === FAQ / menu / allergens — 8 ===
    {"label": "Menu — tomahawk", "lang": "en-US",
     "turns": ["Do you have a tomahawk steak?"]},
    {"label": "Menu — gnocchi", "lang": "en-US",
     "turns": ["Do you serve gnocchi?"]},
    {"label": "Menu — desserts list", "lang": "en-US",
     "turns": ["What desserts do you have?"]},
    {"label": "Menu — price tomahawk", "lang": "en-US",
     "turns": ["How much is the tomahawk?"]},
    {"label": "Allergy — peanuts", "lang": "en-US",
     "turns": ["I have a peanut allergy, what can I have?"]},
    {"label": "Allergy — vegan options", "lang": "en-US",
     "turns": ["Do you have any vegan options?"]},
    {"label": "FAQ — wifi", "lang": "en-US",
     "turns": ["Do you have wifi for guests?"]},
    {"label": "FAQ — valet parking", "lang": "en-US",
     "turns": ["Is there valet parking?"]},
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
