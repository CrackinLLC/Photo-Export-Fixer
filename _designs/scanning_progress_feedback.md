# Fix: No Progress Feedback During Scanning Phase

## Problem

During the scanning phase (Phase 1 of processing), the GUI progress dialog shows 0% with
the message "Scanning files..." and provides no visual feedback of progress. On large
collections (tens of thousands of files), this phase can take hours with no indication
that work is happening. The user has no way to know if the program is working or frozen.

## Root Cause

Two issues combine to create this problem:

### Issue 1: Scanner callback not passed through orchestrator

In `orchestrator.py:290-291`, the scanner is created and called **without** the
`on_progress` callback:

```python
scanner = FileScanner(self.source_path)
scanner.scan()  # <-- no on_progress passed!
```

The scanner's `scan()` method (`scanner.py:75`) DOES accept an `on_progress` parameter
and has built-in progress reporting (directory changes, file counts, adaptive intervals),
but the orchestrator never passes the callback through.

### Issue 2: Progress shows 0% because of how scanning reports

Even if the callback were passed, the scanning phase has a fundamental display problem.
The initial progress call at `orchestrator.py:288` is:

```python
on_progress(0, 100, "[1/3] Scanning files...")
```

This sets progress to 0/100 = 0%. The scanner's own callbacks use `(files_found, files_found)`
as current/total (since the total is unknown during scan), which would show 100% — jumping
from 0% to 100% with nothing in between. Neither behavior is helpful.

## Affected Files

- `pef/core/orchestrator.py` — `process()` Phase 1 (lines 286-291)
- `pef/core/scanner.py` — `scan()` method (lines 75-145)
- `pef/gui/progress.py` — `ProgressDialog.update()` (line 51)

## Proposed Solution

### Approach: Pass scanner progress through with indeterminate-style reporting

Since the total file count is unknown during scanning, use a combination of:

1. **Pass the callback to `scanner.scan()`** so it actually receives updates.

2. **Wrap the callback** so scanner progress messages include the `[1/3]` phase prefix
   and use a format that conveys activity without a misleading percentage.

3. **Switch progress bar to indeterminate mode during scan.** The `ProgressDialog` should
   support an indeterminate/pulsing mode for phases where total is unknown. When the
   scanner reports progress, update the status text (showing file counts and current
   directory) while the progress bar pulses to show activity.

### Implementation Details

#### `progress.py` changes:
Add support for indeterminate mode. When `total` is 0 or a sentinel value (e.g., -1),
switch the progress bar to `mode="indeterminate"` and call `start()` to animate it. When
a real total is provided later, switch back to `mode="determinate"`.

```python
def update(self, current: int, total: int, message: str):
    if total <= 0:
        # Indeterminate mode — pulsing bar, show message only
        if self.progress["mode"] != "indeterminate":
            self.progress.configure(mode="indeterminate")
            self.progress.start(15)  # pulse interval in ms
        self.percent_var.set(f"{current:,} files")  # show count instead of %
    else:
        # Determinate mode — normal percentage
        if self.progress["mode"] != "determinate":
            self.progress.stop()
            self.progress.configure(mode="determinate")
        percent = int((current / total) * 100)
        self.progress["value"] = percent
        self.percent_var.set(f"{percent}%")

    display_msg = message[:60] + "..." if len(message) > 60 else message
    self.status_var.set(display_msg)
    self.dialog.update_idletasks()
```

#### `orchestrator.py` changes:
Pass a wrapped callback to the scanner that uses `total=0` (or -1) to signal
indeterminate mode:

```python
# Phase 1: Scan
if on_progress:
    on_progress(0, 0, "[1/3] Scanning files...")

def scan_progress(current, total, message):
    if on_progress:
        on_progress(current, 0, f"[1/3] {message}")

scanner = FileScanner(self.source_path)
scanner.scan(on_progress=scan_progress)
```

This way, during scanning:
- The progress bar pulses (indeterminate animation)
- The status text updates with `[1/3] Scanning: AlbumName...` and `[1/3] Found 12,345 files...`
- The percentage area shows the file count (e.g., "12,345 files")
- The user gets continuous visual feedback that work is happening

When Phase 2 starts, the first `on_progress(i, total, "[2/3] ...")` call with a real
total switches back to determinate mode with a proper percentage.

## Testing Considerations

- Test: Start processing on a directory with many files → verify progress bar pulses
  during scan and shows file counts updating
- Test: Verify Phase 2/3 still show correct percentage progress (determinate mode)
- Test: Verify scan phase shows current album/directory name in status text
- Test: Ensure no UI freezing during rapid progress updates (the existing adaptive
  interval in scanner.py should handle this)
