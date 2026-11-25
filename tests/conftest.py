"""Shared pytest fixtures for the expense_agent test suite.

pytest loads this file automatically: every test in  ``tests/`` can
request these fixtures by name, without importing anything.
"""

from collections.abc import Callable
from typing import Any

import pytest

from expense_agent.data import load_claims
from expense_agent.models import Claim, to_claims
from expense_agent.paths import GENERATED_DIR, POLICY_PATH
from expense_agent.policy import Policy, load_policy


@pytest.fixture(name="policy", scope="session")
def policy_fixture() -> Policy:
    """Load the real policy once per test run.

    Every test shares this dict: deep-copy it before changing it.
    """
    return load_policy(POLICY_PATH)


@pytest.fixture(name="claims", scope="session")
def claims_fixture() -> list[Claim]:
    """Validate the generated claims once per test run (no labels)."""
    return to_claims(load_claims(GENERATED_DIR))


@pytest.fixture(name="make_claim", scope="session")
def make_claim_fixture(claims: list[Claim]) -> Callable[..., Claim]:
    """Factory: a real claim of a category, re-validated with changes."""
    categories = sorted({c.category for c in claims})

    def make_claim(category: str, **changes: Any) -> Claim:
        base = next((c for c in claims if c.category == category), None)
        if base is None:
            raise ValueError(
                f"Unknown category {category!r}; "
                f"valid: {', '.join(categories)}"
            )
        return Claim.model_validate({**base.model_dump(), **changes})

    return make_claim
