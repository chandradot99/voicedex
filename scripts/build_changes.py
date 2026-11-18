"""Write data/.changes.json from git history (the /changes page and /changes.xml feed read it).

The deploy image has no .git, so CI runs this with a full-history checkout before `docker build`.
Locally the app computes the same thing from git on first use; run this only to inspect the output.

    uv run python scripts/build_changes.py            # writes data/.changes.json
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voicedex.web.changes import CHANGES_FILE, write_changes  # noqa: E402


def main() -> None:
    out = ROOT / "data" / CHANGES_FILE
    n = write_changes(ROOT, out)
    print(f"wrote {out.relative_to(ROOT)} ({n} changes)")


if __name__ == "__main__":
    main()
