# Photo-Export-Fixer - ForgeCrew Usage Guide

This guide explains how to use ForgeCrew to coordinate AI agents working on Photo-Export-Fixer.

## What is ForgeCrew?

ForgeCrew lets you run multiple Claude Code sessions in parallel, each working on different parts of your project. One agent fixes a bug while another adds a feature while a third writes tests. They work in isolated git worktrees so they don't step on each other, and they submit PRs for you to review and merge.

ForgeCrew addresses common LLM agent problems through structured roles, work documents, and a coordination model:

- **Agents drift** - they lose track of the bigger picture as conversations get long
- **Agents get creative** - they "improve" things you didn't ask for
- **Agents forget context** - they don't remember what other agents are doing
- **Agents make mistakes** - they need verification that changes actually work

---

## Core Concepts

### You Are the Supervisor

You don't do the coding. You don't create most tasks. Your job is to:

1. **Set direction** - tell a coordinator what you want built
2. **Distribute work** - spin up agent sessions and point them at tasks
3. **Supervise** - watch for agents going off the rails
4. **Course-correct** - intervene when agents drift or misunderstand
5. **Review and merge** - you're the only one who pushes to the default branch

### Agents and Roles

Agents are Claude Code sessions that you run in separate terminals. Each terminal is an agent. You give them a role and a task, and they execute.

| Role             | Purpose                                                                          |
| ---------------- | -------------------------------------------------------------------------------- |
| **Coordinator**  | Plans and orchestrates. Breaks down work, creates tasks. Your main collaborator. |
| **Engineer**     | Implements features and fixes. Does the actual coding.                           |
| **Gatekeeper**   | Reviews PRs for quality. Checks standards, tests, documentation.                 |
| **Verification** | Tests that changes actually work. Runs code, tries edge cases.                   |
| **Librarian**    | Maintains documentation. Catches drift between code and docs.                    |
| **Researcher**   | Investigates technical questions. Evaluates options and makes recommendations.   |
| **Operations**   | Handles deployment, infrastructure, CI/CD.                                       |

### Worktrees

Each agent works in an isolated git worktree - a separate working directory with its own branch. This means:

- Agents can't interfere with each other's work
- Each agent can run tests, build, etc. without conflicts
- All changes go through PRs that you review

Worktrees are created as siblings to your main project directory (e.g., `../YourProject-engineer-1/`).

### Workstreams

A workstream (WS-ID) is a unit of tracked work. Think of it as a project or epic. Workstreams help organize related tasks and track progress across multiple agents.

### Work Directory

Work documents live in `.forgecrew/work/` (accessible via the `forgecrew-work` symlink):

```
forgecrew-work/
├── intake/    # New work: issues, proposals, breakage reports
├── prep/      # Planning: research, designs, plans
├── tasks/     # Ready-to-execute task assignments
├── review/    # Audits and reviews
└── _archive/  # Completed work
```

Documents flow through these directories as work progresses. A feature request starts as an intake proposal, becomes a prep plan, spawns task assignments, gets reviewed, and ends up archived.

---

## Basic Usage

### Starting a Session

**1. Start a Coordinator**

Open a terminal with Claude Code and tell it:

```
You are coordinator-1. Check in and let's plan some work.
```

The coordinator checks in (creating its worktree) and is ready to collaborate.

**2. Describe What You Want**

Talk to the coordinator like a project manager. Describe the feature, bug, or refactor. The coordinator asks clarifying questions and breaks it down into tasks.

**3. Spin Up Agents**

Open new terminals for each agent. Each terminal is a separate Claude Code session:

```
You are engineer-1. Check in and complete task T-00045.
```

```
You are engineer-2. Check in and complete task T-00046.
```

Run as many agents in parallel as makes sense.

### Supervising Agents

Watch for these common problems:

**Drift** - Agent starts solving a different problem

```
"Hold on - your task is just the logout endpoint. Stay focused."
```

**Over-engineering** - Agent adds unneeded complexity

```
"We don't need a plugin system. Just hardcode support for now."
```

**Misunderstanding** - Agent interprets requirements wrong

```
"No, the session expires after 24 hours, not 24 minutes."
```

**Getting stuck** - Agent spins on a problem

```
"You've been debugging this a while. Let me spin up a researcher."
```

Intervene early. It's easier to correct after 5 minutes than after an hour.

### Reviewing and Merging

When agents complete work, they submit PRs. Review them on GitHub:

- Does it solve the task?
- Are there tests?
- Is documentation updated?
- Does CI pass?

You can spin up a gatekeeper for detailed code review:

```
You are gatekeeper-1. Check in and review PR #42.
```

When satisfied, merge. You're the only one who merges to the default branch.

### Closing Out

After work is done, tell agents to check out:

```
Check out and end your session.
```

Archive completed task documents using the coordinator or directly via the work directory.

---

## Directory Structure

```
Photo-Export-Fixer/
├── .forgecrew/                    # ForgeCrew state (untracked)
│   ├── state.json                 # Agent and workstream state
│   └── work/                      # Shared work documents
│       ├── intake/
│       ├── prep/
│       ├── tasks/
│       ├── review/
│       └── _archive/
│
├── .forgecrew/instruct/           # Agent instructions (tracked)
│   ├── START.md                   # Agent entrypoint
│   └── roles/                     # Role definitions
│
├── docs/forgecrew/                # Project documentation (tracked)
│   ├── README.md                  # This file
│   └── standards/                 # Coding standards
│
├── forgecrew-work/                # Symlink to .forgecrew/work
└── forgecrew.config.json          # Project configuration
```

---

## Tips

### Keep Conversations Focused

Long conversations cause drift. If an agent has been working a while, consider having them submit what they have and starting fresh.

### Don't Hesitate to Intervene

It's cheaper to correct an agent after 5 minutes than after an hour.

### Use Verification

Don't trust that code works just because an agent says it does. Spin up verification to actually test it.

### Let Coordinators Coordinate

Resist the urge to create all tasks yourself. Work with a coordinator.

### One Task, One Agent

Don't give an agent multiple unrelated tasks. Keep assignments focused.

### Archive Completed Work

Don't let work directories fill up with old documents. Archive as you go.

---

## Troubleshooting

### Agent Can't Check In

The agent may already be checked in, or there may be a state inconsistency. Ask the agent to check its status first.

### Agent's Worktree Is Messed Up

Ask the agent to sync with the default branch or reset its worktree.

### PRs Have Merge Conflicts

Have the agent sync with the default branch and resolve the conflicts.

### Agent Is Completely Lost

Sometimes it's easier to start fresh. Have the agent check out and start a new session.

### Lock Contention ("Another agent is checking in")

**This is expected behavior during concurrent operations.** Multiple agents operating simultaneously will occasionally contend for the state file lock.

**What agents may see:**

- `Another agent (engineer-1) is checking in. Retry in 15-30 seconds.`
- `Lock held by engineer-1 for 5s. Expires in 55s.`
- `LOCK_TIMEOUT` in error output

**Why this happens:** Pride serializes state file operations to prevent corruption. When multiple agents try to modify state simultaneously (checkin, checkout, doc_create, doc_archive), one holds the lock while others wait. The lock automatically expires after 60 seconds to prevent deadlocks.

**What agents should do:**

1. **Wait and retry** - Just wait 15-30 seconds and retry the operation
2. **Don't use `pride unlock`** - This can corrupt state if another agent is actively writing
3. **This is normal** - Lock contention during concurrent operation is not a bug or error

**When to escalate:**

- Lock stuck for more than 60 seconds (should auto-expire)
- Repeated failures despite multiple retries
- Error messages indicate the lock holder process is not running

If you suspect a stale lock (the holding agent crashed or was terminated), only then ask the user if they want to run `pride unlock`.

---

## Further Reading

- Agent instructions: `.forgecrew/instruct/START.md`
- Role definitions: `.forgecrew/instruct/roles/`
- Coding standards: `docs/forgecrew/standards/`
- Configuration: `forgecrew.config.json`
- Command help: `forgecrew help`
