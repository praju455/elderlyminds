# Bhumi — Voice-First AI Companion for Elderly Indians

**Never let your grandparent feel alone. Bhumi is their always-listening family member.**

---

## What Is Bhumi?

Bhumi is a **voice-first AI companion** that talks to elderly Indians in their own language — Hindi, Kannada, Tamil, Telugu, Gujarati, Marathi, and English. Zero typing. Zero complexity. Just talk.

### Core Features

| Feature | Elder | Caregiver |
|---------|-------|-----------|
| Voice companion (multilingual) | Y | - |
| Medicine reminders & tracking | Y | Y |
| Health monitoring & mood detection | Y | Y |
| Camera wellness check (rPPG pulse) | Y | Y |
| Emergency SOS (SMS + WhatsApp) | Y | Y |
| Weekly health reports (PDF export) | Y | Y |
| Cultural/spiritual content library | Y | - |
| Caregiver dashboard | - | Y |
| PWA with offline support | Y | Y |

---

## Architecture

```
                        Vercel
                    +--------------+
                    |   Frontend   |
                    |  React/Vite  |
                    |   (PWA)      |
                    +------+-------+
                           |
                           | HTTPS
                           v
                    +------+-------+        Render
                    |   Gateway    | <---  (all services)
                    |   FastAPI    |
                    +--+---+---+--+
                       |   |   |
            +----------+   |   +-----------+
            v              v               v
      +-----+----+  +-----+-----+  +------+------+
      |    AI    |  |   Data    |  |   Alerts    |
      | Service  |  |  Service  |  |   Service   |
      +----+-----+  +-----+----+  +------+------+
           |               |              |
    +------+------+        v              v
    |  Groq /     |    MongoDB       Twilio / Meta
    |  Gemini     |    Atlas         WhatsApp
    +------+------+
           |
    +------+------+
    | gTTS /      |
    | ElevenLabs  |
    +-------------+

      +-------------+
      |  Scheduler  |  (medicine reminders, check-ins,
      |  Service    |   weekly reports, cultural prompts)
      +-------------+
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| **Gateway** | 8010 | Public API — routes all frontend requests |
| **AI Service** | 8001 | Voice pipeline, LLM, TTS, rPPG, PDF reports |
| **Data Service** | 8002 | MongoDB persistence — users, meds, conversations, reports |
| **Alerts Service** | 8003 | SOS, SMS (Twilio), WhatsApp (Meta), report sharing |
| **Scheduler Service** | 8004 | APScheduler — reminders, check-ins, weekly reports |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- MongoDB Atlas cluster (free tier works)

### 1. Backend

```bash
git clone https://github.com/AdvayaBGSCET/team-pixel-pioneers.git
cd team-pixel-pioneers

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set at minimum:
#   MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
#   GROQ_API_KEY=your-groq-key

# Start all services:
# Windows:
.\run_all.cmd
# Mac/Linux:
bash run_all.sh
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Open

```
http://localhost:5173/index.html
```

### Pages

| URL | Screen |
|-----|--------|
| `/index.html` | Home — voice chat |
| `/medication.html` | Medicine tracking |
| `/activity.html` | Activity & camera wellness |
| `/alert.html` | SOS & health alerts |
| `/summary.html` | Weekly report & PDF export |
| `/culture.html` | Cultural & spiritual content |
| `/support.html` | Family manager login |
| `/caregiver.html` | Caregiver dashboard |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_URI` | Yes | MongoDB Atlas connection string |
| `GROQ_API_KEY` | Yes* | Groq LLM API key |
| `GEMINI_API_KEY` | Yes* | Google Gemini API key |
| `TWILIO_ACCOUNT_SID` | No | Twilio SMS (runs in stub mode without) |
| `TWILIO_AUTH_TOKEN` | No | Twilio auth |
| `TWILIO_FROM_PHONE` | No | Twilio phone number |
| `META_WHATSAPP_TOKEN` | No | Meta WhatsApp Business API |
| `OPENWEATHER_API_KEY` | No | Weather context |
| `ELEVENLABS_API_KEY` | No | Premium TTS voice |

*At least one of Groq or Gemini is needed for the AI to work. Both configured = automatic failover.

---

## Deployment

### Backend — Render

A `render.yaml` blueprint is included. To deploy:

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com) > **New** > **Blueprint**
3. Connect your repo — Render reads `render.yaml` and creates all 5 services
4. Set the secret env vars (MONGO_URI, GROQ_API_KEY, etc.) in each service's settings
5. Set `BASE_URL` on `bhumi-gateway` to its Render URL (e.g. `https://bhumi-gateway.onrender.com`)
6. Set `CORS_ALLOW_ORIGINS` to your Vercel frontend URL

### Frontend — Vercel

1. Go to [Vercel](https://vercel.com) > **New Project**
2. Import the repo, set **Root Directory** to `frontend`
3. Add environment variable: `VITE_API_BASE` = your Render gateway URL
4. Deploy

---

## Project Structure

```
team-pixel-pioneers/
|
+-- frontend/                     # Vite + React multi-page PWA
|   +-- src/
|   |   +-- screens/              # Page components
|   |   +-- ui/                   # Shared UI (AppShell, Cards, RppgCaptureCard, etc.)
|   |   +-- lib/                  # API client, session, speech, IndexedDB
|   +-- public/                   # PWA manifest, service worker, icons
|   +-- vercel.json               # Vercel deployment config
|   +-- vite.config.ts            # Multi-page build config
|
+-- gateway/                      # FastAPI API gateway
|   +-- main.py                   # All public endpoints
|   +-- config.py                 # Service URLs from env
|
+-- services/
|   +-- ai_service/               # AI voice pipeline
|   |   +-- main.py               # /voice, /rppg/analyze, /report/pdf, /culture
|   |   +-- tts.py                # ElevenLabs + gTTS fallback
|   |   +-- stt.py                # ElevenLabs + Whisper fallback
|   |   +-- rppg_analysis.py      # Camera pulse estimation (open-rppg)
|   |   +-- pdf_report.py         # Branded wellness PDF generation
|   |   +-- groq_client.py        # Groq LLM
|   |   +-- gemini_client.py      # Gemini LLM
|   |   +-- markers.py            # [HEALTH_LOG]/[MOOD_LOG]/[ALERT] parser
|   |   +-- cultural_library.py   # 40+ cultural/spiritual items
|   |   +-- vedastro_client.py    # Hindu calendar (tithi, festivals)
|   |   +-- weather_client.py     # OpenWeather context
|   |
|   +-- data_service/             # MongoDB persistence
|   |   +-- main.py               # CRUD endpoints
|   |   +-- store.py              # MongoStore + LocalStore
|   |   +-- config.py             # DB connection config
|   |
|   +-- alerts_service/           # Emergency notifications
|   |   +-- main.py               # SOS, SMS, WhatsApp, report sharing
|   |
|   +-- scheduler_service/        # Background jobs
|       +-- main.py               # Medicine reminders, check-ins, reports
|
+-- render.yaml                   # Render blueprint (all backend services)
+-- requirements.txt              # Python dependencies
+-- .env.example                  # Environment template
+-- prompt.md                     # AI system prompt / behavior contract
+-- run_all.sh                    # Start all services (Mac/Linux)
+-- run_all.cmd                   # Start all services (Windows)
```

---

## Tech Stack

### Frontend
- **React 19 + Vite** — multi-page TypeScript app
- **Tailwind CSS** — elder-friendly, large-touch UI
- **GSAP** — micro-interactions and chart animations
- **PWA** — installable, offline-capable with service worker + IndexedDB

### Backend
- **FastAPI** — async Python microservices
- **MongoDB Atlas** — primary database
- **Groq + Gemini** — dual LLM with automatic failover
- **gTTS + ElevenLabs** — text-to-speech with premium fallback
- **ElevenLabs + Whisper** — speech-to-text
- **open-rppg** — experimental camera pulse estimation
- **APScheduler** — medicine reminders and scheduled check-ins
- **Twilio** — SMS alerts (stub mode if not configured)
- **Meta WhatsApp API** — WhatsApp alerts (stub mode if not configured)
- **reportlab** — PDF wellness report generation

---

## Supported Languages

- Hindi, Kannada, Tamil, Telugu, Gujarati, Marathi, English
- Voice input via Whisper/ElevenLabs (99+ languages)
- Voice output via gTTS/ElevenLabs (multilingual)

---

## Important Notes

1. **Not a medical device** — camera wellness check is experimental (signal quality varies). Never replace doctor consultation.
2. **Caregiver notification only** — alerts are informational, not diagnoses.
3. **Privacy** — raw audio is deleted immediately after transcription. Only text logs are stored.
4. **Graceful degradation** — every external API has a fallback. The app works in stub mode without any API keys (limited to fallback responses).

---

## License

MIT License

---

**Built with care for elderly Indians by Team Pixel Pioneers**
