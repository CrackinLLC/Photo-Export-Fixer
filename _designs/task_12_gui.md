# Task 12: Add GUI

## Objective
Create a simple graphical user interface using tkinter that provides an alternative to the command-line interface.

## Prerequisites
- Task 01-10 (All core and CLI modules) complete
- Task 11 (Tests) recommended but not required

## Files to Create
- `pef/gui/__init__.py`
- `pef/gui/main.py`
- `pef/gui/main_window.py`
- `pef/gui/progress.py`
- `pef/gui/settings.py`

## Design Principles

1. **Simple and focused** - Not feature-bloated, just the essential operations
2. **Uses core library** - All processing via `PEFOrchestrator`
3. **Cross-platform** - tkinter works on Windows, macOS, Linux
4. **No extra dependencies** - tkinter is built into Python

## Implementation

### `pef/gui/__init__.py`

```python
"""Graphical user interface for Photo Export Fixer."""

from pef.gui.main import main

__all__ = ["main"]
```

### `pef/gui/main.py`

```python
"""GUI entry point for Photo Export Fixer."""

import sys


def main():
    """Launch the GUI application."""
    from pef.gui.main_window import PEFMainWindow

    app = PEFMainWindow()
    app.run()


if __name__ == "__main__":
    main()
```

### `pef/gui/main_window.py`

```python
"""Main window for Photo Export Fixer GUI."""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from pef.core.orchestrator import PEFOrchestrator
from pef.gui.progress import ProgressDialog


class PEFMainWindow:
    """Main application window."""

    def __init__(self):
        """Initialize the main window."""
        self.root = tk.Tk()
        self.root.title("Photo Export Fixer")
        self.root.geometry("600x400")
        self.root.minsize(500, 350)

        # Variables
        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar()
        self.write_exif = tk.BooleanVar(value=True)

        # Build UI
        self._create_widgets()

    def _create_widgets(self):
        """Create and layout all widgets."""
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Photo Export Fixer",
            font=("", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Source path section
        source_frame = ttk.LabelFrame(main_frame, text="Source Directory", padding="10")
        source_frame.pack(fill=tk.X, pady=5)

        source_entry = ttk.Entry(source_frame, textvariable=self.source_path)
        source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        source_btn = ttk.Button(
            source_frame,
            text="Browse...",
            command=self._browse_source
        )
        source_btn.pack(side=tk.RIGHT)

        # Destination path section
        dest_frame = ttk.LabelFrame(main_frame, text="Destination Directory (optional)", padding="10")
        dest_frame.pack(fill=tk.X, pady=5)

        dest_entry = ttk.Entry(dest_frame, textvariable=self.dest_path)
        dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        dest_btn = ttk.Button(
            dest_frame,
            text="Browse...",
            command=self._browse_dest
        )
        dest_btn.pack(side=tk.RIGHT)

        # Options section
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.pack(fill=tk.X, pady=5)

        exif_check = ttk.Checkbutton(
            options_frame,
            text="Write EXIF metadata (GPS, people tags)",
            variable=self.write_exif
        )
        exif_check.pack(anchor=tk.W)

        # Buttons section
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)

        # Dry run button
        dry_run_btn = ttk.Button(
            button_frame,
            text="Dry Run (Preview)",
            command=self._on_dry_run
        )
        dry_run_btn.pack(side=tk.LEFT, padx=5)

        # Process button
        process_btn = ttk.Button(
            button_frame,
            text="Process Files",
            command=self._on_process,
            style="Accent.TButton"
        )
        process_btn.pack(side=tk.LEFT, padx=5)

        # Extend button
        extend_btn = ttk.Button(
            button_frame,
            text="Extend Metadata",
            command=self._on_extend
        )
        extend_btn.pack(side=tk.LEFT, padx=5)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

    def _browse_source(self):
        """Open file dialog for source directory."""
        path = filedialog.askdirectory(title="Select Google Takeout Directory")
        if path:
            self.source_path.set(path)
            # Auto-fill destination if empty
            if not self.dest_path.get():
                self.dest_path.set(f"{path}_pefProcessed")

    def _browse_dest(self):
        """Open file dialog for destination directory."""
        path = filedialog.askdirectory(title="Select Destination Directory")
        if path:
            self.dest_path.set(path)

    def _validate_source(self) -> bool:
        """Validate source path exists."""
        source = self.source_path.get()
        if not source:
            messagebox.showerror("Error", "Please select a source directory.")
            return False
        if not os.path.isdir(source):
            messagebox.showerror("Error", f"Source directory does not exist:\n{source}")
            return False
        return True

    def _on_dry_run(self):
        """Handle dry run button click."""
        if not self._validate_source():
            return

        self.status_var.set("Running dry run...")

        # Create progress dialog
        progress = ProgressDialog(self.root, "Dry Run Analysis")

        def run():
            try:
                orchestrator = PEFOrchestrator(
                    source_path=self.source_path.get(),
                    dest_path=self.dest_path.get() or None,
                    write_exif=self.write_exif.get()
                )

                result = orchestrator.dry_run(
                    on_progress=lambda c, t, m: progress.update(c, t, m)
                )

                # Show results
                self.root.after(0, lambda: self._show_dry_run_results(result))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, progress.close)
                self.root.after(0, lambda: self.status_var.set("Ready"))

        # Run in background thread
        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _show_dry_run_results(self, result):
        """Show dry run results in a dialog."""
        msg = f"""Dry Run Analysis Complete

Found:
  {result.json_count} JSON metadata files
  {result.file_count} media files

Would process:
  {result.matched_count} files with matching JSON
  {result.unmatched_json_count} JSONs without matching file
  {result.unmatched_file_count} files without matching JSON

Metadata available:
  {result.with_gps} files with GPS coordinates
  {result.with_people} files with people tags

ExifTool: {"Available" if result.exiftool_available else "Not found"}"""

        messagebox.showinfo("Dry Run Results", msg)

    def _on_process(self):
        """Handle process button click."""
        if not self._validate_source():
            return

        # Confirm
        if not messagebox.askyesno(
            "Confirm Processing",
            "This will copy and process all files.\n\nContinue?"
        ):
            return

        self.status_var.set("Processing...")

        # Create progress dialog
        progress = ProgressDialog(self.root, "Processing Files")

        def run():
            try:
                orchestrator = PEFOrchestrator(
                    source_path=self.source_path.get(),
                    dest_path=self.dest_path.get() or None,
                    write_exif=self.write_exif.get()
                )

                result = orchestrator.process(
                    on_progress=lambda c, t, m: progress.update(c, t, m)
                )

                # Show results
                self.root.after(0, lambda: self._show_process_results(result))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, progress.close)
                self.root.after(0, lambda: self.status_var.set("Ready"))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _show_process_results(self, result):
        """Show processing results."""
        msg = f"""Processing Complete!

Processed: {result.stats.processed} files
  With GPS: {result.stats.with_gps}
  With people: {result.stats.with_people}

Unprocessed: {result.stats.unmatched_files} files

Time: {result.elapsed_time} seconds

Output saved to:
{result.output_dir}"""

        messagebox.showinfo("Processing Complete", msg)

    def _on_extend(self):
        """Handle extend metadata button click."""
        if not self._validate_source():
            return

        # Check processed folder exists
        dest = self.dest_path.get() or f"{self.source_path.get()}_pefProcessed"
        processed_path = os.path.join(dest, "Processed")

        if not os.path.isdir(processed_path):
            messagebox.showerror(
                "Error",
                f"Processed folder not found:\n{processed_path}\n\n"
                "Run 'Process Files' first."
            )
            return

        self.status_var.set("Extending metadata...")

        progress = ProgressDialog(self.root, "Extending Metadata")

        def run():
            try:
                orchestrator = PEFOrchestrator(
                    source_path=self.source_path.get(),
                    dest_path=dest,
                    write_exif=True
                )

                result = orchestrator.extend(
                    on_progress=lambda c, t, m: progress.update(c, t, m)
                )

                msg = f"""Extend Complete!

Updated: {result.stats.processed} files
  With GPS: {result.stats.with_gps}
  With people: {result.stats.with_people}

Skipped: {result.stats.skipped}
Errors: {result.stats.errors}

Time: {result.elapsed_time} seconds"""

                self.root.after(0, lambda: messagebox.showinfo("Extend Complete", msg))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, progress.close)
                self.root.after(0, lambda: self.status_var.set("Ready"))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()
```

### `pef/gui/progress.py`

```python
"""Progress dialog for long-running operations."""

import tkinter as tk
from tkinter import ttk
from typing import Optional


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
            total: Total progress value.
            message: Status message.
        """
        if total > 0:
            percent = int((current / total) * 100)
            self.progress["value"] = percent
            self.percent_var.set(f"{percent}%")

        # Truncate long messages
        display_msg = message[:50] + "..." if len(message) > 50 else message
        self.status_var.set(display_msg)

        self.dialog.update_idletasks()

    def close(self):
        """Close the dialog."""
        self.dialog.grab_release()
        self.dialog.destroy()
```

### `pef/gui/settings.py`

```python
"""Settings/preferences management for GUI."""

import os
import json
from typing import Any, Dict, Optional


class Settings:
    """Manages application settings persistence."""

    DEFAULT_SETTINGS = {
        "last_source_path": "",
        "last_dest_path": "",
        "write_exif": True,
        "window_geometry": "600x400",
    }

    def __init__(self):
        """Initialize settings."""
        self._settings: Dict[str, Any] = self.DEFAULT_SETTINGS.copy()
        self._config_path = self._get_config_path()
        self.load()

    def _get_config_path(self) -> str:
        """Get path to config file."""
        if os.name == "nt":  # Windows
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:  # macOS/Linux
            base = os.path.expanduser("~/.config")

        config_dir = os.path.join(base, "pef")
        os.makedirs(config_dir, exist_ok=True)

        return os.path.join(config_dir, "settings.json")

    def load(self):
        """Load settings from file."""
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r") as f:
                    loaded = json.load(f)
                    self._settings.update(loaded)
        except Exception:
            pass  # Use defaults on error

    def save(self):
        """Save settings to file."""
        try:
            with open(self._config_path, "w") as f:
                json.dump(self._settings, f, indent=2)
        except Exception:
            pass  # Ignore save errors

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any):
        """Set a setting value."""
        self._settings[key] = value
```

### Update `pef/__main__.py`

```python
"""Entry point for python -m pef."""

import sys


def main():
    """Main entry point supporting both CLI and GUI modes."""
    # Check if --gui flag is present
    if "--gui" in sys.argv:
        sys.argv.remove("--gui")
        from pef.gui.main import main as gui_main
        gui_main()
    else:
        from pef.cli.main import main as cli_main
        sys.exit(cli_main())


if __name__ == "__main__":
    main()
```

## Usage

```bash
# Launch GUI
python -m pef --gui

# Or create a shortcut script pef-gui.py:
from pef.gui.main import main
main()
```

## Acceptance Criteria

1. [ ] All GUI files created
2. [ ] Main window displays with all controls
3. [ ] Source/destination browsing works
4. [ ] Dry run shows results in dialog
5. [ ] Processing shows progress dialog
6. [ ] Extend mode works
7. [ ] Threading prevents UI freezing
8. [ ] `python -m pef --gui` launches GUI

## Verification

```bash
# Launch GUI
python -m pef --gui

# Test each button:
# 1. Browse for source directory
# 2. Click "Dry Run" - should show analysis
# 3. Click "Process Files" - should process with progress
# 4. Click "Extend Metadata" - should extend if processed folder exists
```

## Future Enhancements

After initial implementation, could add:
- Settings persistence (last used paths)
- Recent directories list
- Drag-and-drop support
- Dark mode support
- Processing log viewer
- Cancel button for long operations
