import sys
from pathlib import Path

import pytest

# `risk` lives in ml/, which is not on the backend's pythonpath.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("sklearn", reason="install ml/requirements.txt to run the ML tests")
