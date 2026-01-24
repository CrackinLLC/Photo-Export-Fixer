"""Main window for Photo Export Fixer GUI."""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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
            command=self._on_process
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
                    on_progress=lambda c, t, m: self.root.after(0, lambda c=c, t=t, m=m: progress.update(c, t, m))
                )

                # Show results
                self.root.after(0, lambda: self._show_dry_run_results(result))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, progress.close)
                self.root.after(0, lambda: self.status_var.set("Ready"))

        # Run in background thread
        thread = threading.Thread(target=run, daemon=False)
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
                    on_progress=lambda c, t, m: self.root.after(0, lambda c=c, t=t, m=m: progress.update(c, t, m))
                )

                # Show results
                self.root.after(0, lambda: self._show_process_results(result))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, progress.close)
                self.root.after(0, lambda: self.status_var.set("Ready"))

        thread = threading.Thread(target=run, daemon=False)
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
                    on_progress=lambda c, t, m: self.root.after(0, lambda c=c, t=t, m=m: progress.update(c, t, m))
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

        thread = threading.Thread(target=run, daemon=False)
        thread.start()

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()
