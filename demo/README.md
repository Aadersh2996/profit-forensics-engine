# Demo walkthrough

All CSV files in this folder are synthetic and exist only to demonstrate the engine. They contain deterministic signals for payment recovery, refunds, discounts, subscriptions, and invoice collection.

Start the API from `backend`:

```powershell
uvicorn app.main:app --reload
```

Then, from the repository root, upload each CSV and execute one investigation:

```powershell
$baseUrl = "http://127.0.0.1:8000"
$datasets = @(
    @{ type = "payments"; path = "demo/payments.csv" },
    @{ type = "refunds"; path = "demo/refunds.csv" },
    @{ type = "discounts"; path = "demo/discounts.csv" },
    @{ type = "subscriptions"; path = "demo/subscriptions.csv" },
    @{ type = "invoices"; path = "demo/invoices.csv" },
    @{ type = "settlements"; path = "demo/settlements.csv" }
) | ForEach-Object {
    Invoke-RestMethod -Method Post -Uri "$baseUrl/datasets/upload" -Form @{
        dataset_type = $_.type
        file = Get-Item $_.path
    }
}

$body = @{
    investigation_id = "PF-DEMO-001"
    datasets = @($datasets | ForEach-Object { $_.dataset })
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Method Post -Uri "$baseUrl/investigations" -ContentType "application/json" -Body $body
Invoke-RestMethod -Method Get -Uri "$baseUrl/investigations/PF-DEMO-001"
```

Expected output includes a completed report, timeline, case files, deterministic financial estimates, and an executive summary. If `OPENAI_API_KEY` is not configured, root-cause and recommendation content is deferred and the executive summary explicitly uses the deterministic fallback.

The example intentionally demonstrates a bounded refinement: payment recovery requests one evidence rerun, consumes the global retry budget, and cannot loop indefinitely.
