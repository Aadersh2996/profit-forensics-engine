# Deployment

Profit Forensics Engine has two deployable services: the Next.js frontend and the FastAPI backend. In the public Buildathon deployment, deploy the backend to Railway and the frontend to Vercel. The frontend keeps browser requests on its own `/api/*` path and rewrites them to Railway, so the application does not need a browser-facing CORS configuration.

For click-by-click instructions, see [Deploy the backend to Railway](docs/DEPLOY_RAILWAY.md) and [Deploy the frontend to Vercel](docs/DEPLOY_VERCEL.md). Deploy Railway first so its public HTTPS URL is available while configuring Vercel.

## Production environment matrix

| Service | Variable | Required | Production value / purpose |
| --- | --- | --- | --- |
| Railway backend | `OPENAI_API_KEY` | Optional | Enables narrative-only synthesis. Leave empty for the deterministic workflow. |
| Railway backend | `OPENAI_MODEL` | Optional | Narrative model; defaults to `gpt-4.1-mini`. |
| Railway backend | `DATABASE_URL` | Yes | `sqlite:////data/profit_forensics.db` when the Railway Volume is mounted at `/data`. |
| Railway backend | `UPLOAD_DIR` | Yes | `/data/uploads` so normalized uploads persist on the same volume. |
| Railway backend | `CONFIDENCE_THRESHOLD` | Yes | `0.7` unless intentionally changed for a validated deployment. |
| Railway backend | `RAZORPAY_KEY_ID` | Optional | Server-managed, read-only Razorpay REST sync. |
| Railway backend | `RAZORPAY_KEY_SECRET` | Optional | Matching Razorpay secret; never expose it to Vercel or the browser. |
| Railway backend | `RAZORPAY_WEBHOOK_SECRET` | Optional* | Required only if enabling Razorpay webhooks. |
| Vercel frontend | `NEXT_PUBLIC_API_URL` | Yes | Railway public URL, e.g. `https://profit-forensics-production.up.railway.app` (no trailing slash). It is a public URL, not a secret. |

`*` CSV upload and the demo dataset work with no Razorpay credentials. Use `ENVIRONMENT=production` on Railway. `MAX_UPLOAD_SIZE_MB` and `RAZORPAY_TIMEOUT_SECONDS` may retain their checked-in defaults unless a deployment has a specific need.

## Docker Compose

From the repository root, optionally copy `.env.example` to `.env` and set `OPENAI_API_KEY` for synthesis. To enable server-managed Razorpay ingestion, also set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`; otherwise users may supply credentials transiently in the UI. Set `RAZORPAY_WEBHOOK_SECRET` when receiving Razorpay webhooks. Then run:

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

The backend Docker image honors Railway's injected `PORT` and otherwise listens on port 8000. The `backend/railway.json` manifest uses `/health` as its deployment health check. Attach a Railway Volume at `/data`; SQLite and uploaded evidence are otherwise ephemeral across a redeploy.

The frontend rewrite is resolved during the Vercel build. After changing `NEXT_PUBLIC_API_URL`, redeploy Vercel so the new backend target is compiled into the rewrite configuration. Never add Razorpay or OpenAI secrets to Vercel.

Set `RAZORPAY_WEBHOOK_SECRET` to the secret configured alongside the public `POST /razorpay/webhook` URL in Razorpay Dashboard. It is separate from the API key secret and must never be committed or logged. Tune `RAZORPAY_TIMEOUT_SECONDS` only when the network environment requires it; collection synchronization uses bounded retries and a per-resource record cap.

## Webhook deployment

Razorpay needs a public HTTPS callback. Route `https://your-host.example/razorpay/webhook` to the backend service, set the same `RAZORPAY_WEBHOOK_SECRET` in the deployment environment and Razorpay Dashboard, then subscribe to the supported payment, refund, order, subscription, invoice, and settlement events documented in the README.

For a local demo, run `ngrok http 8000` after starting the backend and register the generated `https://…/razorpay/webhook` URL in Razorpay Test Mode. Webhook requests are HMAC-SHA256 verified over the raw body with `X-Razorpay-Signature`; malformed requests return 400, malformed shapes return 422, invalid signatures return 401, and an unavailable secret returns 503.
- Do not commit `.env`, SQLite databases, or uploaded evidence files.
