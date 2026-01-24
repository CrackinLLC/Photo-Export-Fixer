#!/usr/bin/env python3
"""Photo Export Fixer - Development entry point.

This is a temporary thin wrapper for testing the new modular architecture.
Once refactoring is complete, this logic moves to the root pef.py.

Usage:
    python pef-dev.py --path "D:/Photos/Takeout" [options]
"""

# Import from the new package structure
from pef.cli.main import main

if __name__ == "__main__":
    main()
