"""Twilio Voice webhooks for inbound AI receptionist calls."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Form,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response
from sqlalchemy import func, select
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient

from app.config import get_settings
from app.services import (
    conversationrelay_twiml,
    crm_client,
    faq,
    language_router,
    llm_stream,
    qualifier,
    sevenrooms_client,
    slack_client,
    twiml_voice,
)
from app.storage.db import session_scope
from app.storage.models import CallSession, Lead

log = structlog.get_logger()
router = APIRouter()

_settings = get_settings()
_validator = RequestValidator(_settings.twilio_auth_token.get_secret_value())
_twilio = TwilioClient(
    _settings.twilio_account_sid,
    _settings.twilio_auth_token.get_secret_value(),
)


async def _validate_signature(request: Request) -> None:
    settings = get_settings()
    if settings.debug_skip_twilio_signature or not settings.twilio_validate_signature:
        return

    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}

    candidate_urls = [url]
    if url.startswith("http://"):
        candidate_urls.append("https://" + url.removeprefix("http://"))
    elif url.startswith("https://"):
        candidate_urls.append("http://" + url.removeprefix("https://"))

    for candidate in candidate_urls:
        if _validator.validate(candidate, params, signature):
            return

    log.warning("twilio.invalid_signature", url=url)
    raise HTTPException(status_code=403, detail="Invalid Twilio signature")


async def _validate_ws_signature(websocket: WebSocket) -> bool:
    settings = get_settings()
    if settings.debug_skip_twilio_signature or not settings.twilio_validate_signature:
        return True

    signature = websocket.headers.get("x-twilio-signature", "")
    params = {k: str(v) for k, v in websocket.query_params.items()}

    ws_url = str(websocket.url)
    candidate_urls = [ws_url]
    if ws_url.startswith("wss://"):
        candidate_urls.append("https://" + ws_url.removeprefix("wss://"))
    if ws_url.startswith("ws://"):
        candidate_urls.append("http://" + ws_url.removeprefix("ws://"))

    for url in candidate_urls:
        if _validator.validate(url, params, signature):
            return True
        if _validator.validate(url, {}, signature):
            return True

    log.warning("twilio.invalid_ws_signature", url=ws_url)
    return False


@router.post("/webhooks/voice/incoming", response_class=Response)
async def voice_incoming(
    request: Request,
    background: BackgroundTasks,
    CallSid: str = Form(...),
    From: str = Form(""),
    To: str = Form(""),
) -> Response:
    await _validate_signature(request)

    async with session_scope() as session:
        call = await _get_or_create_call_session(session, call_sid=CallSid, caller_phone=From)
        call.status = "in_progress"

    log.info("voice.incoming", call_sid=CallSid, from_number=From, to_number=To)

    settings = get_settings()
    if settings.record_calls:
        background.add_task(_start_call_recording, CallSid)

    if settings.voice_mode == "conversationrelay":
        twiml = conversationrelay_twiml.conversationrelay_response()
        return Response(content=twiml, media_type="application/xml", status_code=200)

    greeting = (
        "Thank you for calling Novikov Beverly Hills. "
        "I am your AI reception assistant. "
        "In one sentence, please tell me what you need today."
    )
    twiml = twiml_voice.gather_response(prompt=greeting, action_path="/webhooks/voice/collect")
    return Response(content=twiml, media_type="application/xml", status_code=200)


@router.post("/webhooks/voice/collect", response_class=Response)
async def voice_collect(
    request: Request,
    background: BackgroundTasks,
    CallSid: str = Form(...),
    From: str = Form(""),
    SpeechResult: str = Form(""),
    Digits: str = Form(""),
    Confidence: str = Form(""),
) -> Response:
    await _validate_signature(request)

    user_input = (SpeechResult or Digits or "").strip()
    if not user_input:
        prompt = "I did not catch that. Please say your request one more time."
        twiml = twiml_voice.gather_response(prompt=prompt, action_path="/webhooks/voice/collect")
        return Response(content=twiml, media_type="application/xml", status_code=200)

    async with session_scope() as session:
        call = await _get_or_create_call_session(session, call_sid=CallSid, caller_phone=From)
        decision = qualifier.ingest_turn(call, user_input)

        lead_payload: dict[str, Any] | None = None
        if decision.completed and call.status != "qualified":
            call.status = "qualified"
            lead = _build_lead(call)
            session.add(lead)
            await session.flush()
            lead_payload = _lead_payload(lead)

    log.info(
        "voice.turn_processed",
        call_sid=CallSid,
        confidence=Confidence,
        completed=decision.completed,
        input_len=len(user_input),
    )

    if lead_payload:
        background.add_task(_fanout_lead, lead_payload)

    if decision.completed:
        twiml = twiml_voice.goodbye_response(summary_prompt=decision.prompt)
    else:
        twiml = twiml_voice.gather_response(prompt=decision.prompt, action_path="/webhooks/voice/collect")
    return Response(content=twiml, media_type="application/xml", status_code=200)


@router.post("/webhooks/voice/relay-action", response_class=Response)
async def relay_action(
    request: Request,
    CallSid: str = Form(""),
    ConversationRelayStatus: str = Form(""),
    ErrorMessage: str = Form(""),
    HandoffData: str = Form(""),
) -> Response:
    await _validate_signature(request)
    log.info(
        "voice.relay_action",
        call_sid=CallSid,
        status=ConversationRelayStatus,
        error=ErrorMessage,
        handoff_data=HandoffData,
    )
    return Response(
        content=conversationrelay_twiml.relay_action_response(),
        media_type="application/xml",
        status_code=200,
    )


@router.websocket("/ws/conversationrelay")
async def conversationrelay_ws(websocket: WebSocket) -> None:
    if not await _validate_ws_signature(websocket):
        await websocket.close(code=1008)
        return

    await websocket.accept()

    active_call_sid = ""
    active_from = ""
    active_lang = "en-US"

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            message_type = message.get("type")

            if message_type == "setup":
                active_call_sid = str(message.get("callSid", "") or "")
                active_from = str(message.get("from", "") or "")
                async with session_scope() as session:
                    call = await _get_or_create_call_session(
                        session,
                        call_sid=active_call_sid,
                        caller_phone=active_from,
                    )
                    call.status = "in_progress"
                continue

            if message_type == "interrupt":
                log.info(
                    "voice.relay_interrupt",
                    call_sid=active_call_sid,
                    utterance_until_interrupt=message.get("utteranceUntilInterrupt", ""),
                    duration_ms=message.get("durationUntilInterruptMs", 0),
                )
                continue

            if message_type == "prompt":
                if not bool(message.get("last", True)):
                    continue

                user_input = str(message.get("voicePrompt", "") or "").strip()
                stt_lang = str(message.get("lang", "") or "")
                log.info(
                    "voice.relay_prompt",
                    call_sid=active_call_sid,
                    stt_lang=stt_lang,
                    active_lang=active_lang,
                    voice_prompt=user_input,
                )
                if not user_input:
                    continue

                detected_lang = language_router.normalize_language(
                    stt_lang,
                    user_input,
                )
                if detected_lang != active_lang:
                    log.info(
                        "voice.language_switch",
                        call_sid=active_call_sid,
                        from_lang=active_lang,
                        to_lang=detected_lang,
                        trigger=user_input[:80],
                    )
                    await _send_language_switch(websocket, detected_lang)
                    active_lang = detected_lang

                faq_answer = faq.match_faq(user_input, lang=active_lang)
                if faq_answer is not None:
                    log.info(
                        "voice.faq_answered",
                        call_sid=active_call_sid,
                        topic=faq_answer.topic,
                    )
                    async with session_scope() as session:
                        call = await _get_or_create_call_session(
                            session,
                            call_sid=active_call_sid,
                            caller_phone=active_from,
                        )
                        qualifier.note_faq_turn(call, user_input, faq_answer)
                    await _send_text_token(
                        websocket,
                        faq_answer.text,
                        lang=active_lang,
                        last=True,
                    )
                    continue

                async with session_scope() as session:
                    call = await _get_or_create_call_session(
                        session,
                        call_sid=active_call_sid,
                        caller_phone=active_from,
                    )
                    decision = qualifier.ingest_turn(call, user_input)

                    lead_payload: dict[str, Any] | None = None
                    if decision.completed and call.status != "qualified":
                        call.status = "qualified"
                        lead = _build_lead(call)
                        session.add(lead)
                        await session.flush()
                        lead_payload = _lead_payload(lead)
                    chunks: list[str] = []
                    async for chunk in llm_stream.stream_reply(
                        call=call,
                        user_input=user_input,
                        missing_field=decision.missing_field,
                        lang=active_lang,
                    ):
                        chunks.append(chunk)

                if not chunks:
                    fallback = language_router.build_reply(
                        call,
                        missing_field=decision.missing_field,
                        lang=active_lang,
                    )
                    chunks = [fallback]

                for i, chunk in enumerate(chunks):
                    await _send_text_token(
                        websocket,
                        chunk,
                        lang=active_lang,
                        last=i == len(chunks) - 1,
                    )

                if lead_payload:
                    asyncio.create_task(_fanout_lead(lead_payload))
                continue

            if message_type == "error":
                log.error(
                    "voice.relay_error_message",
                    call_sid=active_call_sid,
                    description=message.get("description", ""),
                )
                continue

    except WebSocketDisconnect:
        log.info("voice.relay_disconnected", call_sid=active_call_sid)


@router.post("/webhooks/voice/recording-status")
async def recording_status_callback(
    request: Request,
    CallSid: str = Form(...),
    RecordingSid: str = Form(""),
    RecordingUrl: str = Form(""),
    RecordingStatus: str = Form(""),
    RecordingDuration: str = Form(""),
) -> dict[str, str]:
    await _validate_signature(request)

    duration: int | None = None
    if RecordingDuration.isdigit():
        duration = int(RecordingDuration)

    async with session_scope() as session:
        result = await session.execute(select(CallSession).where(CallSession.call_sid == CallSid))
        call = result.scalar_one_or_none()
        if call is None:
            call = CallSession(call_sid=CallSid, caller_phone="")
            session.add(call)
            await session.flush()
        call.recording_sid = RecordingSid or call.recording_sid
        call.recording_url = RecordingUrl or call.recording_url
        call.recording_status = RecordingStatus or call.recording_status
        if duration is not None:
            call.recording_duration_sec = duration

    log.info(
        "voice.recording_status",
        call_sid=CallSid,
        recording_sid=RecordingSid,
        status=RecordingStatus,
        duration=duration,
    )
    return {"status": "ok"}


@router.get("/analytics/summary")
async def analytics_summary() -> dict[str, Any]:
    async with session_scope() as session:
        total_calls = await session.scalar(select(func.count()).select_from(CallSession))
        qualified_calls = await session.scalar(
            select(func.count()).select_from(CallSession).where(CallSession.status == "qualified")
        )
        total_leads = await session.scalar(select(func.count()).select_from(Lead))
        avg_turns = await session.scalar(select(func.avg(CallSession.turn_count)))

    return {
        "total_calls": int(total_calls or 0),
        "qualified_calls": int(qualified_calls or 0),
        "total_leads": int(total_leads or 0),
        "avg_turns_per_call": round(float(avg_turns or 0.0), 2),
    }


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


async def _get_or_create_call_session(
    session,
    *,
    call_sid: str,
    caller_phone: str,
) -> CallSession:
    result = await session.execute(select(CallSession).where(CallSession.call_sid == call_sid))
    call = result.scalar_one_or_none()
    if call is None:
        call = CallSession(call_sid=call_sid, caller_phone=caller_phone)
        session.add(call)
        await session.flush()
    elif caller_phone and not call.caller_phone:
        call.caller_phone = caller_phone
    return call


def _build_lead(call: CallSession) -> Lead:
    label = qualifier.qualification_label(call)
    summary = qualifier.summarize(call)
    return Lead(
        call_sid=call.call_sid,
        caller_phone=call.caller_phone,
        intent=call.intent or "general",
        guest_name=call.guest_name or "Unknown",
        party_size=call.party_size,
        reservation_datetime=call.reservation_datetime,
        special_notes=call.special_notes,
        qualification_label=label,
        summary=summary,
    )


def _lead_payload(lead: Lead) -> dict[str, Any]:
    return {
        "call_sid": lead.call_sid,
        "caller_phone": lead.caller_phone,
        "intent": lead.intent,
        "guest_name": lead.guest_name,
        "party_size": lead.party_size,
        "reservation_datetime": lead.reservation_datetime,
        "special_notes": lead.special_notes,
        "qualification_label": lead.qualification_label,
        "summary": lead.summary,
    }


async def _fanout_lead(lead: dict[str, Any]) -> None:
    try:
        await sevenrooms_client.create_reservation(lead)
    except Exception as exc:  # pragma: no cover
        log.error("sevenrooms.push_failed", error=str(exc), call_sid=lead.get("call_sid"))

    try:
        await crm_client.push_lead(lead)
    except Exception as exc:  # pragma: no cover
        log.error("crm.push_failed", error=str(exc), call_sid=lead.get("call_sid"))

    try:
        await slack_client.notify_lead(lead)
    except Exception as exc:  # pragma: no cover
        log.error("slack.notify_failed", error=str(exc), call_sid=lead.get("call_sid"))


async def _send_text_token(
    websocket: WebSocket,
    text: str,
    *,
    lang: str,
    last: bool,
) -> None:
    payload = {
        "type": "text",
        "token": text,
        "lang": lang,
        "last": last,
        "interruptible": True,
        "preemptible": True,
    }
    await websocket.send_text(json.dumps(payload))


async def _send_language_switch(websocket: WebSocket, lang: str) -> None:
    payload = {
        "type": "language",
        "ttsLanguage": lang,
        "transcriptionLanguage": lang,
    }
    await websocket.send_text(json.dumps(payload))


def _absolute_url(path: str) -> str:
    settings = get_settings()
    return settings.app_base_url.rstrip("/") + "/" + path.lstrip("/")


def _start_call_recording(call_sid: str) -> None:
    settings = get_settings()
    callback_url = _absolute_url(settings.recording_status_callback_path)
    _twilio.calls(call_sid).recordings.create(
        recording_channels=settings.recording_channels,
        recording_track=settings.recording_track,
        trim=settings.recording_trim,
        recording_status_callback=callback_url,
        recording_status_callback_method="POST",
    )
