"""GUI entry point for Photo Export Fixer."""


def main():
    """Launch the GUI application."""
    from pef.gui.main_window import PEFMainWindow

    app = PEFMainWindow()
    app.run()


if __name__ == "__main__":
    main()
