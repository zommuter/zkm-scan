from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def make_store(tmp_path: Path) -> Path:
    s = tmp_path / "store"
    (s / "scans").mkdir(parents=True)
    (s / "inbox").mkdir()
    (s / "originals" / "scans").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(s)], check=True)
    return s
