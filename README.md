<h3 align="center">AI Voice Receptionist</h3>

<p align="center"><em>24/7 phone host that answers, qualifies, records, and books — with a YAML-driven scenario harness so you don't need a phone to test it.</em></p>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Twilio Voice](https://img.shields.io/badge/Twilio-Voice-F22F46?logo=twilio&logoColor=white)](https://www.twilio.com/voice)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ed?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Production-style **AI voice receptionist** for upscale hospitality:
- answers inbound calls 24/7 in **English / Spanish / Russian** with mid-call language switching
- qualifies caller intent (`reservation` / `private_event` / `takeout`) and captures structured lead details
- pushes to Slack / CRM / SevenRooms (when configured)
- records the call, persists metadata, and exposes per-call transcripts via API
- comes with a **scenario harness** — 23 YAML scenarios run end-to-end through the WebSocket layer in ≈45 seconds, no phone calls or Twilio bills required

---

## What is implemented

### Voice flow
- Twilio Voice webhook → `<Connect><ConversationRelay>` TwiML
- WebSocket loop at `/ws/conversationrelay` with ElevenLabs TTS + Deepgram STT
- Caller-side interruption handling (barge-in)
- Mid-call language switching (`en-US` / `es-US` / `ru-RU`)
- Streaming OpenAI Chat Completions, with deterministic fallbacks and a **deterministic confirmation on the completion turn** (no LLM hallucinations on the final number / date)
- Multi-turn qualification state machine with SQLite persistence

### Conversational polish
- `services/prosody.py` — style hints, localized holding phrases ("One moment, please" / "Одну секунду, пожалуйста"), interrupt acknowledgements, deterministic disfluency sprinkler
- `services/turn_taking.py` — pre-reply pause and holding-phrase delay scale with the caller's utterance length
- `services/caller_profile.py` + `CallerProfile` model — preferred language, speech pace, formality, intent histogram persisted per `caller_phone`; restored on the next call
- Post-process in `prosody.strip_leading_name_address()` scrubs *"Mr. Kirill,"* / *"Уважаемый Кирилл,"* / *"\<Name\>,"* openers from streamed replies (gpt-4o ignores the system-prompt rule about half the time)

### Multilingual NLU (no LLM in the path)
- `services/datetime_nlu.py` — spoken datetime → ISO-8601 in business timezone (en/ru/es), day-month-name parsing (*"May 9"* / *"9 мая"* / *"9 de mayo"*), PM/AM modifiers (*"вечера"*, *"de la tarde"*, *"in the evening"*), automatic year roll-forward when a date in the past would otherwise be picked
- `services/qualifier.py` — intent priority (`private_event > takeout > reservation`), state-aware extraction of name / party-size / datetime, time-phrase guard so *"в семь часов"* never becomes `party=7`
- `services/faq.py` — deterministic FAQ matcher for hours / valet / DJ / dress code / private dining / smoking / wifi / etc.; **booking-intent guard** so *"book a private event"* doesn't get hijacked into the PDR-capacity FAQ answer

### Recording and analytics
- Auto-start recording on inbound calls; status callbacks at `/webhooks/voice/recording-status`
- `GET /analytics/summary` — total calls, qualified calls, avg turns
- `GET /analytics/calls` and `GET /analytics/calls/{call_sid}` — list calls and pull a single call's full transcript and captured fields

### Integrations
- Slack lead webhook
- Generic CRM webhook push
- SevenRooms reservation handoff adapter (off by default — set `ENABLE_SEVENROOMS=true` and fill the SevenRooms env vars when the venue's API is wired)

---

## Quickstart

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
ngrok http 8000
```

Set Twilio Voice webhook URL to `https://<your-ngrok-domain>/webhooks/voice/incoming` (POST).

---

## Tests

This project ships with **two test layers**:

```bash
# Unit + WebSocket integration (47 tests, ~22s)
pytest -v

# Same plus 23 end-to-end YAML scenarios that drive the WebSocket like Twilio does
# (in-process FastAPI TestClient — no real LLM/Twilio cost)
pytest tests/test_scenarios.py -v
```

Or generate a Markdown transcript review of every scenario:

```bash
python scripts/scenario_report.py
# writes scenarios_report.md with one section per scenario:
#   - the full caller / agent transcript
#   - captured fields (intent / name / party / datetime / label)
#   - any failed assertions
```

To run scenarios against a deployed instance instead of in-process:

```bash
SCENARIO_WS_URL=wss://your-prod-domain/ws/conversationrelay \
SCENARIO_HTTP_URL=https://your-prod-domain \
pytest tests/test_scenarios.py -v
```

---

## Real-call analysis

Every call is recorded by default. To Whisper-transcribe and review the last N production calls:

```bash
python scripts/analyze_real_calls.py --limit 6
# downloads MP3s, runs OpenAI Whisper, pulls the in-app transcript and
# Twilio per-call notifications, and writes real_calls_report.md
```

For a single call, `scripts/transcribe.py CA<call_sid>` does the same one at a time.

---

## Environment variables

See `.env.example`. The important ones:

| Var | What |
|---|---|
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Twilio creds |
| `TWILIO_VOICE_FROM` | The phone number callers dial |
| `APP_BASE_URL` | Public base URL for callbacks (Railway domain in prod) |
| `VOICE_MODE` | `conversationrelay` (recommended) or `twiml_gather` |
| `CONVERSATIONRELAY_TTS_PROVIDER` / `_STT_PROVIDER` | Default: ElevenLabs / Deepgram |
| `CONVERSATIONRELAY_TTS_VOICE` / `_VOICE_EN/_ES/_RU` | Optional voice key per locale (must be a Twilio-registered voice) |
| `LLM_STREAMING_ENABLED`, `OPENAI_API_KEY`, `OPENAI_MODEL` | LLM streaming config |
| `VOICE_HOLDING_PHRASE_DELAY_FAST_MS` / `_SLOW_MS` | When the agent emits "One moment, please" if LLM stalls. Default 8000 / 12000 ms — increase further to silence it entirely. |
| `VOICE_DISFLUENCY_RATE` | Probability (0–1) of prepending a soft acknowledgement. Default 0.05. |
| `RECORD_CALLS` | Whether to auto-start a recording on each call |
| `CRM_WEBHOOK_URL` / `SLACK_WEBHOOK_URL` | Lead fan-out targets |
| `ENABLE_SEVENROOMS` (+ `SEVENROOMS_*`) | Off by default |

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/webhooks/voice/incoming` | Twilio voice webhook |
| POST | `/webhooks/voice/collect` | Twilio Gather turn (legacy mode) |
| POST | `/webhooks/voice/relay-action` | ConversationRelay action callback |
| WS  | `/ws/conversationrelay` | Real-time ConversationRelay socket |
| POST | `/webhooks/voice/recording-status` | Recording lifecycle |
| GET  | `/analytics/summary` | Aggregate stats |
| GET  | `/analytics/calls` | Most recent calls (no transcript body) |
| GET  | `/analytics/calls/{call_sid}` | Full transcript + captured fields for one call |
| GET  | `/healthz` | Health check |
| GET  | `/metrics` | Prometheus-style request metrics |

---

## Project structure

```
app/
  main.py                       — FastAPI app, lifespan, observability middleware
  config.py                     — pydantic-settings, env-var schema
  observability.py              — request metrics
  services/
    conversationrelay_twiml.py  — TwiML for <ConversationRelay>
    twiml_voice.py              — fallback Gather TwiML
    qualifier.py                — intent + state machine + multilingual extractors
    datetime_nlu.py             — multilingual datetime → ISO-8601
    faq.py                      — deterministic FAQ matcher (en/ru/es)
    language_router.py          — language detection, localized prompts
    llm_stream.py               — OpenAI streaming + system prompt
    prosody.py                  — holding phrase, name-prefix scrubber, disfluencies
    turn_taking.py              — pause / holding-phrase timing per utterance length
    caller_profile.py           — per-phone preferences, restored on the next call
    crm_client.py               — generic CRM webhook
    slack_client.py             — Slack lead alerts
    sevenrooms_client.py        — SevenRooms reservation adapter (gated)
  storage/
    db.py / models.py           — async SQLAlchemy: CallSession, Lead, CallerProfile
  webhooks/
    voice.py                    — all Twilio HTTP + WebSocket handlers

scenarios/                       — 23 YAML scenarios (en/ru/es)
scripts/
  simulate_call.py              — CLI WebSocket simulator (one-off or YAML)
  scenario_report.py            — non-failing harness → scenarios_report.md
  transcribe.py                 — Whisper one call + merge with app transcript
  analyze_real_calls.py         — Whisper N recent calls + Markdown report
docs/
  architecture.md
  brand_profile.md              — full brand & host knowledge base for the agent
  twilio_setup.md
  case_study.md
  production_roadmap.md
tests/
  test_qualifier.py
  test_faq.py
  test_voice_webhook.py         — WebSocket integration: holding phrase, interrupt ack, partial-prompt buffering
  test_scenarios.py             — auto-discovers every YAML in scenarios/
```

---

## Docs

- [`docs/architecture.md`](docs/architecture.md) — high-level component map
- [`docs/brand_profile.md`](docs/brand_profile.md) — single source of truth for what the agent knows about the venue and how it should sound
- [`docs/twilio_setup.md`](docs/twilio_setup.md)
- [`docs/case_study.md`](docs/case_study.md)
- [`docs/production_roadmap.md`](docs/production_roadmap.md)

MIT License.
