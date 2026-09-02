#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cg_tamizaje.models.timbio_hpylori_v2 import run


if __name__ == "__main__":
    artifacts = run()
    print(artifacts.results.to_string(index=False))
    print(f"Selected model: {artifacts.selected_model}")
    print(f"Report: {artifacts.report_path}")
