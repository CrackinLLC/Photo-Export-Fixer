# Development Standards

## Overview

This document covers environment setup, development workflow, and quality tooling for ForgeCrew.

---

## Prerequisites

- **Node.js:** v24.0.0+ (managed via Volta, pinned to 24.13.0)
- **Package manager:** npm
- **TypeScript:** v5.3+
- **OS:** Windows, macOS, or Linux

---

## Environment Setup

```bash
# Clone the repository
git clone <repo-url>
cd ForgeCrew

# Install dependencies
npm install

# Build tools (den + pride)
npm run build

# Verify setup
npm run check
```

No environment variables are required for local development.

---

## Development Workflow

The standard workflow for agents and humans:

### 1. Edit

Make your changes in `src/`. ForgeCrew is a TypeScript project using ES modules (`NodeNext` module resolution, `ES2022` target, `strict: true`).

### 2. Targeted Test

Run tests for the area you changed — don't run the full suite on every edit.

**Agents (MCP):**

```
mcp__den__test({ id: "engineer-1", args: "src/path/to/file.test.ts" })
```

**Humans (CLI):**

```bash
npm test -- src/path/to/file.test.ts
```

### 3. Submit

When your work is ready, submit it. `den submit` handles everything: staging, committing, syncing, quality checks, tests, pushing, and PR creation.

**Agents (MCP):**

```
mcp__den__submit({ id: "engineer-1", title: "T-XXXXX: Description", body: "..." })
```

**Humans (CLI):**

```bash
den submit --title "T-XXXXX: Description"
```

---

## Quality Tools

| Command        | What It Runs                                 | Purpose                                        |
| -------------- | -------------------------------------------- | ---------------------------------------------- |
| `den test`     | Vitest                                       | Run tests (targeted or full suite)             |
| `den validate` | Clean + Analyze + Test (full quality gate)   | Run the full quality pipeline                  |
| `den analyze`  | TypeScript + Knip (dead code)                | Detection-only checks (no auto-fix, no tests)  |
| `den clean`    | Biome (format + lint fix)                    | Auto-fix formatting and lint issues            |
| `den build`    | `npm run build`                              | Produce release artifacts (not for validation) |
| `den submit`   | Stage + Commit + Sync + Validate + Push + PR | The finishing command — does everything        |

**Key points:**

- `den submit` is the only command you need when you're done working. It runs validate (clean + analyze + test) + push + PR.
- `den validate` is the full quality gate: clean (auto-fix) → analyze (detect) → test (full suite). Use it to debug failures.
- `den analyze` is detection-only. It runs TypeScript type-check and Knip dead code detection. No auto-fix, no tests.
- `den clean` auto-fixes only. It writes formatting and lint fixes to your files. By default it operates on staged files only.
- `den build` produces release artifacts. Never use it for validation.

For full quality tool details, see `_ENG_STANDARDS.md` > "Quality Tools Quick Reference".

---

## Project Structure

```
src/           # TypeScript source code
  den/         # Den tool (git workflow)
  pride/       # Pride tool (agent lifecycle)
  cli/         # CLI entry points
  mcp/         # MCP server entry points
02_instruct/   # Source: agent role docs → deploys to .forgecrew/instruct/
03_docs/       # Source: project standards → deploys to docs/forgecrew/
04_templates/  # Source: document templates
```

---

## Build

```bash
npm run build          # Build den + pride tools
npm run clean          # Remove dist/ and 01_bin/
```

The build produces CLI binaries in `01_bin/` and compiled output in `dist/`.

---

## Versioning

The **single source of truth** for the project version is the `version` field in `package.json`.

When bumping the version, only update these files manually:

- `package.json`
- `package-lock.json`
- `forgecrew.config.json` (`_forgecrewVersion` field)

**Do NOT manually update `<!-- ForgeCrew vX.X.X -->` footers in markdown files.** The build script (`scripts/build-tools.js` via `syncDocs()`) automatically injects version footers into all files in `02_instruct/` and `03_docs/` from `package.json`. Running `npm run build` after a version bump propagates the new version everywhere.

<!-- ForgeCrew v0.3.12 -->
