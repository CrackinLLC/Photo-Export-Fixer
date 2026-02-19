# Claude Code User Settings

This guide explains how to configure user-level Claude Code settings for ForgeCrew.

## Why User-Level Settings?

Claude Code settings can be configured at three levels:

1. **User-level** (`~/.claude/settings.json`) - applies globally
2. **Project-level** (`.claude/settings.json`) - project-specific
3. **Worktree-level** (`.claude/settings.local.json`) - worktree overrides

**Important:** Project-level settings do NOT fully inherit to git worktrees. Since
ForgeCrew agents work in worktrees, user-level settings provide the most consistent
permission behavior across all agent sessions.

---

## Quick Start

Run this command to install the recommended settings:

```bash
forgecrew config user-settings
```

Or manually copy the template from your ForgeCrew installation.

---

## Manual Installation

### 1. Locate Your Settings File

| OS      | Path                                  |
| ------- | ------------------------------------- |
| Windows | `%USERPROFILE%\.claude\settings.json` |
| macOS   | `~/.claude/settings.json`             |
| Linux   | `~/.claude/settings.json`             |

### 2. Create the Directory

**Windows (PowerShell):**

```powershell
mkdir -Force "$env:USERPROFILE\.claude"
```

**macOS/Linux:**

```bash
mkdir -p ~/.claude
```

### 3. Copy the Template

The template is located at:

```
<forgecrew-install>/04_templates/user-settings.json
```

Copy it to your settings location and rename to `settings.json`.

---

## What the Settings Do

### Default Mode: `acceptEdits`

Auto-approves Read, Edit, and Write operations without prompting, reducing friction
when agents make file changes.

### Allowlisted Operations

| Category              | Operations                      |
| --------------------- | ------------------------------- |
| **File tools**        | Read, Edit, Write, Task         |
| **Package managers**  | npm, node, npx                  |
| **Git (read-only)**   | status, diff, log, branch, show |
| **Directory listing** | ls, dir                         |
| **File viewing**      | cat, type, head, tail           |
| **Navigation**        | pwd, cd, echo                   |

### Denied Operations

| Category                 | Blocked Patterns                                  |
| ------------------------ | ------------------------------------------------- |
| **Destructive git**      | push --force, reset --hard, clean -f, checkout -- |
| **Recursive delete**     | rm -rf, rm -r, rmdir /s, del /s, rd /s            |
| **Privilege escalation** | sudo, runas                                       |
| **Network downloads**    | curl, wget, Invoke-WebRequest                     |
| **Remote access**        | ssh, scp                                          |
| **Secrets access**       | .env, secrets/, .aws/, credentials, _.pem, _.key  |

---

## Customization

### Adding Allowances

Edit `~/.claude/settings.json` and add to the `allow` array:

```json
"allow": [
  "Bash(docker *)",
  "Bash(make *)",
  "Bash(pytest *)"
]
```

### Adding Restrictions

Add patterns to the `deny` array:

```json
"deny": [
  "Bash(chmod *)",
  "Read(**/config/production/**)"
]
```

---

## Known Limitations

1. **Global scope** - User-level settings apply to ALL projects on your machine
2. **Subagent inheritance** - Task tool subagents may not fully inherit permissions
3. **Deny list maintenance** - New dangerous patterns may need to be added over time

---

## Verification

After applying settings:

1. **Test auto-approval:** Ask Claude to read a file - it should proceed without prompting
2. **Test blocking:** Ask Claude to run `rm -rf /tmp/test` - it should refuse
3. **Test in worktree:** Check in as an agent and verify behavior is consistent
