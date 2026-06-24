# Agent Files

This folder documents the agent workflow used for the Fiskal MVP.

GitHub Copilot in VS Code was used as the implementation assistant. The repository keeps only public-safe orchestration notes here and in `AGENTS.md`; it does not include private prompts, chat transcripts, local credentials, or generated tool output.

## Workflow

1. Interpret the assignment and MVP scope.
2. Build the Flask sandbox and deterministic VAT review rules.
3. Add realistic CSV profiles and generated PDF source documents.
4. Validate behavior with Python tests, Playwright tests, Docker checks, and Azure smoke checks.
5. Keep external integrations simulated and visibly marked as simulated.
