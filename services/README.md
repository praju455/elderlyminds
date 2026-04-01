# ElderMind Services

This folder contains the internal microservices:

- `ai_service` (STT/emotion/LLM/TTS)
- `data_service` (persistence + reports)
- `alerts_service` (Twilio + SOS + severity logic)
- `scheduler_service` (APScheduler jobs)

The public entrypoint is the `gateway/` FastAPI app.

