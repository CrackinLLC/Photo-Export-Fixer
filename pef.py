#!/usr/bin/env python3
"""Photo Export Fixer - Main entry point.

Usage:
    python pef.py --path "D:/Photos/Takeout" [options]
    python pef.py --gui
"""

import sys

if __name__ == "__main__":
    if "--gui" in sys.argv:
        sys.argv.remove("--gui")
        from pef.gui.main import main as gui_main
        gui_main()
    else:
        from pef.cli.main import main as cli_main
        sys.exit(cli_main())
