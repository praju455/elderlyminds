from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .config import settings
from .store import LocalStore, MongoStore, Store, _password_hash, _slugify


# --- Pydantic request models for input validation ---

class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=4, max_length=200)
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="elder", max_length=20)
    phone: str = Field(default="", max_length=20)
    relation: str = Field(default="Support", max_length=50)
    linked_user_id: str = Field(default="", max_length=100)
    user_id: str = Field(default="", max_length=100)
    support_id: str = Field(default="", max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v


class LoginRequest(BaseModel):
    identifier: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    age: int | None = Field(default=None, ge=0, le=150)
    language: str | None = Field(default=None, max_length=50)
    region: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    origin: str | None = Field(default=None, max_length=200)
    wake_time: str | None = Field(default=None, max_length=10)
    sleep_time: str | None = Field(default=None, max_length=10)
    caretaker_name: str | None = Field(default=None, max_length=100)
    caretaker_phone: str | None = Field(default=None, max_length=20)
    caregiver_name: str | None = Field(default=None, max_length=100)
    caregiver_phone: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    healthcare_phone: str | None = Field(default=None, max_length=20)
    conditions: list[str] | None = None
    allergies: list[str] | None = None
    preferences: list[str] | None = None
    family_contacts: list[dict[str, Any]] | None = None
    settings: dict[str, Any] | None = None


def _cors_origins() -> list[str]:
    raw = (settings.cors_allow_origins or "*").strip()
    if raw == "*":
        return [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ]
    return [item.strip() for item in raw.split(",") if item.strip()]


app = FastAPI(title="ElderMind Data Service", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})

store: Store
mode = (settings.store_mode or "local").strip().lower()
if mode == "mongo":
    if not settings.mongo_uri:
        raise RuntimeError("MONGO_URI is required when DATA_STORE_MODE=mongo")
    store = MongoStore(settings.mongo_uri, settings.mongo_db_name)
elif mode == "local":
    store = LocalStore(settings.data_dir)
else:
    raise RuntimeError(f"Unsupported DATA_STORE_MODE: {mode}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return _now().date().isoformat()


def _next_alarm_iso(time_text: str) -> str:
    now = datetime.now().astimezone()
    hour_part, minute_part = [int(part) for part in str(time_text or "08:00").split(":", 1)]
    when = now.replace(hour=hour_part, minute=minute_part, second=0, microsecond=0)
    if when <= now:
        when += timedelta(days=1)
    return when.isoformat()


def _mood_value(mood: str) -> int:
    normalized = (mood or "okay").strip().lower()
    return {
        "good": 100,
        "okay": 75,
        "low": 42,
        "anxious": 35,
        "watch": 52,
    }.get(normalized, 70)


def _resolve_user_id(caregiver_id: str) -> str:
    direct = store.get_user(caregiver_id)
    if direct.get("user_id") == caregiver_id:
        return caregiver_id
    matched = store.find_user_by_caregiver(caregiver_id)
    if matched:
        return str(matched.get("user_id") or "")
    return ""


def _support_contacts(user: dict[str, Any]) -> list[dict[str, str]]:
    contacts: list[dict[str, str]] = []
    primary_name = str(user.get("caretaker_name") or user.get("caregiver_name") or "").strip()
    primary_phone = str(user.get("caretaker_phone") or user.get("caregiver_phone") or "").strip()
    if primary_name or primary_phone:
        contacts.append(
            {
                "id": "primary-support",
                "name": primary_name or "Primary support",
                "phone": primary_phone,
                "role": "primary",
                "relation": "Primary support",
                "email": "",
            }
        )

    for item in user.get("family_contacts") or []:
        if not isinstance(item, dict):
            continue
        contacts.append(
            {
                "id": str(item.get("id") or "").strip(),
                "name": str(item.get("name") or item.get("relation") or "Family support").strip() or "Family support",
                "phone": str(item.get("phone") or "").strip(),
                "role": str(item.get("role") or item.get("relation") or "family").strip() or "family",
                "relation": str(item.get("relation") or item.get("role") or "family").strip() or "family",
                "email": str(item.get("email") or "").strip().lower(),
            }
        )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in contacts:
        dedupe_key = item.get("phone") or item.get("id") or item.get("email") or item.get("name") or ""
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(item)
    return deduped


def _primary_support_contact(user: dict[str, Any]) -> dict[str, str]:
    primary_name = str(user.get("caretaker_name") or user.get("caregiver_name") or "").strip()
    primary_phone = str(user.get("caretaker_phone") or user.get("caregiver_phone") or "").strip()
    return {
        "id": "primary-support",
        "name": primary_name or "Primary support",
        "phone": primary_phone,
        "role": "primary",
    }


def _find_support_account_for_user(user_id: str, contact: dict[str, Any]) -> dict[str, Any] | None:
    contact_email = str(contact.get("email") or "").strip().lower()
    contact_phone = str(contact.get("phone") or "").strip()
    for account in store.list_accounts():
        if str(account.get("role") or "").strip().lower() not in {"support", "caretaker", "caregiver"}:
            continue
        if str(account.get("user_id") or "").strip().lower() != user_id:
            continue
        if contact_email and str(account.get("email") or "").strip().lower() == contact_email:
            return account
        if contact_phone and str(account.get("phone") or "").strip() == contact_phone:
            return account
        if str(contact.get("id") or "").strip() and str(account.get("account_id") or "").strip() == str(contact.get("id") or "").strip():
            return account
    return None


def _append_audit(
    user_id: str,
    *,
    action: str,
    summary: str,
    actor_name: str = "",
    actor_role: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    appender = getattr(store, "append_audit", None)
    if callable(appender):
        appender(
            user_id,
            {
                "action": action,
                "summary": summary,
                "actor_name": actor_name,
                "actor_role": actor_role,
                "meta": meta or {},
            },
        )


def _compute_report(user_id: str) -> dict[str, Any]:
    now = _now()
    start = (now - timedelta(days=6)).date()
    end = now.date()

    conversations = store.list_conversations(user_id, limit=150)
    med_logs = store.list_med_logs(user_id, limit=200)
    alerts = store.list_alerts(user_id, limit=80)

    day_keys = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    mood_trend: list[int] = []
    sleep_samples: list[float] = []
    steps_samples: list[int] = []
    health_counts: dict[str, int] = {}

    for day_key in day_keys:
        day_conversations = [
            item
            for item in conversations
            if str(item.get("ts") or "").startswith(day_key)
        ]
        if day_conversations:
            day_moods = [_mood_value(str(item.get("mood") or "okay")) for item in day_conversations]
            mood_trend.append(int(mean(day_moods)))
        else:
            mood_trend.append(74)

        day_wellness = store.get_wellness_day(user_id, day_key)
        sleep_samples.append(float(day_wellness.get("sleep_hours") or 7.5))
        steps_samples.append(int(day_wellness.get("steps") or 4200))

        for convo in day_conversations:
            for issue in convo.get("health_logs") or []:
                health_counts[str(issue)] = health_counts.get(str(issue), 0) + 1

    scheduled_slots = sum(len(med.get("times") or []) for med in store.list_meds(user_id)) * 7
    taken_logs = [
        log
        for log in med_logs
        if str(log.get("status") or "").lower() == "taken"
        and str(log.get("created_at") or log.get("confirmed_time") or "").startswith(tuple(day_keys))
    ]
    medicine_adherence = int(round((len(taken_logs) / max(1, scheduled_slots)) * 100))
    medicine_adherence = max(0, min(100, medicine_adherence))

    avg_steps = int(round(mean(steps_samples))) if steps_samples else 4200
    avg_sleep = round(mean(sleep_samples), 1) if sleep_samples else 7.5
    mood_score = int(round(mean(mood_trend))) if mood_trend else 75
    health_issues = [name.replace("_", " ") for name, _ in sorted(health_counts.items(), key=lambda item: item[1], reverse=True)[:4]]

    recommendations: list[str] = []
    if medicine_adherence < 85:
        recommendations.append("Keep medicine reminders on and confirm each dose after taking it.")
    if mood_score < 60:
        recommendations.append("Spend 5 to 10 minutes talking with family or hearing a favorite prayer.")
    if avg_steps < 3500:
        recommendations.append("Take a short walk after lunch, even for 10 minutes.")
    if avg_sleep < 7:
        recommendations.append("Try a lighter evening routine and listen to a calm prayer before sleep.")
    if not recommendations:
        recommendations = [
            "Keep the same calm routine this week.",
            "Drink one extra glass of water in the afternoon.",
            "Call or message family once today.",
        ]

    return {
        "week_start": str(start),
        "week_end": str(end),
        "mood_score": mood_score,
        "mood_trend": mood_trend,
        "activity_steps_per_day": avg_steps,
        "medicine_adherence": medicine_adherence,
        "sleep_hours": avg_sleep,
        "health_issues": health_issues,
        "recommendations": recommendations[:4],
        "alert_count": len(
            [item for item in alerts if str(item.get("time_created") or "").startswith(tuple(day_keys))]
        ),
    }


def _compute_activity(user_id: str) -> dict[str, Any]:
    today = _today_key()
    user = store.get_user(user_id)
    day = store.get_wellness_day(user_id, today)
    report = _compute_report(user_id)
    alerts = store.list_alerts(user_id, limit=6)
    conversations = store.list_conversations(user_id, limit=10)
    latest_mood = "okay"
    if conversations:
        latest_mood = str(conversations[-1].get("mood") or "okay")
    return {
        "user_id": user_id,
        "name": user.get("name") or "Friend",
        "day": today,
        "status": day.get("status") or "okay",
        "mood": day.get("mood") or latest_mood,
        "steps": int(day.get("steps") or report["activity_steps_per_day"]),
        "sleep_hours": float(day.get("sleep_hours") or report["sleep_hours"]),
        "water_cups": int(day.get("water_cups") or 5),
        "notes": day.get("notes") or [],
        "recent_alerts": alerts,
        "mood_score": report["mood_score"],
    }


def _user_exists(user_id: str) -> bool:
    return any(str(item.get("user_id") or "") == user_id for item in store.list_users())


def _managed_users(account_id: str) -> list[dict[str, Any]]:
    getter = getattr(store, "get_account", None)
    if not callable(getter):
        return []
    account = getter(account_id) or {}
    managed_ids = [str(item).strip() for item in account.get("managed_user_ids") or [] if str(item).strip()]
    users: list[dict[str, Any]] = []
    for user_id in managed_ids:
        user = store.get_user(user_id)
        if user.get("user_id"):
            users.append(user)
    return users


def _sync_family_manager_profile(old_account: dict[str, Any], new_account: dict[str, Any]) -> None:
    managed_ids = [str(item).strip() for item in new_account.get("managed_user_ids") or [] if str(item).strip()]
    old_email = str(old_account.get("email") or "").strip().lower()
    new_email = str(new_account.get("email") or "").strip().lower()
    old_name = str(old_account.get("name") or "").strip()
    new_name = str(new_account.get("name") or "").strip()
    old_phone = str(old_account.get("phone") or "").strip()
    new_phone = str(new_account.get("phone") or "").strip()
    new_relation = str(new_account.get("relation") or "Son / Daughter").strip() or "Son / Daughter"

    for user_id in managed_ids:
        user = store.get_user(user_id)
        contacts = list(user.get("family_contacts") or [])
        changed = False
        for item in contacts:
            if not isinstance(item, dict):
                continue
            item_email = str(item.get("email") or "").strip().lower()
            item_phone = str(item.get("phone") or "").strip()
            item_name = str(item.get("name") or "").strip()
            matches = False
            if old_email and item_email == old_email:
                matches = True
            elif old_phone and item_phone == old_phone and item_name == old_name:
                matches = True
            elif old_name and item_name == old_name and str(item.get("role") or item.get("relation") or "").strip().lower() in {"support", "son", "daughter", "family"}:
                matches = True
            if not matches:
                continue
            item["id"] = item.get("id") or _slugify(new_email or new_name, "support")
            item["name"] = new_name or item_name or "Family manager"
            item["phone"] = new_phone
            item["email"] = new_email
            item["relation"] = new_relation
            item["role"] = "support"
            changed = True

        if not changed:
            continue

        patch: dict[str, Any] = {"family_contacts": contacts}
        if str(user.get("caretaker_name") or "") == old_name:
            patch["caretaker_name"] = new_name
        if str(user.get("caretaker_phone") or "") == old_phone:
            patch["caretaker_phone"] = new_phone
        store.upsert_user(user_id, patch)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "data"}


@app.post("/auth/session")
async def create_session(payload: dict[str, Any]):
    return {"status": "success", "session": store.create_session(payload)}


@app.post("/auth/signup")
async def signup(payload: SignupRequest):
    email = payload.email
    password = payload.password
    role = payload.role.strip().lower()
    name = payload.name.strip()
    if store.find_account_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    if role in {"support", "caretaker", "caregiver"}:
        linked_user_id = (payload.linked_user_id or payload.user_id or "").strip().lower()
        relation = (payload.relation or "Support").strip() or "Support"
        phone = (payload.phone or "").strip()
        contact_id = (payload.support_id or email.split("@")[0] or name).strip().lower()
        linked_user = None
        if linked_user_id:
            if not _user_exists(linked_user_id):
                raise HTTPException(status_code=404, detail="Linked elder profile not found")
            linked_user = store.get_user(linked_user_id)
        account = store.create_account(
            {
                "role": "support",
                "user_id": linked_user_id,
                "name": name,
                "relation": relation,
                "phone": phone,
                "managed_user_ids": [linked_user_id] if linked_user_id else [],
                "email": email,
                "password": password,
            }
        )

        if linked_user_id:
            contacts = list(linked_user.get("family_contacts") or [])
            if not any(str(item.get("id") or "") == contact_id or str(item.get("phone") or "") == phone for item in contacts if isinstance(item, dict)):
                contacts.append(
                    {
                        "id": contact_id,
                        "name": name,
                        "relation": relation,
                        "role": "support",
                        "phone": phone,
                        "email": email,
                    }
                )
            store.upsert_user(
                linked_user_id,
                {
                    "family_contacts": contacts,
                    "caretaker_name": linked_user.get("caretaker_name") or name,
                    "caretaker_phone": linked_user.get("caretaker_phone") or phone,
                },
            )

        session = store.create_session(
            {
                "role": "support",
                "user_id": linked_user_id,
                "name": name,
                "email": email,
                "caregiver_id": str(account.get("account_id") or contact_id),
            }
        )
        return {"status": "success", "session": session, "user": linked_user or {"user_id": "", "name": name}}

    raise HTTPException(
        status_code=400,
        detail="Parents are created inside the family manager dashboard. Create the child account here first, then add parent logins from Family Hub.",
    )


@app.post("/auth/login")
async def login(payload: LoginRequest):
    identifier = (payload.identifier or payload.email or "").strip().lower()
    password = payload.password
    if not identifier:
        raise HTTPException(status_code=400, detail="Email or parent user id is required")

    account = store.login_account(identifier, password)
    if not account:
        raise HTTPException(status_code=401, detail="Invalid email or parent user id, or wrong password")

    role = "support" if str(account.get("role") or "").lower() in {"support", "caretaker", "caregiver"} else "elder"
    managed_ids = [str(item).strip() for item in account.get("managed_user_ids") or [] if str(item).strip()]
    session_user_id = str(account.get("user_id") or "").strip() or (managed_ids[0] if managed_ids else "")
    session = store.create_session(
        {
            "role": role,
            "user_id": session_user_id,
            "name": account.get("name") or "User",
            "email": account.get("email"),
            "caregiver_id": account.get("account_id"),
        }
    )
    if role == "support" and not session_user_id:
        return {"status": "success", "session": session, "user": {"user_id": "", "name": account.get("name") or "Support"}}
    session_user_id = str(session.get("user_id") or "").strip()
    return {"status": "success", "session": session, "user": store.get_user(session_user_id) if session_user_id else {"user_id": "", "name": account.get("name") or "Support"}}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "session": session}


@app.get("/users")
async def users():
    return {"status": "success", "items": store.list_users()}


@app.get("/user/{user_id}")
async def get_user(user_id: str):
    user = store.get_user(user_id)
    if not user.get("name") and not _user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "user": user}


@app.put("/user/{user_id}")
async def update_user(user_id: str, payload: UserUpdateRequest):
    return {"status": "success", "user": store.upsert_user(user_id, payload.model_dump(exclude_none=True))}


@app.get("/support/account/{account_id}")
async def support_workspace(account_id: str, active_user_id: str | None = None):
    getter = getattr(store, "get_account", None)
    if not callable(getter):
        raise HTTPException(status_code=501, detail="Support workspace is not available")
    account = getter(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Support account not found")
    managed = _managed_users(account_id)
    chosen_user_id = (active_user_id or "").strip() or (managed[0].get("user_id") if managed else "")
    active: dict[str, Any] | None = None
    if chosen_user_id:
        active = {
            "user": store.get_user(chosen_user_id),
            "support_contacts": _support_contacts(store.get_user(chosen_user_id)),
            "recent_conversations": store.list_conversations(chosen_user_id, limit=12),
            "medicine_logs": store.list_med_logs(chosen_user_id, limit=20),
            "alerts": store.list_alerts(chosen_user_id, limit=20),
            "memories": store.list_memories(chosen_user_id, limit=8),
            "medicines": store.list_meds(chosen_user_id),
            "alarms": store.list_alarms(chosen_user_id),
            "reports": store.list_reports(chosen_user_id, limit=10),
            "audit": store.list_audit(chosen_user_id, limit=20) if callable(getattr(store, "list_audit", None)) else [],
        }
    return {"status": "success", "account": account, "managed_users": managed, "active": active}


@app.put("/support/account/{account_id}")
async def update_support_account(account_id: str, payload: dict[str, Any]):
    getter = getattr(store, "get_account", None)
    updater = getattr(store, "update_account", None)
    if not callable(getter) or not callable(updater):
        raise HTTPException(status_code=501, detail="Support workspace is not available")
    account = getter(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Support account not found")

    next_name = str(payload.get("name") or account.get("name") or "").strip()
    next_email = str(payload.get("email") or account.get("email") or "").strip().lower()
    next_phone = str(payload.get("phone") or account.get("phone") or "").strip()
    next_relation = str(payload.get("relation") or account.get("relation") or "Son / Daughter").strip() or "Son / Daughter"

    if not next_name or not next_email:
        raise HTTPException(status_code=400, detail="Family manager name and email are required")

    existing = store.find_account_by_email(next_email)
    if existing and str(existing.get("account_id") or "") != account_id:
        raise HTTPException(status_code=409, detail="That email is already used by another login")

    updated = updater(
        account_id,
        {
            "name": next_name,
            "email": next_email,
            "phone": next_phone,
            "relation": next_relation,
        },
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Could not update family manager profile")

    _sync_family_manager_profile(account, updated)
    return {"status": "success", "account": updated}


@app.post("/support/account/{account_id}/elders")
async def support_add_elder(account_id: str, payload: dict[str, Any]):
    getter = getattr(store, "get_account", None)
    add_managed = getattr(store, "add_managed_user", None)
    if not callable(getter) or not callable(add_managed):
        raise HTTPException(status_code=501, detail="Support workspace is not available")
    account = getter(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Support account not found")

    name = str(payload.get("name") or "").strip()
    requested_user_id = str(payload.get("user_id") or "").strip().lower()
    parent_password = str(payload.get("password") or "")
    if not name:
        raise HTTPException(status_code=400, detail="Parent name is required")
    if not requested_user_id:
        raise HTTPException(status_code=400, detail="Parent user id is required")
    if not parent_password:
        raise HTTPException(status_code=400, detail="Parent password is required")
    user_id = _slugify(requested_user_id, "elder")
    if _user_exists(user_id):
        raise HTTPException(status_code=409, detail="A parent profile with this id already exists")
    existing_parent_account = getattr(store, "find_account_by_user_id", None)
    if callable(existing_parent_account) and existing_parent_account(user_id, role="elder"):
        raise HTTPException(status_code=409, detail="That parent login id is already taken")
    requested_email = str(payload.get("email") or "").strip().lower()
    if requested_email and store.find_account_by_email(requested_email):
        raise HTTPException(status_code=409, detail="That email is already used by another login")

    family_contacts = list(payload.get("family_contacts") or [])
    manager_name = str(account.get("name") or "Family Manager").strip() or "Family Manager"
    manager_phone = str(account.get("phone") or "").strip()
    manager_email = str(account.get("email") or "").strip().lower()
    manager_contact = {
        "id": _slugify(manager_email or manager_name, "support"),
        "name": manager_name,
        "relation": str(account.get("relation") or "Son / Daughter"),
        "role": "support",
        "phone": manager_phone,
        "email": manager_email,
    }
    if not any(str(item.get("email") or "").strip().lower() == manager_email for item in family_contacts if isinstance(item, dict)):
        family_contacts.insert(0, manager_contact)

    user = store.upsert_user(
        user_id,
        {
            "name": name,
            "age": payload.get("age") or 68,
            "language": payload.get("language") or "Hindi",
            "region": payload.get("region") or "",
            "city": payload.get("city") or "",
            "origin": payload.get("origin") or "",
            "wake_time": payload.get("wake_time") or "07:00",
            "sleep_time": payload.get("sleep_time") or "21:00",
            "caretaker_name": payload.get("caretaker_name") or manager_name,
            "caretaker_phone": payload.get("caretaker_phone") or manager_phone,
            "phone": payload.get("phone") or "",
            "healthcare_phone": payload.get("healthcare_phone") or "",
            "conditions": payload.get("conditions") or [],
            "allergies": payload.get("allergies") or [],
            "preferences": payload.get("preferences") or [],
            "family_contacts": family_contacts,
            "settings": payload.get("settings") or {},
        },
    )
    created_account = store.create_account(
        {
            "role": "elder",
            "user_id": user_id,
            "password": parent_password,
            "name": name,
            "phone": str(payload.get("phone") or "").strip(),
            "email": requested_email,
        }
    )
    add_managed(account_id, user_id)
    _append_audit(
        user_id,
        action="parent_created",
        summary=f"Parent profile {name} was created.",
        actor_name=str(account.get("name") or ""),
        actor_role="family_manager",
        meta={"account_id": account_id},
    )
    return {
        "status": "success",
        "user": user,
        "login": {
            "user_id": user_id,
            "account_id": created_account.get("account_id"),
        },
    }


@app.post("/support/account/{account_id}/caretakers")
async def support_add_caretaker(account_id: str, payload: dict[str, Any]):
    getter = getattr(store, "get_account", None)
    if not callable(getter):
        raise HTTPException(status_code=501, detail="Support workspace is not available")
    account = getter(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Support account not found")
    user_id = str(payload.get("user_id") or "").strip().lower()
    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    phone = str(payload.get("phone") or "").strip()
    relation = str(payload.get("relation") or "Caretaker").strip() or "Caretaker"
    if not user_id or not name or not email or not password:
        raise HTTPException(status_code=400, detail="user_id, name, email, and password are required")
    if not _user_exists(user_id):
        raise HTTPException(status_code=404, detail="Parent profile not found")
    if store.find_account_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = store.get_user(user_id)
    contacts = list(user.get("family_contacts") or [])
    contact_id = _slugify(email or name, "caretaker")
    contacts.append(
        {
            "id": contact_id,
            "name": name,
            "relation": relation,
            "role": "support",
            "phone": phone,
            "email": email,
        }
    )
    store.upsert_user(
        user_id,
        {
            "family_contacts": contacts,
            "caretaker_name": user.get("caretaker_name") or name,
            "caretaker_phone": user.get("caretaker_phone") or phone,
        },
    )
    created = store.create_account(
        {
            "email": email,
            "password": password,
            "role": "support",
            "user_id": user_id,
            "name": name,
            "relation": relation,
            "phone": phone,
            "managed_user_ids": [user_id],
        }
    )
    _append_audit(
        user_id,
        action="caretaker_added",
        summary=f"Caretaker login {name} was added.",
        actor_name=str(account.get("name") or ""),
        actor_role="family_manager",
        meta={"caretaker_email": email, "relation": relation},
    )
    return {"status": "success", "account": created, "user": store.get_user(user_id)}


@app.post("/support/account/{account_id}/elders/{user_id}/reset-password")
async def support_reset_parent_password(account_id: str, user_id: str, payload: dict[str, Any]):
    getter = getattr(store, "get_account", None)
    updater = getattr(store, "update_account", None)
    finder = getattr(store, "find_account_by_user_id", None)
    if not callable(getter) or not callable(updater) or not callable(finder):
        raise HTTPException(status_code=501, detail="Support workspace is not available")
    account = getter(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Support account not found")
    normalized_user_id = str(user_id or "").strip().lower()
    if normalized_user_id not in [str(item).strip().lower() for item in account.get("managed_user_ids") or []]:
        raise HTTPException(status_code=403, detail="That parent is not managed by this family account")
    parent_account = finder(normalized_user_id, role="elder")
    if not parent_account:
        raise HTTPException(status_code=404, detail="Parent login not found")
    new_password = str(payload.get("password") or "").strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    updated = updater(str(parent_account.get("account_id") or ""), {"password_hash": _password_hash(new_password)})
    _append_audit(
        normalized_user_id,
        action="parent_password_reset",
        summary="Parent login password was reset.",
        actor_name=str(account.get("name") or ""),
        actor_role="family_manager",
        meta={"account_id": account_id},
    )
    return {"status": "success", "account": updated}


@app.put("/support/account/{account_id}/caretakers/{contact_id}")
async def support_update_caretaker(account_id: str, contact_id: str, payload: dict[str, Any]):
    getter = getattr(store, "get_account", None)
    updater = getattr(store, "update_account", None)
    if not callable(getter) or not callable(updater):
        raise HTTPException(status_code=501, detail="Support workspace is not available")
    account = getter(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Support account not found")
    user_id = str(payload.get("user_id") or "").strip().lower()
    if not user_id or not _user_exists(user_id):
        raise HTTPException(status_code=404, detail="Parent profile not found")
    user = store.get_user(user_id)
    contacts = list(user.get("family_contacts") or [])
    target_index = next((index for index, item in enumerate(contacts) if isinstance(item, dict) and str(item.get("id") or "").strip() == contact_id), -1)
    if target_index < 0:
        raise HTTPException(status_code=404, detail="Support member not found")
    current_contact = contacts[target_index]
    updated_contact = {
        **current_contact,
        "name": str(payload.get("name") or current_contact.get("name") or "").strip() or current_contact.get("name") or "Support",
        "relation": str(payload.get("relation") or current_contact.get("relation") or "support").strip() or "support",
        "role": str(payload.get("role") or current_contact.get("role") or current_contact.get("relation") or "support").strip() or "support",
        "phone": str(payload.get("phone") or current_contact.get("phone") or "").strip(),
        "email": str(payload.get("email") or current_contact.get("email") or "").strip().lower(),
    }
    contacts[target_index] = updated_contact
    user_patch: dict[str, Any] = {"family_contacts": contacts}
    if user.get("caretaker_name") == current_contact.get("name"):
        user_patch["caretaker_name"] = updated_contact["name"]
    if user.get("caretaker_phone") == current_contact.get("phone"):
        user_patch["caretaker_phone"] = updated_contact["phone"]
    updated_user = store.upsert_user(user_id, user_patch)
    linked_account = _find_support_account_for_user(user_id, current_contact)
    updated_account = None
    if linked_account:
        account_patch = {
            "name": updated_contact["name"],
            "relation": updated_contact["relation"],
            "phone": updated_contact["phone"],
            "email": updated_contact["email"] or linked_account.get("email"),
        }
        next_password = str(payload.get("password") or "").strip()
        if next_password:
            account_patch["password_hash"] = _password_hash(next_password)
        updated_account = updater(str(linked_account.get("account_id") or ""), account_patch)
    _append_audit(
        user_id,
        action="caretaker_updated",
        summary=f"Support member {updated_contact['name']} was updated.",
        actor_name=str(account.get("name") or ""),
        actor_role="family_manager",
        meta={"contact_id": contact_id},
    )
    return {"status": "success", "user": updated_user, "account": updated_account, "contact": updated_contact}


@app.delete("/support/account/{account_id}/caretakers/{contact_id}")
async def support_delete_caretaker(account_id: str, contact_id: str, user_id: str):
    getter = getattr(store, "get_account", None)
    deleter = getattr(store, "delete_account", None)
    if not callable(getter) or not callable(deleter):
        raise HTTPException(status_code=501, detail="Support workspace is not available")
    account = getter(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Support account not found")
    normalized_user_id = str(user_id or "").strip().lower()
    if not normalized_user_id or not _user_exists(normalized_user_id):
        raise HTTPException(status_code=404, detail="Parent profile not found")
    user = store.get_user(normalized_user_id)
    contacts = list(user.get("family_contacts") or [])
    current_contact = next((item for item in contacts if isinstance(item, dict) and str(item.get("id") or "").strip() == contact_id), None)
    if not current_contact:
        raise HTTPException(status_code=404, detail="Support member not found")
    remaining_contacts = [item for item in contacts if not (isinstance(item, dict) and str(item.get("id") or "").strip() == contact_id)]
    user_patch: dict[str, Any] = {"family_contacts": remaining_contacts}
    if user.get("caretaker_name") == current_contact.get("name"):
        fallback = remaining_contacts[0] if remaining_contacts else {}
        user_patch["caretaker_name"] = str(fallback.get("name") or "")
        user_patch["caretaker_phone"] = str(fallback.get("phone") or "")
    updated_user = store.upsert_user(normalized_user_id, user_patch)
    linked_account = _find_support_account_for_user(normalized_user_id, current_contact)
    deleted_account = False
    if linked_account:
        deleted_account = bool(deleter(str(linked_account.get("account_id") or "")))
    _append_audit(
        normalized_user_id,
        action="caretaker_removed",
        summary=f"Support member {current_contact.get('name') or contact_id} was removed.",
        actor_name=str(account.get("name") or ""),
        actor_role="family_manager",
        meta={"contact_id": contact_id},
    )
    return {"status": "success", "user": updated_user, "deleted_account": deleted_account}


@app.post("/support/account/{account_id}/link-parent")
async def support_link_existing_parent(account_id: str, payload: dict[str, Any]):
    getter = getattr(store, "get_account", None)
    add_managed = getattr(store, "add_managed_user", None)
    if not callable(getter) or not callable(add_managed):
        raise HTTPException(status_code=501, detail="Support workspace is not available")
    account = getter(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Support account not found")

    requested_user_id = str(payload.get("user_id") or "").strip().lower()
    requested_email = str(payload.get("email") or "").strip().lower()

    target_user_id = requested_user_id
    if not target_user_id and requested_email:
        linked_account = store.find_account_by_email(requested_email)
        if not linked_account:
            raise HTTPException(status_code=404, detail="No parent account found with that email")
        if str(linked_account.get("role") or "").lower() != "elder":
            raise HTTPException(status_code=400, detail="That email does not belong to a parent account")
        target_user_id = str(linked_account.get("user_id") or "").strip().lower()

    if not target_user_id:
        raise HTTPException(status_code=400, detail="user_id or email is required")
    if not _user_exists(target_user_id):
        raise HTTPException(status_code=404, detail="Parent profile not found")

    user = store.get_user(target_user_id)
    add_managed(account_id, target_user_id)

    contacts = list(user.get("family_contacts") or [])
    manager_email = str(account.get("email") or "").strip().lower()
    manager_phone = str(account.get("phone") or "").strip()
    manager_name = str(account.get("name") or "Family Manager").strip() or "Family Manager"
    if not any(str(item.get("email") or "").strip().lower() == manager_email for item in contacts if isinstance(item, dict)):
        contacts.insert(
            0,
            {
                "id": _slugify(manager_email or manager_name, "support"),
                "name": manager_name,
                "relation": str(account.get("relation") or "Son / Daughter"),
                "role": "support",
                "phone": manager_phone,
                "email": manager_email,
            },
        )
        user = store.upsert_user(target_user_id, {"family_contacts": contacts})

    _append_audit(
        target_user_id,
        action="parent_linked",
        summary=f"Parent profile {user.get('name') or target_user_id} was linked to a family manager.",
        actor_name=manager_name,
        actor_role="family_manager",
        meta={"account_id": account_id},
    )
    return {"status": "success", "user": user}


@app.get("/medicine/{user_id}")
async def get_meds(user_id: str):
    return {
        "user_id": user_id,
        "medicines": store.list_meds(user_id),
        "logs": store.list_med_logs(user_id, limit=60),
    }


@app.put("/medicine/{user_id}")
async def save_meds(user_id: str, payload: dict[str, Any]):
    medicines = payload.get("medicines")
    if not isinstance(medicines, list):
        raise HTTPException(status_code=400, detail="medicines must be a list")
    saved = store.save_meds(user_id, medicines)
    _append_audit(
        user_id,
        action="medicines_updated",
        summary=f"Medicine plan was updated with {len(saved)} items.",
        actor_name=str(payload.get("actor_name") or ""),
        actor_role=str(payload.get("actor_role") or ""),
        meta={"count": len(saved)},
    )
    return {"status": "success", "medicines": saved}


@app.post("/medicine/{user_id}/sync-reminders")
async def sync_medication_reminders(user_id: str):
    medicines = store.list_meds(user_id)
    delete_by_source = getattr(store, "delete_alarms_by_source", None)
    if callable(delete_by_source):
        delete_by_source(user_id, "medicine_plan:")
    created: list[dict[str, Any]] = []
    for med in medicines:
        med_name = str(med.get("name") or "Medicine").strip() or "Medicine"
        dose = str(med.get("dose") or "").strip()
        for time_text in med.get("times") or []:
            if not str(time_text).strip():
                continue
            created.append(
                store.add_alarm(
                    user_id,
                    {
                        "title": f"{med_name} reminder",
                        "time_iso": _next_alarm_iso(str(time_text)),
                        "label": f"Time to take {med_name}{f' {dose}' if dose else ''}.",
                        "source": f"medicine_plan:{med.get('id') or med_name}:{time_text}",
                    },
                )
            )
    _append_audit(
        user_id,
        action="medicine_reminders_synced",
        summary=f"Medicine reminders were synced from the schedule ({len(created)} reminders).",
        meta={"count": len(created)},
    )
    return {"status": "success", "items": created}


@app.post("/medicine/{med_id}/confirm")
async def confirm_med(med_id: str, payload: dict[str, Any]):
    user_id = str(payload.get("user_id") or "demo")
    status = str(payload.get("status") or "taken").lower()
    medicines = store.list_meds(user_id)
    medicine = next((item for item in medicines if str(item.get("id")) == med_id), None)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")

    scheduled_time = payload.get("scheduled_time")
    if not scheduled_time and medicine.get("times"):
        scheduled_time = medicine["times"][0]

    record = store.append_med_log(
        user_id,
        {
            "med_id": med_id,
            "medicine_name": medicine.get("name"),
            "status": status,
            "scheduled_time": scheduled_time,
            "confirmed_time": payload.get("confirmed_time") or _now().isoformat(),
            "created_at": _now().isoformat(),
            "source": payload.get("source") or "manual",
        },
    )
    store.append_conversation(
        user_id,
        {
            "ts": _now().isoformat(),
            "text_input": f"[medicine_{status}] {medicine.get('name')}",
            "ai_response": "Medicine log updated.",
            "mood": "good" if status == "taken" else "okay",
            "emotion": "supportive",
            "source": "medication",
        },
    )
    return {"status": "success", "logged": record}


@app.post("/conversations/{user_id}")
async def append_conversation(user_id: str, payload: dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    return {"status": "success", "item": store.append_conversation(user_id, payload)}


@app.get("/conversations/{user_id}")
async def list_conversations(user_id: str, limit: int = 20):
    return {"status": "success", "items": store.list_conversations(user_id, limit=limit)}


@app.delete("/conversations/{user_id}")
async def clear_conversations(user_id: str):
    store.clear_conversations(user_id)
    return {"status": "success"}


@app.delete("/conversations/{user_id}/item/{item_id}")
async def delete_conversation_item(user_id: str, item_id: str):
    store.delete_conversation(user_id, item_id)
    return {"status": "success"}


@app.delete("/conversations/{user_id}/day/{day_key}")
async def delete_conversation_day(user_id: str, day_key: str):
    store.delete_conversations_for_day(user_id, day_key)
    return {"status": "success"}


@app.post("/alerts/{user_id}")
async def append_alert(user_id: str, payload: dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    return {"status": "success", "item": store.append_alert(user_id, payload)}


@app.get("/alerts/{user_id}")
async def list_alerts(user_id: str, limit: int = 20):
    return {"status": "success", "items": store.list_alerts(user_id, limit=limit)}


@app.delete("/alerts/{user_id}")
async def clear_alerts(user_id: str):
    store.clear_alerts(user_id)
    return {"status": "success"}


@app.post("/memory/{user_id}")
async def add_memory(user_id: str, payload: dict[str, Any]):
    return {"status": "success", "item": store.add_memory(user_id, payload)}


@app.get("/memory/{user_id}")
async def list_memory(user_id: str, limit: int = 20):
    return {"status": "success", "items": store.list_memories(user_id, limit=limit)}


@app.delete("/memory/{user_id}")
async def clear_memory(user_id: str):
    store.clear_memories(user_id)
    return {"status": "success"}


@app.post("/alarms/{user_id}")
async def add_alarm(user_id: str, payload: dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    if not str(payload.get("time_iso") or "").strip():
        raise HTTPException(status_code=400, detail="time_iso is required")
    return {"status": "success", "item": store.add_alarm(user_id, payload)}


@app.get("/alarms/{user_id}")
async def list_alarms(user_id: str):
    return {"status": "success", "items": store.list_alarms(user_id)}


@app.delete("/alarms/{user_id}/{alarm_id}")
async def delete_alarm(user_id: str, alarm_id: str):
    store.delete_alarm(user_id, alarm_id)
    return {"status": "success"}


@app.post("/reports/{user_id}")
async def add_report(user_id: str, payload: dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    if not str(payload.get("image_data_url") or "").strip():
        raise HTTPException(status_code=400, detail="image_data_url is required")
    item = store.add_report(user_id, payload)
    _append_audit(
        user_id,
        action="report_uploaded",
        summary=f"Medical report {item.get('file_name') or 'report'} was uploaded.",
        actor_name=str(payload.get("actor_name") or ""),
        actor_role=str(payload.get("actor_role") or ""),
        meta={"report_id": item.get("id")},
    )
    return {"status": "success", "item": item}


@app.get("/reports/{user_id}")
async def list_reports(user_id: str, limit: int = 20):
    return {"status": "success", "items": store.list_reports(user_id, limit=limit)}


@app.delete("/reports/{user_id}/{report_id}")
async def delete_report(user_id: str, report_id: str):
    store.delete_report(user_id, report_id)
    _append_audit(
        user_id,
        action="report_deleted",
        summary="A stored medical report was deleted.",
        meta={"report_id": report_id},
    )
    return {"status": "success"}


@app.get("/audit/{user_id}")
async def list_audit(user_id: str, limit: int = 40):
    reader = getattr(store, "list_audit", None)
    return {"status": "success", "items": reader(user_id, limit=limit) if callable(reader) else []}


@app.post("/reports/{user_id}/{report_id}/review")
async def review_report(user_id: str, report_id: str, payload: dict[str, Any]):
    suggestions = payload.get("medicines")
    decision = str(payload.get("decision") or "approve").strip().lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be approve or reject")
    if decision == "approve":
        if not isinstance(suggestions, list):
            raise HTTPException(status_code=400, detail="medicines must be a list for approval")
        saved = store.save_meds(user_id, suggestions)
        _append_audit(
            user_id,
            action="report_medicines_approved",
            summary=f"Imported medicines from report were approved ({len(saved)} items).",
            actor_name=str(payload.get("actor_name") or ""),
            actor_role=str(payload.get("actor_role") or ""),
            meta={"report_id": report_id, "count": len(saved)},
        )
        return {"status": "success", "decision": decision, "medicines": saved}

    _append_audit(
        user_id,
        action="report_medicines_rejected",
        summary="Imported medicines from report were rejected.",
        actor_name=str(payload.get("actor_name") or ""),
        actor_role=str(payload.get("actor_role") or ""),
        meta={"report_id": report_id},
    )
    return {"status": "success", "decision": decision}


@app.post("/reports/{user_id}/{report_id}/share")
async def share_report_analysis(user_id: str, report_id: str, payload: dict[str, Any] | None = None):
    payload = payload or {}
    report = next((item for item in store.list_reports(user_id, limit=200) if str(item.get("id") or "") == report_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{settings.alerts_service_url}/report-share",
            json={
                "user_id": user_id,
                "file_name": report.get("file_name"),
                "summary": report.get("summary"),
                "advice": report.get("advice"),
                "severity": payload.get("severity") or 55,
            },
        )
    if response.is_error:
        detail: Any = response.text
        try:
            detail = response.json()
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    _append_audit(
        user_id,
        action="report_shared",
        summary=f"Report analysis for {report.get('file_name') or 'report'} was shared with the support circle.",
        actor_name=str(payload.get("actor_name") or ""),
        actor_role=str(payload.get("actor_role") or ""),
        meta={"report_id": report_id},
    )
    return {"status": "success", "report": report, "delivery": response.json()}


@app.get("/activity/{user_id}")
async def get_activity(user_id: str):
    return {"status": "success", "activity": _compute_activity(user_id)}


@app.post("/activity/{user_id}/status")
async def update_activity(user_id: str, payload: dict[str, Any]):
    today = _today_key()
    updated = store.update_wellness_day(user_id, today, payload)
    note = str(payload.get("note") or payload.get("status") or "").strip()
    if note:
        store.append_conversation(
            user_id,
            {
                "ts": _now().isoformat(),
                "text_input": note,
                "ai_response": "Thanks for sharing today's status.",
                "mood": payload.get("mood") or payload.get("status") or "okay",
                "emotion": "supportive",
                "source": "activity",
            },
        )
    return {"status": "success", "activity": updated}


@app.get("/dashboard/{caregiver_id}")
async def dashboard(caregiver_id: str):
    user_id = _resolve_user_id(caregiver_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="No linked parent profile found")
    user = store.get_user(user_id)
    return {
        "caregiver_id": caregiver_id,
        "user": user,
        "support_contacts": _support_contacts(user),
        "recent_conversations": store.list_conversations(user_id, limit=12),
        "medicine_logs": store.list_med_logs(user_id, limit=20),
        "alerts": store.list_alerts(user_id, limit=20),
        "memories": store.list_memories(user_id, limit=8),
    }


@app.get("/report/weekly/{user_id}")
async def weekly(user_id: str):
    return _compute_report(user_id)
