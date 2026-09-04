# Profit Forensics Engine — Judging Guide

## Three-minute demo script

**0:00–0:25 — Problem.** Payment operations data is fragmented across refunds, failed payments, discounts, subscriptions, and invoices. Teams need evidence and impact, not a black-box anomaly score.

**0:25–0:55 — Ingestion.** On the landing page, select **Run demo dataset**. Explain that it uploads the checked-in synthetic CSVs through the same API used for a customer upload. There are no mocked report values.

**0:55–1:25 — Investigation.** Continue to case creation and launch it. Point out that the planner selects investigators from dataset metadata. The completion page deliberately waits for authoritative persisted state rather than inventing progress.

**1:25–2:20 — Dashboard.** Show monthly and annual exposure, the selected plan, case cards, traceable record counts, and confidence. Open Timeline to show the bounded refinement and final report milestones.

**2:20–3:00 — Differentiator.** Explain that calculations, routing, anomaly rules, confidence, and retries are deterministic. LLMs are confined to optional narrative synthesis, never arithmetic. Open Connect Razorpay to show the REST and webhook ingestion paths are normalized before the same engine.

## Five-minute demo script

Use the three-minute flow, then add:

1. **Cases tab:** choose a payment or invoice case and point to rule, source records, confidence, and traceable amount.
2. **Executive report:** explain the deterministic fallback works even when no OpenAI key is configured.
3. **Razorpay page:** show Test Mode credential guidance, selected resources, environment-credential status, and the fact that credentials are not stored.
4. **Architecture:** use the React Flow visual and README diagram. CSV, REST, and signed webhook payloads converge at the normalizer and then use identical planner/investigator contracts.
5. **Webhook proof:** mention `POST /razorpay/webhook` validates raw-body HMAC-SHA256, records source timeline annotations, and starts a fresh existing investigation.

## Judge talking points

- This is a financial-operations investigation product, not a generic chatbot dashboard.
- It turns operational records into case files that a finance or payments team can verify.
- The deterministic layer prevents a language model from inventing amounts or risk scores.
- Razorpay is a first-class source through REST and verified webhooks, while CSV keeps the demo usable without credentials.
- The UI makes it easy to explain how a number was produced.

## Architecture explanation

All sources create the existing `DatasetMetadata` contract. DataFrames are temporary; they never enter LangGraph state. The deterministic planner uses metadata to choose the relevant investigators. Investigators emit evidence and case files. A global retry budget of one bounds evidence refinement. Deterministic impact estimation runs before optional narrative synthesis and persisted reporting.

## Why deterministic investigators

Financial investigation needs reproducibility. Given the same rows, the system should make the same routing, rule, confidence, retry, and financial-impact decisions. That lets an operator review the inputs and trust that the report is not based on generated arithmetic.

## Why LangGraph

LangGraph gives the investigation explicit typed state, visible stages, pure routing, and a bounded retry path. It helps structure multi-step analysis without turning deterministic business rules into opaque prompts.

## Why confidence refinement

Low confidence does not automatically mean a finding is wrong—it can mean supporting data would materially improve evidence. The system performs at most one deterministic refinement when the required corroborating data exists, then completes. It cannot loop forever.

## Razorpay integration

REST synchronization uses read-only credentials, pagination, bounded retry handling, response validation, and provider normalization. Webhooks validate the raw request body with `X-Razorpay-Signature` before parsing. Both flows emit the same normalized records and ordinary dataset metadata, so investigators do not need Razorpay-specific code.

## Without live API credentials

Use the **Run demo dataset** shortcut. It loads six synthetic CSVs already committed in `demo/` through the real upload endpoint. The full graph, planner, investigators, impact estimator, dashboard, and timeline run normally. The Razorpay page remains available to explain Test Mode, environment credentials, and webhook setup.

## Future roadmap

- Idempotent event handling and queued webhook work.
- Authoritative streaming progress for longer investigations.
- Authenticated workspaces and retention controls.
- Managed persistence and production migrations.
- Broader provider fixtures and reconciliation sources.
