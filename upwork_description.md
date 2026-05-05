# AI Voice Receptionist (Twilio + FastAPI + CRM/SevenRooms)

Built a production-style 24/7 AI voice receptionist for an upscale-restaurant use case.

## What it does
- Accepts inbound phone calls through Twilio Voice
- Understands speech (STT), responds via TTS, and runs multi-turn qualification
- Captures intent + booking details (reservation/private event/takeout)
- Writes structured lead data to CRM webhook
- Sends instant Slack alerts for staff
- Supports optional SevenRooms reservation handoff via adapter layer (disabled by default)
- Starts and tracks call recordings for QA/analytics

## Stack
- FastAPI (Python)
- Twilio Voice + ConversationRelay (webhooks, real-time WebSocket loop, interruption handling)
- ElevenLabs TTS + Deepgram STT through Twilio ConversationRelay
- SQLite + SQLAlchemy (session state + lead persistence)
- Slack webhook
- Generic CRM + SevenRooms integration adapters

## Production notes
- Signature validation for Twilio webhooks
- Signature validation for ConversationRelay WebSocket handshake
- Recording status callback support
- Analytics summary endpoint for operations visibility
- Multi-language switching during live calls (`en-US`, `es-US`, `ru-RU`)
