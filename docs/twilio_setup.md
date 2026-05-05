# Twilio Setup

## 1) Buy/configure voice number

- Twilio Console -> Phone Numbers -> Buy Number
- Enable Voice capability
- Set incoming webhook URL to:
  - `https://YOUR_DOMAIN/webhooks/voice/incoming`
  - Method: `POST`

## 2) App configuration

In `.env`:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `APP_BASE_URL` (public app URL)
- `VOICE_MODE=conversationrelay`
- `CONVERSATIONRELAY_TTS_PROVIDER=ElevenLabs`
- `CONVERSATIONRELAY_STT_PROVIDER=Deepgram`
- `OPENAI_API_KEY` (optional, for streamed AI responses; without it local fallback replies are used)

Keep signature validation on in production:
- `TWILIO_VALIDATE_SIGNATURE=true`
- `DEBUG_SKIP_TWILIO_SIGNATURE=false`

## 3) Recording callback

The app starts recording via API when calls arrive and sends status updates to:
- `/webhooks/voice/recording-status`

Ensure `APP_BASE_URL` is public and correct, otherwise recording callback delivery will fail.

## 4) ConversationRelay socket

ConversationRelay will connect to your WebSocket endpoint:
- `wss://YOUR_DOMAIN/ws/conversationrelay`

No extra Twilio console setting is required for this URL because it is embedded in the TwiML returned by `/webhooks/voice/incoming`.

## 5) Local testing

```bash
uvicorn app.main:app --reload --port 8000
ngrok http 8000
```

Use ngrok URL for Twilio incoming webhook.
