from __future__ import annotations

import os
import random

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI


AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8001")
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://127.0.0.1:8002")
DEMO_FAST_SCHEDULE = os.getenv("DEMO_FAST_SCHEDULE", "1") == "1"

CHECKIN_VARIATIONS = [
    "Sab theek hai na?",
    "Khaana kha liya?",
    "Paani to pee liya?",
    "Aaj mood kaisa hai?",
    "Thodi der aaraam kiya kya?",
]

app = FastAPI(title="ElderMind Scheduler Service", version="0.2.0")
sched = AsyncIOScheduler()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "scheduler", "running": sched.running}


async def _post_voice(text: str) -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        await client.post(f"{AI_SERVICE_URL}/voice", json={"user_id": "demo", "text": text})


async def _poke_checkin():
    await _post_voice(random.choice(CHECKIN_VARIATIONS))


async def _morning_greeting():
    await _post_voice("Good morning. Kaise neend aayi? Aaj ka din shanti se shuru karte hain.")


async def _cultural_prompt():
    await _post_voice("Ek sundar doha sunna chahenge?")


async def _evening_check():
    await _post_voice("Shaam ho gayi. Aaj ka din kaisa raha?")


async def _bedtime_prompt():
    await _post_voice("Sone ka waqt ho gaya. Koi chhoti si prarthana sunenge?")


async def _weekly_report_ping():
    async with httpx.AsyncClient(timeout=20) as client:
        await client.get(f"{DATA_SERVICE_URL}/weekly-report/demo")


async def _sync_medicine_reminders():
    """Re-sync medicine reminders for all users so alarms repeat daily."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            users_res = await client.get(f"{DATA_SERVICE_URL}/users")
            users = (users_res.json() or {}).get("users") or []
            for user in users:
                user_id = user.get("user_id") or ""
                if user_id:
                    await client.post(f"{DATA_SERVICE_URL}/medicine/{user_id}/sync-reminders")
    except Exception:
        pass


@app.on_event("startup")
async def _startup():
    if DEMO_FAST_SCHEDULE:
        sched.add_job(_poke_checkin, "interval", minutes=2, id="checkin_demo")
        sched.add_job(_cultural_prompt, "interval", minutes=5, id="cultural_demo")
        sched.add_job(_weekly_report_ping, "interval", minutes=7, id="weekly_demo")
        sched.add_job(_morning_greeting, "interval", minutes=11, id="morning_demo")
        sched.add_job(_evening_check, "interval", minutes=13, id="evening_demo")
        sched.add_job(_bedtime_prompt, "interval", minutes=17, id="bedtime_demo")
        sched.add_job(_sync_medicine_reminders, "interval", minutes=9, id="medsync_demo")
    else:
        sched.add_job(_poke_checkin, "interval", hours=2, id="checkin_2h")
        sched.add_job(_cultural_prompt, "cron", hour=15, minute=0, id="cultural_3pm")
        sched.add_job(_weekly_report_ping, "cron", day_of_week="mon", hour=9, minute=0, id="weekly_mon")
        sched.add_job(_morning_greeting, "cron", hour=7, minute=0, id="morning_7am")
        sched.add_job(_evening_check, "cron", hour=18, minute=0, id="evening_6pm")
        sched.add_job(_bedtime_prompt, "cron", hour=21, minute=0, id="bedtime_9pm")
        sched.add_job(_sync_medicine_reminders, "cron", hour=0, minute=5, id="medsync_daily")
    sched.start()


@app.on_event("shutdown")
async def _shutdown():
    if sched.running:
        sched.shutdown(wait=False)
