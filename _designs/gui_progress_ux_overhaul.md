# GUI Progress UX Overhaul: Draggability, Inline Progress, and Cancellation

## Problems

### 1. Window drag lag during processing
The `ProgressDialog` is a modal `Toplevel` with `grab_set()`. During processing, the
worker thread posts UI updates via `root.after(0, ...)` which queue lambda callbacks on
the tkinter main loop. When many updates arrive rapidly (especially during Phase 2/3 with
adaptive intervals as low as every 1 item for small collections, or every 25-100 for
larger ones), the main thread's event loop becomes saturated processing these queued
callbacks. Since window dragging relies on the main thread processing mouse/WM_MOVE
events, this manifests as drag lag — sometimes the window responds, sometimes it doesn't.

### 2. Processing shown in a separate small window
Currently `ProgressDialog` (`progress.py`) is a separate `Toplevel` window. The user
wants the progress to replace the main window's content instead, creating a single-window
experience.

### 3. No cancel button during processing
There is no way to cancel from the GUI. The CLI handles `KeyboardInterrupt` and calls
`orchestrator.save_progress()`, but the GUI has no equivalent mechanism. A cancel button
should prompt for confirmation with a note about resume capability.

## Affected Files

- `pef/gui/main_window.py` — widget layout, `_run_async()`, `_on_process()`
- `pef/gui/progress.py` — `ProgressDialog` class (will be significantly reworked or replaced)
- `pef/core/orchestrator.py` — needs a cancellation check mechanism in the processing loop

## Proposed Solution

### Part 1: Fix drag lag via update throttling

**Root cause:** `root.after(0, ...)` queues updates immediately. When the worker thread
fires progress callbacks rapidly (e.g., every 25-100 items in Phase 2), the main thread
event queue fills with UI update lambdas, starving mouse/window-management events.

**Fix:** Throttle UI updates on the main-thread side. Instead of `root.after(0, ...)`,
use a time-based throttle so the UI only redraws progress at most every ~100-150ms. This
is frequent enough for smooth visual feedback but leaves ample time for the main thread to
process drag events.

Implementation approach — store last-update timestamp and skip redundant updates:

```python
def _run_async(self, status_msg, dialog_title, operation, on_complete):
    self.status_var.set(status_msg)
    self._show_progress_view()  # switch to inline progress view

    last_update = [0]  # mutable container for closure

    def progress_cb(c, t, m):
        now = time.monotonic()
        # Throttle to ~8 updates/second; always allow final update (c >= t)
        if now - last_update[0] < 0.12 and (t > 0 and c < t):
            return  # skip this update
        last_update[0] = now
        self.root.after(0, lambda c=c, t=t, m=m: self._update_progress(c, t, m))

    # ... rest of async setup
```

Key points:
- Throttle happens in the **worker thread** before posting to the main thread, so we
  never even queue the excess callbacks.
- Final updates (`c >= t`) always pass through so we never miss completion.
- ~120ms interval = ~8 updates/sec. Visually smooth, leaves ~87% of main-loop time free
  for window management events.
- The worker thread's actual processing speed is unaffected — only the callback posting
  is throttled.

### Part 2: Inline progress in main window (replace separate dialog)

Instead of spawning a `ProgressDialog` `Toplevel`, swap the main window's content to show
a progress view. This involves:

#### Layout strategy:
The main window currently has this structure inside `main_frame`:
- `header_frame` (title, source/dest fields) — packed TOP
- `scroll_frame` (advanced options) — packed with expand
- `button_frame` (Preview/Start buttons) — packed BOTTOM
- `status_frame` (status bar) — packed BOTTOM

When processing starts, **hide** the setup widgets (`header_frame`, `scroll_frame`,
`button_frame`) and **show** a progress frame in their place. When processing finishes
(or is cancelled), reverse the swap.

#### Progress view contents:
- Title label: "Processing..." (or the phase label)
- Progress bar (same as current `ProgressDialog`)
- Percentage / file count label
- Status message label (current file being processed)
- Cancel button (see Part 3)

#### Implementation:

```python
def _create_widgets(self):
    # ... existing setup widgets (store references for hiding) ...
    self._setup_widgets = [header_frame, self.scroll_frame, button_frame]

    # Progress view (created once, hidden initially)
    self._progress_frame = ttk.Frame(main_frame, padding="20")
    # ... progress bar, labels, cancel button ...
    # Don't pack yet

def _show_progress_view(self):
    """Switch from setup view to progress view."""
    for w in self._setup_widgets:
        w.pack_forget()
    self._progress_frame.pack(fill=tk.BOTH, expand=True)
    # Reset progress state
    self._progress_bar["value"] = 0
    self._progress_percent.set("0%")
    self._progress_status.set("Starting...")

def _show_setup_view(self):
    """Switch from progress view back to setup view."""
    self._progress_frame.pack_forget()
    # Re-pack setup widgets in original order
    # (status_frame and button_frame are packed BOTTOM first, then header TOP, then scroll)
    for w in self._setup_widgets:
        w.pack(...)  # re-pack in correct order with correct options
```

Note: We need to store the pack configuration for each widget so we can restore it. An
alternative is to use a container frame for setup vs progress and just swap which
container is packed.

**Simpler approach using container frames:**

```python
def _create_widgets(self):
    main_frame = ttk.Frame(self.root, padding="15")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Setup container — holds all setup widgets
    self._setup_container = ttk.Frame(main_frame)
    self._setup_container.pack(fill=tk.BOTH, expand=True)

    # Build all setup widgets inside self._setup_container
    # (same as current code, but parent is self._setup_container)

    # Progress container — holds progress view (hidden initially)
    self._progress_container = ttk.Frame(main_frame)
    # Build progress widgets inside self._progress_container
    # Don't pack yet

def _show_progress_view(self):
    self._setup_container.pack_forget()
    self._progress_container.pack(fill=tk.BOTH, expand=True)

def _show_setup_view(self):
    self._progress_container.pack_forget()
    self._setup_container.pack(fill=tk.BOTH, expand=True)
```

This is cleaner — each container manages its own internal layout independently.

### Part 3: Cancel button with confirmation and resume note

#### GUI side:
Add a cancel button to the progress view. When clicked:

```python
def _on_cancel(self):
    if messagebox.askyesno(
        "Cancel Processing",
        "Are you sure you want to cancel?\n\n"
        "Progress will be saved. You can resume later by running "
        "again with the same source and destination directories."
    ):
        self._cancel_requested = True
        self._progress_status.set("Cancelling... saving progress")
        self._cancel_btn.config(state=tk.DISABLED)
```

#### Orchestrator side — cooperative cancellation:
The orchestrator's processing loops need to check a cancellation flag. The cleanest
approach is to use a `threading.Event`:

```python
# In _run_async:
self._cancel_event = threading.Event()

def run():
    orchestrator = self._create_orchestrator()
    try:
        result = orchestrator.process(
            on_progress=progress_cb,
            force=force,
            cancel_event=self._cancel_event
        )
        # ...
    except CancelledError:
        orchestrator.save_progress()
        self.root.after(0, lambda: self._on_processing_cancelled())
```

In the orchestrator's `process()` method, check the event periodically in the main loops:

```python
# orchestrator.py — in Phase 2 loop:
for i, json_path in enumerate(jsons_to_process):
    if cancel_event and cancel_event.is_set():
        raise CancelledError("Processing cancelled by user")
    # ... rest of processing ...

# orchestrator.py — in Phase 3 loop:
for i, file_info in enumerate(unmatched_files):
    if cancel_event and cancel_event.is_set():
        raise CancelledError("Processing cancelled by user")
    # ... rest of processing ...
```

A custom `CancelledError` exception (or just a flag check) propagates up. The `finally`
block in `_run_async` handles cleanup, and the state is saved so the user can resume.

#### After cancellation:
- Switch back to the setup view
- Show a status message like "Cancelled — progress saved. Resume by clicking Start again."
- The existing resume logic in the orchestrator will handle picking up where it left off

## Performance Impact Assessment

- **Throttling (Part 1):** Improves performance slightly — fewer cross-thread dispatches
  and fewer `update_idletasks()` calls. No negative impact.
- **Inline progress (Part 2):** No performance impact — same number of widgets being
  updated, just in the main window instead of a Toplevel.
- **Cancel check (Part 3):** Negligible — one `Event.is_set()` call per loop iteration.
  This is a simple flag read, essentially free compared to the file I/O in each iteration.

## Testing Considerations

- Test: Start processing, drag the main window smoothly during all phases
- Test: Cancel during Phase 2, verify progress is saved, restart resumes correctly
- Test: Cancel during Phase 3, verify partial unmatched files are handled
- Test: Cancel confirmation dialog — click "No" to continue processing
- Test: Processing completes normally — verify setup view is restored with results
- Test: Window shows progress inline — no separate Toplevel window appears
- Test: Cancel button disables after clicking to prevent double-cancel
