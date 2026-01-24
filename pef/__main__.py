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
