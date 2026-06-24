# Fiskal VAT Review Sandbox

## Quick View

- `Fiskal` is a BTW co-pilot for Dutch bookkeeping offices.
- It helps bookkeepers review quarterly VAT work before approval.
- It uses sample ledger data, local review flows, and simulated write-back payloads.
- It does not call real ledger, bank, SBR, or Digipoort APIs.

## Core Flow

- Load CSV exports from `Moneybird`, `Exact Online`, `Twinfield`, and `SnelStart`.
- Check each client with explainable VAT rules.
- Assign a status and confidence score.
- Show the exact source transactions that need work.
- Let the bookkeeper review, correct, request evidence, and approve.
- Preview the JSON payload that would be sent back to a ledger API.

## Features

- `Small`, `Medium`, and `Large` bookkeeping-office profiles.
- Q2 `2026` VAT queue.
- Statuses: `Ready`, `Review`, `Flagged`, and `Filed`.
- Transaction-level issue labels.
- Evidence columns for `VAT evidence` and `Transport proof`.
- Sample PDFs for every transaction.
- Hard-to-OCR receipt values for `Review` cases.
- Manual extraction fields for human review.
- Simulated email replies and evidence PDFs for `Flagged` cases.
- Reset action for approvals, manual values, and evidence replies.
- Docker support.
- Unit tests and Playwright browser tests.

## Scope

- No real customer data.
- No real ledger OAuth.
- No real bank or PSD2 connection.
- No real tax filing.
- No production security model.
- No machine-learning training pipeline.

## Rule Engine

- Heuristic and explainable.
- Not machine learning.
- Starts each client near `96%` confidence.
- Lowers the score with fixed warning penalties.
- Adds a small deterministic client-ID adjustment.
- Uses the score as an attention signal.
- Keeps final approval with the bookkeeper.

## Warning Penalties

| Signal | Penalty |
| --- | ---: |
| Unclear receipt extraction | `-8` |
| Reverse charge or foreign B2B case | `-22` |
| Unknown VAT code | `-28` |
| Other flagged exception | `-12` |

## Status Meaning

- `Ready`: no open warnings that need a human check.
- `Review`: source PDF value exists, but OCR confidence is low.
- `Flagged`: external evidence is missing.
- `Filed`: CSV data says the client was already filed, or the bookkeeper approved and filed it in the sandbox.

## Transaction Review

- `Clear`: no issue found on the row.
- `Review`: open the PDF and enter the value manually.
- `Flagged`: contact the company for missing evidence.
- `Corrected`: value entered or evidence PDF accepted.

## Evidence Rules

- `EU_REVERSE`: `VAT to be accounted for by the recipient`.
- Reverse-charge services need `Buyer VAT number evidence`.
- Intra-EU goods shipments also need `Transport proof`.
- Service rows show `Not required` when transport proof is not needed.
- Goods-shipment rows show `Missing` until transport evidence is accepted.
- Accepted evidence fills the VAT number and transport reference.

## Sample Data

- `data/profiles/small/`: small bookkeeping office.
- `data/profiles/medium/`: medium bookkeeping office.
- `data/profiles/large/`: large bookkeeping office.

| File | Contains |
| --- | --- |
| `office.csv` | Office profile |
| `clients.csv` | Client accounts |
| `transactions.csv` | Ledger rows |
| `exceptions.csv` | Flagged evidence signals |

## Included Edge Cases

- Hard-to-read receipt IDs.
- Foreign B2B reverse-charge rows.
- Unknown VAT-code rows.
- Missing VAT-number evidence.
- Missing transport proof for EU goods shipments.

## Run Locally

```powershell
cd C:\Users\stijn\Desktop\BAM\fintech\assignment2\github_folder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

- Open `http://localhost:8000`.

## Run With Docker

```powershell
cd C:\Users\stijn\Desktop\BAM\fintech\assignment2\github_folder
docker build -t fiskal-vat-review .
docker run --rm -p 8000:8000 fiskal-vat-review
```

- Open `http://localhost:8000`.

## Deploy To Azure

The `infra/main.bicep` template deploys the sandbox to Azure Container Apps in resource group `rg-AgentExperiment`. It creates an Azure Container Registry, Log Analytics workspace, Container Apps environment, and public Container App with health probes.

Current hosted URL: `https://fiskal-app.happycliff-ffe64e1f.swedencentral.azurecontainerapps.io`

```powershell
cd C:\Users\stijn\Desktop\BAM\fintech\assignment2\github_folder
az login
.\infra\deploy.ps1 -ResourceGroup rg-AgentExperiment -Location swedencentral -AppName fiskal -ImageTag latest
```

Detailed manual commands are in `infra/README.md`.

## Run Tests

```powershell
python -m pytest
```

```powershell
npm install
npx playwright install chromium
npm run test:e2e
```

## Walkthrough

1. Open the app.
2. Switch between `Small`, `Medium`, and `Large`.
3. Filter by `Review` and `Flagged`.
4. Open a client with warnings.
5. Check the confidence score.
6. Open the source transaction row.
7. Open the sample PDF.
8. For `Review`, enter the PDF value manually.
9. If the value is unreadable, use the client-contact fallback.
10. For `Flagged`, contact the company for evidence.
11. Analyse the received evidence PDF.
12. Approve the client when it becomes `Ready`.
13. Check the simulated ledger payload.
14. Use `Reset sandbox state` to clear the local review state.

## Suggested Topics

- `fintech`
- `vat`
- `bookkeeping`
- `flask`
- `docker`
- `playwright`
- `csv-data`
- `dutch-tax`
- `sandbox`

## Agent Orchestration

Public-safe agent workflow notes are documented in `AGENTS.md` and `.agents/README.md`.