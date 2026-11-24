"""Tests for expense_agent.models."""

from typing import get_args

import pandas as pd
import pytest
from pydantic import ValidationError

from expense_agent.data import load_claims
from expense_agent.models import (
    Claim,
    Flag,
    Violation,
    ViolationCode,
    to_claims,
)
from expense_agent.paths import GENERATED_DIR, POLICY_PATH
from expense_agent.policy import load_policy



EXPECTED_CLAIMS = 330



@pytest.fixture(name="claims", scope="module")
def claims_fixture() -> list[Claim]:
    """Validate the venerated claims once for every test."""
    return to_claims(load_claims(GENERATED_DIR))


def test_generated_claims_validate(claims: list[Claim]) -> None:
    assert len(claims) == EXPECTED_CLAIMS
    assert len({c.claim_id for c in claims}) == EXPECTED_CLAIMS


def test_violation_codes_match_policy() -> None:
    policy = load_policy(POLICY_PATH)
    assert set(get_args(ViolationCode)) == set(policy["violation_codes"])


@pytest.mark.parametrize("blank", [None, "", "  ", float("nan"), pd.NA])
def test_blank_purpose_becomes_none(
    claims: list[Claim], blank: object
) -> None:
    claim = Claim.model_validate({**claims[0].model_dump, 
                                  "business_purpose": blank})
    assert claim.business_purpose is None



def test_purpose_is_stripped(claims: list[Claim]) -> None:
    claim = Claim.model_validate({**claims[0].model_dump(),
                                  "business_purpose": "  Client dinner "})
    assert claim.business_purpose == "Client dinner"



@pytest.mark.parametrize("ref", ["POL-2.2", "POL-2", "POL-2.2 "])
def test_bad_policy_ref_rejected(ref: str) -> None:
    with pytest.raises(ValidationError):
        Violation(claim_id="X", code="over_cap", policy_ref=ref, detail="t")


def test_good_policy_ref_accepted() -> None:
    violation = Violation(claim_id="X", code="over_cap", policy_ref="POL-2.2", detail="t")
    assert violation.policy_ref == "POL-2.2"



def test_flag_rejects_violation_code() -> None:
    with pytest.raises(ValidationError):
        Flag(claim_id="X", code="over_cap", policy_ref="POL-5.1", detail="t")



def test_claim_is_frozen(claims: list[Claim]) -> None:
    with pytest.raises(ValidationError):
        claims[0].amount = 1.0

