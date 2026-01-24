# Task 01: Create Module Structure

## Objective
Create the basic package directory structure without changing any behavior. This is the foundation for all subsequent refactoring.

## Prerequisites
None - this is the first task.

## Files to Create

```
pef/
├── __init__.py
├── __main__.py
├── core/
│   └── __init__.py
├── cli/
│   └── __init__.py
├── gui/
│   └── __init__.py
└── tests/
    └── __init__.py
```

## Implementation Steps

### 1. Create package directories
```bash
mkdir -p pef/core pef/cli pef/gui pef/tests
```

### 2. Create `pef/__init__.py`
```python
"""Photo Export Fixer - Process and organize Google Photos exports."""

__version__ = "3.1.0"
```

### 3. Create `pef/__main__.py`
This allows running as `python -m pef`:
```python
"""Entry point for python -m pef."""
from pef.cli.main import main

if __name__ == "__main__":
    main()
```

### 4. Create subpackage `__init__.py` files
Each should be empty initially:
- `pef/core/__init__.py`
- `pef/cli/__init__.py`
- `pef/gui/__init__.py`
- `pef/tests/__init__.py`

### 5. Update root `pef.py` as thin wrapper
The existing `pef.py` in the repo root becomes a backwards-compatible entry point:
```python
#!/usr/bin/env python3
"""Photo Export Fixer - backwards compatible entry point.

For new usage, prefer: python -m pef
"""

# TODO: After full refactoring, this becomes:
# from pef.cli.main import main
#
# if __name__ == "__main__":
#     main()

# For now, keep all existing code until refactoring is complete
# ... (existing code unchanged)
```

## Acceptance Criteria

1. [ ] Directory structure exists: `pef/`, `pef/core/`, `pef/cli/`, `pef/gui/`, `pef/tests/`
2. [ ] All `__init__.py` files exist
3. [ ] `pef/__main__.py` exists (but won't work until CLI is refactored)
4. [ ] Original `pef.py` still works exactly as before
5. [ ] `python pef.py --dry-run --path <test>` produces same output as before

## Verification

```bash
# Verify structure
ls -la pef/
ls -la pef/core/
ls -la pef/cli/
ls -la pef/gui/
ls -la pef/tests/

# Verify original still works
python pef.py --dry-run --path "D:\Photos\_Google Photos Backup\Google Photos"
```

## Notes

- Keep all existing code in root `pef.py` working throughout refactoring
- Each subsequent task will extract code from `pef.py` into the appropriate module
- Only after all modules are complete will `pef.py` become a thin wrapper
