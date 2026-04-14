# Lint Notes And Anti-Patterns

- Keep all imports at the top of the file.
- Keep Python imports sorted to satisfy `ruff` import ordering.
- Avoid untyped dictionaries in API contracts. Define typed interfaces or dataclasses instead.
- Do not leave placeholder tests out when scaffolding a new feature surface.
- Avoid `async` test mocks that do not actually await anything.
- Prefer TypeScript `--noEmit` validation in this repo so generated config artifacts do not break linting.
- Prefer explicit return types on helpers even when inference would work.
- Keep API documentation updated when routes or payloads change.
- Keep pytest setup blocks wrapped across lines to stay inside the 100-character ruff limit.
- When importing multiple names from the same module would exceed 100 chars, use a parenthesised multi-line import rather than a `# noqa: E501` suppressor.
- **E501 in string literals and `query_string` dicts**: long inline strings inside `jsonify({"error": ...})` calls, `query_string` keyword arguments, and similar dictionary/call expressions are a common E501 source. Break them onto multiple lines using a parenthesised continuation or a named variable before the call — never suppress with `# noqa`.
