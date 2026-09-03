# Profit Forensics Engine

Profit Forensics Engine is a FastAPI and LangGraph MVP for deterministic financial investigations. It identifies payment recovery, refund, discount, subscription, and invoice-collection signals from supplied CSV datasets. LLMs are limited to optional root-cause, recommendation, and executive-report wording; all routing, detection, confidence, retry decisions, and financial calculations are deterministic.

## Architecture

- `backend/app/models/schemas.py` contains the validated public and domain contracts.
- `backend/app/graph/state.py` defines the LangGraph runtime state. CSV data is loaded only while an investigator runs and is never stored in state.
- `backend/app/graph/nodes/` contains the case manager, planner, five investigators, refinement, synthesis, and report nodes.
- `backend/app/graph/builder.py` compiles the fixed investigation workflow.
- `backend/app/api/` exposes dataset upload and investigation endpoints.
- `backend/app/services/razorpay_normalization.py` is a pure provider-payload boundary; it does not make Razorpay API calls.

The global retry budget is one. A refinement transition changes the active plan item to `retrying`; the router then reruns only that investigator.

## Run locally

From `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The service exposes `GET /health` and interactive API documentation at `/docs`.

## API flow

1. Upload a CSV with `POST /datasets/upload`, supplying multipart fields `dataset_type` and `file`.
2. Submit returned dataset metadata to `POST /investigations`.
3. Retrieve a persisted report with `GET /investigations/{investigation_id}`.

`dataset_type` controls deterministic plan selection. Supported type keywords include `payment`, `refund`, `discount`, `subscription`, `invoice`, and `settlement`.

## Optional LLM synthesis

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` to enable root-cause hypotheses, recommendations, and executive-report synthesis. Without credentials, the engine completes with an explicit deterministic executive-summary fallback. No LLM receives authority to calculate money, confidence, or routing decisions.

## Testing

From `backend`:

```powershell
python -m pytest ..\tests
python -m compileall app
```

See `demo/README.md` for a complete synthetic demo dataset and walkthrough.
