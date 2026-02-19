"""Inline progress view for long-running operations."""

import tkinter as tk
from tkinter import ttk


class InlineProgressView(ttk.Frame):
    """Inline progress view that replaces setup widgets during processing.

    Shows title, progress bar, percentage/file count, status message,
    and cancel button. Supports both determinate and indeterminate modes.
    """

    def __init__(self, parent: ttk.Frame, on_cancel=None, **kwargs):
        """Create inline progress view.

        Args:
            parent: Parent frame to pack into.
            on_cancel: Callback when cancel button is clicked.
        """
        super().__init__(parent, **kwargs)

        # Title label
        self._title_var = tk.StringVar(value="Processing...")
        title_label = ttk.Label(
            self,
            textvariable=self._title_var,
            font=("", 14, "bold")
        )
        title_label.pack(fill=tk.X, pady=(20, 15))

        # Progress bar
        self._progress = ttk.Progressbar(self, mode="determinate", length=400)
        self._progress.pack(fill=tk.X, padx=20, pady=(0, 5))

        # Percentage / file count label
        self._percent_var = tk.StringVar(value="0%")
        percent_label = ttk.Label(self, textvariable=self._percent_var)
        percent_label.pack(pady=(0, 5))

        # Status message label
        self._status_var = tk.StringVar(value="Starting...")
        status_label = ttk.Label(
            self,
            textvariable=self._status_var,
            foreground="gray"
        )
        status_label.pack(fill=tk.X, padx=20, pady=(0, 15))

        # Cancel button
        self._cancel_btn = ttk.Button(
            self,
            text="Cancel",
            command=on_cancel,
            width=15
        )
        self._cancel_btn.pack(pady=(0, 10))

    def set_title(self, title: str):
        """Set the progress title."""
        self._title_var.set(title)

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

        # Truncate long messages
        display_msg = message[:60] + "..." if len(message) > 60 else message
        self._status_var.set(display_msg)

    def disable_cancel(self):
        """Disable the cancel button (e.g. after cancel is clicked)."""
        self._cancel_btn.config(state="disabled")

    def set_status(self, message: str):
        """Set the status message directly."""
        self._status_var.set(message)
