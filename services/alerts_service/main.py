from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from twilio.rest import Client as TwilioClient

from .config import settings


app = FastAPI(title="ElderMind Alerts Service", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_allow_origins == "*" else settings.cors_allow_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "alerts"}


async def _fetch_user(user_id: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(f"{settings.data_service_url}/user/{user_id}")
            if res.is_success:
                return (res.json() or {}).get("user") or {}
    except Exception:
        pass
    return {}


async def _persist_alert(user_id: str, alert: dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{settings.data_service_url}/alerts/{user_id}", json=alert)
    except Exception:
        pass


async def _fetch_activity(user_id: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(f"{settings.data_service_url}/activity/{user_id}")
            if res.is_success:
                return (res.json() or {}).get("activity") or {}
    except Exception:
        pass
    return {}


async def _send_support_message(user: dict[str, Any], payload: dict[str, Any], body: str) -> list[str]:
    contacts = _support_contacts(user, payload) or [
        {"name": "Primary support", "phone": "+91-9999999999", "role": "fallback"}
    ]
    sent_to: list[str] = []

    if _twilio_ready():
        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        for contact in contacts:
            try:
                msg = client.messages.create(
                    from_=settings.twilio_from_phone,
                    to=contact["phone"],
                    body=body,
                )
                sent_to.append(f"sms:{contact['phone']}:{msg.sid}")
            except Exception:
                sent_to.append(f"sms_error:{contact['phone']}")
    else:
        sent_to.extend([f"stub:{contact['phone']}" for contact in contacts])

    unique_targets: list[str] = []
    seen_targets: set[str] = set()
    for contact in contacts:
        phone = str(contact.get("phone") or "").strip()
        normalized = _normalize_whatsapp_phone(phone)
        if not normalized or normalized in seen_targets:
            continue
        seen_targets.add(normalized)
        unique_targets.append(phone)
    for phone in unique_targets:
        sent_to.append(await _send_meta_whatsapp(phone, body))
    return sent_to


def _support_contacts(user: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, str]]:
    contacts: list[dict[str, str]] = []
    primary_phone = str(payload.get("to") or "").strip() or str(
        user.get("caretaker_phone") or user.get("caregiver_phone") or ""
    ).strip()
    primary_name = str(
        payload.get("label")
        or user.get("caretaker_name")
        or user.get("caregiver_name")
        or "Primary support"
    ).strip()
    if primary_phone:
        contacts.append({"name": primary_name or "Primary support", "phone": primary_phone, "role": "primary"})

    for item in user.get("family_contacts") or []:
        if not isinstance(item, dict):
            continue
        phone = str(item.get("phone") or "").strip()
        if not phone:
            continue
        contacts.append(
            {
                "name": str(item.get("name") or item.get("relation") or "Family support").strip() or "Family support",
                "phone": phone,
                "role": str(item.get("role") or item.get("relation") or "family").strip() or "family",
            }
        )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in contacts:
        if item["phone"] in seen:
            continue
        seen.add(item["phone"])
        deduped.append(item)
    return deduped


def _twilio_ready() -> bool:
    return bool(settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_phone)


def _meta_whatsapp_ready() -> bool:
    return bool(settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id)


def _normalize_whatsapp_phone(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    return digits


def _formal_alert_message(user: dict[str, Any], activity: dict[str, Any], reason: str, severity: int) -> str:
    name = str(user.get("name") or "the registered elder").strip() or "the registered elder"
    mood = str(activity.get("mood") or "unknown").strip() or "unknown"
    status = str(activity.get("status") or "unknown").strip() or "unknown"
    steps = str(activity.get("steps") or "unknown").strip() or "unknown"
    sleep = str(activity.get("sleep_hours") or "unknown").strip() or "unknown"
    notes = activity.get("notes") or []
    latest_note = ""
    if isinstance(notes, list) and notes:
        latest_note = str(notes[-1]).strip()
    activity_line = f"Recent activity: status {status}, mood {mood}, steps {steps}, sleep {sleep} hours."
    if latest_note:
        activity_line += f" Latest note: {latest_note}."
    return (
        f"Bhumi Alert: Please check on {name}. "
        f"Reason: {reason}. "
        f"Severity: {severity}. "
        f"{activity_line} "
        "Open the app or contact them as soon as possible."
    )


async def _send_meta_whatsapp(phone: str, body: str) -> str:
    if not _meta_whatsapp_ready():
        return f"whatsapp_stub:{phone}"
    normalized = _normalize_whatsapp_phone(phone)
    if not normalized:
        return f"whatsapp_invalid:{phone}"
    url = (
        f"https://graph.facebook.com/{settings.meta_whatsapp_version}/"
        f"{settings.meta_whatsapp_phone_number_id}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.meta_whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": normalized,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(url, headers=headers, json=payload)
    if res.is_success:
        return f"whatsapp:{phone}"
    return f"whatsapp_error:{phone}"


@app.post("/whatsapp/test")
async def whatsapp_test(payload: dict[str, Any]):
    user_id = str(payload.get("user_id") or "").strip()
    explicit_phone = str(payload.get("phone") or "").strip()
    message = str(payload.get("message") or "Test message from Bhumi.").strip() or "Test message from Bhumi."
    user = await _fetch_user(user_id) if user_id else {}
    contacts = _support_contacts(user, payload) if user else []
    target = explicit_phone or str((contacts[0] if contacts else {}).get("phone") or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="No WhatsApp target phone is available")
    result = await _send_meta_whatsapp(target, message)
    return {
        "status": "success",
        "configured": _meta_whatsapp_ready(),
        "target": target,
        "result": result,
        "message": message,
    }


@app.post("/report-share")
async def report_share(payload: dict[str, Any]):
    user_id = str(payload.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    user = await _fetch_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Parent profile not found")
    file_name = str(payload.get("file_name") or "medical report").strip() or "medical report"
    summary = str(payload.get("summary") or "").strip()
    advice = str(payload.get("advice") or "").strip()
    activity = await _fetch_activity(user_id)
    base_message = _formal_alert_message(
        user,
        activity,
        f"Report analysis shared from {file_name}",
        int(payload.get("severity") or 55),
    )
    message = (
        f"{base_message} "
        f"Report summary: {summary or 'No summary available.'} "
        f"Suggested next steps: {advice or 'Please review the report in the app.'}"
    )
    sent_to = await _send_support_message(user, payload, message)
    return {
        "status": "success",
        "alerts_sent_to": sent_to,
        "message": f"Report analysis shared with the support circle ({len(sent_to)} deliveries attempted).",
    }


@app.post("/sos")
async def sos(payload: dict[str, Any]):
    user_id = str(payload.get("user_id") or "demo")
    user = await _fetch_user(user_id)
    activity = await _fetch_activity(user_id)
    reason = payload.get("reason") or "SOS pressed"
    severity = int(payload.get("severity") or 90)
    contacts = _support_contacts(user, payload) or [{"name": "Primary support", "phone": "+91-9999999999", "role": "fallback"}]
    alert = {
        "id": str(uuid4()),
        "type": "sos",
        "severity": severity,
        "time_created": datetime.now(timezone.utc).isoformat(),
        "message": reason,
        "user_id": user_id,
        "location": payload.get("location"),
        "support_targets": contacts,
    }
    await _persist_alert(user_id, alert)

    sent_to = await _send_support_message(user, payload, _formal_alert_message(user, activity, str(reason), severity))

    return {
        "status": "success",
        "alerts_sent_to": sent_to,
        "timestamp": alert["time_created"],
        "severity": severity,
        "message": f"Alert shared with the support circle ({len(contacts)} contact{'s' if len(contacts) != 1 else ''}).",
    }


@app.post("/call")
async def call_contact(payload: dict[str, Any]):
    user_id = str(payload.get("user_id") or "demo")
    user = await _fetch_user(user_id)
    contacts = _support_contacts(user, payload)
    primary = contacts[0] if contacts else None
    target = (
        str(payload.get("to") or "").strip()
        or str((primary or {}).get("phone") or "").strip()
        or str(user.get("phone") or "").strip()
        or "+91-9999999999"
    )
    label = str(
        payload.get("label")
        or (primary or {}).get("name")
        or user.get("caretaker_name")
        or user.get("caregiver_name")
        or user.get("name")
        or "support contact"
    )

    if _twilio_ready():
        try:
            client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
            call = client.calls.create(
                to=target,
                from_=settings.twilio_from_phone,
                url="http://demo.twilio.com/docs/voice.xml",
            )
            return {
                "status": "success",
                "mode": "twilio",
                "call_id": call.sid,
                "target": target,
                "label": label,
            }
        except Exception:
            return {
                "status": "success",
                "mode": "fallback",
                "target": target,
                "label": label,
            }

    return {
        "status": "success",
        "mode": "fallback",
        "target": target,
        "label": label,
    }
