from __future__ import annotations

import json
import hashlib
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, MongoClient


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str | None, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return cleaned or fallback


_file_locks: dict[str, threading.Lock] = {}
_file_locks_guard = threading.Lock()


def _get_file_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _file_locks_guard:
        if key not in _file_locks:
            _file_locks[key] = threading.Lock()
        return _file_locks[key]


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _locked_update(path: Path, default: Any, updater):
    """Read-modify-write with a per-file lock to prevent race conditions."""
    lock = _get_file_lock(path)
    with lock:
        data = _load(path, default)
        result = updater(data)
        _save(path, data)
        return result


def _merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if value is None:
            continue
        out[key] = value
    return out


def _password_hash(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _password_verify(password: str, hashed: str) -> bool:
    import bcrypt
    # Support legacy SHA-256 hashes during migration
    if len(hashed) == 64 and all(c in "0123456789abcdef" for c in hashed):
        if hashlib.sha256(password.encode("utf-8")).hexdigest() == hashed:
            return True
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _normalize_user(user: dict[str, Any]) -> dict[str, Any]:
    out = dict(user)
    caretaker_name = out.get("caretaker_name") or out.get("caregiver_name")
    caretaker_phone = out.get("caretaker_phone") or out.get("caregiver_phone")
    if caretaker_name:
        out["caretaker_name"] = caretaker_name
        out["caregiver_name"] = caretaker_name
    if caretaker_phone:
        out["caretaker_phone"] = caretaker_phone
        out["caregiver_phone"] = caretaker_phone
    settings = dict(out.get("settings") or {})
    settings.setdefault("history_enabled", True)
    settings.setdefault("location_enabled", True)
    settings.setdefault("wake_word_enabled", True)
    settings.setdefault("wake_words", DEFAULT_WAKE_WORDS)
    settings.setdefault("auto_send_on_pause", True)
    out["settings"] = settings
    out.setdefault("conditions", [])
    out.setdefault("allergies", [])
    out.setdefault("preferences", [])
    out.setdefault("family_contacts", [])
    out.setdefault("origin", "")
    return out


DEFAULT_WAKE_WORDS = ["bhumi", "hey bhumi", "hi bhumi", "hello bhumi"]

LEGACY_SEED_USER_IDS = {"prajwal", "aniket"}
LEGACY_SEED_ACCOUNT_EMAILS = {
    "prajwal@eldermind.app",
    "aniket@eldermind.app",
    "kiran.support@eldermind.app",
    "aniketbxr11@gmail.com",
    "rhea.support@eldermind.app",
    "meera.support@eldermind.app",
}


@dataclass(frozen=True)
class StorePaths:
    root: Path

    @property
    def users(self) -> Path:
        return self.root / "users.json"

    @property
    def meds(self) -> Path:
        return self.root / "meds.json"

    @property
    def conv(self) -> Path:
        return self.root / "conversations.json"

    @property
    def alerts(self) -> Path:
        return self.root / "alerts.json"

    @property
    def med_logs(self) -> Path:
        return self.root / "med_logs.json"

    @property
    def memories(self) -> Path:
        return self.root / "memories.json"

    @property
    def alarms(self) -> Path:
        return self.root / "alarms.json"

    @property
    def wellness(self) -> Path:
        return self.root / "wellness.json"

    @property
    def reports(self) -> Path:
        return self.root / "reports.json"

    @property
    def audit(self) -> Path:
        return self.root / "audit.json"

    @property
    def sessions(self) -> Path:
        return self.root / "sessions.json"

    @property
    def accounts(self) -> Path:
        return self.root / "accounts.json"


class LocalStore:
    def __init__(self, data_dir: str):
        self.paths = StorePaths(Path(data_dir))
        self.paths.root.mkdir(parents=True, exist_ok=True)
        self._ensure_storage()
        self._cleanup_legacy_seed_data()

    def _ensure_storage(self) -> None:
        for path, default in [
            (self.paths.users, {}),
            (self.paths.meds, {}),
            (self.paths.conv, {}),
            (self.paths.alerts, {}),
            (self.paths.med_logs, {}),
            (self.paths.memories, {}),
            (self.paths.alarms, {}),
            (self.paths.wellness, {}),
            (self.paths.reports, {}),
            (self.paths.audit, {}),
            (self.paths.sessions, {}),
            (self.paths.accounts, {}),
        ]:
            if not path.exists():
                _save(path, default)

    def _cleanup_legacy_seed_data(self) -> None:
        users = _load(self.paths.users, {})
        for user_id in LEGACY_SEED_USER_IDS:
            users.pop(user_id, None)
        _save(self.paths.users, users)

        accounts = _load(self.paths.accounts, {})
        cleaned_accounts = {
            account_id: item
            for account_id, item in accounts.items()
            if str((item or {}).get("email") or "").strip().lower() not in LEGACY_SEED_ACCOUNT_EMAILS
        }
        _save(self.paths.accounts, cleaned_accounts)

        sessions = _load(self.paths.sessions, {})
        cleaned_sessions = {
            session_id: item
            for session_id, item in sessions.items()
            if str((item or {}).get("user_id") or "").strip() not in LEGACY_SEED_USER_IDS
            and str((item or {}).get("email") or "").strip().lower() not in LEGACY_SEED_ACCOUNT_EMAILS
        }
        _save(self.paths.sessions, cleaned_sessions)

        for path in [self.paths.meds, self.paths.conv, self.paths.alerts, self.paths.med_logs, self.paths.memories, self.paths.alarms, self.paths.wellness, self.paths.reports, self.paths.audit]:
            data = _load(path, {})
            for user_id in LEGACY_SEED_USER_IDS:
                data.pop(user_id, None)
            _save(path, data)

    def list_users(self) -> list[dict[str, Any]]:
        return [_normalize_user(item) for item in list((_load(self.paths.users, {})).values())]

    def get_user(self, user_id: str) -> dict[str, Any]:
        users = _load(self.paths.users, {})
        return _normalize_user(users.get(user_id) or {"user_id": user_id})

    def find_user_by_caregiver(self, key: str) -> dict[str, Any] | None:
        slug = _slugify(key, "")
        for user in self.list_users():
            if user.get("user_id") == key:
                return user
            if _slugify(str(user.get("caregiver_name") or ""), "") == slug:
                return user
            if _slugify(str(user.get("caretaker_name") or ""), "") == slug:
                return user
            for contact in user.get("family_contacts") or []:
                if not isinstance(contact, dict):
                    continue
                if contact.get("id") == key or _slugify(str(contact.get("name") or ""), "") == slug:
                    return user
        return None

    def upsert_user(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = {}
        def _update(users):
            nonlocal result
            existing = users.get(user_id) or {"user_id": user_id}
            merged = _normalize_user(_merge_dict(existing, payload))
            merged["user_id"] = user_id
            users[user_id] = merged
            result = merged
        _locked_update(self.paths.users, {}, _update)
        return result

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        role = str(payload.get("role") or "elder").lower()
        sessions = _load(self.paths.sessions, {})
        session_id = str(uuid4())

        if role in {"caregiver", "caretaker", "support"}:
            target_user_id = str(payload.get("user_id") or "")
            user = self.get_user(target_user_id)
            caregiver_name = str(payload.get("name") or user.get("caretaker_name") or user.get("caregiver_name") or "Support")
            caregiver_id = _slugify(str(payload.get("caregiver_id") or caregiver_name), "caretaker")
            session = {
                "session_id": session_id,
                "role": "support",
                "user_id": target_user_id,
                "caregiver_id": caregiver_id,
                "display_name": caregiver_name,
                "email": payload.get("email"),
                "created_at": _now_iso(),
            }
        else:
            name = str(payload.get("name") or "Ramesh").strip() or "Ramesh"
            requested_id = str(payload.get("user_id") or "").strip()
            user_id = requested_id or _slugify(name, "elder")
            existing = self.get_user(user_id) if requested_id else {}
            profile = self.upsert_user(
                user_id,
                {
                    "name": name,
                    "age": payload.get("age") or existing.get("age") or 72,
                    "language": payload.get("language") or existing.get("language") or "Hindi",
                    "region": payload.get("region") or existing.get("region") or "",
                    "city": payload.get("city") or existing.get("city") or "",
                    "origin": payload.get("origin") or existing.get("origin") or "",
                    "wake_time": payload.get("wake_time") or existing.get("wake_time") or "07:00",
                    "sleep_time": payload.get("sleep_time") or existing.get("sleep_time") or "21:00",
                    "caretaker_name": payload.get("caretaker_name") or payload.get("caregiver_name") or existing.get("caretaker_name") or existing.get("caregiver_name") or "",
                    "caretaker_phone": payload.get("caretaker_phone") or payload.get("caregiver_phone") or existing.get("caretaker_phone") or existing.get("caregiver_phone") or "",
                    "phone": payload.get("phone") or existing.get("phone") or "",
                    "conditions": payload.get("conditions") or existing.get("conditions") or [],
                    "allergies": payload.get("allergies") or existing.get("allergies") or [],
                    "preferences": payload.get("preferences") or existing.get("preferences") or [],
                    "family_contacts": payload.get("family_contacts") or existing.get("family_contacts") or [],
                    "settings": payload.get("settings") or existing.get("settings") or {},
                },
            )
            session = {
                "session_id": session_id,
                "role": "elder",
                "user_id": user_id,
                "caregiver_id": _slugify(str(profile.get("caretaker_name") or profile.get("caregiver_name") or "caretaker"), "caretaker"),
                "display_name": profile.get("name") or name,
                "email": payload.get("email"),
                "created_at": _now_iso(),
            }

        sessions[session_id] = session
        _save(self.paths.sessions, sessions)
        return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return (_load(self.paths.sessions, {})).get(session_id)

    def list_accounts(self) -> list[dict[str, Any]]:
        return list((_load(self.paths.accounts, {})).values())

    def find_account_by_email(self, email: str) -> dict[str, Any] | None:
        normalized = email.strip().lower()
        for account in self.list_accounts():
            if str(account.get("email") or "").strip().lower() == normalized:
                return account
        return None

    def find_account_by_user_id(self, user_id: str, *, role: str | None = None) -> dict[str, Any] | None:
        normalized = user_id.strip().lower()
        for account in self.list_accounts():
            if str(account.get("user_id") or "").strip().lower() != normalized:
                continue
            if role and str(account.get("role") or "").strip().lower() != role.strip().lower():
                continue
            return account
        return None

    def create_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        accounts = _load(self.paths.accounts, {})
        account_id = str(uuid4())
        role = str(payload.get("role") or "elder").lower()
        user_id = str(payload.get("user_id") or "").strip().lower()
        email = str(payload.get("email") or "").strip().lower()
        if not email and role == "elder" and user_id:
            email = f"{user_id}@parent.bhumi.local"
        account = {
            "account_id": account_id,
            "email": email,
            "password_hash": _password_hash(str(payload.get("password") or "")),
            "role": role,
            "user_id": user_id,
            "name": str(payload.get("name") or "").strip(),
            "relation": str(payload.get("relation") or "").strip(),
            "phone": str(payload.get("phone") or "").strip(),
            "managed_user_ids": list(payload.get("managed_user_ids") or []),
            "created_at": _now_iso(),
        }
        accounts[account_id] = account
        _save(self.paths.accounts, accounts)
        return account

    def login_account(self, identifier: str, password: str) -> dict[str, Any] | None:
        account = self.find_account_by_email(identifier)
        if not account and "@" not in identifier:
            account = self.find_account_by_user_id(identifier, role="elder")
        if not account:
            return None
        if not _password_verify(password, str(account.get("password_hash") or "")):
            return None
        # Rehash legacy SHA-256 to bcrypt on successful login
        if len(str(account.get("password_hash") or "")) == 64:
            self.update_account(str(account["account_id"]), {"password_hash": _password_hash(password)})
        return account

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        return (_load(self.paths.accounts, {})).get(account_id)

    def update_account(self, account_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        accounts = _load(self.paths.accounts, {})
        account = accounts.get(account_id)
        if not isinstance(account, dict):
            return None
        merged = _merge_dict(account, payload)
        accounts[account_id] = merged
        _save(self.paths.accounts, accounts)
        return merged

    def delete_account(self, account_id: str) -> bool:
        accounts = _load(self.paths.accounts, {})
        if account_id not in accounts:
            return False
        accounts.pop(account_id, None)
        _save(self.paths.accounts, accounts)
        return True

    def add_managed_user(self, account_id: str, user_id: str) -> dict[str, Any] | None:
        account = self.get_account(account_id)
        if not account:
            return None
        managed = list(account.get("managed_user_ids") or [])
        if user_id not in managed:
            managed.append(user_id)
        return self.update_account(account_id, {"managed_user_ids": managed})

    def list_meds(self, user_id: str) -> list[dict[str, Any]]:
        meds = _load(self.paths.meds, {})
        return meds.get(user_id) or []

    def save_meds(self, user_id: str, meds: list[dict[str, Any]]) -> list[dict[str, Any]]:
        data = _load(self.paths.meds, {})
        data[user_id] = meds
        _save(self.paths.meds, data)
        return meds

    def append_med_log(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {"id": item.get("id") or str(uuid4()), **item}
        def _update(data):
            data.setdefault(user_id, [])
            data[user_id].append(record)
        _locked_update(self.paths.med_logs, {"demo": []}, _update)
        return record

    def list_med_logs(self, user_id: str, limit: int = 30) -> list[dict[str, Any]]:
        data = _load(self.paths.med_logs, {"demo": []})
        return (data.get(user_id, []) or [])[-limit:]

    def append_conversation(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {"id": item.get("id") or str(uuid4()), **item}
        def _update(data):
            data.setdefault(user_id, [])
            data[user_id].append(record)
        _locked_update(self.paths.conv, {"demo": []}, _update)
        return record

    def list_conversations(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        data = _load(self.paths.conv, {"demo": []})
        return (data.get(user_id, []) or [])[-limit:]

    def clear_conversations(self, user_id: str) -> None:
        data = _load(self.paths.conv, {"demo": []})
        data[user_id] = []
        _save(self.paths.conv, data)

    def delete_conversation(self, user_id: str, item_id: str) -> None:
        data = _load(self.paths.conv, {"demo": []})
        data[user_id] = [item for item in (data.get(user_id) or []) if str(item.get("id") or "") != item_id]
        _save(self.paths.conv, data)

    def delete_conversations_for_day(self, user_id: str, day_key: str) -> None:
        data = _load(self.paths.conv, {"demo": []})
        data[user_id] = [
            item
            for item in (data.get(user_id) or [])
            if not str(item.get("ts") or "").startswith(day_key)
        ]
        _save(self.paths.conv, data)

    def append_alert(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {"id": item.get("id") or str(uuid4()), **item}
        def _update(data):
            data.setdefault(user_id, [])
            data[user_id].append(record)
        _locked_update(self.paths.alerts, {"demo": []}, _update)
        return record

    def list_alerts(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        data = _load(self.paths.alerts, {"demo": []})
        return (data.get(user_id, []) or [])[-limit:]

    def clear_alerts(self, user_id: str) -> None:
        data = _load(self.paths.alerts, {"demo": []})
        data[user_id] = []
        _save(self.paths.alerts, data)

    def add_memory(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        data = _load(self.paths.memories, {"demo": []})
        data.setdefault(user_id, [])
        fact = str(item.get("fact") or "").strip()
        category = str(item.get("category") or "general").strip() or "general"
        if fact:
            for existing in data[user_id]:
                if not isinstance(existing, dict):
                    continue
                if str(existing.get("fact") or "").strip().lower() == fact.lower() and existing.get("category") == category:
                    existing["date"] = item.get("date") or _now_iso()
                    existing["source"] = item.get("source") or existing.get("source") or "conversation"
                    _save(self.paths.memories, data)
                    return existing
        record = {
            "id": item.get("id") or str(uuid4()),
            "fact": fact,
            "date": item.get("date") or _now_iso(),
            "category": category,
            "source": item.get("source") or "conversation",
        }
        data[user_id].append(record)
        _save(self.paths.memories, data)
        return record

    def list_memories(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        data = _load(self.paths.memories, {"demo": []})
        return (data.get(user_id, []) or [])[-limit:]

    def clear_memories(self, user_id: str) -> None:
        data = _load(self.paths.memories, {"demo": []})
        data[user_id] = []
        _save(self.paths.memories, data)

    def add_alarm(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        data = _load(self.paths.alarms, {"demo": []})
        data.setdefault(user_id, [])
        record = {
            "id": item.get("id") or str(uuid4()),
            "user_id": user_id,
            "title": str(item.get("title") or "Alarm").strip() or "Alarm",
            "time_iso": str(item.get("time_iso") or ""),
            "label": str(item.get("label") or "").strip(),
            "created_at": item.get("created_at") or _now_iso(),
            "source": item.get("source") or "manual",
        }
        data[user_id].append(record)
        data[user_id] = sorted(data[user_id], key=lambda alarm: str(alarm.get("time_iso") or ""))
        _save(self.paths.alarms, data)
        return record

    def list_alarms(self, user_id: str) -> list[dict[str, Any]]:
        data = _load(self.paths.alarms, {"demo": []})
        return list(data.get(user_id, []) or [])

    def delete_alarm(self, user_id: str, alarm_id: str) -> None:
        data = _load(self.paths.alarms, {"demo": []})
        data[user_id] = [item for item in (data.get(user_id) or []) if str(item.get("id") or "") != alarm_id]
        _save(self.paths.alarms, data)

    def delete_alarms_by_source(self, user_id: str, source_prefix: str) -> None:
        data = _load(self.paths.alarms, {"demo": []})
        data[user_id] = [
            item
            for item in (data.get(user_id) or [])
            if not str(item.get("source") or "").startswith(source_prefix)
        ]
        _save(self.paths.alarms, data)

    def add_report(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        data = _load(self.paths.reports, {})
        data.setdefault(user_id, [])
        record = {
            "id": item.get("id") or str(uuid4()),
            "user_id": user_id,
            "file_name": str(item.get("file_name") or "report").strip() or "report",
            "mime_type": str(item.get("mime_type") or "image/jpeg").strip() or "image/jpeg",
            "image_data_url": str(item.get("image_data_url") or "").strip(),
            "ocr_text": str(item.get("ocr_text") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
            "advice": str(item.get("advice") or "").strip(),
            "created_at": item.get("created_at") or _now_iso(),
        }
        data[user_id].append(record)
        data[user_id] = sorted(data[user_id], key=lambda report: str(report.get("created_at") or ""), reverse=True)
        _save(self.paths.reports, data)
        return record

    def list_reports(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        data = _load(self.paths.reports, {})
        return list((data.get(user_id) or [])[:limit])

    def delete_report(self, user_id: str, report_id: str) -> None:
        data = _load(self.paths.reports, {})
        data[user_id] = [item for item in (data.get(user_id) or []) if str(item.get("id") or "") != report_id]
        _save(self.paths.reports, data)

    def append_audit(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        data = _load(self.paths.audit, {})
        data.setdefault(user_id, [])
        record = {
            "id": item.get("id") or str(uuid4()),
            "user_id": user_id,
            "action": str(item.get("action") or "update").strip() or "update",
            "actor_name": str(item.get("actor_name") or "").strip(),
            "actor_role": str(item.get("actor_role") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
            "meta": item.get("meta") or {},
            "created_at": item.get("created_at") or _now_iso(),
        }
        data[user_id].append(record)
        data[user_id] = sorted(data[user_id], key=lambda audit: str(audit.get("created_at") or ""), reverse=True)
        _save(self.paths.audit, data)
        return record

    def list_audit(self, user_id: str, limit: int = 40) -> list[dict[str, Any]]:
        data = _load(self.paths.audit, {})
        return list((data.get(user_id) or [])[:limit])

    def get_wellness_day(self, user_id: str, day_key: str) -> dict[str, Any]:
        data = _load(self.paths.wellness, {"demo": {}})
        user_days = data.setdefault(user_id, {})
        return user_days.get(day_key) or {
            "day": day_key,
            "status": "okay",
            "steps": 4200,
            "sleep_hours": 7.5,
            "water_cups": 5,
            "mood": "okay",
            "notes": [],
            "updated_at": _now_iso(),
        }

    def update_wellness_day(self, user_id: str, day_key: str, patch: dict[str, Any]) -> dict[str, Any]:
        data = _load(self.paths.wellness, {"demo": {}})
        user_days = data.setdefault(user_id, {})
        current = self.get_wellness_day(user_id, day_key)
        notes = list(current.get("notes") or [])
        new_note = patch.get("note")
        if isinstance(new_note, str) and new_note.strip():
            notes.append(new_note.strip())
        merged = _merge_dict(current, patch)
        merged["day"] = day_key
        merged["notes"] = notes
        merged["updated_at"] = _now_iso()
        user_days[day_key] = merged
        _save(self.paths.wellness, data)
        return merged


class MongoStore:
    def __init__(self, mongo_uri: str, db_name: str) -> None:
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self._ensure_indexes()
        self._cleanup_legacy_seed_data()

    @staticmethod
    def _clean(doc: dict[str, Any] | None) -> dict[str, Any]:
        if not doc:
            return {}
        out = dict(doc)
        out.pop("_id", None)
        return out

    def _default_wellness_day(self, day_key: str) -> dict[str, Any]:
        return {
            "day": day_key,
            "status": "okay",
            "steps": 4200,
            "sleep_hours": 7.5,
            "water_cups": 5,
            "mood": "okay",
            "notes": [],
            "updated_at": _now_iso(),
        }

    def _ensure_indexes(self) -> None:
        self.db.users.create_index([("user_id", ASCENDING)], unique=True)
        self.db.accounts.create_index([("email", ASCENDING)], unique=True)
        self.db.sessions.create_index([("session_id", ASCENDING)], unique=True)
        self.db.meds.create_index([("user_id", ASCENDING)])
        self.db.med_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.db.conversations.create_index([("user_id", ASCENDING), ("ts", DESCENDING)])
        self.db.alerts.create_index([("user_id", ASCENDING), ("time_created", DESCENDING)])
        self.db.memories.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
        self.db.alarms.create_index([("user_id", ASCENDING), ("time_iso", ASCENDING)])
        self.db.reports.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.db.audit.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.db.wellness.create_index([("user_id", ASCENDING), ("day", ASCENDING)], unique=True)

    def _cleanup_legacy_seed_data(self) -> None:
        self.db.users.delete_many({"user_id": {"$in": list(LEGACY_SEED_USER_IDS)}})
        self.db.accounts.delete_many({"email": {"$in": list(LEGACY_SEED_ACCOUNT_EMAILS)}})
        self.db.sessions.delete_many(
            {
                "$or": [
                    {"user_id": {"$in": list(LEGACY_SEED_USER_IDS)}},
                    {"email": {"$in": list(LEGACY_SEED_ACCOUNT_EMAILS)}},
                ]
            }
        )
        for collection_name in ["meds", "med_logs", "conversations", "alerts", "memories", "alarms", "reports", "audit", "wellness"]:
            getattr(self.db, collection_name).delete_many({"user_id": {"$in": list(LEGACY_SEED_USER_IDS)}})

    def list_users(self) -> list[dict[str, Any]]:
        return [_normalize_user(self._clean(doc)) for doc in self.db.users.find().sort("name", ASCENDING)]

    def get_user(self, user_id: str) -> dict[str, Any]:
        doc = self.db.users.find_one({"user_id": user_id})
        if doc:
            return _normalize_user(self._clean(doc))
        return _normalize_user({"user_id": user_id})

    def find_user_by_caregiver(self, key: str) -> dict[str, Any] | None:
        slug = _slugify(key, "")
        for user in self.list_users():
            if user.get("user_id") == key:
                return user
            if _slugify(str(user.get("caregiver_name") or ""), "") == slug:
                return user
            if _slugify(str(user.get("caretaker_name") or ""), "") == slug:
                return user
            for contact in user.get("family_contacts") or []:
                if not isinstance(contact, dict):
                    continue
                if contact.get("id") == key or _slugify(str(contact.get("name") or ""), "") == slug:
                    return user
        return None

    def upsert_user(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_user(user_id)
        merged = _normalize_user(_merge_dict(existing, payload))
        merged["user_id"] = user_id
        self.db.users.replace_one({"user_id": user_id}, {"_id": user_id, **merged}, upsert=True)
        return merged

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        role = str(payload.get("role") or "elder").lower()
        session_id = str(uuid4())
        if role in {"caregiver", "caretaker", "support"}:
            target_user_id = str(payload.get("user_id") or "")
            user = self.get_user(target_user_id)
            caregiver_name = str(payload.get("name") or user.get("caretaker_name") or user.get("caregiver_name") or "Support")
            caregiver_id = _slugify(str(payload.get("caregiver_id") or caregiver_name), "caretaker")
            session = {
                "session_id": session_id,
                "role": "support",
                "user_id": target_user_id,
                "caregiver_id": caregiver_id,
                "display_name": caregiver_name,
                "email": payload.get("email"),
                "created_at": _now_iso(),
            }
        else:
            name = str(payload.get("name") or "Ramesh").strip() or "Ramesh"
            requested_id = str(payload.get("user_id") or "").strip()
            user_id = requested_id or _slugify(name, "elder")
            existing = self.get_user(user_id) if requested_id else {}
            profile = self.upsert_user(
                user_id,
                {
                    "name": name,
                    "age": payload.get("age") or existing.get("age") or 72,
                    "language": payload.get("language") or existing.get("language") or "Hindi",
                    "region": payload.get("region") or existing.get("region") or "",
                    "city": payload.get("city") or existing.get("city") or "",
                    "origin": payload.get("origin") or existing.get("origin") or "",
                    "wake_time": payload.get("wake_time") or existing.get("wake_time") or "07:00",
                    "sleep_time": payload.get("sleep_time") or existing.get("sleep_time") or "21:00",
                    "caretaker_name": payload.get("caretaker_name") or payload.get("caregiver_name") or existing.get("caretaker_name") or existing.get("caregiver_name") or "",
                    "caretaker_phone": payload.get("caretaker_phone") or payload.get("caregiver_phone") or existing.get("caretaker_phone") or existing.get("caregiver_phone") or "",
                    "phone": payload.get("phone") or existing.get("phone") or "",
                    "conditions": payload.get("conditions") or existing.get("conditions") or [],
                    "allergies": payload.get("allergies") or existing.get("allergies") or [],
                    "preferences": payload.get("preferences") or existing.get("preferences") or [],
                    "family_contacts": payload.get("family_contacts") or existing.get("family_contacts") or [],
                    "settings": payload.get("settings") or existing.get("settings") or {},
                },
            )
            session = {
                "session_id": session_id,
                "role": "elder",
                "user_id": user_id,
                "caregiver_id": _slugify(str(profile.get("caretaker_name") or profile.get("caregiver_name") or "caretaker"), "caretaker"),
                "display_name": profile.get("name") or name,
                "email": payload.get("email"),
                "created_at": _now_iso(),
            }
        self.db.sessions.replace_one({"session_id": session_id}, {"_id": session_id, **session}, upsert=True)
        return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        doc = self.db.sessions.find_one({"session_id": session_id})
        return self._clean(doc) if doc else None

    def list_accounts(self) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.accounts.find().sort("email", ASCENDING)]

    def find_account_by_email(self, email: str) -> dict[str, Any] | None:
        doc = self.db.accounts.find_one({"email": email.strip().lower()})
        return self._clean(doc) if doc else None

    def find_account_by_user_id(self, user_id: str, *, role: str | None = None) -> dict[str, Any] | None:
        query: dict[str, Any] = {"user_id": user_id.strip().lower()}
        if role:
            query["role"] = role.strip().lower()
        doc = self.db.accounts.find_one(query)
        return self._clean(doc) if doc else None

    def create_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        account_id = str(uuid4())
        role = str(payload.get("role") or "elder").lower()
        user_id = str(payload.get("user_id") or "").strip().lower()
        email = str(payload.get("email") or "").strip().lower()
        if not email and role == "elder" and user_id:
            email = f"{user_id}@parent.bhumi.local"
        account = {
            "account_id": account_id,
            "email": email,
            "password_hash": _password_hash(str(payload.get("password") or "")),
            "role": role,
            "user_id": user_id,
            "name": str(payload.get("name") or "").strip(),
            "relation": str(payload.get("relation") or "").strip(),
            "phone": str(payload.get("phone") or "").strip(),
            "managed_user_ids": list(payload.get("managed_user_ids") or []),
            "created_at": _now_iso(),
        }
        self.db.accounts.insert_one({"_id": account_id, **account})
        return account

    def login_account(self, identifier: str, password: str) -> dict[str, Any] | None:
        account = self.find_account_by_email(identifier)
        if not account and "@" not in identifier:
            account = self.find_account_by_user_id(identifier, role="elder")
        if not account:
            return None
        if not _password_verify(password, str(account.get("password_hash") or "")):
            return None
        # Rehash legacy SHA-256 to bcrypt on successful login
        if len(str(account.get("password_hash") or "")) == 64:
            self.update_account(str(account["account_id"]), {"password_hash": _password_hash(password)})
        return account

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        doc = self.db.accounts.find_one({"account_id": account_id})
        return self._clean(doc) if doc else None

    def update_account(self, account_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_account(account_id)
        if not current:
            return None
        merged = _merge_dict(current, payload)
        self.db.accounts.replace_one({"account_id": account_id}, {"_id": account_id, **merged}, upsert=True)
        return merged

    def delete_account(self, account_id: str) -> bool:
        result = self.db.accounts.delete_one({"account_id": account_id})
        return bool(result.deleted_count)

    def add_managed_user(self, account_id: str, user_id: str) -> dict[str, Any] | None:
        current = self.get_account(account_id)
        if not current:
            return None
        managed = list(current.get("managed_user_ids") or [])
        if user_id not in managed:
            managed.append(user_id)
        return self.update_account(account_id, {"managed_user_ids": managed})

    def list_meds(self, user_id: str) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.meds.find({"user_id": user_id}).sort("name", ASCENDING)]

    def save_meds(self, user_id: str, meds: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.db.meds.delete_many({"user_id": user_id})
        if meds:
            docs: list[dict[str, Any]] = []
            for med in meds:
                med_id = str(med.get("id") or uuid4())
                docs.append({"_id": f"{user_id}:{med_id}", "user_id": user_id, **med, "id": med_id})
            self.db.meds.insert_many(docs)
        return meds

    def append_med_log(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {"id": item.get("id") or str(uuid4()), "user_id": user_id, **item}
        self.db.med_logs.insert_one({"_id": record["id"], **record})
        return record

    def list_med_logs(self, user_id: str, limit: int = 30) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.med_logs.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit)][::-1]

    def append_conversation(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {"id": item.get("id") or str(uuid4()), "user_id": user_id, **item}
        self.db.conversations.insert_one({"_id": record["id"], **record})
        return record

    def list_conversations(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.conversations.find({"user_id": user_id}).sort("ts", DESCENDING).limit(limit)][::-1]

    def clear_conversations(self, user_id: str) -> None:
        self.db.conversations.delete_many({"user_id": user_id})

    def delete_conversation(self, user_id: str, item_id: str) -> None:
        self.db.conversations.delete_one({"user_id": user_id, "id": item_id})

    def delete_conversations_for_day(self, user_id: str, day_key: str) -> None:
        self.db.conversations.delete_many({"user_id": user_id, "ts": {"$regex": f"^{re.escape(day_key)}"}})

    def append_alert(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {"id": item.get("id") or str(uuid4()), "user_id": user_id, **item}
        self.db.alerts.insert_one({"_id": record["id"], **record})
        return record

    def list_alerts(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.alerts.find({"user_id": user_id}).sort("time_created", DESCENDING).limit(limit)][::-1]

    def clear_alerts(self, user_id: str) -> None:
        self.db.alerts.delete_many({"user_id": user_id})

    def add_memory(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        fact = str(item.get("fact") or "").strip()
        category = str(item.get("category") or "general").strip() or "general"
        if fact:
            existing = self.db.memories.find_one({"user_id": user_id, "fact": {"$regex": f"^{re.escape(fact)}$", "$options": "i"}, "category": category})
            if existing:
                updated = {
                    **self._clean(existing),
                    "date": item.get("date") or _now_iso(),
                    "source": item.get("source") or existing.get("source") or "conversation",
                }
                self.db.memories.replace_one({"_id": existing["_id"]}, {"_id": existing["_id"], **updated}, upsert=True)
                return updated
        record = {
            "id": item.get("id") or str(uuid4()),
            "user_id": user_id,
            "fact": fact,
            "date": item.get("date") or _now_iso(),
            "category": category,
            "source": item.get("source") or "conversation",
        }
        self.db.memories.insert_one({"_id": record["id"], **record})
        return record

    def list_memories(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.memories.find({"user_id": user_id}).sort("date", DESCENDING).limit(limit)][::-1]

    def clear_memories(self, user_id: str) -> None:
        self.db.memories.delete_many({"user_id": user_id})

    def add_alarm(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": item.get("id") or str(uuid4()),
            "user_id": user_id,
            "title": str(item.get("title") or "Alarm").strip() or "Alarm",
            "time_iso": str(item.get("time_iso") or ""),
            "label": str(item.get("label") or "").strip(),
            "created_at": item.get("created_at") or _now_iso(),
            "source": item.get("source") or "manual",
        }
        self.db.alarms.insert_one({"_id": record["id"], **record})
        return record

    def list_alarms(self, user_id: str) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.alarms.find({"user_id": user_id}).sort("time_iso", ASCENDING)]

    def delete_alarm(self, user_id: str, alarm_id: str) -> None:
        self.db.alarms.delete_one({"user_id": user_id, "id": alarm_id})

    def delete_alarms_by_source(self, user_id: str, source_prefix: str) -> None:
        self.db.alarms.delete_many({"user_id": user_id, "source": {"$regex": f"^{re.escape(source_prefix)}"}})

    def add_report(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": item.get("id") or str(uuid4()),
            "user_id": user_id,
            "file_name": str(item.get("file_name") or "report").strip() or "report",
            "mime_type": str(item.get("mime_type") or "image/jpeg").strip() or "image/jpeg",
            "image_data_url": str(item.get("image_data_url") or "").strip(),
            "ocr_text": str(item.get("ocr_text") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
            "advice": str(item.get("advice") or "").strip(),
            "created_at": item.get("created_at") or _now_iso(),
        }
        self.db.reports.insert_one({"_id": record["id"], **record})
        return record

    def list_reports(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.reports.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit)]

    def delete_report(self, user_id: str, report_id: str) -> None:
        self.db.reports.delete_one({"user_id": user_id, "id": report_id})

    def append_audit(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": item.get("id") or str(uuid4()),
            "user_id": user_id,
            "action": str(item.get("action") or "update").strip() or "update",
            "actor_name": str(item.get("actor_name") or "").strip(),
            "actor_role": str(item.get("actor_role") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
            "meta": item.get("meta") or {},
            "created_at": item.get("created_at") or _now_iso(),
        }
        self.db.audit.insert_one({"_id": record["id"], **record})
        return record

    def list_audit(self, user_id: str, limit: int = 40) -> list[dict[str, Any]]:
        return [self._clean(doc) for doc in self.db.audit.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit)]

    def get_wellness_day(self, user_id: str, day_key: str) -> dict[str, Any]:
        doc = self.db.wellness.find_one({"user_id": user_id, "day": day_key})
        if doc:
            return self._clean(doc)
        return self._default_wellness_day(day_key)

    def update_wellness_day(self, user_id: str, day_key: str, patch: dict[str, Any]) -> dict[str, Any]:
        current = self.get_wellness_day(user_id, day_key)
        notes = list(current.get("notes") or [])
        note = patch.get("note")
        if isinstance(note, str) and note.strip():
            notes.append(note.strip())
        merged = _merge_dict(current, patch)
        merged["user_id"] = user_id
        merged["day"] = day_key
        merged["notes"] = notes
        merged["updated_at"] = _now_iso()
        self.db.wellness.replace_one({"user_id": user_id, "day": day_key}, {"_id": f"{user_id}:{day_key}", **merged}, upsert=True)
        return merged


Store = LocalStore | MongoStore
