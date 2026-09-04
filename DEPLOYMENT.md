# Deployment

The submission ships as a FastAPI backend and a Next.js frontend. The frontend proxies browser API requests to FastAPI; this avoids exposing separate cross-origin configuration in the demo.

## Docker Compose

From the repository root, optionally copy `.env.example` to `.env` and set `OPENAI_API_KEY` for synthesis. To enable server-managed Razorpay ingestion, also set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`; otherwise users may supply credentials transiently in the UI. Then run:

```powershell
docker compose up --build
```

Open the demo UI at `http://localhost:3000`. FastAPI health and API documentation are available at `http://localhost:8000/health` and `http://localhost:8000/docs`.

The Compose volume `profit-forensics-data` retains SQLite data and uploaded CSVs across container restarts. It is suitable for a demo deployment; use managed persistence and a migration workflow before a multi-instance production deployment.

## Local startup

Start FastAPI in one terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Start Next.js in a second terminal:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

The browser UI runs at `http://localhost:3000`; `BACKEND_URL` defaults to `http://127.0.0.1:8000`.

## Production configuration

Required operational settings are listed in `.env.example` and `backend/.env.example`.

- Set `ENVIRONMENT=production`.
- Set a durable `DATABASE_URL` and `UPLOAD_DIR`.
- Set `OPENAI_API_KEY` only when optional narrative synthesis is desired.
- Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` only for server-managed, read-only Razorpay ingestion. They are injected into the backend container and must never be committed.
- Tune `RAZORPAY_TIMEOUT_SECONDS` only when the network environment requires it; collection synchronization uses bounded retries and a per-resource record cap.
- Do not commit `.env`, SQLite databases, or uploaded evidence files.
