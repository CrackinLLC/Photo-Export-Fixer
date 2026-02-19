# Fix: Output Directory Selection & Creation Bug

## Problem

Two related bugs in the GUI around output directory handling:

### Bug 1: Cannot select a non-existent output directory
When the user browses for an output directory via the GUI, `filedialog.askdirectory()`
(`main_window.py:409`) only allows selecting **existing** directories. If the user wants
to target a new directory (e.g. the auto-suggested `<source>_processed`), they must
manually create it first. This is a poor UX since the program will create the directory
anyway when processing starts.

### Bug 2: Output directory gets "(2)" suffix when it already exists
When processing starts, `orchestrator.py:270` calls `checkout_dir(self.dest_path, onlynew=True)`
for fresh runs. Since `onlynew=True`, `get_unique_path()` in `utils.py:47-77` sees the
directory already exists (because the user had to create it to select it in Bug 1) and
appends `(2)` to create a unique name. The user ends up with output in an unexpected
directory.

The root cause chain: Bug 1 forces the user to pre-create the directory, which then
triggers Bug 2 because the code assumes a fresh run should always get a new directory.

## Affected Files

- `pef/gui/main_window.py` — `_browse_dest()` (line 407), `_on_process()` (line 507)
- `pef/core/orchestrator.py` — `process()` directory setup logic (lines 242-274)
- `pef/core/utils.py` — `checkout_dir()` (line 80), `get_unique_path()` (line 47)

## Proposed Solution

### Part 1: Allow selecting non-existent directories

Replace `filedialog.askdirectory()` with a flow that allows the user to specify a
directory that doesn't exist yet. Options:

- **Option A (Recommended):** Keep `filedialog.askdirectory()` for browsing to a parent
  location, but also allow the user to simply type/paste a path into the destination text
  field. Remove any validation that rejects non-existent destination paths. The hint label
  already says "Leave empty to auto-create next to source folder" — extend this concept
  to also accept typed paths that don't exist yet.

- **Option B:** After `askdirectory()` returns, show a secondary dialog asking for a
  subfolder name. More complex, less intuitive.

The key change: the destination path should be accepted regardless of whether it currently
exists on disk. The program will create it when processing starts.

### Part 2: Fix directory creation logic for fresh runs

The orchestrator's directory setup logic at `orchestrator.py:264-270` currently does:

```python
else:
    # Fresh start or force
    if exists(self.dest_path) and force:
        output_dir = self.dest_path
    else:
        output_dir = checkout_dir(self.dest_path, onlynew=True)
```

For a **fresh run** (no prior state file), if the destination directory exists but is
**empty** (or has no `_pef/processing_state.json`), the program should reuse it directly
rather than creating a `(2)` variant. The `onlynew=True` behavior should only kick in
when there's evidence of a prior completed run (which is already handled by the
`state.is_completed()` branch at line 260).

Proposed change for the `else` (fresh start) branch:

```python
else:
    # Fresh start or force
    if exists(self.dest_path):
        # Directory exists — reuse it (no prior state means it's safe)
        output_dir = self.dest_path
    else:
        # Directory doesn't exist — create it
        output_dir = checkout_dir(self.dest_path)  # onlynew=False → creates dir
```

This is safe because:
- If there WAS a prior completed run, `state.is_completed()` catches it above (line 260)
- If there WAS a prior in-progress run, `state.can_resume()` catches it above (line 248)
- The only remaining case is: no state file exists → either empty dir or first run → safe to reuse

## Testing Considerations

- Test: Select a non-existent destination path → processing creates it and uses it
- Test: Select an existing empty directory → processing uses it directly (no "(2)")
- Test: Complete a run, then run again with same dest → should create "(2)" (existing behavior preserved)
- Test: Resume an interrupted run → should reuse same directory (existing behavior preserved)
- Test: Leave destination blank → auto-creates `<source>_processed` (existing behavior preserved)
