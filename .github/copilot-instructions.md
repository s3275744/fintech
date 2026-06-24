# Copilot Instructions For Fiskal

Use these instructions when working on the Fiskal VAT review sandbox.

## Product Scope

- This is a sandbox MVP for a Dutch VAT review co-pilot.
- Use sample data only.
- Do not add real ledger, bank, SBR, Digipoort, or tax-filing API calls.
- Keep simulated payloads visibly marked as simulated.
- Keep final approval with the bookkeeper.

## Implementation Style

- Prefer readable Flask and Python code over unnecessary abstraction.
- Keep deterministic, explainable VAT rules; do not present the rule engine as trained ML.
- Preserve the status meanings: `Ready`, `Review`, `Flagged`, and `Filed`.
- Treat `Review` as source-PDF/OCR/manual extraction work.
- Treat `Flagged` as missing external evidence or compliance proof.
- Update tests and README sections when behavior, setup, Docker, or Azure deployment changes.

## Validation

- Run Python tests after rule, payload, or PDF changes.
- Run Playwright tests after important UI workflow changes.
- For generated PDFs, check that text stays inside the page and money columns do not overlap.
- For deployment changes, verify Docker locally and `/healthz` on Azure Container Apps.
