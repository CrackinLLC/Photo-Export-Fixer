# Claude Code Permission Standards

This document defines how to configure Claude Code permissions for ForgeCrew multi-agent worktree workflows.

---

## Why User-Level Settings Are Required

Claude Code does NOT recognize git worktrees as related to the main repository. Each worktree is treated as a completely separate directory.

This means:

- Project-level settings (`.claude/settings.json`) do NOT apply to worktrees
- Session permissions don't transfer between directories
- Only user-level settings (`~/.claude/settings.json`) apply globally

**Key insight:** MCP tools like `mcp__den` and `mcp__pride` auto-approve because they have their own permission model. File operations (Read/Edit/Write) go through Claude Code's built-in permission system and require explicit configuration.

---

## Permission Hierarchy

Settings are loaded from multiple locations with this precedence (highest to lowest):

| Level              | Location                              | Scope                        |
| ------------------ | ------------------------------------- | ---------------------------- |
| **Managed**        | System-level managed-settings.json    | Enterprise deployments       |
| **CLI Flags**      | `--allowedTools`, `--disallowedTools` | Current session only         |
| **Local Project**  | `.claude/settings.local.json`         | Current directory only       |
| **Shared Project** | `.claude/settings.json`               | Current directory only       |
| **User**           | `~/.claude/settings.json`             | **All directories globally** |

### Rule Evaluation Order

1. **Deny** (highest priority) - blocks immediately
2. **Allow** - auto-approves if matched
3. **Ask** (default) - prompts for confirmation

**Deny rules always take precedence over allow rules.**

---

## Required Configuration

The `forgecrew setup` command generates a Claude Code settings template. You should install this template at your user-level settings location.

### Settings File Location

| OS      | Path                                  |
| ------- | ------------------------------------- |
| Windows | `%USERPROFILE%\.claude\settings.json` |
| macOS   | `~/.claude/settings.json`             |
| Linux   | `~/.claude/settings.json`             |

### Recommended Settings Template

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Read",
      "Edit",
      "Write",
      "Task",
      "Bash(npm *)",
      "Bash(node *)",
      "Bash(npx *)",
      "Bash(git status)",
      "Bash(git status *)",
      "Bash(git diff)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(git branch *)",
      "Bash(git show *)",
      "Bash(ls)",
      "Bash(ls *)",
      "Bash(dir)",
      "Bash(dir *)",
      "Bash(cat *)",
      "Bash(type *)",
      "Bash(head *)",
      "Bash(tail *)",
      "Bash(echo *)",
      "Bash(pwd)",
      "Bash(cd *)"
    ],
    "deny": [
      "Bash(git push --force *)",
      "Bash(git push -f *)",
      "Bash(git reset --hard *)",
      "Bash(git clean -f *)",
      "Bash(git clean -fd *)",
      "Bash(git checkout -- *)",
      "Bash(rm -rf *)",
      "Bash(rm -r *)",
      "Bash(rmdir /s *)",
      "Bash(del /s *)",
      "Bash(rd /s *)",
      "Bash(sudo *)",
      "Bash(runas *)",
      "Bash(curl *)",
      "Bash(wget *)",
      "Bash(ssh *)",
      "Bash(scp *)",
      "Bash(Invoke-WebRequest *)",
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/secrets/**)",
      "Read(**/.aws/**)",
      "Read(**/credentials*)",
      "Read(**/*.pem)",
      "Read(**/*.key)"
    ]
  }
}
```

### What Each Section Does

**`defaultMode: "acceptEdits"`** - Auto-approves file edit operations (Read/Edit/Write) without prompts.

**`allow`** - Operations auto-approved without prompts:

- `Read`, `Edit`, `Write` - Core file operations
- `Task` - Spawning subagents
- `Bash(npm *)`, `Bash(node *)`, etc. - Safe development commands

**`deny`** - Operations blocked entirely (cannot be approved):

- Destructive git operations (force push, hard reset)
- Recursive file deletion
- Privilege escalation (sudo, runas)
- Network operations (curl, wget, ssh) - data exfiltration risk
- Sensitive file access (.env, secrets, credentials, keys)

---

## Security Considerations

### Why Deny Rules Are Critical

Deny rules protect against:

1. **Accidental destruction** - `rm -rf`, `git reset --hard`
2. **Credential exposure** - Reading `.env` files or private keys
3. **Data exfiltration** - Network commands that could send data externally
4. **Privilege escalation** - Running commands as admin/root

### Blocked Operations Explained

| Pattern                            | Risk                                          |
| ---------------------------------- | --------------------------------------------- |
| `Bash(git push --force *)`         | Overwrites remote history, can lose team work |
| `Bash(git reset --hard *)`         | Discards uncommitted changes                  |
| `Bash(rm -rf *)`                   | Recursive deletion with no confirmation       |
| `Bash(curl *)`, `Bash(wget *)`     | Could exfiltrate code or secrets              |
| `Bash(sudo *)`                     | Privilege escalation                          |
| `Read(.env*)`                      | Contains secrets, API keys                    |
| `Read(**/*.pem)`, `Read(**/*.key)` | Private keys for encryption/signing           |

### Customizing for Your Environment

You may need to adjust the template if your project:

**Needs curl/wget:** If your build process requires network access, you can:

- Remove the deny rule (not recommended)
- Add specific allow rules: `"Bash(curl https://your-trusted-domain.com/*)"`

**Has different secrets locations:** Adjust the deny patterns to match your project's sensitive file locations.

**Uses different package managers:** Add allow rules for `Bash(yarn *)`, `Bash(pnpm *)`, etc.

---

## Path Pattern Syntax

Permission patterns support different path types:

| Prefix             | Meaning                               | Example                       |
| ------------------ | ------------------------------------- | ----------------------------- |
| `//path`           | Absolute filesystem path              | `Edit(//C:/_work/project/**)` |
| `~/path`           | Relative to home directory            | `Edit(~/workspace/**)`        |
| `/path`            | Relative to settings.json location    | `Edit(/src/**)`               |
| `./path` or `path` | Relative to current working directory | `Edit(./src/**)`              |

**Glob patterns:**

- `*` - Match any characters within a path segment
- `**` - Match any number of path segments

---

## Verifying Configuration

### Check Settings Are Applied

1. **Verify file exists:**

   ```bash
   # Windows
   type %USERPROFILE%\.claude\settings.json

   # macOS/Linux
   cat ~/.claude/settings.json
   ```

2. **Test in Claude Code:**
   - Start Claude Code in a worktree directory
   - Request a file edit operation
   - If configured correctly, no permission prompt should appear

### Check Deny Rules Work

Test that blocked operations are actually blocked:

- Try to read a `.env` file - should be denied
- Try a `curl` command - should be denied

---

## Troubleshooting

### Still Getting Permission Prompts?

**Check settings location:**

- User-level settings must be at `~/.claude/settings.json`
- Project-level settings only apply to that specific directory, not worktrees

**Check JSON syntax:**

- Ensure your settings file is valid JSON
- Use a JSON validator if unsure

**Check pattern matching:**

- Patterns are case-sensitive on Linux/macOS
- Ensure wildcards are correct (`*` vs `**`)

### How Do I Add New Allowed Commands?

Add them to the `allow` array:

```json
{
  "permissions": {
    "allow": ["Bash(your-command *)"]
  }
}
```

### What If I Need curl/wget for My Project?

Options in order of preference:

1. **Use specific allows** - Allow only trusted domains:

   ```json
   "allow": ["Bash(curl https://registry.npmjs.org/*)"]
   ```

2. **Use a dedicated tool** - Consider whether an MCP tool could handle this

3. **Remove the deny rule** - Last resort, removes protection against data exfiltration

### Piped Commands Still Prompt

This is a known limitation (GitHub Issue #13340). Permission patterns use prefix matching, so piped commands like `ls | grep foo` may prompt even if both parts are allowed individually.

**Workaround:** Use the individual commands separately, or accept the prompt.

---

## Known Limitations

### Subagent Permission Inheritance

GitHub Issue #10906 reports that built-in subagents (Plan, Task) may not inherit parent permissions. You may still see occasional prompts even with proper configuration.

### Worktree Navigation

Claude Code does not support navigating between worktrees (Issue #2180 - closed as "not planned"). Each worktree session is independent.

### Deny Rule Inconsistencies

Some edge cases may bypass deny rules (Issue #6631). Use multiple layers of protection when possible.

---

## References

- [Claude Code Settings Documentation](https://code.claude.com/docs/en/settings)
- [Claude Code Security Model](https://code.claude.com/docs/en/security)
- [GitHub Issue #2180 - Worktree Navigation](https://github.com/anthropics/claude-code/issues/2180)
- [GitHub Issue #10906 - Subagent Permission Inheritance](https://github.com/anthropics/claude-code/issues/10906)
- [GitHub Issue #13340 - Piped Commands](https://github.com/anthropics/claude-code/issues/13340)

<!-- ForgeCrew v0.3.12 -->
