# Architecture

## High-level flow

```text
Caller
  → Twilio Voice number
      → POST /webhooks/voice/incoming  (signature validated)
          → CallSession persisted (SQLite, async)
          → optional: API call to start dual-channel recording
          → TwiML: <Connect><ConversationRelay>
          → Twilio opens WebSocket to /ws/conversationrelay

ConversationRelay messages on the WS:
  setup            → load CallerProfile, restore preferred_language
  prompt (partial) → buffered (Twilio sometimes splits an utterance)
  prompt (last)    → see "Per-turn pipeline" below
  interrupt        → mark "interrupted recently" for the next reply
  error            → log voice.relay_error_message

Recording lifecycle:
  POST /webhooks/voice/recording-status
      → CallSession.recording_sid / _url / _status / _duration_sec persisted

Operational visibility:
  GET /analytics/summary             — aggregate counts
  GET /analytics/calls               — recent CallSessions
  GET /analytics/calls/{call_sid}    — full transcript + captured fields
  GET /metrics                       — Prometheus-style HTTP request metrics
  GET /healthz
```

## Per-turn pipeline (when a `prompt:last` arrives)

```text
1. compute_timing(user_input)
   — utterance length → pre-reply pause + holding-phrase delay

2. normalize_language(stt_lang, user_input)
   — Cyrillic / Spanish triggers / explicit "speak Russian" phrases
   — if changed, send {type: "language", ttsLanguage, transcriptionLanguage}

3. faq.match_faq(user_input, lang)
   — booking-intent guard skips FAQ when caller is clearly trying to book
   — on hit: log voice.faq_answered, write to transcript, return canonical
     answer (en/es/ru), no LLM, no qualifier

4. qualifier.ingest_turn(call, user_input)
   — extract_intent (priority private_event > takeout > reservation, recheck
     while still 'general')
   — extract guest_name, party_size (digit-with-cue OR word-with-cue OR
     word+noun adjacency; bare numbers ignored), reservation_datetime via
     datetime_nlu
   — state-aware fallbacks for short replies right after we asked for that
     specific field; time-phrase guard so 'в семь часов' is never party=7
   — returns TurnDecision(prompt, completed, missing_field)

5. caller_profile.update_profile_from_turn(...)
   — speech_pace, formality, intent histogram

6. if decision.completed:
       send language_router.build_reply(call, missing_field=None, lang)
       — DETERMINISTIC, no LLM. Avoids hallucinations like party=8 when
         caller said 2.
       fan-out lead to Slack / CRM / SevenRooms
       continue

7. asyncio.sleep(timing.pause_ms / 1000)

8. if interrupted_recently:
       send prosody.interruption_ack(lang)  ('Of course' / 'Конечно' / 'Claro')

9. llm_stream.stream_reply(call, user_input, missing_field, lang,
                           style_profile, caller_profile_context)
   — first chunk: prosody.strip_leading_name_address scrubs
     'Mr. Kirill,' / 'Уважаемый Кирилл,' / '<Name>,' openers
   — first chunk: prosody.maybe_add_disfluency may prepend
     'Of course,' / 'Конечно,' (default ~5% of turns)
   — if no first chunk within timing.holding_delay_ms (default 8s/12s):
       send prosody.holding_phrase(lang)  ('One moment, please.')
   — stream chunks back to Twilio with type=text, last marker on the final
```

## Storage model

```text
CallSession      one row per call_sid
  call_sid, caller_phone, intent, guest_name, party_size,
  reservation_datetime (ISO-8601 string), special_notes,
  recording_sid / _url / _status / _duration_sec,
  status (in_progress / qualified), turn_count,
  transcript (JSON list of {role, text}), created_at, updated_at

Lead             one row per qualified call
  call_sid, caller_phone, intent, guest_name, party_size,
  reservation_datetime, special_notes, qualification_label
  (HOT / WARM / COLD per qualifier.qualification_label),
  summary, created_at

CallerProfile    one row per caller_phone (re-used across calls)
  caller_phone, preferred_language, speech_pace, formality,
  typical_intents (JSON histogram), created_at, updated_at
```

## Components

| File | Role |
|---|---|
| `app/webhooks/voice.py` | Twilio HTTP + WebSocket handlers, fan-out orchestration, `/analytics/calls*` endpoints |
| `app/services/conversationrelay_twiml.py` | `<ConversationRelay>` TwiML builder with optional per-locale voice override |
| `app/services/qualifier.py` | Intent priority, state-machine, multilingual extractors, deterministic natural-language summary |
| `app/services/datetime_nlu.py` | Spoken datetime → ISO-8601 (en/ru/es), month-name + day, PM/AM modifiers, year roll-forward |
| `app/services/language_router.py` | Language detection + localized prompts and confirmations |
| `app/services/faq.py` | Deterministic FAQ matcher with booking-intent guard |
| `app/services/llm_stream.py` | Streaming OpenAI Chat Completions with hardened system prompt |
| `app/services/prosody.py` | Style hints, holding phrase, interrupt ack, name-opener scrubber, disfluencies |
| `app/services/turn_taking.py` | Pre-reply pause + holding-phrase delay scaled to utterance length |
| `app/services/caller_profile.py` | Per-phone preference persistence and prompt-context formatter |
| `app/services/sevenrooms_client.py` | Reservation handoff adapter (gated by `ENABLE_SEVENROOMS`) |
| `app/services/crm_client.py` | Generic JSON CRM webhook |
| `app/services/slack_client.py` | Lead notifications |
| `app/storage/models.py` | `CallSession`, `Lead`, `CallerProfile` |

## Test layers

| Layer | Where | What it covers |
|---|---|---|
| Unit | `tests/test_qualifier.py`, `tests/test_faq.py` | Extractors and topic detection in isolation |
| WebSocket integration | `tests/test_voice_webhook.py` | Healthz, FAQ shortcut, holding phrase under slow LLM, interrupt ack, partial-prompt buffering |
| End-to-end YAML scenarios | `tests/test_scenarios.py` (auto-discovers `scenarios/*.yaml`) + `scripts/scenario_report.py` for a Markdown transcript review | Drives the in-process WebSocket like Twilio does — validates per-turn replies, language switches, and final captured fields against expectations declared in YAML |

23 scenarios today: en/ru/es happy paths, FAQ in three languages, the
large-party manager-approval flow, and explicit regression cases for every
bug found in real calls (greedy party-size, missed date, time-as-party
hijack, internal-field echo in confirmation, repeated-name opener,
LLM hallucinating party_size at confirmation time).

## Deployment

- Repo: <https://github.com/KirillHat/ai-voice-receptionist>
- Runtime: Railway (Dockerfile, persistent process; `$PORT` honored)
- TTS provider on prod: ElevenLabs (default voice). Per-locale overrides
  via `CONVERSATIONRELAY_VOICE_*` — the voice key MUST be one Twilio
  registered for that provider, otherwise Twilio returns error 64101.
- Twilio webhook: `https://ai-voice-production-eb9e.up.railway.app/webhooks/voice/incoming` (POST)
- WebSocket signature validation: `_validate_ws_signature` retries with
  `https`/`http` swap because Railway terminates SSL at the edge and
  Twilio signs the original `wss://`/`https://` URL.

## Production extension path

1. Persistent storage on Railway (volume on `/app/data`, or attach a
   managed Postgres).
2. Post-call transcript analytics (Whisper diff vs. app transcript →
   sentiment / missed-booking reasons / objections).
3. Human handoff policy: when qualifier flags `requires_manager_approval`
   or sees a clear correction signal ("there's a mistake, I said two,
   not eight"), reset the affected field and ask again.
4. Outbound reservation-confirmation calls using the same scripts (host
   manual phone-confirmation script is already documented in
   `docs/brand_profile.md` §4.4).
