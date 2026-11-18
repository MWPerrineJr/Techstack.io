"""Tests for expense_agent.data."""

from pathlib import Path

import pandas as pd
import pytest

from expense_agent.data import (
    CLAIMS_FILE,
    LABELS_FILE,
    load_claims,
    load_dataset,
)


def write_files(folder: Path, labels: dict[str, list[str]]) -> None:
    """Write a two-claim import file and the given answer key."""
    claims = {
        "claim_id": [
            "C1",
            "C2",
        ],
        "amount": [10.0, 20.0],
    }
    pd.DataFrame(claims).to_csv(folder / CLAIMS_FILE, index=False)
    pd.DataFrame(labels).to_csv(folder / LABELS_FILE, index=False)


def test_join_keeps_empty_label_strings(tmp_path: Path) -> None:
    write_files(tmp_path, {"claim_id": ["C1", "C2"], "violation_type": ["", "x"]})
    data = load_dataset(tmp_path)
    assert len(data) == 2
    first = data.loc[data["claim_id"] == "C1", "violation_type"].item()
    assert first == ""


def test_claims_have_no_label_columns(tmp_path: Path) -> None:
    write_files(tmp_path, {"claim_id": ["C1", "C2"], "violation_type": ["", "x"]})
    assert "violation_type" not in load_claims(tmp_path).columns


def test_duplicate_label_rows_raise(tmp_path: Path) -> None:
    write_files(
        tmp_path,
        {"claim_id": ["C1", "C1", "C2"], "violation_type": ["", "", ""]},
    )
    with pytest.raises(pd.errors.MergeError):
        load_dataset(tmp_path)
