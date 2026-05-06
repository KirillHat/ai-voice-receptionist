"""WebSocket call simulator for the AI voice receptionist.

Connects to the same /ws/conversationrelay endpoint Twilio's ConversationRelay
uses, sends a setup frame and a sequence of prompts, and prints / asserts the
agent's text replies. Lets us exercise the full app stack (qualifier, FAQ,
language router, prosody, LLM streaming) without making a real phone call.

Usage:
    # one-off:
    python scripts/simulate_call.py --target prod \
        --say "Hi, I'd like a reservation for two tomorrow at 8pm" \
        --say "My name is Alex"

    # YAML scenario:
    python scripts/simulate_call.py --scenario scenarios/en_reservation.yaml

    # localhost (after `uvicorn app.main:app`):
    python scripts/simulate_call.py --target local --scenario scenarios/foo.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import dotenv_values
from websockets.sync.client import connect as ws_connect

ROOT = Path(__file__).resolve().parent.parent
ENV = dotenv_values(ROOT / ".env")

PROD_WS = "wss://ai-voice-production-eb9e.up.railway.app/ws/conversationrelay"
PROD_HTTP = "https://ai-voice-production-eb9e.up.railway.app"
LOCAL_WS = "ws://127.0.0.1:8000/ws/conversationrelay"
LOCAL_HTTP = "http://127.0.0.1:8000"


@dataclass
class Step:
    say: str
    lang: str = "en-US"
    expect_contains: list[str] = field(default_factory=list)
    expect_language_switch: str | None = None
    expect_topic: str | None = None  # FAQ topic match


@dataclass
class Scenario:
    name: str
    steps: list[Step]
    expect_intent: str | None = None
    expect_party_size: int | None = None
    expect_party_size_is_none: bool = False
    expect_guest_name: str | None = None
    expect_reservation_datetime_contains: str | None = None
    expect_qualified: bool | None = None
    expect_qualification_label: str | None = None
    expect_status: str | None = None


def _load_scenario(path: Path) -> Scenario:
    raw = yaml.safe_load(path.read_text())
    steps = [Step(**s) for s in raw.get("steps", [])]
    return Scenario(
        name=raw.get("name", path.stem),
        steps=steps,
        expect_intent=raw.get("expect_intent"),
        expect_party_size=raw.get("expect_party_size"),
        expect_party_size_is_none=bool(raw.get("expect_party_size_is_none", False)),
        expect_guest_name=raw.get("expect_guest_name"),
        expect_reservation_datetime_contains=raw.get("expect_reservation_datetime_contains"),
        expect_qualified=raw.get("expect_qualified"),
        expect_qualification_label=raw.get("expect_qualification_label"),
        expect_status=raw.get("expect_status"),
    )


def _drain_text_messages(ws, *, timeout: float = 25.0) -> tuple[list[dict], str | None]:
    """Read frames until we see a text frame with last=True. Returns all frames + final lang switch."""
    frames: list[dict] = []
    lang_switch: str | None = None
    saw_last_text = False
    while not saw_last_text:
        try:
            raw = ws.recv(timeout=timeout)
        except TimeoutError:
            break
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            continue
        frames.append(msg)
        if msg.get("type") == "language":
            lang_switch = msg.get("ttsLanguage") or msg.get("transcriptionLanguage")
            continue
        if msg.get("type") == "text" and msg.get("last") is True:
            saw_last_text = True
    return frames, lang_switch


def _stitch_text(frames: list[dict]) -> str:
    return "".join(str(f.get("token", "")) for f in frames if f.get("type") == "text").strip()


def _fetch_call_detail(http_base: str, call_sid: str) -> dict | None:
    url = f"{http_base.rstrip('/')}/analytics/calls/{urllib.parse.quote(call_sid)}"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception as exc:
        print(f"  (could not fetch /analytics/calls: {exc})", file=sys.stderr)
        return None


@dataclass
class StepResult:
    step: Step
    reply: str
    saw_lang_switch: str | None
    failures: list[str]


@dataclass
class ScenarioResult:
    name: str
    call_sid: str
    step_results: list[StepResult]
    final_failures: list[str]
    detail: dict | None

    @property
    def ok(self) -> bool:
        if self.final_failures:
            return False
        return not any(s.failures for s in self.step_results)


def run_scenario(scenario: Scenario, *, ws_url: str, http_base: str) -> ScenarioResult:
    call_sid = f"CA{uuid.uuid4().hex[:30]}"
    step_results: list[StepResult] = []
    final_failures: list[str] = []
    detail: dict | None = None

    with ws_connect(ws_url, open_timeout=8, close_timeout=4) as ws:
        ws.send(json.dumps({"type": "setup", "callSid": call_sid, "from": "+15555550100"}))

        for step in scenario.steps:
            ws.send(
                json.dumps(
                    {
                        "type": "prompt",
                        "voicePrompt": step.say,
                        "lang": step.lang,
                        "last": True,
                    }
                )
            )
            frames, lang_switch = _drain_text_messages(ws)
            reply = _stitch_text(frames)
            failures: list[str] = []
            for needle in step.expect_contains:
                if needle.lower() not in reply.lower():
                    failures.append(f"reply missing {needle!r}")
            if step.expect_language_switch and lang_switch != step.expect_language_switch:
                failures.append(
                    f"expected language switch to {step.expect_language_switch}, got {lang_switch!r}"
                )
            step_results.append(StepResult(step, reply, lang_switch, failures))

    detail = _fetch_call_detail(http_base, call_sid)
    if detail is None:
        if any(
            v is not None
            for v in (
                scenario.expect_intent,
                scenario.expect_party_size,
                scenario.expect_guest_name,
                scenario.expect_reservation_datetime_contains,
                scenario.expect_qualified,
                scenario.expect_qualification_label,
                scenario.expect_status,
            )
        ) or scenario.expect_party_size_is_none:
            final_failures.append("could not fetch call detail to validate state")
    else:
        if scenario.expect_intent and detail.get("intent") != scenario.expect_intent:
            final_failures.append(
                f"expected intent={scenario.expect_intent}, got {detail.get('intent')!r}"
            )
        if scenario.expect_party_size is not None and detail.get("party_size") != scenario.expect_party_size:
            final_failures.append(
                f"expected party_size={scenario.expect_party_size}, got {detail.get('party_size')!r}"
            )
        if scenario.expect_party_size_is_none and detail.get("party_size") is not None:
            final_failures.append(
                f"expected party_size to be unset, got {detail.get('party_size')!r}"
            )
        if scenario.expect_guest_name and detail.get("guest_name") != scenario.expect_guest_name:
            final_failures.append(
                f"expected guest_name={scenario.expect_guest_name!r}, got {detail.get('guest_name')!r}"
            )
        if scenario.expect_reservation_datetime_contains:
            value = detail.get("reservation_datetime") or ""
            if scenario.expect_reservation_datetime_contains.lower() not in value.lower():
                final_failures.append(
                    f"expected reservation_datetime containing "
                    f"{scenario.expect_reservation_datetime_contains!r}, got {value!r}"
                )
        if scenario.expect_status and detail.get("status") != scenario.expect_status:
            final_failures.append(
                f"expected status={scenario.expect_status!r}, got {detail.get('status')!r}"
            )
        if scenario.expect_qualified is not None:
            actually_qualified = detail.get("status") == "qualified"
            if actually_qualified != scenario.expect_qualified:
                final_failures.append(
                    f"expected qualified={scenario.expect_qualified}, "
                    f"got status={detail.get('status')!r}"
                )
        if scenario.expect_qualification_label:
            lead = detail.get("lead") or {}
            if lead.get("qualification_label") != scenario.expect_qualification_label:
                final_failures.append(
                    f"expected qualification_label={scenario.expect_qualification_label!r}, "
                    f"got {lead.get('qualification_label')!r}"
                )

    return ScenarioResult(scenario.name, call_sid, step_results, final_failures, detail)


def _print_result(result: ScenarioResult, *, verbose: bool = True) -> None:
    GREEN = "\033[92m"
    RED = "\033[91m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    END = "\033[0m"

    status = f"{GREEN}PASS{END}" if result.ok else f"{RED}FAIL{END}"
    print(f"{BOLD}[{status}] {result.name}{END}  {DIM}({result.call_sid}){END}")

    for sr in result.step_results:
        marker = f"{GREEN}✓{END}" if not sr.failures else f"{RED}✗{END}"
        print(f"  {marker} 👤 {sr.step.say}")
        if verbose:
            print(f"      🤖 {sr.reply}")
        if sr.saw_lang_switch:
            print(f"      {DIM}lang→ {sr.saw_lang_switch}{END}")
        for f in sr.failures:
            print(f"      {RED}- {f}{END}")

    if result.final_failures:
        for f in result.final_failures:
            print(f"  {RED}✗ {f}{END}")
    elif result.detail:
        d = result.detail
        print(
            f"  {DIM}→ intent={d.get('intent')!r} name={d.get('guest_name')!r} "
            f"party={d.get('party_size')!r} time={d.get('reservation_datetime')!r} "
            f"status={d.get('status')!r}{END}"
        )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target", choices=["prod", "local"], default="prod")
    p.add_argument("--ws-url")
    p.add_argument("--http-url")
    p.add_argument("--scenario", action="append", default=[])
    p.add_argument("--say", action="append", default=[])
    p.add_argument("--lang", default="en-US")
    p.add_argument("-q", "--quiet", action="store_true")
    args = p.parse_args()

    if args.ws_url:
        ws_url, http_base = args.ws_url, args.http_url or PROD_HTTP
    elif args.target == "prod":
        ws_url, http_base = PROD_WS, PROD_HTTP
    else:
        ws_url, http_base = LOCAL_WS, LOCAL_HTTP

    print(f"target: {ws_url}")

    if not args.scenario and not args.say:
        print("error: pass --scenario or --say", file=sys.stderr)
        return 2

    results: list[ScenarioResult] = []

    for scenario_path in args.scenario:
        scenario = _load_scenario(Path(scenario_path))
        result = run_scenario(scenario, ws_url=ws_url, http_base=http_base)
        _print_result(result, verbose=not args.quiet)
        results.append(result)

    if args.say:
        ad_hoc = Scenario(
            name="ad-hoc",
            steps=[Step(say=line, lang=args.lang) for line in args.say],
        )
        result = run_scenario(ad_hoc, ws_url=ws_url, http_base=http_base)
        _print_result(result, verbose=not args.quiet)
        results.append(result)

    failed = [r for r in results if not r.ok]
    if failed:
        print(f"\n{len(failed)} of {len(results)} scenario(s) failed.")
        return 1
    print(f"\nAll {len(results)} scenario(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
