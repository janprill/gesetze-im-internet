"""Compatibility package for local execution from repository checkout.

The actual implementation lives in ``src/sgbpot``; this shim keeps
``python -m sgbpot.cli`` working without requiring installation.
"""

from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parent.parent / "src" / "sgbpot"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Make ``sgbpot`` a namespace that also searches into ``src/sgbpot``.
__path__ = [str(__path__[0]), str(_SRC)]  # type: ignore[name-defined]
