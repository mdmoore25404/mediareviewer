---
applyTo: "backend/**/*.py"
description: "Use when editing Media Reviewer backend Python files. Enforce explicit typing, top-level imports, docstrings, pytest coverage, and ruff-clean code."
---

# Python Backend Guidance

- Type every function signature, dataclass field, and public attribute.
- Keep imports at module scope.
- Prefer dataclasses and small service classes for configuration and background job orchestration.
- Add or revise pytest coverage when routes, services, or configuration behavior changes.
- Run `ruff check backend/src backend/tests` and the relevant pytest targets before closing the request.
