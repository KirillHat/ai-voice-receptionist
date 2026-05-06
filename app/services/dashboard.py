"""Server-rendered manager dashboard.

A single static HTML page (no JS framework) that pulls today's call
activity from the DB. Aimed at restaurant managers who don't want to
read JSON. Refresh with the browser; ~50 KB on the wire.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import phrase_metrics
from app.services.funnel import build_report
from app.storage.models import CallSession, Lead


def _esc(value: object) -> str:
    return html.escape(str(value)) if value is not None else "—"


async def _today_stats(db: AsyncSession, tz: ZoneInfo) -> dict[str, int]:
    now_local = datetime.now(tz)
    start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_of_day.astimezone(timezone.utc)

    calls_q = select(CallSession).where(CallSession.created_at >= start_utc)
    calls = list((await db.execute(calls_q)).scalars())
    qualified = sum(1 for c in calls if c.status == "qualified")

    leads_q = select(Lead).where(Lead.created_at >= start_utc)
    leads = list((await db.execute(leads_q)).scalars())
    label_counts: dict[str, int] = {"HOT": 0, "WARM": 0, "COLD": 0}
    total_party = 0
    for lead in leads:
        label_counts[lead.qualification_label] = label_counts.get(lead.qualification_label, 0) + 1
        if lead.party_size:
            total_party += int(lead.party_size)

    return {
        "calls": len(calls),
        "qualified": qualified,
        "leads": len(leads),
        "guests_booked": total_party,
        **{f"label_{k.lower()}": v for k, v in label_counts.items()},
    }


async def _recent_leads(db: AsyncSession, *, limit: int = 20) -> list[Lead]:
    q = select(Lead).order_by(desc(Lead.created_at)).limit(limit)
    return list((await db.execute(q)).scalars())


async def _recent_calls(db: AsyncSession, *, limit: int = 20) -> list[CallSession]:
    q = select(CallSession).order_by(desc(CallSession.created_at)).limit(limit)
    return list((await db.execute(q)).scalars())


def _label_chip(label: str) -> str:
    color = {"HOT": "#dc2626", "WARM": "#ea580c", "COLD": "#475569"}.get(label, "#475569")
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        f'background:{color};color:#fff;font-size:11px;font-weight:600">'
        f"{_esc(label)}</span>"
    )


def _format_local(value: datetime | None, tz: ZoneInfo) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz).strftime("%b %-d, %H:%M")


async def render_dashboard(db: AsyncSession) -> str:
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)

    stats = await _today_stats(db, tz)
    leads = await _recent_leads(db, limit=20)
    calls = await _recent_calls(db, limit=15)
    funnel = await build_report(db, window_hours=168)
    phrases = phrase_metrics.snapshot()

    leads_rows = "".join(
        f"<tr>"
        f"<td>{_format_local(lead.created_at, tz)}</td>"
        f"<td>{_label_chip(lead.qualification_label)}</td>"
        f"<td>{_esc(lead.intent)}</td>"
        f"<td><strong>{_esc(lead.guest_name)}</strong></td>"
        f"<td>{_esc(lead.party_size or '—')}</td>"
        f"<td>{_esc(lead.reservation_datetime or '—')}</td>"
        f"<td>{_esc(lead.caller_phone)}</td>"
        f'<td><a href="/dashboard/call/{_esc(lead.call_sid)}" '
        f'style="color:#2563eb">view →</a></td>'
        f"</tr>"
        for lead in leads
    ) or '<tr><td colspan="8" style="text-align:center;color:#64748b;padding:24px">No leads yet today.</td></tr>'

    calls_rows = "".join(
        f"<tr>"
        f"<td>{_format_local(call.created_at, tz)}</td>"
        f'<td><span style="font-size:11px;color:{"#16a34a" if call.status == "qualified" else "#64748b"}">'
        f"{_esc(call.status)}</span></td>"
        f"<td>{_esc(call.intent or '—')}</td>"
        f"<td>{_esc(call.guest_name or '—')}</td>"
        f"<td>{_esc(call.turn_count)}</td>"
        f"<td>{_esc(call.caller_phone)}</td>"
        f'<td><a href="/dashboard/call/{_esc(call.call_sid)}" '
        f'style="color:#2563eb">view →</a></td>'
        f"</tr>"
        for call in calls
    ) or '<tr><td colspan="7" style="text-align:center;color:#64748b;padding:24px">No calls yet.</td></tr>'

    funnel_bar = ""
    max_count = max(funnel.counts.values()) if funnel.counts else 1
    for stage in ("greeted", "intent_captured", "name_captured",
                   "party_captured", "datetime_captured", "qualified"):
        count = funnel.counts.get(stage, 0)
        pct = (count / max_count * 100) if max_count else 0
        funnel_bar += (
            f"<div style='margin:6px 0'>"
            f"<div style='display:flex;justify-content:space-between;font-size:12px;color:#475569'>"
            f"<span>{stage.replace('_', ' ')}</span><span><strong>{count}</strong></span></div>"
            f"<div style='height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden'>"
            f"<div style='width:{pct:.1f}%;height:100%;background:#2563eb'></div></div>"
            f"</div>"
        )

    drop_rows = "".join(
        f"<tr><td>{_esc(transition)}</td>"
        f"<td>{_esc(funnel.drop_off[transition])}</td>"
        f"<td>{int(funnel.drop_rate[transition] * 100)}%</td></tr>"
        for transition in funnel.drop_off
    )

    phrase_rows = "".join(
        f"<tr><td>{_esc(label)}</td><td>{_esc(count)}</td></tr>"
        for label, count in sorted(phrases.items(), key=lambda x: -x[1])
    ) or '<tr><td colspan="2" style="color:#64748b">No data yet.</td></tr>'

    return _PAGE.format(
        venue=_esc(settings.business_name),
        now_local=datetime.now(tz).strftime("%a, %b %-d %H:%M"),
        calls=stats["calls"], qualified=stats["qualified"],
        leads=stats["leads"], guests=stats["guests_booked"],
        hot=stats.get("label_hot", 0),
        warm=stats.get("label_warm", 0),
        cold=stats.get("label_cold", 0),
        leads_rows=leads_rows,
        calls_rows=calls_rows,
        funnel_bar=funnel_bar,
        drop_rows=drop_rows,
        phrase_rows=phrase_rows,
    )


async def render_call_detail(db: AsyncSession, call_sid: str) -> str | None:
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)

    q = select(CallSession).where(CallSession.call_sid == call_sid)
    call = (await q.options() if False else await db.execute(q)).scalar_one_or_none()
    if call is None:
        return None

    transcript = call.transcript or []
    bubbles = ""
    for entry in transcript:
        role = entry.get("role", "")
        text = entry.get("text", "")
        if role == "caller":
            bubbles += (
                f'<div style="margin:8px 0;padding:10px 14px;background:#dbeafe;'
                f'border-radius:14px 14px 14px 2px;max-width:75%;align-self:flex-start">'
                f"<strong style='font-size:11px;color:#1e40af'>CALLER</strong><br>"
                f"{_esc(text)}</div>"
            )
        else:
            bubbles += (
                f'<div style="margin:8px 0;padding:10px 14px;background:#f1f5f9;'
                f'border-radius:14px 14px 2px 14px;max-width:75%;align-self:flex-end;'
                f'margin-left:auto">'
                f"<strong style='font-size:11px;color:#475569'>RECEPTIONIST</strong><br>"
                f"{_esc(text)}</div>"
            )

    return _CALL_PAGE.format(
        venue=_esc(settings.business_name),
        sid=_esc(call.call_sid),
        phone=_esc(call.caller_phone),
        when=_format_local(call.created_at, tz),
        intent=_esc(call.intent or "—"),
        name=_esc(call.guest_name or "—"),
        party=_esc(call.party_size or "—"),
        dt=_esc(call.reservation_datetime or "—"),
        status=_esc(call.status),
        turns=_esc(call.turn_count),
        notes=_esc(call.special_notes or ""),
        bubbles=bubbles or '<p style="color:#64748b">No transcript captured.</p>',
    )


_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><title>{venue} — Receptionist Dashboard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; background:#f8fafc; color:#0f172a; margin:0; padding:24px; }}
  h1 {{ margin:0 0 4px; font-size:22px; }}
  h2 {{ margin:0 0 12px; font-size:14px; color:#475569; text-transform:uppercase; letter-spacing:0.05em; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:24px; }}
  .stat {{ background:#fff; padding:16px; border-radius:8px; border:1px solid #e2e8f0; }}
  .stat-num {{ font-size:28px; font-weight:700; color:#0f172a; }}
  .stat-lbl {{ font-size:12px; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; }}
  .grid {{ display:grid; grid-template-columns:2fr 1fr; gap:24px; }}
  .card {{ background:#fff; padding:20px; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:24px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ text-align:left; padding:8px; border-bottom:1px solid #e2e8f0; font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; }}
  td {{ padding:8px; border-bottom:1px solid #f1f5f9; }}
  tr:hover {{ background:#f8fafc; }}
  .footer {{ font-size:11px; color:#64748b; margin-top:24px; text-align:center; }}
  @media (max-width: 900px) {{
    .stats {{ grid-template-columns:repeat(2,1fr); }}
    .grid {{ grid-template-columns:1fr; }}
  }}
</style></head><body>
<div class="container">
<h1>{venue}</h1>
<p style="margin:0 0 24px;color:#64748b">Receptionist dashboard · {now_local}</p>

<div class="stats">
  <div class="stat"><div class="stat-num">{calls}</div><div class="stat-lbl">Calls today</div></div>
  <div class="stat"><div class="stat-num">{qualified}</div><div class="stat-lbl">Qualified</div></div>
  <div class="stat"><div class="stat-num">{leads}</div><div class="stat-lbl">Leads · 🔥{hot} 🟧{warm} ⚪️{cold}</div></div>
  <div class="stat"><div class="stat-num">{guests}</div><div class="stat-lbl">Guests booked</div></div>
</div>

<div class="grid">
  <div>
    <div class="card">
      <h2>Recent leads</h2>
      <table>
        <thead><tr><th>Time</th><th>Label</th><th>Intent</th><th>Name</th><th>Party</th><th>When</th><th>Phone</th><th></th></tr></thead>
        <tbody>{leads_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>Recent calls</h2>
      <table>
        <thead><tr><th>Time</th><th>Status</th><th>Intent</th><th>Name</th><th>Turns</th><th>Phone</th><th></th></tr></thead>
        <tbody>{calls_rows}</tbody>
      </table>
    </div>
  </div>

  <div>
    <div class="card">
      <h2>Funnel · last 7 days</h2>
      {funnel_bar}
    </div>
    <div class="card">
      <h2>Drop-off</h2>
      <table>
        <thead><tr><th>Transition</th><th>Lost</th><th>Rate</th></tr></thead>
        <tbody>{drop_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>Phrase usage</h2>
      <table>
        <thead><tr><th>Phrase</th><th>Count</th></tr></thead>
        <tbody>{phrase_rows}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="footer">Data resets when the process restarts (phrase usage). Lead and call data persist in the database.</div>
</div>
</body></html>
"""

_CALL_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><title>Call {sid} — {venue}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background:#f8fafc; color:#0f172a; margin:0; padding:24px; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  .card {{ background:#fff; padding:20px; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:24px; }}
  h1 {{ margin:0 0 4px; font-size:18px; font-family:monospace; }}
  h2 {{ margin:0 0 12px; font-size:14px; color:#475569; text-transform:uppercase; letter-spacing:0.05em; }}
  .meta {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8px; font-size:13px; }}
  .meta dt {{ color:#64748b; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; }}
  .meta dd {{ margin:0 0 8px; font-weight:500; }}
  .transcript {{ display:flex; flex-direction:column; max-height:60vh; overflow:auto; }}
  a.back {{ color:#2563eb; text-decoration:none; font-size:13px; display:inline-block; margin-bottom:16px; }}
</style></head><body>
<div class="container">
<a class="back" href="/dashboard">← back to dashboard</a>
<div class="card">
  <h1>{sid}</h1>
  <p style="color:#64748b;margin:0 0 16px">{when} · {phone}</p>
  <dl class="meta">
    <div><dt>Status</dt><dd>{status}</dd></div>
    <div><dt>Turns</dt><dd>{turns}</dd></div>
    <div><dt>Intent</dt><dd>{intent}</dd></div>
    <div><dt>Guest</dt><dd>{name}</dd></div>
    <div><dt>Party</dt><dd>{party}</dd></div>
    <div><dt>Date/time</dt><dd>{dt}</dd></div>
  </dl>
  {notes}
</div>
<div class="card">
  <h2>Transcript</h2>
  <div class="transcript">{bubbles}</div>
</div>
</div></body></html>
"""
