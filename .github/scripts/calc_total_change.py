"""Calculate the total change metric for GLAM Tools reports."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    data = sys.stdin.buffer.read().split(b"\0")
    total = 0
    for raw_path in data:
        if not raw_path:
            continue
        path = Path(raw_path.decode())
        try:
            file_data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        value = file_data.get("diff_label")
        if value is None:
            summary = file_data.get("summary_differences")
            if isinstance(summary, dict):
                value = summary.get("pages_used")

        if isinstance(value, str):
            value = value.strip()

        try:
            number = int(value)
        except (TypeError, ValueError):
            try:
                number = int(float(value))
            except (TypeError, ValueError):
                continue

        total += abs(number)

    print(total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
