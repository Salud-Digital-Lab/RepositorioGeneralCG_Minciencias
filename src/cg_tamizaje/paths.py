from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
DOCS = ROOT / "docs"
CONFIGS = ROOT / "configs"
ARTIFACTS = ROOT / "artifacts"
