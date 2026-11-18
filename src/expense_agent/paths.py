"""Project paths, resolved from this file so they work from any folder."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = PROJECT_ROOT / "config" / "policy.yaml"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
GENERATED_DIR = PROJECT_ROOT / "data" / "generated"
