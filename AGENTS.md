# Agent Orchestration

This project used GitHub Copilot as the coding assistant for planning, implementation, testing, and deployment support.

## Agent Setup

- Primary agent: GitHub Copilot in VS Code.
- Scope: Flask MVP, VAT rule logic, sample data, UI templates, tests, Docker, Bicep, and README documentation.
- Human role: product decisions, MVP scope, demo priorities, and final review.
- External systems: all ledger, bank, SBR, Digipoort, and tax-filing integrations remain simulated.

## Working Rules

- Keep the MVP explainable and deterministic.
- Use sample data only.
- Do not include real customer data, real API credentials, or production secrets.
- Keep public statuses simple: `Ready`, `Review`, `Flagged`, and `Filed`.
- Treat `Review` as source-PDF/OCR/manual extraction work.
- Treat `Flagged` as missing external evidence or compliance proof.
- Preserve Docker and Azure deployment instructions when application behavior changes.

## Validation

The agent-supported workflow used repeatable checks before upload:

- Python unit tests with `pytest`.
- Generated-PDF layout regression tests.
- Playwright browser tests that simulate user clicks through the main review workflow, including filtering, client detail review, manual correction, evidence handling, approval, filing, and payload preview.
- A public Playwright CLI skill reference is included under `.agents/skills/playwright-cli/` to document the agent-side browser automation workflow.
- Docker build and `/healthz` smoke checks.
- Azure Container Apps deployment smoke checks.

Playwright was used after UI changes so agent-made edits could be automatically checked in a real browser workflow instead of only by reading templates.

## Repository Hygiene

The repository should not include local caches, dependency folders, environment files, credentials, screenshots, test output folders, or private chat transcripts.
