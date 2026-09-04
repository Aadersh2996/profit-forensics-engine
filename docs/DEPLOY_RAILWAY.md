# Deploy the FastAPI backend to Railway

This guide deploys the existing FastAPI service only. Complete it before deploying the frontend, because Vercel needs the backend's public URL.

## Before you begin

- Push the repository to GitHub. Do not commit `.env` files, databases, or Razorpay/OpenAI secrets.
- Create or sign in to a Railway account.
- Keep the repository layout unchanged: the backend service lives in `backend/`.

## Create the Railway service

1. In Railway, select **New Project** and then **Deploy from GitHub repo**.
2. Authorize GitHub if prompted, select this repository, and select the branch to deploy (normally `main`).
3. Open the new service, choose **Settings**, and set **Root Directory** to `backend`.
4. Confirm the build uses the checked-in `backend/Dockerfile`. The checked-in `backend/railway.json` sets the Dockerfile builder and `/health` deployment health check.
5. Under **Settings** → **Volumes**, choose **Add Volume** and use `/data` as the mount path. This is required: the service intentionally uses SQLite and stores uploaded CSV evidence there.

## Add service variables

Open the service **Variables** page. Add the following values exactly; Railway keeps secret values out of the repository.

| Variable | Value | Required |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | Yes |
| `DATABASE_URL` | `sqlite:////data/profit_forensics.db` | Yes |
| `UPLOAD_DIR` | `/data/uploads` | Yes |
| `CONFIDENCE_THRESHOLD` | `0.7` | Yes |
| `OPENAI_API_KEY` | Your key | Optional; narrative synthesis only |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Optional |
| `RAZORPAY_KEY_ID` | Razorpay Test/Live key ID | Optional; read-only REST sync |
| `RAZORPAY_KEY_SECRET` | Matching Razorpay key secret | Optional; never place this in Vercel |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook secret from Razorpay Dashboard | Optional; required only for webhooks |

Leave optional values unset when they are not in use. CSV upload and the checked-in demo dataset need no third-party credentials.

## Deploy and verify

1. Select **Deploy** (or wait for Railway's automatic GitHub deployment).
2. Open the deployment logs. A healthy startup logs that Profit Forensics Engine started in production.
3. In **Settings** → **Networking**, select **Generate Domain**. Railway supplies a URL similar to `https://<project>.up.railway.app`.
4. Open `https://<project>.up.railway.app/health`. It must return a JSON response with `"status": "ok"`.
5. Save this base URL without a trailing slash. It becomes Vercel's `NEXT_PUBLIC_API_URL`.

## Optional Razorpay webhook

After Railway has a public HTTPS domain, configure Razorpay Dashboard to send events to:

```text
https://<project>.up.railway.app/razorpay/webhook
```

Set the identical webhook secret in Railway as `RAZORPAY_WEBHOOK_SECRET`. Webhook verification occurs on the raw request body; do not route this endpoint through a credential-injecting proxy.

## Troubleshooting

- **Health check fails:** verify the Root Directory is `backend`, deployment logs show the Dockerfile build, and `/health` is reachable on the generated domain.
- **Uploads or cases disappear after deployment:** verify a Railway Volume is attached at `/data` and the two persistence variables match the table above.
- **Razorpay sync says credentials are unavailable:** supply request-scoped credentials in the UI or set both server-side Razorpay REST variables in Railway.
