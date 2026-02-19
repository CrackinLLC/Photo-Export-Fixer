# Testing Standards

## Overview

ForgeCrew uses **Vitest** for all testing. Tests run as part of the `den submit` pipeline automatically. During development, use targeted test runs to iterate quickly.

---

## Test Framework

- **Framework:** Vitest (v4+)
- **Coverage provider:** V8 (`@vitest/coverage-v8`)
- **Configuration:** `vitest.config.ts` at project root
- **Global setup:** `src/test-setup.ts`

---

## Running Tests

### For Agents (MCP)

```
mcp__den__test({ id: "engineer-1" })                           // Run all tests
mcp__den__test({ id: "engineer-1", args: "src/utils.test.ts" }) // Run specific file
mcp__den__test({ id: "engineer-1", args: "--grep validation" }) // Run matching tests
mcp__den__test({ id: "engineer-1", coverage: true })            // Run with coverage
```

### For Humans (CLI)

```bash
npm test                                    # Run all tests
npm test -- src/utils.test.ts               # Run specific file
npm test -- --grep "validation"             # Run matching tests
npm run test -- --coverage                  # Run with coverage
```

### During Development

Run targeted tests for the area you're changing — don't run the full suite on every edit. `den submit` runs all tests automatically before pushing.

---

## Test File Conventions

- Test files use the `.test.ts` suffix (e.g., `utils.test.ts`)
- Tests are co-located with source files in `src/`
- Test files are excluded from TypeScript compilation (`tsconfig.json`) and Biome linting

---

## Coverage Configuration

Coverage is configured in `vitest.config.ts`:

- **Provider:** V8
- **Reporters:** `text`, `text-summary`
- **Includes:** `src/**/*.ts`
- **Excludes:**
  - `src/**/*.test.ts` (test files)
  - `src/**/index.ts` (barrel exports)
  - `src/cli/**` (CLI wiring — not unit testable)
  - `src/mcp/**` (MCP server wiring — not unit testable)
- **No enforced thresholds** — coverage is reported but not gated

---

## Test Quality Standards

- **Write tests that fail first** — new behavior tests should fail before implementation
- **Test one thing per test** — each test should verify a single behavior
- **Use descriptive test names** — name should describe the scenario and expected outcome
- **Avoid test interdependence** — tests should not depend on other tests' state
- **Clean up after tests** — reset state to avoid polluting other tests

For additional testing policies (flaky test handling, failure escalation, `skipFailures` usage), see `_ENG_STANDARDS.md`.

<!-- ForgeCrew v0.3.12 -->
