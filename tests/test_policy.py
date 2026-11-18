"""Tests for expense_agent.policy."""

from pathlib import Path

import pytest

from expense_agent.paths import POLICY_PATH
from expense_agent.policy import Policy, cap_usage, city_tier, load_policy


@pytest.fixture(scope="module")
def policy() -> Policy:
    """Load the real policy once for every test in this file."""
    return load_policy(POLICY_PATH)


def test_load_policy_reads_version(policy: Policy) -> None:
    assert policy["version"] == "1.0"


def test_load_policy_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_policy(tmp_path / "missing_yaml")


def test_city_tier(policy: Policy) -> None:
    expensive = policy["city_tiers"]["high_cost"][0]
    assert city_tier(expensive, policy) == "high_cost"
    assert city_tier("Nowhere, ZZ", policy) == "standard"


def test_lodging_cap_is_per_night(policy: Policy) -> None:
    claim = {
        "category": "Lodging",
        "amount": 600.0,
        "nights": 3,
        "city": "Nowhere, ZZ",
    }
    assert cap_usage(claim, policy) == (200.0, 250.0)


def test_client_meals_cap_is_per_person(policy: Policy) -> None:
    claim = {"category": "Client Meals", "amount": 300.0, "attendees": 4}
    cap = policy["categories"]["Client Meals"]["per_person_cap"]
    assert cap_usage(claim, policy) == (75.0, cap)


@pytest.mark.parametrize(
    ("category", "cap_key"),
    [
        ("Meals", "daily_per_diem"),
        ("Conference", "per_event_cap"),
        ("Home Office", "per_purchase_cap"),
        ("Office Supplies", "per_purchase_cap"),
    ],
)
def test_flat_caps_use_full_amount(policy: Policy, category: str, cap_key: str) -> None:
    claim = {"category": category, "amount": 42.0}
    cap = policy["categories"][category][cap_key]
    assert cap_usage(claim, policy) == (42.0, cap)


def test_uncapped_category_returns_none(policy: Policy) -> None:
    assert cap_usage({"category": "Mileage", "amount": 50.0}, policy) is None


def test_unknown_category_raises(policy: Policy) -> None:
    with pytest.raises(KeyError):
        cap_usage({"category": "Yachts", "amount": 1.0}, policy)
