"""Main window for Photo Export Fixer GUI."""

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from pef.core.orchestrator import PEFOrchestrator
from pef.core.exiftool import is_exiftool_available, get_install_instructions
from pef.gui.progress import InlineProgressView
from pef.gui.settings import Settings


class ScrollableFrame(ttk.Frame):
    """A scrollable frame using Canvas."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # Create canvas and scrollbar
        self._canvas = tk.Canvas(self, highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._content = ttk.Frame(self._canvas)

        # Configure canvas scrolling
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        # Pack scrollbar and canvas
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create window inside canvas
        self._canvas_window = self._canvas.create_window((0, 0), window=self._content, anchor=tk.NW)

        # Bind events for resizing
        self._content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Bind mousewheel
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_content_configure(self, event=None):
        """Update scroll region when content changes."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        # Show/hide scrollbar based on content height
        if self._content.winfo_reqheight() > self._canvas.winfo_height():
            self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            self._scrollbar.pack_forget()

    def _on_canvas_configure(self, event):
        """Update content width when canvas resizes."""
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling."""
        # Only scroll if content is taller than canvas
        if self._content.winfo_reqheight() <= self._canvas.winfo_height():
            return
        if event.num == 4:  # Linux scroll up
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self._canvas.yview_scroll(1, "units")
        else:  # Windows/Mac
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    @property
    def content(self) -> ttk.Frame:
        """Get the content frame to add widgets to."""
        return self._content


class CollapsibleFrame(ttk.Frame):
    """A frame that can be collapsed/expanded."""

    def __init__(self, parent, text="Advanced Options", on_toggle=None, **kwargs):
        super().__init__(parent, **kwargs)

        self._is_expanded = tk.BooleanVar(value=False)
        self._on_toggle = on_toggle

        # Header button
        self._toggle_btn = ttk.Checkbutton(
            self,
            text=f"\u25b6 {text}",  # Right-pointing triangle
            variable=self._is_expanded,
            command=self._toggle,
            style="Toolbutton"
        )
        self._toggle_btn.pack(fill=tk.X, pady=(5, 0))

        # Content frame (hidden by default)
        self._content = ttk.Frame(self, padding=(20, 10, 10, 10))
        self._text = text

    def _toggle(self):
        """Toggle visibility of content."""
        if self._is_expanded.get():
            self._content.pack(fill=tk.X, expand=True)
            self._toggle_btn.config(text=f"\u25bc {self._text}")  # Down triangle
        else:
            self._content.forget()
            self._toggle_btn.config(text=f"\u25b6 {self._text}")  # Right triangle
        if self._on_toggle:
            self._on_toggle()

    @property
    def content(self) -> ttk.Frame:
        """Get the content frame to add widgets to."""
        return self._content

    def expand(self):
        """Expand the frame."""
        self._is_expanded.set(True)
        self._toggle()

    def collapse(self):
        """Collapse the frame."""
        self._is_expanded.set(False)
        self._toggle()


class PEFMainWindow:
    """Main application window."""

    def __init__(self):
        """Initialize the main window."""
        self.root = tk.Tk()
        self.root.title("Photo Export Fixer")
        self.root.geometry("600x460")
        self.root.minsize(500, 380)

        # Load settings
        self.settings = Settings()

        # Variables - Main
        self.source_path = tk.StringVar(value=self.settings.get("last_source_path", ""))
        self.dest_path = tk.StringVar(value=self.settings.get("last_dest_path", ""))
        self.write_exif = tk.BooleanVar(value=self.settings.get("write_exif", True))

        # Variables - Advanced
        self.force_restart = tk.BooleanVar(value=False)
        self.verbose_logging = tk.BooleanVar(value=self.settings.get("verbose", False))
        self.rename_mp = tk.BooleanVar(value=self.settings.get("rename_mp", False))

        # ExifTool availability (set by _check_exiftool)
        self._exiftool_available = False

        # Cancel event for cooperative cancellation
        self._cancel_event = None
        self._is_preview_mode = False
        self._progress_view = None

        # Build UI
        self._create_widgets()

        # Check ExifTool on startup
        self.root.after(100, self._check_exiftool)

        # Save settings on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        """Create and layout all widgets."""
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== BOTTOM SECTION (pack first to stay at bottom) =====

        # Status bar (always visible)
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(5, 3)
        )
        status_bar.pack(fill=tk.X)

        # ===== SETUP CONTAINER (shown when not processing) =====

        self._setup_container = ttk.Frame(main_frame)
        self._setup_container.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(self._setup_container)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 5))

        dry_run_btn = ttk.Button(
            button_frame,
            text="Preview",
            command=self._on_dry_run,
            width=15
        )
        dry_run_btn.pack(side=tk.LEFT, padx=(0, 10))

        style = ttk.Style()
        style.configure("Accent.TButton", font=("", 10, "bold"))

        process_btn = ttk.Button(
            button_frame,
            text="Start",
            command=self._on_process,
            style="Accent.TButton",
            width=15
        )
        process_btn.pack(side=tk.LEFT)

        # ===== TOP SECTION (fixed header) =====

        header_frame = ttk.Frame(self._setup_container)
        header_frame.pack(fill=tk.X, side=tk.TOP)

        # Title
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))

        title_label = ttk.Label(
            title_frame,
            text="Photo Export Fixer",
            font=("", 18, "bold")
        )
        title_label.pack(side=tk.LEFT)

        subtitle_label = ttk.Label(
            title_frame,
            text="Fix metadata from Google Takeout exports",
            font=("", 10)
        )
        subtitle_label.pack(side=tk.LEFT, padx=(15, 0), pady=(5, 0))

        # Source path
        source_frame = ttk.LabelFrame(header_frame, text="Source Directory", padding="10")
        source_frame.pack(fill=tk.X, pady=(0, 10))

        source_entry = ttk.Entry(source_frame, textvariable=self.source_path)
        source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        source_btn = ttk.Button(
            source_frame,
            text="Browse...",
            command=self._browse_source
        )
        source_btn.pack(side=tk.RIGHT)

        # Destination path
        dest_frame = ttk.LabelFrame(header_frame, text="Destination Directory", padding="10")
        dest_frame.pack(fill=tk.X, pady=(0, 5))

        dest_entry = ttk.Entry(dest_frame, textvariable=self.dest_path)
        dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        dest_btn = ttk.Button(
            dest_frame,
            text="Browse...",
            command=self._browse_dest
        )
        dest_btn.pack(side=tk.RIGHT)

        dest_hint = ttk.Label(
            header_frame,
            text="Leave empty to auto-create, or type any path (will be created if needed)",
            font=("", 8),
            foreground="gray"
        )
        dest_hint.pack(anchor=tk.W, pady=(0, 5))

        # ===== MIDDLE SECTION (scrollable) =====

        self.scroll_frame = ScrollableFrame(self._setup_container)
        self.scroll_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        scroll_content = self.scroll_frame.content

        # Advanced Options (collapsible)
        self.advanced_frame = CollapsibleFrame(
            scroll_content,
            text="Advanced Options",
            on_toggle=self._on_advanced_toggle
        )
        self.advanced_frame.pack(fill=tk.X, pady=(0, 10))

        advanced_content = self.advanced_frame.content

        # ExifTool checkbox with status indicator and install button
        exif_frame = ttk.Frame(advanced_content)
        exif_frame.pack(fill=tk.X, pady=2)

        exif_check = ttk.Checkbutton(
            exif_frame,
            text="Write EXIF metadata (GPS coordinates, people tags)",
            variable=self.write_exif
        )
        exif_check.pack(side=tk.LEFT)

        self.exif_status = ttk.Label(exif_frame, text="", font=("", 8))
        self.exif_status.pack(side=tk.LEFT, padx=(10, 0))

        # Install/Instructions button (shown when ExifTool not found)
        if sys.platform == "win32":
            self.exif_install_btn = ttk.Button(
                exif_frame,
                text="Install",
                command=self._try_install_exiftool,
                width=8
            )
        else:
            self.exif_install_btn = ttk.Button(
                exif_frame,
                text="How to Install",
                command=self._show_exiftool_instructions,
                width=12
            )
        # Button starts hidden, shown by _check_exiftool if needed

        # Force restart option
        force_check = ttk.Checkbutton(
            advanced_content,
            text="Start fresh (ignore saved progress from previous run)",
            variable=self.force_restart
        )
        force_check.pack(anchor=tk.W, pady=2)

        # Verbose logging option
        verbose_check = ttk.Checkbutton(
            advanced_content,
            text="Verbose logging (log all operations, not just errors)",
            variable=self.verbose_logging
        )
        verbose_check.pack(anchor=tk.W, pady=2)

        # Rename MP option
        rename_mp_check = ttk.Checkbutton(
            advanced_content,
            text="Rename .MP motion photos to .MP4",
            variable=self.rename_mp
        )
        rename_mp_check.pack(anchor=tk.W, pady=2)

        # ===== PROGRESS CONTAINER (hidden initially, shown during processing) =====

        self._progress_container = ttk.Frame(main_frame)
        # Not packed yet — shown by _show_progress_view()

    def _on_advanced_toggle(self):
        """Handle advanced options toggle - update scroll region."""
        self.root.after(10, lambda: self.scroll_frame._on_content_configure(None))

    def _check_exiftool(self):
        """Check ExifTool availability and update UI."""
        self._exiftool_available = is_exiftool_available()

        if self._exiftool_available:
            self.exif_status.config(text="(available)", foreground="green")
            # Always enable when available, ignore saved settings
            self.write_exif.set(True)
            # Hide install button
            self.exif_install_btn.pack_forget()
        else:
            # Platform-specific message
            if sys.platform == "win32":
                self.exif_status.config(text="(not found)", foreground="orange")
            else:
                self.exif_status.config(text="(not found)", foreground="orange")
            self.write_exif.set(False)
            # Show install button
            self.exif_install_btn.pack(side=tk.LEFT, padx=(10, 0))

    def _try_install_exiftool(self):
        """Attempt to install ExifTool (Windows only).

        Runs download in a background thread to keep the GUI responsive.
        """
        self.status_var.set("Downloading ExifTool...")
        self.exif_install_btn.config(state="disabled")

        def download():
            from pef.core.exiftool import auto_download_exiftool
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            return auto_download_exiftool(base_dir)

        def on_result(success):
            if not self.root.winfo_exists():
                return
            if success:
                from pef.core.exiftool import _reset_exiftool_cache
                _reset_exiftool_cache()
                self._check_exiftool()
                if self._exiftool_available:
                    self.status_var.set("ExifTool installed successfully!")
                    messagebox.showinfo("Success", "ExifTool has been installed successfully!")
                else:
                    self.status_var.set("Installation failed")
                    self.exif_install_btn.config(state="normal")
                    messagebox.showerror("Error", "ExifTool installation failed. Please install manually.")
            else:
                self.status_var.set("Installation failed")
                self.exif_install_btn.config(state="normal")
                messagebox.showerror(
                    "Installation Failed",
                    "Could not download ExifTool automatically.\n\n"
                    "Please download manually from https://exiftool.org/"
                )

        def run():
            try:
                success = download()
            except Exception:
                success = False
            self.root.after(0, lambda: on_result(success))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _browse_source(self):
        """Open file dialog for source directory."""
        initial = self.source_path.get() or os.path.expanduser("~")
        path = filedialog.askdirectory(
            title="Select Google Takeout Directory",
            initialdir=initial
        )
        if path:
            self.source_path.set(path)
            self.settings.set("last_source_path", path)
            # Auto-fill destination if empty
            if not self.dest_path.get():
                self.dest_path.set(f"{path}_processed")

    def _browse_dest(self):
        """Open file dialog for destination directory."""
        initial = self.dest_path.get() or self.source_path.get() or os.path.expanduser("~")
        path = filedialog.askdirectory(
            title="Select Destination Directory",
            initialdir=initial
        )
        if path:
            self.dest_path.set(path)
            self.settings.set("last_dest_path", path)

    def _validate_source(self) -> bool:
        """Validate source path exists."""
        source = self.source_path.get().strip()
        if not source:
            messagebox.showerror("Error", "Please select a source directory.")
            return False
        if not os.path.isdir(source):
            messagebox.showerror("Error", f"Source directory does not exist:\n{source}")
            return False
        return True

    def _create_orchestrator(self):
        """Create orchestrator with current settings."""
        return PEFOrchestrator(
            source_path=self.source_path.get().strip(),
            dest_path=self.dest_path.get().strip() or None,
            write_exif=self.write_exif.get(),
            verbose=self.verbose_logging.get(),
            rename_mp=self.rename_mp.get()
        )

    def _show_progress_view(self, title: str):
        """Swap from setup view to inline progress view."""
        self._setup_container.pack_forget()
        self._progress_view = InlineProgressView(
            self._progress_container,
            on_cancel=self._on_cancel
        )
        self._progress_view.set_title(title)
        self._progress_view.pack(fill=tk.BOTH, expand=True)
        self._progress_container.pack(fill=tk.BOTH, expand=True)

    def _show_setup_view(self):
        """Swap from progress view back to setup view."""
        self._progress_container.pack_forget()
        # Destroy progress view widgets
        for child in self._progress_container.winfo_children():
            child.destroy()
        self._progress_view = None
        self._setup_container.pack(fill=tk.BOTH, expand=True)

    def _on_cancel(self):
        """Handle cancel button click with confirmation dialog."""
        if not self._cancel_event:
            return

        # Detect whether we're in preview or process mode
        is_preview = self._is_preview_mode

        if is_preview:
            title = "Cancel Preview"
            message = "Are you sure you want to cancel the preview?"
            cancel_status = "Cancelling..."
        else:
            title = "Cancel Processing"
            message = (
                "Are you sure you want to cancel?\n\n"
                "Progress will be saved. You can resume later."
            )
            cancel_status = "Cancelling... saving progress"

        confirmed = messagebox.askyesno(title, message)
        if confirmed:
            self._cancel_event.set()
            if self._progress_view:
                self._progress_view.disable_cancel()
                self._progress_view.set_status(cancel_status)
            self.status_var.set("Cancelling...")

    def _run_async(self, status_msg: str, title: str, operation, on_complete):
        """Run an operation asynchronously with inline progress view."""
        self.status_var.set(status_msg)
        self._show_progress_view(title)

        def run():
            success = False
            try:
                orchestrator = self._create_orchestrator()
                last_update = [0.0]

                def progress_cb(c, t, m):
                    now = time.monotonic()
                    # Throttle to ~8 updates/sec; always allow final/completion updates
                    if now - last_update[0] < 0.12 and t > 0 and c < t:
                        return
                    last_update[0] = now

                    def update_ui(c=c, t=t, m=m):
                        if self.root.winfo_exists() and self._progress_view:
                            self._progress_view.update_progress(c, t, m)

                    self.root.after(0, update_ui)

                result = operation(orchestrator, progress_cb)
                self.root.after(0, lambda: self._on_operation_complete(result, on_complete))
                success = True
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self._on_operation_error(error_msg))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _on_operation_complete(self, result, on_complete):
        """Handle operation completion on the main thread."""
        if not self.root.winfo_exists():
            return
        self._cancel_event = None
        self._is_preview_mode = False
        self._show_setup_view()
        on_complete(result)

    def _on_operation_error(self, error_msg):
        """Handle operation error on the main thread."""
        if not self.root.winfo_exists():
            return
        self._cancel_event = None
        self._is_preview_mode = False
        self._show_setup_view()
        self.status_var.set("Ready")
        messagebox.showerror("Error", error_msg)

    def _on_dry_run(self):
        """Handle dry run button click."""
        if not self._validate_source():
            return

        self._cancel_event = threading.Event()
        self._is_preview_mode = True
        cancel_event = self._cancel_event
        self._run_async(
            "Analyzing...",
            "Analyzing Files",
            lambda orch, cb: orch.dry_run(on_progress=cb, cancel_event=cancel_event),
            self._show_dry_run_results
        )

    def _show_dry_run_results(self, result):
        """Show dry run results in a dialog."""
        if result.cancelled:
            self.status_var.set("Preview cancelled")
            return

        # Determine EXIF status message
        if result.exiftool_available:
            if self.write_exif.get():
                exif_status = "Enabled (will write GPS/people tags)"
            else:
                exif_status = "Disabled (available but not selected)"
        else:
            exif_status = "Not installed (GPS/people tags won't be written)"

        msg = f"""Found:
  {result.json_count:,} JSON metadata files
  {result.file_count:,} media files

Would process:
  {result.matched_count:,} files with matching metadata
  {result.unmatched_json_count:,} JSONs without matching file
  {result.unmatched_file_count:,} files without matching JSON

Metadata available:
  {result.with_gps:,} files with GPS coordinates
  {result.with_people:,} files with people tags

ExifTool: {exif_status}"""

        self.status_var.set(f"Preview complete: {result.matched_count:,} files would be processed")
        messagebox.showinfo("Preview Results", msg)

    def _on_process(self):
        """Handle process button click."""
        if not self._validate_source():
            return

        # Check ExifTool if EXIF writing is enabled
        if self.write_exif.get() and not is_exiftool_available():
            result = messagebox.askyesnocancel(
                "ExifTool Not Found",
                "ExifTool is not installed. Without it, GPS coordinates and people tags won't be written.\n\n"
                "Do you want to continue anyway?\n\n"
                "Yes = Continue without EXIF\n"
                "No = Show installation instructions\n"
                "Cancel = Go back"
            )
            if result is None:  # Cancel
                return
            elif result is False:  # No - show instructions
                self._show_exiftool_instructions()
                return
            else:  # Yes - continue without EXIF
                self.write_exif.set(False)

        # Confirm
        dest = self.dest_path.get().strip() or f"{self.source_path.get().strip()}_processed"
        if not messagebox.askyesno(
            "Confirm Processing",
            f"This will copy and process files to:\n{dest}\n\nContinue?"
        ):
            return

        force = self.force_restart.get()
        self._cancel_event = threading.Event()
        self._is_preview_mode = False
        cancel_event = self._cancel_event
        self._run_async(
            "Processing...",
            "Processing Files",
            lambda orch, cb: orch.process(on_progress=cb, force=force, cancel_event=cancel_event),
            self._show_process_results
        )

    def _show_exiftool_instructions(self):
        """Show ExifTool installation instructions."""
        instructions = get_install_instructions()
        messagebox.showinfo("ExifTool Installation", instructions)

    def _show_process_results(self, result):
        """Show processing results."""
        if result.cancelled:
            self.status_var.set(
                "Cancelled \u2014 progress saved. Resume by clicking Start again."
            )
            return

        # Build result message
        lines = [
            f"Processed: {result.stats.processed:,} files",
            f"  With GPS data: {result.stats.with_gps:,}",
            f"  With people tags: {result.stats.with_people:,}",
        ]

        if result.stats.unmatched_files > 0:
            lines.append(f"\nFiles without metadata: {result.stats.unmatched_files:,}")

        if result.motion_photo_count > 0:
            lines.append(f"Motion photos: {result.motion_photo_count:,}")

        lines.append(f"\nTime: {result.elapsed_time:.1f} seconds")
        lines.append(f"\nOutput folder:\n{result.output_dir}")

        msg = "\n".join(lines)

        self.status_var.set(f"Complete: {result.stats.processed:,} files in {result.elapsed_time:.1f}s")

        # Show results with option to open folder
        open_folder = messagebox.askyesno(
            "Processing Complete",
            msg + "\n\nWould you like to open the output folder?"
        )

        if open_folder:
            self._open_folder(result.output_dir)

    def _open_folder(self, path: str):
        """Open a folder in the system file browser."""
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", path], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def _on_close(self):
        """Handle window close - save settings."""
        self.settings.set("last_source_path", self.source_path.get())
        self.settings.set("last_dest_path", self.dest_path.get())
        self.settings.set("write_exif", self.write_exif.get())
        self.settings.set("verbose", self.verbose_logging.get())
        self.settings.set("rename_mp", self.rename_mp.get())
        self.settings.save()
        self.root.destroy()

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()
