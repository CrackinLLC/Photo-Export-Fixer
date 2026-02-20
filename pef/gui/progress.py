"""Inline progress view for long-running operations."""

import time
import tkinter as tk
from tkinter import ttk


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as H:MM:SS or M:SS."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class InlineProgressView(ttk.Frame):
    """Inline progress view that replaces setup widgets during processing.

    Shows phase label with timer, progress bar, status message,
    completed phase history, total elapsed timer, and cancel button.
    Supports both determinate and indeterminate modes.
    """

    def __init__(self, parent: ttk.Frame, on_cancel=None, **kwargs):
        """Create inline progress view.

        Args:
            parent: Parent frame to pack into.
            on_cancel: Callback when cancel button is clicked.
        """
        super().__init__(parent, **kwargs)

        self._start_time = time.monotonic()
        self._phase_start_time = self._start_time
        self._current_phase = None
        self._completed_phases = []
        self._timer_id = None

        # === Current phase header (phase name + phase timer) ===
        phase_row = ttk.Frame(self)
        phase_row.pack(fill=tk.X, padx=20, pady=(20, 5))

        self._phase_var = tk.StringVar(value="")
        phase_label = ttk.Label(
            phase_row,
            textvariable=self._phase_var,
            font=("", 12, "bold")
        )
        phase_label.pack(side=tk.LEFT)

        self._phase_timer_var = tk.StringVar(value="")
        phase_timer_label = ttk.Label(
            phase_row,
            textvariable=self._phase_timer_var,
            font=("", 11),
            foreground="gray"
        )
        phase_timer_label.pack(side=tk.RIGHT)

        # === Progress bar ===
        self._progress = ttk.Progressbar(self, mode="determinate", length=400)
        self._progress.pack(fill=tk.X, padx=20, pady=(5, 3))

        # Percentage / file count label
        self._percent_var = tk.StringVar(value="")
        percent_label = ttk.Label(self, textvariable=self._percent_var)
        percent_label.pack(pady=(0, 3))

        # Status message label (what's happening right now)
        self._status_var = tk.StringVar(value="Starting...")
        status_label = ttk.Label(
            self,
            textvariable=self._status_var,
            foreground="gray"
        )
        status_label.pack(fill=tk.X, padx=20, pady=(0, 10))

        # === Completed phases history ===
        self._history_frame = ttk.Frame(self)
        self._history_frame.pack(fill=tk.X, padx=20, pady=(0, 5))
        # Labels added dynamically as phases complete

        # Separator before total
        self._sep = ttk.Separator(self, orient=tk.HORIZONTAL)
        # Not packed until we have completed phases

        # === Total elapsed ===
        total_row = ttk.Frame(self)
        total_row.pack(fill=tk.X, padx=20, pady=(2, 10))

        total_label = ttk.Label(
            total_row,
            text="Total elapsed",
            font=("", 10)
        )
        total_label.pack(side=tk.LEFT)

        self._total_timer_var = tk.StringVar(value="0:00")
        total_timer_label = ttk.Label(
            total_row,
            textvariable=self._total_timer_var,
            font=("", 10, "bold")
        )
        total_timer_label.pack(side=tk.RIGHT)

        # === Buttons ===
        self._btn_frame = ttk.Frame(self)
        self._btn_frame.pack(pady=(0, 10))

        self._cancel_btn = ttk.Button(
            self._btn_frame,
            text="Cancel",
            command=on_cancel,
            width=15
        )
        self._cancel_btn.pack(side=tk.LEFT, padx=(0, 5))

        self._on_force_quit = None
        self._force_quit_btn = ttk.Button(
            self._btn_frame,
            text="Force Quit",
            command=self._handle_force_quit,
            width=15
        )

        # Start the 1-second timer tick
        self._tick_timers()

    def _tick_timers(self):
        """Update timer displays every second."""
        if not self.winfo_exists():
            return

        now = time.monotonic()

        # Update phase timer
        if self._current_phase is not None:
            phase_elapsed = now - self._phase_start_time
            self._phase_timer_var.set(_format_elapsed(phase_elapsed))

        # Update total timer
        total_elapsed = now - self._start_time
        self._total_timer_var.set(_format_elapsed(total_elapsed))

        self._timer_id = self.after(1000, self._tick_timers)

    def stop_timers(self):
        """Stop the timer tick. Call on completion or cancellation."""
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
            self._timer_id = None

    def set_title(self, title: str):
        """Set the progress title (kept for compatibility but now unused by default)."""
        # Title is now driven by phase labels; this is kept for backward compat
        pass

    def set_phase(self, phase_number: int, phase_name: str, total_phases: int):
        """Set the current phase label and start its timer.

        Args:
            phase_number: 1-based phase number.
            phase_name: Human-readable phase name (e.g., "Scanning").
            total_phases: Total number of phases.
        """
        now = time.monotonic()

        # Record completed phase
        if self._current_phase is not None:
            elapsed = now - self._phase_start_time
            self._add_completed_phase(self._current_phase, elapsed)

        self._current_phase = f"Phase {phase_number}/{total_phases}: {phase_name}"
        self._phase_start_time = now
        self._phase_var.set(self._current_phase)
        self._phase_timer_var.set("0:00")

    def set_scan_summary(self, file_count: int, json_count: int):
        """Show scan summary briefly after Phase 1 completes.

        Args:
            file_count: Number of media files found.
            json_count: Number of JSON metadata files found.
        """
        self._status_var.set(
            f"Found {file_count:,} files and {json_count:,} JSONs"
        )

    def _add_completed_phase(self, phase_label: str, elapsed: float):
        """Add a completed phase to the history display."""
        self._completed_phases.append((phase_label, elapsed))

        row = ttk.Frame(self._history_frame)
        row.pack(fill=tk.X, pady=1)

        name_label = ttk.Label(
            row,
            text=phase_label,
            font=("", 9),
            foreground="gray"
        )
        name_label.pack(side=tk.LEFT)

        # Dotted leader
        dots = ttk.Label(
            row,
            text=" " + "." * 20 + " ",
            font=("", 9),
            foreground="gray"
        )
        dots.pack(side=tk.LEFT, fill=tk.X, expand=True)

        time_label = ttk.Label(
            row,
            text=_format_elapsed(elapsed),
            font=("", 9),
            foreground="gray"
        )
        time_label.pack(side=tk.RIGHT)

        # Show separator above total once we have history
        if len(self._completed_phases) == 1:
            self._sep.pack(fill=tk.X, padx=20, pady=(2, 2))

    def show_final_summary(self):
        """Finalize the display: record current phase and stop timers."""
        now = time.monotonic()
        if self._current_phase is not None:
            elapsed = now - self._phase_start_time
            self._add_completed_phase(self._current_phase, elapsed)
            self._current_phase = None

        # Final total
        total_elapsed = now - self._start_time
        self._total_timer_var.set(_format_elapsed(total_elapsed))

        # Clear phase header since we're done
        self._phase_var.set("Complete")
        self._phase_timer_var.set("")

        self.stop_timers()

    def update_progress(self, current: int, total: int, message: str):
        """Update progress display.

        Args:
            current: Current progress value.
            total: Total progress value. Use 0 or negative for indeterminate mode.
            message: Status message.
        """
        if total <= 0:
            # Indeterminate mode — pulsing bar, show file count
            if self._progress["mode"] != "indeterminate":
                self._progress.configure(mode="indeterminate")
                self._progress.start(15)
            self._percent_var.set(f"{current:,} files" if current > 0 else "")
        else:
            # Determinate mode — normal percentage
            if self._progress["mode"] != "determinate":
                self._progress.stop()
                self._progress.configure(mode="determinate")
            percent = int((current / total) * 100)
            self._progress["value"] = percent
            self._percent_var.set(f"{percent}% ({current:,} / {total:,})")

        # Strip phase prefix from message for display (phase is shown separately)
        display_msg = message
        if display_msg.startswith("[") and "] " in display_msg:
            display_msg = display_msg.split("] ", 1)[1]

        # Truncate long messages
        if len(display_msg) > 80:
            display_msg = display_msg[:77] + "..."
        self._status_var.set(display_msg)

    def disable_cancel(self):
        """Disable the cancel button (e.g. after cancel is clicked)."""
        self._cancel_btn.config(state="disabled")

    def show_force_quit(self, on_force_quit):
        """Show the Force Quit button.

        Args:
            on_force_quit: Callback when Force Quit is clicked.
        """
        self._on_force_quit = on_force_quit
        self._force_quit_btn.pack(side=tk.LEFT, padx=(5, 0))

    def _handle_force_quit(self):
        """Handle Force Quit button click."""
        if self._on_force_quit:
            self._force_quit_btn.config(state="disabled")
            self._status_var.set("Force quitting...")
            self._on_force_quit()

    def set_status(self, message: str):
        """Set the status message directly."""
        self._status_var.set(message)

    def destroy(self):
        """Clean up timers before destroying widget."""
        self.stop_timers()
        super().destroy()
