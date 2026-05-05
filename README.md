<h3 align="center">AI Voice Receptionist</h3>

<p align="center"><em>24/7 phone host that answers, qualifies, records and books.</em></p>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Twilio Voice](https://img.shields.io/badge/Twilio-Voice-F22F46?logo=twilio&logoColor=white)](https://www.twilio.com/voice)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ed?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Production-style **AI voice receptionist** for upscale hospitality:
- answers inbound calls 24/7
- qualifies caller intent (reservation / private event / takeout)
- captures lead details in structured format
- pushes to CRM + Slack
- records call audio and stores recording metadata for QA analytics

---

## What is implemented now

### Voice flow (working MVP)
- Twilio Voice webhook: `/webhooks/voice/incoming`
- Real-time speech loop via `<Connect><ConversationRelay>` + WebSocket
- ElevenLabs TTS provider and Deepgram STT provider via Twilio ConversationRelay
- Interruption support (caller can barge in while the agent is speaking)
- Runtime language switching (`en-US`, `es-US`, `ru-RU`)
- Streaming reply tokens back to Twilio (lower perceived latency)
- Multi-turn qualification state machine with SQLite persistence

### Recording and analytics
- Auto-start recording on inbound calls (`record_calls=true`)
- Recording status callback endpoint: `/webhooks/voice/recording-status`
- Call-level recording metadata persisted (`recording_sid`, `recording_url`, duration)
- Summary analytics endpoint: `/analytics/summary`

### Integrations
- Slack lead notifications
- Generic CRM webhook push
- SevenRooms reservation handoff adapter (optional, disabled by default)

---

## Human-like voice quality

The default setup in this repo is quality-first:
- `VOICE_MODE=conversationrelay`
- Twilio ConversationRelay for low-latency full-duplex voice interactions
- ElevenLabs voices for natural prosody and less robotic tone
- Backchannel handling (`ignoreBackchannel=true`) to reduce accidental interruptions from short acknowledgements

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

Set Twilio Voice webhook URL to:

`https://<your-ngrok-domain>/webhooks/voice/incoming`

---

## Environment variables

See `.env.example`.

Important ones:
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
- `APP_BASE_URL` (used for recording status callback)
- `VOICE_MODE`, `CONVERSATIONRELAY_TTS_PROVIDER`, `CONVERSATIONRELAY_STT_PROVIDER`
- `LLM_STREAMING_ENABLED`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- `CRM_WEBHOOK_URL`, `SLACK_WEBHOOK_URL`
- `ENABLE_SEVENROOMS` (default `false`)
- `SEVENROOMS_API_BASE_URL`, `SEVENROOMS_API_KEY`, `SEVENROOMS_VENUE_ID` (only if enabled)

---

## API endpoints

- `POST /webhooks/voice/incoming` - initial Twilio Voice webhook
- `POST /webhooks/voice/collect` - speech/DTMF turn processing
- `POST /webhooks/voice/relay-action` - ConversationRelay action callback
- `WS /ws/conversationrelay` - real-time Twilio ConversationRelay socket
- `POST /webhooks/voice/recording-status` - recording lifecycle callback
- `GET /analytics/summary` - basic operational analytics
- `GET /healthz` - health check
- `GET /metrics` - Prometheus-style request metrics

---

## Tests

```bash
pytest -v
ruff check .
```

---

## Notes on SevenRooms

SevenRooms integrations can be account/partner dependent. In this project they are **off by default** (`ENABLE_SEVENROOMS=false`).  
When you are ready, enable the flag and fill SevenRooms credentials; the adapter layer in `app/services/sevenrooms_client.py` is already wired.

## Docs

- `docs/architecture.md`
- `docs/twilio_setup.md`
- `docs/case_study.md`
- `docs/production_roadmap.md`

---

MIT License.
