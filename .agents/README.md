# Agent Workflow

This folder documents the AI-agent workflow used for the Fiskal MVP. It is public-safe: it records how agents and automation were used, without copying private prompts, chat transcripts, local paths, credentials, or generated tool output.

The public Playwright CLI skill reference is included at `.agents/skills/playwright-cli/SKILL.md`, with its supporting reference files. It documents browser automation commands and patterns used around Playwright-assisted testing.

## Agents And Automation

- GitHub Copilot in VS Code was the primary coding agent for implementation, testing, documentation, Docker, and Azure deployment support.
- Playwright and the Playwright CLI skill reference were used for browser-automation planning and validation after UI changes.
- Python `pytest` was used for VAT-rule, payload, and generated-PDF regression tests.
- Docker and Azure CLI were used for deployment smoke checks.

## Playwright-Assisted Validation

Playwright simulated real browser clicks and form input through the main user workflows:

1. Switch between the `Small`, `Medium`, and `Large` sample offices.
2. Filter the dashboard by review state.
3. Open client detail pages.
4. Correct handwritten/OCR `Review` cases.
5. Request and analyse evidence for `Flagged` cases.
6. Approve and file ready clients.
7. Inspect the simulated ledger payload.

Those browser checks were used to automatically test agent-made UI and workflow changes in a running app. The repeatable test command is `npm run test:e2e`.

## What Is Not Included

- Private Copilot chat transcripts.
- Private VS Code or Copilot internals.
- Public/third-party skill files without a known source or redistribution basis.
- Credentials, tokens, environment files, or local machine paths.
- Dependency folders, generated caches, screenshots, traces, or test-output folders.
