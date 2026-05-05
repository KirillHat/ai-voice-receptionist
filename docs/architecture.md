# Architecture

## High-level flow

```text
Caller
  -> Twilio Voice Number
      -> /webhooks/voice/incoming
          -> SQLite call session (state)
          -> optional: start call recording
          -> TwiML <Connect><ConversationRelay>
          -> WebSocket /ws/conversationrelay

ConversationRelay messages
  -> setup / prompt / interrupt events
  -> app processes prompt text
      -> qualifier state machine
      -> when complete: create Lead
      -> fan-out:
          - SevenRooms adapter
          - CRM webhook
          - Slack alert
      -> send text token + optional language switch command

Recording lifecycle
  -> /webhooks/voice/recording-status
      -> persist recording SID/URL/status/duration

Ops visibility
  -> /analytics/summary
  -> /metrics
```

## Components

- `app/webhooks/voice.py`: Twilio webhook handlers + fanout orchestration
- `app/services/conversationrelay_twiml.py`: `<ConversationRelay>` TwiML builder
- `app/services/language_router.py`: language normalization + localized prompts
- `app/services/llm_stream.py`: streaming token reply generator (OpenAI or local fallback)
- `app/services/qualifier.py`: deterministic qualification flow
- `app/services/sevenrooms_client.py`: reservation handoff adapter
- `app/services/crm_client.py`: generic JSON CRM sink
- `app/services/slack_client.py`: team notifications
- `app/storage/models.py`: call session + leads + recording metadata

## Production extension path

1. Add streaming LLM response tokens (instead of one-shot localized templates)
2. Add post-call transcript analytics (sentiment, missed-booking reasons, objections)
3. Add human handoff policy and fallback routing for unresolved cases
