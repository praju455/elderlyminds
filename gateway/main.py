from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

logger = logging.getLogger("gateway")

_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
]


def _cors_origins() -> list[str]:
    raw = (settings.cors_allow_origins or "").strip()
    if not raw or raw == "*":
        return _ALLOWED_ORIGINS
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- Auth middleware -----------------------------------------------------------

_PUBLIC_PREFIXES = ("/health", "/auth/", "/docs", "/openapi.json")


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """Validates session token on protected routes.

    Expects header: Authorization: Bearer <session_id>
    Validates against the data service's session endpoint.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Allow public routes and OPTIONS (CORS preflight) through
        if request.method == "OPTIONS" or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("authorization") or ""
        session_id = ""
        if auth_header.lower().startswith("bearer "):
            session_id = auth_header[7:].strip()

        if not session_id:
            return JSONResponse(
                status_code=401,
                content={"status": "error", "detail": "Missing or invalid Authorization header. Use: Bearer <session_id>"},
            )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.get(f"{settings.data_service_url}/session/{session_id}")
            if res.is_error:
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "detail": "Invalid or expired session"},
                )
            session_data = res.json()
            request.state.session = session_data
        except httpx.RequestError:
            logger.warning("Could not validate session — data service unreachable, allowing request")
            request.state.session = None

        return await call_next(request)


app = FastAPI(title="ElderMind Gateway", version="0.2.0")

app.add_middleware(SessionAuthMiddleware)
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


async def _proxy_json(method: str, url: str, *, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.request(method, url, json=json, params=params)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc
    if res.is_error:
        detail: Any = res.text
        try:
            payload = res.json()
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("message") or payload
            else:
                detail = payload
        except Exception:
            pass
        raise HTTPException(status_code=res.status_code, detail=detail)
    return res.json()


async def _proxy_raw(method: str, url: str) -> Response:
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.request(method, url)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc
    return Response(
        content=res.content,
        status_code=res.status_code,
        media_type=res.headers.get("content-type"),
        headers={"cache-control": res.headers.get("cache-control", "no-cache")},
    )


@app.get("/media/{path:path}")
async def media(path: str):
    return await _proxy_raw("GET", f"{settings.ai_service_url}/media/{path}")


@app.post("/voice")
async def voice(request: Request):
    user_id = "demo"
    text: str | None = None
    audio: UploadFile | None = None
    lat: float | None = None
    lon: float | None = None

    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        body = await request.json()
        user_id = str(body.get("user_id") or user_id)
        text = body.get("text")
        if body.get("lat") is not None and body.get("lon") is not None:
            try:
                lat = float(body.get("lat"))
                lon = float(body.get("lon"))
            except Exception:
                lat = None
                lon = None
    else:
        form = await request.form()
        user_id = str(form.get("user_id") or user_id)
        text = form.get("text")
        _aud = form.get("audio")
        audio = _aud if hasattr(_aud, "filename") else None
        if form.get("lat") is not None and form.get("lon") is not None:
            try:
                lat = float(str(form.get("lat")))
                lon = float(str(form.get("lon")))
            except Exception:
                lat = None
                lon = None

    if audio is not None:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                files = {"audio": (audio.filename or "audio.webm", await audio.read(), audio.content_type or "application/octet-stream")}
                data = {"user_id": user_id}
                if text:
                    data["text"] = text
                if lat is not None and lon is not None:
                    data["lat"] = str(lat)
                    data["lon"] = str(lon)
                res = await client.post(f"{settings.ai_service_url}/voice", data=data, files=files)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc
        if res.is_error:
            detail: Any = res.text
            try:
                payload = res.json()
                if isinstance(payload, dict):
                    detail = payload.get("detail") or payload.get("message") or payload
                else:
                    detail = payload
            except Exception:
                pass
            raise HTTPException(status_code=res.status_code, detail=detail)
        return res.json()

    payload: dict[str, Any] = {"user_id": user_id, "text": text}
    if lat is not None and lon is not None:
        payload["lat"] = lat
        payload["lon"] = lon
    return await _proxy_json("POST", f"{settings.ai_service_url}/voice", json=payload)


@app.post("/rppg/analyze")
async def rppg_analyze(request: Request):
    form = await request.form()
    user_id = str(form.get("user_id") or "").strip()
    video = form.get("video")
    if video is None or not hasattr(video, "read"):
        raise HTTPException(status_code=400, detail="video file is required")
    try:
        async with httpx.AsyncClient(timeout=240) as client:
            files = {
                "video": (
                    video.filename or "face-video.mp4",
                    await video.read(),
                    video.content_type or "video/mp4",
                )
            }
            data = {"user_id": user_id} if user_id else {}
            res = await client.post(f"{settings.ai_service_url}/rppg/analyze", data=data, files=files)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc
    if res.is_error:
        detail: Any = res.text
        try:
            payload = res.json()
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("message") or payload
            else:
                detail = payload
        except Exception:
            pass
        raise HTTPException(status_code=res.status_code, detail=detail)
    return res.json()


@app.post("/report/analyze")
async def analyze_report(payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.ai_service_url}/report/analyze", json=payload)


@app.post("/auth/session")
async def create_session(payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/auth/session", json=payload)


@app.post("/auth/signup")
async def signup(payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/auth/signup", json=payload)


@app.post("/auth/login")
async def login(payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/auth/login", json=payload)


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    return await _proxy_json("GET", f"{settings.data_service_url}/session/{session_id}")


@app.get("/user/{user_id}")
async def get_user(user_id: str):
    return await _proxy_json("GET", f"{settings.data_service_url}/user/{user_id}")


@app.put("/user/{user_id}")
async def update_user(user_id: str, payload: dict[str, Any]):
    return await _proxy_json("PUT", f"{settings.data_service_url}/user/{user_id}", json=payload)


@app.get("/support/account/{account_id}")
async def support_workspace(account_id: str, active_user_id: str = ""):
    params = {"active_user_id": active_user_id} if active_user_id else None
    return await _proxy_json("GET", f"{settings.data_service_url}/support/account/{account_id}", params=params)


@app.put("/support/account/{account_id}")
async def update_support_account(account_id: str, payload: dict[str, Any]):
    return await _proxy_json("PUT", f"{settings.data_service_url}/support/account/{account_id}", json=payload)


@app.post("/support/account/{account_id}/elders")
async def support_add_elder(account_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/support/account/{account_id}/elders", json=payload)


@app.post("/support/account/{account_id}/caretakers")
async def support_add_caretaker(account_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/support/account/{account_id}/caretakers", json=payload)


@app.post("/support/account/{account_id}/elders/{user_id}/reset-password")
async def support_reset_parent_password(account_id: str, user_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/support/account/{account_id}/elders/{user_id}/reset-password", json=payload)


@app.put("/support/account/{account_id}/caretakers/{contact_id}")
async def support_update_caretaker(account_id: str, contact_id: str, payload: dict[str, Any]):
    return await _proxy_json("PUT", f"{settings.data_service_url}/support/account/{account_id}/caretakers/{contact_id}", json=payload)


@app.delete("/support/account/{account_id}/caretakers/{contact_id}")
async def support_delete_caretaker(account_id: str, contact_id: str, user_id: str):
    return await _proxy_json("DELETE", f"{settings.data_service_url}/support/account/{account_id}/caretakers/{contact_id}", params={"user_id": user_id})


@app.post("/support/account/{account_id}/link-parent")
async def support_link_parent(account_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/support/account/{account_id}/link-parent", json=payload)


@app.get("/medicine/{user_id}")
async def medicines(user_id: str):
    return await _proxy_json("GET", f"{settings.data_service_url}/medicine/{user_id}")


@app.put("/medicine/{user_id}")
async def save_medicines(user_id: str, payload: dict[str, Any]):
    return await _proxy_json("PUT", f"{settings.data_service_url}/medicine/{user_id}", json=payload)


@app.post("/medicine/{user_id}/sync-reminders")
async def sync_medicine_reminders(user_id: str):
    return await _proxy_json("POST", f"{settings.data_service_url}/medicine/{user_id}/sync-reminders")


@app.post("/medicine/{med_id}/confirm")
async def confirm_medicine(med_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/medicine/{med_id}/confirm", json=payload)


@app.get("/conversations/{user_id}")
async def conversations(user_id: str, limit: int = 30):
    return await _proxy_json("GET", f"{settings.data_service_url}/conversations/{user_id}", params={"limit": limit})


@app.post("/conversations/{user_id}")
async def add_conversation(user_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/conversations/{user_id}", json=payload)


@app.delete("/conversations/{user_id}")
async def clear_conversation_history(user_id: str):
    return await _proxy_json("DELETE", f"{settings.data_service_url}/conversations/{user_id}")


@app.delete("/conversations/{user_id}/item/{item_id}")
async def delete_conversation_item(user_id: str, item_id: str):
    return await _proxy_json("DELETE", f"{settings.data_service_url}/conversations/{user_id}/item/{item_id}")


@app.delete("/conversations/{user_id}/day/{day_key}")
async def delete_conversation_day(user_id: str, day_key: str):
    return await _proxy_json("DELETE", f"{settings.data_service_url}/conversations/{user_id}/day/{day_key}")


@app.get("/memory/{user_id}")
async def memories(user_id: str, limit: int = 20):
    return await _proxy_json("GET", f"{settings.data_service_url}/memory/{user_id}", params={"limit": limit})


@app.delete("/memory/{user_id}")
async def clear_memories(user_id: str):
    return await _proxy_json("DELETE", f"{settings.data_service_url}/memory/{user_id}")


@app.post("/alarms/{user_id}")
async def add_alarm(user_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/alarms/{user_id}", json=payload)


@app.get("/alarms/{user_id}")
async def alarms(user_id: str):
    return await _proxy_json("GET", f"{settings.data_service_url}/alarms/{user_id}")


@app.delete("/alarms/{user_id}/{alarm_id}")
async def delete_alarm(user_id: str, alarm_id: str):
    return await _proxy_json("DELETE", f"{settings.data_service_url}/alarms/{user_id}/{alarm_id}")


@app.post("/reports/{user_id}")
async def add_report(user_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/reports/{user_id}", json=payload)


@app.get("/reports/{user_id}")
async def reports(user_id: str, limit: int = 20):
    return await _proxy_json("GET", f"{settings.data_service_url}/reports/{user_id}", params={"limit": limit})


@app.delete("/reports/{user_id}/{report_id}")
async def delete_report(user_id: str, report_id: str):
    return await _proxy_json("DELETE", f"{settings.data_service_url}/reports/{user_id}/{report_id}")


@app.post("/reports/{user_id}/{report_id}/review")
async def review_report(user_id: str, report_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/reports/{user_id}/{report_id}/review", json=payload)


@app.post("/reports/{user_id}/{report_id}/share")
async def share_report(user_id: str, report_id: str, payload: dict[str, Any] | None = None):
    return await _proxy_json("POST", f"{settings.data_service_url}/reports/{user_id}/{report_id}/share", json=payload or {})


@app.get("/audit/{user_id}")
async def audit(user_id: str, limit: int = 40):
    return await _proxy_json("GET", f"{settings.data_service_url}/audit/{user_id}", params={"limit": limit})


@app.get("/activity/{user_id}")
async def activity(user_id: str):
    return await _proxy_json("GET", f"{settings.data_service_url}/activity/{user_id}")


@app.post("/activity/{user_id}/status")
async def update_activity(user_id: str, payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.data_service_url}/activity/{user_id}/status", json=payload)


@app.post("/sos")
async def sos(payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.alerts_service_url}/sos", json=payload)


@app.post("/call")
async def call(payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.alerts_service_url}/call", json=payload)


@app.post("/whatsapp/test")
async def whatsapp_test(payload: dict[str, Any]):
    return await _proxy_json("POST", f"{settings.alerts_service_url}/whatsapp/test", json=payload)


@app.get("/dashboard/{caretaker_id}")
async def dashboard(caretaker_id: str):
    return await _proxy_json("GET", f"{settings.data_service_url}/dashboard/{caretaker_id}")


@app.get("/report/weekly/{user_id}")
async def weekly(user_id: str):
    return await _proxy_json("GET", f"{settings.data_service_url}/report/weekly/{user_id}")


@app.get("/report/pdf/{user_id}")
async def pdf_report(user_id: str):
    return await _proxy_json("GET", f"{settings.ai_service_url}/report/pdf/{user_id}")


@app.get("/culture/library")
async def culture_library(q: str = "", category: str = ""):
    return await _proxy_json("GET", f"{settings.ai_service_url}/culture/library", params={"q": q, "category": category})


@app.get("/culture/daily/{user_id}")
async def culture_daily(user_id: str):
    return await _proxy_json("GET", f"{settings.ai_service_url}/culture/daily/{user_id}")
