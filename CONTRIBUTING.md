# Contributing to DTOS

Read `AGENTS.md`, `DTOS_PHILOSOPHY.md`, the architecture guide, and the relevant intelligence-domain documentation before editing.

Create a focused branch from current `main`. Preserve existing behavior, environment overrides, explainability, and Windows compatibility. Application services must use the Intelligence Orchestrator rather than importing domain implementations. Every recommendation needs observable evidence, confidence, limitations, and explicit uncertainty.

Add meaningful tests for changed behavior and failure modes. Run `.\.venv\Scripts\python.exe -m tools.validation.validate_release`. Open a pull request describing scope, user impact, risks, and validation. Never commit secrets, generated cache data, virtual environments, or bypassed checks.
