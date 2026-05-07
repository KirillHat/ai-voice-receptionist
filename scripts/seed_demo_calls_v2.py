"""Round-2 seed: 30 fresh scenarios across new topics.

Topics covered (different from seed_demo_calls.py):
- Hold-on / wait phrases mid-call
- Mid-call corrections (caller changes party / time)
- Mixed inquiry + booking ('do you have valet AND book me a table')
- Edge times: very early, very late
- Wine / cocktail / specific dish queries
- Russian / Spanish naturalistic openings
- HOT leads (large groups, corporate)
- Cancellation request flow
- Hold-on detection
- Multi-language code switch
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.seed_demo_calls import _load_dotenv_token, run_one  # noqa: E402

SCENARIOS_V2: list[dict] = [
    # === Bookings with mid-call corrections / quirks ===
    {"label": "Reservation hold-on then continue (Sarah)", "lang": "en-US",
     "turns": ["Hi, I want to book a table",
               "Hold on, let me check my calendar",
               "OK, four people on Saturday at 8 pm",
               "I'm Sarah",
               "Yes"]},
    {"label": "Reservation party correction (Brian)", "lang": "en-US",
     "turns": ["Hi, table for four tomorrow at 8",
               "Actually make it six people",
               "Brian",
               "Yes"]},
    {"label": "Reservation time correction (Linda)", "lang": "en-US",
     "turns": ["Reservation for two on Friday at 6 pm",
               "Linda",
               "Wait, change that to 7:30 pm",
               "Yes"]},
    {"label": "Very early lunch (Robert)", "lang": "en-US",
     "turns": ["Can I get a table for two at 11:30 am tomorrow",
               "Robert",
               "Yes"]},
    {"label": "Very late dinner Friday (Hassan)", "lang": "en-US",
     "turns": ["Late table for four Friday at 1 am",
               "Hassan",
               "Yes"]},
    {"label": "HOT corporate 30 guests (Margaret)", "lang": "en-US",
     "turns": ["I'd like to host a corporate dinner for thirty",
               "I'm Margaret from Apple",
               "Next Wednesday at 7",
               "Yes"]},

    # === Special preferences explicitly ===
    {"label": "Vegan dinner reservation (Chloe)", "lang": "en-US",
     "turns": ["A vegan dinner for two tomorrow at 8 pm",
               "Chloe",
               "Yes"]},
    {"label": "Stroller and high chair (Priya)", "lang": "en-US",
     "turns": ["Table for three with a stroller and high chair tomorrow at 7",
               "Priya",
               "Yes"]},
    {"label": "Wheelchair access (George)", "lang": "en-US",
     "turns": ["Reservation for two, we'll need wheelchair access, tomorrow at 6 pm",
               "George",
               "Yes"]},
    {"label": "Quiet table proposal (Ethan)", "lang": "en-US",
     "turns": ["Hi, table for two on Friday at 8 — quiet table please, I'm proposing",
               "Ethan",
               "Yes"]},

    # === Menu / wine / cocktail questions ===
    {"label": "Menu — wine list", "lang": "en-US",
     "turns": ["Do you have a wine list?"]},
    {"label": "Menu — caviar price", "lang": "en-US",
     "turns": ["How much is your caviar?"]},
    {"label": "Menu — what cocktails", "lang": "en-US",
     "turns": ["What cocktails do you have?"]},
    {"label": "Menu — corkage fee", "lang": "en-US",
     "turns": ["Do you have a corkage fee?"]},
    {"label": "Menu — gluten-free dessert", "lang": "en-US",
     "turns": ["Do you have any gluten-free desserts?"]},

    # === FAQ / operations ===
    {"label": "FAQ — dress code", "lang": "en-US",
     "turns": ["What's the dress code?"]},
    {"label": "FAQ — pets allowed", "lang": "en-US",
     "turns": ["Are dogs allowed on your patio?"]},
    {"label": "FAQ — private dining room capacity", "lang": "en-US",
     "turns": ["How big is your private dining room?"]},
    {"label": "FAQ — parking near", "lang": "en-US",
     "turns": ["Where can I park nearby?"]},

    # === Russian variations ===
    {"label": "RU vegan with kid (Светлана)", "lang": "ru-RU",
     "turns": ["Здравствуйте, столик на двух взрослых и одного ребёнка завтра в семь",
               "Меня зовут Светлана",
               "Да, верно"]},
    {"label": "RU late night (Артём)", "lang": "ru-RU",
     "turns": ["Можно ли забронировать столик в пятницу в полночь",
               "Артём",
               "Да, всё верно"]},
    {"label": "RU big group HOT (Олег)", "lang": "ru-RU",
     "turns": ["Хочу провести юбилей на двадцать человек",
               "Меня зовут Олег",
               "В субботу в восемь вечера",
               "Да"]},
    {"label": "RU change party (Татьяна)", "lang": "ru-RU",
     "turns": ["Бронь на четверых завтра в восемь",
               "Меня зовут Татьяна",
               "Подождите, лучше на пятерых",
               "Да"]},
    {"label": "RU hours specific day", "lang": "ru-RU",
     "turns": ["До скольки вы работаете в субботу?"]},

    # === Spanish variations ===
    {"label": "ES private event 12 (Camila)", "lang": "es-US",
     "turns": ["Quisiera celebrar mi cumpleaños con doce personas",
               "Soy Camila",
               "El sábado a las nueve",
               "Sí, correcto"]},
    {"label": "ES wine pairing question", "lang": "es-US",
     "turns": ["¿Tienen maridaje de vinos?"]},
    {"label": "ES change time (Roberto)", "lang": "es-US",
     "turns": ["Una reserva para tres mañana a las ocho",
               "Soy Roberto",
               "Espera, mejor a las nueve",
               "Sí"]},

    # === Mixed: question + booking ===
    {"label": "Valet question then book (Tom)", "lang": "en-US",
     "turns": ["Do you have valet parking? And I'd like to book a table for two on Friday at 7 pm",
               "I'm Tom",
               "Yes"]},

    # === Edge cases ===
    {"label": "Caller hangs up after intent only", "lang": "en-US",
     "turns": ["Hi, I want to book a table"]},  # Stops here — should be in_progress
    {"label": "All-allergens dinner (Rachel)", "lang": "en-US",
     "turns": ["Table for two tomorrow at 7, severe nut and dairy allergy, vegan only please",
               "Rachel",
               "Yes"]},
]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--token", default=None)
    parser.add_argument("--only", default=None)
    args = parser.parse_args()

    token = args.token or os.environ.get("TWILIO_AUTH_TOKEN") or _load_dotenv_token()
    if not token:
        raise SystemExit("no auth token")

    selected = [s for s in SCENARIOS_V2 if not args.only or args.only.lower() in s["label"].lower()]
    print(f"Running {len(selected)} v2 scenario(s) against {args.base}")
    for scenario in selected:
        try:
            await run_one(args.base, scenario, token)
        except Exception as exc:
            print(f"  ERROR: {exc}")
        await asyncio.sleep(0.6)
    print("\nDone. Open /dashboard to see the calls.")


if __name__ == "__main__":
    asyncio.run(main())
