"""Make the src-layout package importable for target-runtime integration tests."""

from pathlib import Path
import sys


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
PROJECT_ROOT = SOURCE_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
