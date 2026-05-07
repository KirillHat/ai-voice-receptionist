"""Twilio Voice webhooks for inbound AI receptionist calls."""

from __future__ import annotations

import asyncio
import json
from time import monotonic
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
    caller_profile,
    conversationrelay_twiml,
    crm_client,
    faq,
    language_router,
    llm_stream,
    phrase_metrics,
    prosody,
    qualifier,
    sevenrooms_client,
    slack_client,
    turn_taking,
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

    settings = get_settings()
    active_call_sid = ""
    active_from = ""
    active_lang = settings.conversationrelay_primary_language
    profile_context = ""
    buffered_prompt_parts: list[str] = []
    last_interrupt_at = 0.0
    saw_interrupt = False
    last_caller_activity_at = monotonic()
    silence_nudge_sent = False

    try:
        while True:
            # Poll more often than the nudge threshold so we don't oversleep
            # past the silence boundary on slow callers.
            poll_timeout = max(0.4, settings.voice_silence_nudge_sec / 5)
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=poll_timeout
                )
            except asyncio.TimeoutError:
                # No message for 5s. Decide whether to nudge or end the call.
                idle = monotonic() - last_caller_activity_at
                if (
                    not silence_nudge_sent
                    and idle >= settings.voice_silence_nudge_sec
                    and active_call_sid
                ):
                    log.info(
                        "voice.silence_nudge",
                        call_sid=active_call_sid,
                        idle_sec=int(idle),
                    )
                    await _send_text_token(
                        websocket,
                        prosody.silence_nudge(active_lang),
                        lang=active_lang,
                        last=True,
                    )
                    silence_nudge_sent = True
                    continue
                if (
                    silence_nudge_sent
                    and idle >= settings.voice_silence_endcall_sec
                    and active_call_sid
                ):
                    log.info(
                        "voice.silence_giveup",
                        call_sid=active_call_sid,
                        idle_sec=int(idle),
                    )
                    await _send_text_token(
                        websocket,
                        prosody.silence_giveup(active_lang),
                        lang=active_lang,
                        last=True,
                    )
                    await asyncio.sleep(0.3)
                    await websocket.close()
                    return
                continue
            message = json.loads(raw)
            message_type = message.get("type")

            if message_type == "setup":
                active_call_sid = str(message.get("callSid", "") or "")
                active_from = str(message.get("from", "") or "")
                returning_greeting: str | None = None
                async with session_scope() as session:
                    call = await _get_or_create_call_session(
                        session,
                        call_sid=active_call_sid,
                        caller_phone=active_from,
                    )
                    call.status = "in_progress"
                    profile = await caller_profile.get_or_create_profile(session, active_from)
                    if profile:
                        if profile.preferred_language:
                            active_lang = profile.preferred_language
                        if caller_profile.is_returning_caller(profile):
                            returning_greeting = caller_profile.returning_caller_greeting(
                                profile, active_lang
                            )
                        caller_profile.mark_call_started(profile)
                    profile_context = caller_profile.profile_prompt_context(profile)
                if active_lang != settings.conversationrelay_primary_language:
                    await _send_language_switch(websocket, active_lang)
                if returning_greeting:
                    await _send_text_token(
                        websocket,
                        returning_greeting,
                        lang=active_lang,
                        last=True,
                    )
                continue

            if message_type == "interrupt":
                log.info(
                    "voice.relay_interrupt",
                    call_sid=active_call_sid,
                    duration_ms=message.get("durationUntilInterruptMs", 0),
                )
                saw_interrupt = True
                last_interrupt_at = monotonic()
                continue

            if message_type == "prompt":
                prompt_chunk = str(message.get("voicePrompt", "") or "").strip()
                if not bool(message.get("last", True)):
                    if prompt_chunk:
                        buffered_prompt_parts.append(prompt_chunk)
                    continue

                if prompt_chunk:
                    buffered_prompt_parts.append(prompt_chunk)
                user_input = " ".join(buffered_prompt_parts).strip()
                buffered_prompt_parts = []
                # Caller spoke a complete utterance — reset silence tracking.
                last_caller_activity_at = monotonic()
                silence_nudge_sent = False
                stt_lang = str(message.get("lang", "") or "")
                timing = turn_taking.compute_timing(user_input)
                interrupted_recently = saw_interrupt and (
                    monotonic() - last_interrupt_at <= settings.voice_interrupt_ack_window_sec
                )
                saw_interrupt = False
                log.info(
                    "voice.relay_prompt",
                    call_sid=active_call_sid,
                    stt_lang=stt_lang,
                    active_lang=active_lang,
                    input_len=len(user_input),
                    utterance_kind=timing.utterance_kind,
                )
                if not user_input:
                    continue

                # Caller asked us to wait ('hold on, let me check the
                # calendar'). Acknowledge once, then go silent — do NOT
                # advance the qualifier or invoke the LLM. The next time
                # the caller speaks we resume the flow normally.
                if prosody.detect_hold_request(user_input):
                    log.info(
                        "voice.hold_request_detected",
                        call_sid=active_call_sid,
                        input_len=len(user_input),
                    )
                    await _send_text_token(
                        websocket,
                        prosody.hold_acknowledgement(active_lang),
                        lang=active_lang,
                        last=True,
                    )
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
                        trigger_len=min(len(user_input), 80),
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
                        # Even when the FAQ matcher owns the spoken reply,
                        # silently extract any guest fields the caller
                        # mentioned in the same breath ('I'm John, and I
                        # have a nut allergy'). The TurnDecision drives the
                        # qualified-state transition; the spoken reply is
                        # the FAQ answer.
                        silent_decision = qualifier.ingest_turn(
                            call, user_input, lang=active_lang
                        )
                        if silent_decision.completed and call.status != "qualified":
                            call.status = "qualified"
                        qualifier.note_faq_turn(call, user_input, faq_answer)
                        profile = await caller_profile.get_or_create_profile(session, active_from)
                        if profile:
                            caller_profile.update_profile_from_turn(
                                profile,
                                utterance=user_input,
                                detected_lang=active_lang,
                                intent=call.intent,
                                guest_name=call.guest_name,
                            )
                            profile_context = caller_profile.profile_prompt_context(profile)
                    if interrupted_recently:
                        await _send_text_token(
                            websocket,
                            prosody.interruption_ack(active_lang),
                            lang=active_lang,
                            last=False,
                        )
                    await _send_text_token(
                        websocket,
                        faq_answer.text,
                        lang=active_lang,
                        last=True,
                    )
                    continue

                lead_payload: dict[str, Any] | None = None
                # Keep DB work short; do not hold a DB transaction while awaiting LLM/network I/O.
                async with session_scope() as session:
                    call = await _get_or_create_call_session(
                        session,
                        call_sid=active_call_sid,
                        caller_phone=active_from,
                    )
                    decision = qualifier.ingest_turn(call, user_input, lang=active_lang)
                    if decision.completed and call.status != "qualified":
                        call.status = "qualified"
                        lead = _build_lead(call)
                        session.add(lead)
                        await session.flush()
                        lead_payload = _lead_payload(lead)
                    profile = await caller_profile.get_or_create_profile(session, active_from)
                    if profile:
                        caller_profile.update_profile_from_turn(
                            profile,
                            utterance=user_input,
                            detected_lang=active_lang,
                            intent=call.intent,
                            guest_name=call.guest_name,
                        )
                        profile_context = caller_profile.profile_prompt_context(profile)

                style_profile = caller_profile.choose_profile_mode(
                    call,
                    interrupted_recently=interrupted_recently,
                )
                await asyncio.sleep(timing.pause_ms / 1000)

                if interrupted_recently:
                    await _send_text_token(
                        websocket,
                        prosody.interruption_ack(active_lang),
                        lang=active_lang,
                        last=False,
                    )

                # On the completion turn, skip the LLM entirely. The model has a
                # bad habit of inventing a different party_size or dropping the
                # date in confirmations ('your reservation for 8 on May 6' when
                # the caller said 2). The deterministic summary is faithful to
                # the captured fields and is rendered in the active language.
                if decision.completed:
                    confirmation = language_router.build_reply(
                        call,
                        missing_field=None,
                        lang=active_lang,
                    )
                    await _send_text_token(
                        websocket,
                        confirmation,
                        lang=active_lang,
                        last=True,
                    )
                    if lead_payload:
                        asyncio.create_task(_fanout_lead(lead_payload))
                    continue

                # Read-back / reopen turns deliver the qualifier's
                # deterministic prompt directly (verbatim is the whole
                # point — we want the caller to verify the captured
                # fields, not see an LLM paraphrase).
                if decision.kind in ("readback", "reopen"):
                    await _send_text_token(
                        websocket,
                        decision.prompt,
                        lang=active_lang,
                        last=True,
                    )
                    continue

                stream = llm_stream.stream_reply(
                    call=call,
                    user_input=user_input,
                    missing_field=decision.missing_field,
                    lang=active_lang,
                    style_profile=style_profile,
                    caller_profile_context=profile_context,
                )
                try:
                    first_chunk = await asyncio.wait_for(
                        anext(stream),
                        timeout=timing.holding_delay_ms / 1000,
                    )
                except asyncio.TimeoutError:
                    await _send_text_token(
                        websocket,
                        prosody.holding_phrase(active_lang),
                        lang=active_lang,
                        last=False,
                    )
                    try:
                        first_chunk = await anext(stream)
                    except StopAsyncIteration:
                        first_chunk = None
                except StopAsyncIteration:
                    first_chunk = None

                sent_any = False
                pending_chunk: str | None = first_chunk
                decorated_first_chunk = False
                # Capture everything we actually speak so we can persist
                # the real reply (not the qualifier's English placeholder)
                # to the call transcript.
                spoken_parts: list[str] = []
                if pending_chunk is not None:
                    pending_chunk = prosody.strip_leading_name_address(
                        pending_chunk,
                        guest_name=call.guest_name,
                    )
                async for chunk in stream:
                    if pending_chunk is not None and not decorated_first_chunk:
                        pending_chunk = prosody.maybe_add_disfluency(
                            pending_chunk,
                            lang=active_lang,
                            call_sid=active_call_sid,
                            turn_count=int(call.turn_count or 0),
                        )
                        decorated_first_chunk = True
                    if pending_chunk is not None:
                        sent_any = True
                        spoken_parts.append(pending_chunk)
                        await _send_text_token(
                            websocket,
                            pending_chunk,
                            lang=active_lang,
                            last=False,
                        )
                    pending_chunk = chunk

                if pending_chunk is not None:
                    if not decorated_first_chunk:
                        pending_chunk = prosody.maybe_add_disfluency(
                            pending_chunk,
                            lang=active_lang,
                            call_sid=active_call_sid,
                            turn_count=int(call.turn_count or 0),
                        )
                    sent_any = True
                    spoken_parts.append(pending_chunk)
                    await _send_text_token(
                        websocket,
                        pending_chunk,
                        lang=active_lang,
                        last=True,
                    )

                if spoken_parts:
                    spoken_full = "".join(spoken_parts).strip()
                    async with session_scope() as session:
                        call = await _get_or_create_call_session(
                            session,
                            call_sid=active_call_sid,
                            caller_phone=active_from,
                        )
                        # Replace qualifier's deterministic placeholder
                        # with the actual paraphrase the caller heard.
                        transcript = list(call.transcript or [])
                        if transcript and transcript[-1].get("role") == "assistant":
                            transcript[-1] = {"role": "assistant", "text": spoken_full}
                        else:
                            transcript.append({"role": "assistant", "text": spoken_full})
                        call.transcript = transcript

                if not sent_any:
                    fallback = language_router.build_reply(
                        call,
                        missing_field=decision.missing_field,
                        lang=active_lang,
                    )
                    await _send_text_token(
                        websocket,
                        fallback,
                        lang=active_lang,
                        last=True,
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


@router.get("/analytics/calls/{call_sid}")
async def analytics_call_detail(call_sid: str) -> dict[str, Any]:
    """Return the full transcript and metadata for a single call."""
    async with session_scope() as session:
        result = await session.execute(select(CallSession).where(CallSession.call_sid == call_sid))
        call = result.scalar_one_or_none()
        if call is None:
            raise HTTPException(status_code=404, detail="Call session not found")
        lead_result = await session.execute(select(Lead).where(Lead.call_sid == call_sid))
        lead = lead_result.scalar_one_or_none()

    return {
        "call_sid": call.call_sid,
        "caller_phone": call.caller_phone,
        "status": call.status,
        "intent": call.intent,
        "guest_name": call.guest_name,
        "party_size": call.party_size,
        "reservation_datetime": call.reservation_datetime,
        "special_notes": call.special_notes,
        "turn_count": call.turn_count,
        "recording_sid": call.recording_sid,
        "recording_url": call.recording_url,
        "recording_duration_sec": call.recording_duration_sec,
        "created_at": call.created_at.isoformat() if call.created_at else None,
        "transcript": list(call.transcript or []),
        "lead": (
            {
                "intent": lead.intent,
                "guest_name": lead.guest_name,
                "party_size": lead.party_size,
                "reservation_datetime": lead.reservation_datetime,
                "qualification_label": lead.qualification_label,
                "summary": lead.summary,
            }
            if lead is not None
            else None
        ),
    }


@router.get("/analytics/calls")
async def analytics_calls_list(limit: int = 20) -> dict[str, Any]:
    """Return the most recent calls (no transcript)."""
    limit = max(1, min(100, limit))
    async with session_scope() as session:
        result = await session.execute(
            select(CallSession).order_by(CallSession.created_at.desc()).limit(limit)
        )
        calls = result.scalars().all()
    return {
        "calls": [
            {
                "call_sid": c.call_sid,
                "caller_phone": c.caller_phone,
                "status": c.status,
                "intent": c.intent,
                "guest_name": c.guest_name,
                "turn_count": c.turn_count,
                "recording_sid": c.recording_sid,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in calls
        ]
    }


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/admin/digest/run")
async def run_digest_now() -> dict[str, object]:
    """Build and post the daily digest immediately. Useful for testing."""
    from app.services.digest import build_payload, render_blocks, send_digest

    posted = await send_digest()
    payload = await build_payload()
    return {
        "posted": posted,
        "calls": payload.total_calls,
        "qualified": payload.qualified_calls,
        "leads_total": sum(payload.labels.values()),
    }


@router.get("/dashboard", response_class=Response)
async def dashboard_root() -> Response:
    """Server-rendered manager dashboard (HTML)."""
    from app.services.dashboard import render_dashboard

    async with session_scope() as db:
        html_body = await render_dashboard(db)
    return Response(content=html_body, media_type="text/html")


@router.get("/dashboard/call/{call_sid}", response_class=Response)
async def dashboard_call_detail(call_sid: str) -> Response:
    from app.services.dashboard import render_call_detail

    async with session_scope() as db:
        html_body = await render_call_detail(db, call_sid)
    if html_body is None:
        return Response(content="<p>Call not found</p>", status_code=404, media_type="text/html")
    return Response(content=html_body, media_type="text/html")


@router.get("/analytics/funnel")
async def analytics_funnel(window_hours: int = 168) -> dict[str, object]:
    """Conversion funnel over the last ``window_hours`` (default 7 days).

    Returns counts at each stage, plus drop-off counts and rates between
    consecutive stages.
    """
    from app.services.funnel import build_report

    async with session_scope() as db:
        report = await build_report(db, window_hours=window_hours)
    return {
        "window_hours": report.window_hours,
        "total": report.total,
        "counts": report.counts,
        "drop_off": report.drop_off,
        "drop_rate": report.drop_rate,
    }


@router.get("/analytics/phrase-usage")
async def phrase_usage() -> dict[str, int]:
    """Process-local tally of canonical phrase emissions.

    Used to spot canned phrases worth shortening or skipping. Note:
    counts reset on process restart since we don't persist this — for
    long-window analysis, ship to a stats backend.
    """
    return phrase_metrics.snapshot()


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
    phrase_metrics.record(text)
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
