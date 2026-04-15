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

## Theme awareness

- The app supports three modes: **light**, **dark**, and **auto** (follows system). The active theme is applied via Bootstrap 5.3 `data-bs-theme` on `<html>`.
- **The review overlay (`.review-overlay`, `.review-dialog`) is always rendered on a dark background regardless of the active theme.** Any CSS for elements inside the overlay must use explicit dark-context values (e.g. `color: rgba(255,255,255,0.7)`) rather than relying on inheritance, Bootstrap theme variables, or `opacity` alone.
- For all other UI regions (topnav, sidebar, grid), use Bootstrap semantic color tokens (`--bs-body-color`, `text-secondary`, `btn-outline-*`) so they adapt automatically across all three modes.
- Never hardcode `#000` or `#fff` text colors outside the overlay context; use CSS custom properties or Bootstrap utility classes.
- After adding or changing any color, border, or background CSS, visually verify (or explicitly reason through) how the rule behaves in both a dark `data-bs-theme="dark"` and light `data-bs-theme="light"` context before committing.
