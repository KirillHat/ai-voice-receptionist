# Production Roadmap

## Phase 1 — MVP voice flow ✅

- [x] Twilio webhook + signature validation
- [x] STT/TTS via ConversationRelay WebSocket loop
- [x] Multi-turn qualifier with SQLite persistence
- [x] Recording lifecycle + status callbacks
- [x] Lead fan-out: Slack / generic CRM webhook / SevenRooms adapter
- [x] Render / Railway deploy assets

## Phase 2 — Human-like voice tuning ✅

- [x] Streaming reply tokens via OpenAI
- [x] Mid-call language switching (en-US / es-US / ru-RU)
- [x] Localized holding phrases ("One moment", "Одну секунду", "Un momento")
- [x] Interrupt acknowledgement before resuming
- [x] Pre-reply pause + holding-phrase delay scaled to utterance length
- [x] Deterministic disfluency sprinkler (low-rate "of course" / "конечно")
- [x] Name-prefix scrubber so the agent stops opening every reply with the guest's name
- [x] Female TTS voice anchor in the system prompt with explicit no-name-prefix rule
- [x] Deterministic confirmation on the completion turn (no LLM hallucinating party_size or dropping the date)
- [x] Multilingual datetime NLU: relative days, weekdays, day-month-name, PM/AM modifiers, year roll-forward
- [x] Booking-intent guard for the FAQ matcher so "book a private event" doesn't get hijacked into the PDR-capacity FAQ
- [x] Caller profile persistence — preferred language, pace, formality, intent histogram restored on the next call

## Phase 3 — Test infrastructure ✅

- [x] Pytest with TestClient WebSocket integration tests
- [x] YAML scenario harness driving the in-process WebSocket (no real Twilio cost)
- [x] 23 declarative scenarios: en/ru/es happy paths, FAQ, regressions, large-party flow
- [x] `scripts/simulate_call.py` — CLI WebSocket simulator
- [x] `scripts/scenario_report.py` — non-failing Markdown report with full transcripts
- [x] `scripts/transcribe.py` and `scripts/analyze_real_calls.py` — Whisper transcripts of recorded calls, merged with the in-app transcript
- [x] Live override via `SCENARIO_WS_URL` / `SCENARIO_HTTP_URL` to point pytest at a deployed instance

## Phase 4 — SevenRooms direct booking

- [ ] Obtain venue API contract / sandbox credentials from SevenRooms
- [ ] Replace adapter payload mapper with venue-specific schema
- [ ] Availability pre-check before confirmation
- [ ] Booking confirmation + fallback path to a human host if reservation API fails

## Phase 5 — Conversation analytics pipeline

- [ ] Move SQLite to Railway persistent volume or managed Postgres
- [ ] Auto-Whisper after recording completion → diff against in-app transcript to surface STT misreads
- [ ] Structured analytics tags per call (intent accuracy, sentiment, escalation risk, missed-opportunity reason)
- [ ] Daily ops summary pushed to Slack / email

## Phase 6 — Human handoff and recovery

- [ ] Detect explicit corrections ("there's a mistake, I said two, not eight") and reset the affected field
- [ ] Auto-flag `requires_manager_approval` for parties ≥ 12 (already labeled HOT, but the agent should not promise the booking is final)
- [ ] Press / lost-and-found / job-inquiry intents routed to dedicated capture flows
- [ ] Live transfer to a human if the agent fails the same field three times

## Phase 7 — Outbound flows

- [ ] Pre-shift reservation-confirmation calls using the host-manual script
  (already documented in `docs/brand_profile.md` §4.4)
- [ ] Post-call SMS recap to the caller
