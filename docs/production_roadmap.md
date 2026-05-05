# Production Roadmap (Premium Voice + SevenRooms)

## Phase 1 - Current MVP (done)
- Twilio webhook call handling
- STT/TTS via ConversationRelay WebSocket loop
- Qualification + lead persistence
- Recording metadata callbacks
- CRM/Slack/SevenRooms adapter fanout

## Phase 2 - Human-like voice tuning
- Tune ElevenLabs voice IDs per language/persona
- Add streaming token replies from LLM for lower perceived latency
- Add explicit style guardrails (brevity, empathy, interruption recovery)
- Add barge-in resume policy per intent type

## Phase 3 - SevenRooms direct booking
- Obtain venue API contract/sandbox credentials from SevenRooms
- Replace adapter payload mapper with venue-specific schema
- Add availability pre-check before confirmation
- Add booking confirmation + fallback path to human host if reservation fails

## Phase 4 - Conversation analytics pipeline
- Persist recording URLs and call metadata
- Auto-transcribe after recording completion
- Store structured analytics tags:
  - intent accuracy
  - sentiment / escalation risk
  - missed-opportunity reasons
- Daily ops summary pushed to Slack/email
