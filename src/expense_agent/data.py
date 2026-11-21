"""Read the exported claims and the answer key."""

from pathlib import Path

import pandas as pd

CLAIMS_FILE = "expense_reports.csv"
LABELS_FILE = "ground_truth_labels.csv"
CLAIM_DTYPES = {"nights": "Int64", "attendees": "Int64", "miles": "Int64"}


def load_claims(folder: Path) -> pd.DataFrame:
    """Read the label-free import CSV (all the agent may ever see)."""
    return pd.read_csv(folder / CLAIMS_FILE, dtype=CLAIM_DTYPES)


def load_labels(folder: Path) -> pd.DataFrame:
    """Read the answer key; empty strings stay "" instead of NaN."""
    return pd.read_csv(folder / LABELS_FILE, keep_default_na=False)


def load_dataset(folder: Path) -> pd.DataFrame:
    """Read claims joined to the answer key (EDA and evaluation only)."""
    return load_claims(folder).merge(
        load_labels(folder), on="claim_id", validate="one_to_one"
    )
