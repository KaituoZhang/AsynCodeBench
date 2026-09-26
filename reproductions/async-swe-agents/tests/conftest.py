from __future__ import annotations

import sys
from pathlib import Path


RUNNER_ROOT = Path(__file__).parents[1]
if str(RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNER_ROOT))
