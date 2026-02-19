# Coding Standards

General coding conventions for this project.

## File Organization

- Group related files together
- Keep files focused on a single responsibility
- Use consistent naming conventions

## Code Style

- Follow the project's linter and formatter configurations
- Use descriptive variable and function names
- Keep functions small and focused

## Comments

- Write self-documenting code where possible
- Add comments for complex logic
- Keep comments up-to-date with code changes

## Error Handling

- Handle errors explicitly
- Provide meaningful error messages
- Log errors appropriately

## Testing

- Write tests for new functionality
- Maintain existing tests when refactoring
- Test edge cases and error conditions

---

## Biome Rule Coverage (vs P-00029 Engineering Standards)

This section documents which rules from research P-00029 are enforced by Biome (`biome.json`) and which remain manual review items for Gatekeeper.

### Biome-Enforced Rules (Automatic)

Rules enforced via `biome.json` — violations are caught by `den clean` or `den analyze`.

| P-00029 Section | Rule | Biome Rule | Severity | Source |
|----------------|------|------------|----------|--------|
| §3.5 Dead code | No unused imports | `correctness/noUnusedImports` | error | explicit |
| §3.5 Dead code | No unused variables | `correctness/noUnusedVariables` | error | explicit |
| §4.1 Type safety | No `any` in application code | `suspicious/noExplicitAny` | error | explicit |
| §4.1 Type safety | No `var` | `suspicious/noVar` | error | explicit |
| §4.1 Type safety | Use `const` by default | `style/useConst` | error | recommended |
| §4.1 Type safety | Use `===` / `!==` | `suspicious/noDoubleEquals` | error | recommended |
| §4.1 Type safety | No non-null assertions without justification | `style/noNonNullAssertion` | warn | explicit |
| §4.1 Type safety | Use `import type` for type-only imports | `style/useImportType` | error | recommended |
| §4.2 Imports | Named exports only (no default exports) | `style/noDefaultExport` | error | recommended |
| §4.2 Imports | Use `export type` for type-only exports | `style/useExportType` | error | recommended |
| §4.2 Imports | No `require()` — use ESM | `style/noCommonJs` | warn | explicit |
| §4.2 Imports | No barrel files for internal code | `performance/noBarrelFile` | warn | explicit |
| §4.3 Async | No floating promises | `nursery/noFloatingPromises` | warn | explicit |
| §4.3 Async | No misused promises | `nursery/noMisusedPromises` | warn | explicit |
| §4.3 Async | Await only thenables | `nursery/useAwaitThenable` | warn | explicit |
| §4.3 Async | Async functions must use await | `suspicious/useAwait` | warn | explicit |
| §4.5 Control flow | No fall-through in switch cases | `suspicious/noFallthroughSwitchClause` | error | recommended |
| §4.5 Control flow | No declarations in switch cases | `correctness/noSwitchDeclarations` | error | recommended |
| §4.6 Disallowed | No `eval()` | `security/noGlobalEval` | error | recommended |
| §4.6 Disallowed | No `debugger` | `suspicious/noDebugger` | error | recommended |
| §6.4 Secrets | No secrets in source code | `security/noSecrets` | error | explicit |
| §10.1 Errors | Only throw `Error` subclasses | `style/useThrowOnlyError` | error | recommended |
| §10.1 Errors | Use `new Error()` not `Error()` | `style/useThrowNewError` | error | explicit |
| §10.1 Errors | No empty block statements | `suspicious/noEmptyBlockStatements` | warn | explicit |

### Intentionally Not Enabled

| Rule | Reason |
|------|--------|
| `suspicious/noConsole` | This is a CLI tool — console output is core functionality |

### Manual Review Items (Gatekeeper Must Check)

These P-00029 rules cannot be enforced by Biome and require human review:

| P-00029 Section | Rule |
|----------------|------|
| §3.1 | Naming conventions (PascalCase, camelCase, CONSTANT_CASE, file kebab-case) |
| §3.2 | Function length (~40 lines) and cyclomatic complexity (~10 branches) |
| §3.3 | Single responsibility per file/class/module |
| §3.4 | DRY vs readability judgment (no premature abstraction) |
| §4.1 | No `@ts-ignore` (enforced by tsconfig, not Biome) |
| §4.1 | No wrapper types (`String`/`Boolean`/`Number`) |
| §4.1 | Discriminated unions with exhaustive `never` checks |
| §4.2 | No mutable exports |
| §4.3 | Use `Promise.all()` for independent parallel operations |
| §4.4 | Module organization by feature/domain, clear dependency direction |
| §4.5 | All switch statements have `default` case |
| §4.5 | Always use braces, even for single-statement blocks |
| §5.x | All testing standards (AAA structure, naming, isolation, mocking discipline) |
| §6.1 | Input validation with Zod at boundaries |
| §6.2 | Path traversal prevention |
| §6.3 | Injection prevention (`execFile`/`spawn` over `exec`) |
| §6.5 | Dependency hygiene (lockfile, `npm audit`) |
| §6.6 | Prototype pollution prevention |
| §7.x | All performance rules (N+1, allocations, streaming) |
| §8.x | Git/PR hygiene (commit messages, PR size, atomic commits) |
| §9.x | Documentation standards (JSDoc on exports, comment quality) |
| §10.x | Error propagation patterns (cause chaining, Result pattern, user-facing messages) |

---

_This is a starting template. Customize for your project's specific needs._

<!-- ForgeCrew v0.3.12 -->
