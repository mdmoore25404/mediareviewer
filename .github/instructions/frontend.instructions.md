---
applyTo: "frontend/**/*.{ts,tsx,js,jsx}"
description: "Use when editing Media Reviewer frontend files. Enforce TypeScript-first React code, explicit interfaces, tests, and eslint-clean changes."
---

# Frontend Guidance

- Prefer TypeScript for all new client code.
- Keep data contracts in typed interfaces alongside the API client code.
- Keep imports at module scope.
- Add or revise Vitest coverage when UI behavior or API integration changes.
- Run `npm run lint`, `npm run test`, and `npm run build` for the affected frontend slice before closing the request.
