# Fiskal VAT Review Sandbox

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Playwright Tested](https://img.shields.io/badge/Playwright-tested-2EAD33?logo=playwright&logoColor=white)
![Azure Container Apps](https://img.shields.io/badge/Azure%20Container%20Apps-deployed-0078D4?logo=microsoftazure&logoColor=white)

Live demo: [https://fiskal-app.happycliff-ffe64e1f.swedencentral.azurecontainerapps.io](https://fiskal-app.happycliff-ffe64e1f.swedencentral.azurecontainerapps.io)

Fiskal is a sandbox MVP for a Dutch bookkeeping-office VAT review co-pilot. It helps a bookkeeper inspect quarterly BTW work before filing by combining sample ledger exports, generated source PDFs, deterministic VAT checks, human review flows, and a simulated ledger write-back payload.

The app is intentionally not connected to real customers, ledgers, banks, SBR, Digipoort, or tax-filing systems.

## Topic Tags

`fintech` `vat` `btw` `bookkeeping` `flask` `docker` `azure-container-apps` `bicep` `playwright` `ai-agents` `github-copilot` `csv-data` `dutch-tax` `sandbox`

## Requirements

- Python `3.12` (`3.12.7` was used for development and testing)
- Node.js `20+` for Playwright browser tests
- Docker Desktop for container runs
- Azure CLI for Azure deployment

## Install And Run

Run these commands from the repository root.

### Windows PowerShell

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

### macOS Or Linux

```bash
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Open `http://localhost:8000`.

## Run Tests

Python tests:

```powershell
python --version
python -m pytest tests
```

Browser tests:

```powershell
npm ci
npx playwright install chromium
npm run test:e2e
```

The Playwright tests simulate real browser clicks through the review queue, client detail pages, evidence flow, manual review flow, approval flow, and payload preview. They were used to automatically verify agent-made UI and workflow changes.

## Run With Docker

```powershell
docker build -t fiskal-vat-review .
docker run --rm -p 8000:8000 fiskal-vat-review
```

Open `http://localhost:8000`.

## Deploy To Azure

The Bicep template in `infra/main.bicep` deploys the app to Azure Container Apps. It creates:

- Azure Container Registry
- Log Analytics workspace
- Container Apps managed environment
- Public Container App with `/healthz` probes

Deploy from the repository root:

```powershell
az login
.\infra\deploy.ps1 -ResourceGroup rg-AgentExperiment -Location swedencentral -AppName fiskal -ImageTag latest
```

Manual Azure commands are documented in `infra/README.md`.

## Core Workflow

1. Load CSV exports from Moneybird, Exact Online, Twinfield, and SnelStart sample ledgers.
2. Group transactions by client and quarter.
3. Apply deterministic VAT review rules.
4. Assign each client one public status: `Ready`, `Review`, `Flagged`, or `Filed`.
5. Show the source transaction rows and generated source PDFs behind each warning.
6. Let the bookkeeper enter missing receipt values or request evidence.
7. Move resolved clients to `Ready`.
8. Approve and file ready clients inside the sandbox.
9. Preview the simulated ledger payload. No external API call is made.

## Status Meaning

- `Ready`: no open warnings that need a human check.
- `Review`: the value should exist in the source PDF, but OCR/manual extraction needs a human check.
- `Flagged`: external evidence or compliance proof is missing.
- `Filed`: the CSV says the client was already filed, or the bookkeeper approved and filed it in the sandbox.

## Rule Engine

- Heuristic and explainable.
- Not machine learning.
- Uses fixed warning penalties and a small deterministic client-ID adjustment.
- Keeps final approval with the bookkeeper.

## Sample Data

The repository includes three bookkeeping-office profiles:

- `data/profiles/small/`
- `data/profiles/medium/`
- `data/profiles/large/`

Each profile contains:

| File | Purpose |
| --- | --- |
| `office.csv` | Bookkeeping office profile |
| `clients.csv` | Client accounts |
| `transactions.csv` | Ledger rows |
| `exceptions.csv` | Flagged evidence signals |

Included edge cases:

- Hard-to-read handwritten receipt IDs
- Reverse-charge service rows
- Intra-EU goods rows needing transport proof
- Missing buyer VAT-number evidence
- Unknown VAT-code rows
- Clients that are already filed in source data

## Generated PDFs

Fiskal generates local sample PDFs for source invoices, receipts, and evidence documents. These PDFs are generated from sample data and do not contain real customer documents.

The test suite includes a PyMuPDF layout check that verifies generated PDF text stays inside the page and that money columns do not overlap.

## Project Structure

```text
app.py                  Flask routes and session workflow
fiskal/data_loader.py   CSV loading and normalization
fiskal/rules.py         Deterministic VAT review rules
fiskal/payloads.py      Simulated ledger payload builder
fiskal/sample_pdf.py    Generated sample/evidence PDF renderer
templates/              Dashboard and client-detail HTML
static/                 CSS
data/profiles/          Small, medium, and large sample datasets
tests/                  Python and Playwright regression tests
infra/                  Azure Bicep deployment files
```

## Agent Orchestration

Public-safe agent workflow notes are documented in `AGENTS.md` and `.agents/README.md`. Project-specific GitHub Copilot guidance is documented in `.github/copilot-instructions.md`.

The repository also includes the public Playwright CLI skill reference at `.agents/skills/playwright-cli/SKILL.md`. That skill documents the browser-automation workflow used around Playwright-assisted testing; the repeatable regression command remains `npm run test:e2e`.

No private prompts, chat transcripts, local credentials, generated caches, or test output folders are part of the repository.
