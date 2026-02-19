"""Progress dialog for long-running operations."""

import tkinter as tk
from tkinter import ttk


class ProgressDialog:
    """Modal progress dialog with progress bar and status text."""

    def __init__(self, parent: tk.Tk, title: str = "Processing"):
        """Create progress dialog.

        Args:
            parent: Parent window.
            title: Dialog title.
        """
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x120")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 120) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Content
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Status label
        self.status_var = tk.StringVar(value="Starting...")
        status_label = ttk.Label(frame, textvariable=self.status_var)
        status_label.pack(fill=tk.X, pady=(0, 10))

        # Progress bar
        self.progress = ttk.Progressbar(frame, mode="determinate", length=350)
        self.progress.pack(fill=tk.X)

        # Percentage label
        self.percent_var = tk.StringVar(value="0%")
        percent_label = ttk.Label(frame, textvariable=self.percent_var)
        percent_label.pack(pady=(5, 0))

        # Prevent closing
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)

    def update(self, current: int, total: int, message: str):
        """Update progress.

        Args:
            current: Current progress value.
            total: Total progress value. Use 0 or negative for indeterminate mode.
            message: Status message.
        """
        if total <= 0:
            # Indeterminate mode — pulsing bar, show file count
            if self.progress["mode"] != "indeterminate":
                self.progress.configure(mode="indeterminate")
                self.progress.start(15)
            self.percent_var.set(f"{current:,} files" if current > 0 else "")
        else:
            # Determinate mode — normal percentage
            if self.progress["mode"] != "determinate":
                self.progress.stop()
                self.progress.configure(mode="determinate")
            percent = int((current / total) * 100)
            self.progress["value"] = percent
            self.percent_var.set(f"{percent}%")

        # Truncate long messages
        display_msg = message[:60] + "..." if len(message) > 60 else message
        self.status_var.set(display_msg)

        self.dialog.update_idletasks()

    def close(self):
        """Close the dialog."""
        self.dialog.grab_release()
        self.dialog.destroy()
