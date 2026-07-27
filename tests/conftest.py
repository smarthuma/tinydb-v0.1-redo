"""Worktree conftest: ensure `import tinydb` resolves to THIS worktree's package.

The shared .venv editable install points at the main repo's tinydb. Running tests
from a worktree must test the worktree's code, so we strip the editable finder
and prepend the worktree root to sys.path.
"""
import os
import sys

_WORKTREE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Remove the shared editable finder that pins tinydb to the main repo.
sys.meta_path = [f for f in sys.meta_path if type(f).__name__ != "_EditableFinder"]

# Prepend worktree root so `import tinydb` finds the worktree package first.
if _WORKTREE_ROOT not in sys.path:
    sys.path.insert(0, _WORKTREE_ROOT)
