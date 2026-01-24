"""Interactive wizard mode for Photo Export Fixer."""

from typing import Optional


def run_wizard() -> Optional[str]:
    """Run interactive wizard to get path from user.

    Returns:
        Path entered by user, or None if cancelled.
    """
    print("\nYou have not given arguments needed, so you have been redirected to the Wizard setup")

    try:
        path = input("Enter path to your folder with takeouts: ")
        return path.strip() if path else None
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return None
