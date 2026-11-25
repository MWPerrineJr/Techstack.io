"""Tests for expense_agent.

Policy numbers are hard-coded on purpose: the tests are an
independent statement of the policy, while the rules read
``config/policy.yaml``. If the two disagree, a test fails.
"""

import copy
from collections.abc import Callable
from datetime import date, timedelta

import pytest

from expense_agent.models import Claim, Flag, Violation
from expense_agent.policy import Policy
from expense_agent.rules import (
    RESULT_COLUMNS,
    check_cap,
    check_duplicates,
    check_fare_class,
    check_high_value,
    check_late,
    check_mileage,
    check_missing_purpose,
    check_near_cap,
    check_prohibited_hint,
    check_receipt,
    check_rental_class,
    check_software_vendor,
    check_splits,
    mileage_rate,
    rule_decision,
    run_rules,
)

MakeClaim = Callable[..., Claim]


def code_of(finding: Violation | Flag | None) -> str | None:
    """Return a finding's code, or None when the rule passed."""
    return None if finding is None else finding.code


# --- Fixture sanity -----------------------------------------------


def test_make_claim_unknown_category(make_claim: MakeClaim) -> None:
    with pytest.raises(ValueError, match="valid: .*Meals"):
        make_claim("meals")


# --- Single-claim deny rules (POL-1.2, 1.3, 2.1, 2.2, 2.5, 2.6) ----


@pytest.mark.parametrize(
    ("days", "expected"),
    [(60, None), (61, "late_submission")],  # POL-1.2: "more than 60"
)
def test_late(
    make_claim: MakeClaim, policy: Policy, days: int, expected: str | None
) -> None:
    submitted = make_claim("Meals").submitted_date
    claim = make_claim("Meals", expense_date=submitted - timedelta(days=days))
    assert code_of(check_late(claim, policy)) == expected


@pytest.mark.parametrize(
    ("category", "amount", "receipt", "expected"),
    [
        ("Meals", 75.00, False, None),  # at the threshold: fine
        ("Meals", 75.01, False, "missing_receipt"),
        ("Meals", 75.01, True, None),
        ("Mileage", 500.00, False, None),  # mileage never needs one
    ],
)
def test_receipt(
    make_claim: MakeClaim,
    policy: Policy,
    category: str,
    amount: float,
    receipt: bool,
    expected: str | None,
) -> None:
    claim = make_claim(category, amount=amount, receipt_attached=receipt)
    assert code_of(check_receipt(claim, policy)) == expected


@pytest.mark.parametrize(
    ("city", "nightly", "nights", "expected"),
    [
        ("New York, NY", 350.00, 2, None),  # high-cost cap
        ("New York, NY", 350.01, 2, "over_cap"),
        ("Austin, TX", 250.00, 2, None),  # standard cap
        ("Austin, TX", 250.01, 2, "over_cap"),
        ("Austin, TX", 249.99, 7, None),  # float safety
    ],
)
def test_lodging_cap(
    make_claim: MakeClaim,
    policy: Policy,
    city: str,
    nightly: float,
    nights: int,
    expected: str | None,
) -> None:
    claim = make_claim(
        "Lodging", city=city, nights=nights, amount=nightly * nights
    )
    assert code_of(check_cap(claim, policy)) == expected


@pytest.mark.parametrize(
    ("fare", "hours", "preapproved", "expected"),
    [
        ("Economy", 2.0, False, None),
        ("Business", 6.0, True, None),  # boundary: >= 6h + preapproval
        ("Business", 5.9, True, "premium_class"),
        ("Business", 8.0, False, "premium_class"),
        ("First", 12.0, True, "premium_class"),
    ],
)
def test_fare_class(
    make_claim: MakeClaim,
    policy: Policy,
    fare: str,
    hours: float,
    preapproved: bool,
    expected: str | None,
) -> None:
    claim = make_claim(
        "Airfare",
        fare_class=fare,
        flight_hours=hours,
        preapproved=preapproved,
    )
    assert code_of(check_fare_class(claim, policy)) == expected


@pytest.mark.parametrize(
    ("rental", "expected"),
    [("Mid-size", None), ("Luxury", "premium_class")],
)
def test_rental_class(
    make_claim: MakeClaim, policy: Policy, rental: str, expected: str | None
) -> None:
    claim = make_claim("Ground Transport", rental_class=rental)
    assert code_of(check_rental_class(claim, policy)) == expected


@pytest.mark.parametrize(
    ("day", "amount", "expected"),
    [
        (date(2026, 6, 30), 72.50, None),  # 100 x $0.725
        (date(2026, 6, 30), 72.51, "over_cap"),
        (date(2026, 7, 1), 76.00, None),  # new rate from Jul 1
        (date(2026, 7, 1), 76.01, "over_cap"),
    ],
)
def test_mileage(
    make_claim: MakeClaim,
    policy: Policy,
    day: date,
    amount: float,
    expected: str | None,
) -> None:
    claim = make_claim("Mileage", expense_date=day, miles=100, amount=amount)
    assert code_of(check_mileage(claim, policy)) == expected


@pytest.mark.parametrize(
    ("day", "rate"),
    [
        (date(2026, 6, 30), 0.725),  # last day of  the first band
        (date(2026, 7, 1), 0.76),  # first day of the second band
        (date(2026, 10, 5), 0.76),  # regression raise inside the loop
    ],
)
def test_mileage_rate_bands(policy: Policy, day: date, rate: float) -> None:
    assert mileage_rate(day, policy) == rate


def test_mileage_rate_outside_bands_raises(policy: Policy) -> None:
    with pytest.raises(ValueError, match="No mileage rate"):
        mileage_rate(date(1999, 1, 1), policy)


# --- Review flags (POL-2.8, 3.x) -----------------------------------------------------


@pytest.mark.parametrize(
    ("category", "merchant", "description", "expected_ref"),
    [
        ("Meals", "Corner Bar", "Team drinks", "POL-3.1"),
        ("Client Meals", "Corner Bar", "Wine w/ Acme", None),  # POL-2.4
        ("Meals", "Hotel", "In-room movies", "POL-3.6"),
        ("Meals", "Cafe", "Workspace lunch", None),  # "spa" inside a word
    ],
)
def test_prohibited_hint(
    make_claim: MakeClaim,
    policy: Policy,
    category: str,
    merchant: str,
    description: str,
    expected_ref: str | None,
) -> None:
    claim = make_claim(category, merchant=merchant, description=description)
    hint = check_prohibited_hint(claim, policy)
    assert (hint.policy_ref if hint else None) == expected_ref


def test_prohibited_hint_reads_the_given_policy(
    make_claim: MakeClaim, policy: Policy
) -> None:
    claim = make_claim("Meals", merchant="Harbor Yachts", description="Lunch")
    assert check_prohibited_hint(claim, policy) is None

    custom = copy.deepcopy(policy)  # never mutate the shared fixture
    custom["prohibited"].append(
        {"code": "TEST_YACHT", "policy_ref": "POL-3.9", "keywords": ["yacht"]}
    )
    hint = check_prohibited_hint(claim, custom)
    assert hint is not None and hint.detail.startswith("TEST_YACHT")


@pytest.mark.parametrize(
    ("vendor", "expected"),
    [("Slack", None), ("Unlisted SaaS Inc", "unapproved_vendor")],
)
def test_software_vendor(
    make_claim: MakeClaim, policy: Policy, vendor: str, expected: str | None
) -> None:
    claim = make_claim("Software", merchant=vendor)
    assert code_of(check_software_vendor(claim, policy)) == expected


# --- Escalation flags (POL-5.1 - 5.3) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "expected"),
    [(1000.00, None), (1000.01, "high_value")],
)
def test_high_value(
    make_claim: MakeClaim, policy: Policy, amount: float, expected: str | None
) -> None:
    claim = make_claim("Office Supplies", amount=amount)
    assert code_of(check_high_value(claim, policy)) == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (134.99, None),  # below the band
        (135.00, "near_cap"),  # band is [cap x 0.9, cap]
        (150.00, "near_cap"),
        (150.01, None),  # over cap; check_cap owns it
    ],
)
def test_near_cap(
    make_claim: MakeClaim, policy: Policy, amount: float, expected: str | None
) -> None:
    claim = make_claim("Office Supplies", amount=amount)
    assert code_of(check_near_cap(claim, policy)) == expected


def test_near_cap_hands_off_to_cap(
    make_claim: MakeClaim, policy: Policy
) -> None:
    claim = make_claim("Office Supplies", amount=150.01)
    assert code_of(check_cap(claim, policy)) == "over_cap"


@pytest.mark.parametrize(
    ("purpose", "expected"),
    [
        (None, "missing_purpose"),
        ("", "missing_purpose"),
        ("   ", "missing_purpose"),
        ("Meeting", None),  # vague is the agent's job (05)
    ],
)
def test_missing_purpose(
    make_claim: MakeClaim,
    policy: Policy,
    purpose: str | None,
    expected: str | None,
) -> None:
    claim = make_claim("Meals", business_purpose=purpose)
    assert code_of(check_missing_purpose(claim, policy)) == expected


# --- Cross-claim deny rules (POL-1.4, 1.5) ---------------------------------------------------------------------


def test_duplicate_is_the_later_submission(make_claim: MakeClaim) -> None:
    original = make_claim("Home Office")
    repeat = make_claim(
        "Home Office",
        claim_id="T-DUP",
        submitted_date=original.submitted_date + timedelta(days=1),
    )
    found = check_duplicates([repeat, original])  # list order reversed
    assert [v.claim_id for v in found] == ["T-DUP"]
    assert found[0].detail.endswith(original.claim_id)


@pytest.mark.parametrize(
    ("first", "second", "expected_ids"),
    [
        (300.00, 250.00, ["T-P1", "T-P2"]),  # each under $500, total over
        (300.00, 150.00, []),  # total within the cap
        (600.00, 100.00, []),  # one part over the cap: over_cap owns it
    ],
)
def test_splits(
    make_claim: MakeClaim,
    policy: Policy,
    first: float,
    second: float,
    expected_ids: list[str],
) -> None:
    part1 = make_claim("Home Office", claim_id="T-P1", amount=first)
    part2 = make_claim(
        "Home Office",
        claim_id="T-P2",
        amount=second,
        submitted_date=part1.submitted_date + timedelta(days=1),
    )

    found = check_splits([part1, part2], policy, skip_ids=set())
    assert sorted(v.claim_id for v in found) == expected_ids


# --- Decision and pipeline (POL-5) ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("violations", "flags", "expected"),
    [
        (["over_cap"], ["high_value"], "deny"),  # deny beats review
        ([], ["near_cap"], "review"),
        ([], [], "approve"),
    ],
)
def test_rule_decision(
    violations: list[str], flags: list[str], expected: str
) -> None:
    assert rule_decision(violations, flags) == expected


def test_pipeline_vendor_is_review_not_deny(
    make_claim: MakeClaim, policy: Policy
) -> None:
    claim = make_claim(
        "Software", merchant="Unlisted SaaS Inc", receipt_attached=True
    )
    row = run_rules([claim], policy).iloc[0]
    assert row["rule_decision"] == "review", row["violations"]
    assert row["flags"] == ["unapproved_vendor"]


def test_pipeline_deny_keeps_its_flags(
    make_claim: MakeClaim, policy: Policy
) -> None:
    claim = make_claim(
        "Office Supplies", amount=1000.01, receipt_attached=True
    )
    row = run_rules([claim], policy).iloc[0]
    assert row["rule_decision"] == "deny"
    assert "over_cap" in row["violations"]
    assert "high_value" in row["flags"]  # Session 7: flags stay on denies


def test_run_rules_empty_input(policy: Policy) -> None:
    results = run_rules([], policy)
    assert results.empty
    assert list(results.columns) == RESULT_COLUMNS


# --- Golden master: the generated dataset --------------------------------------------------


def test_baseline_on_generated_data(
    claims: list[Claim], policy: Policy
) -> None:
    results = run_rules(claims, policy)
    assert len(results) == len(claims) == 330
    assert results["claim_id"].is_unique
    denied = results["rule_decision"] == "deny"
    assert results.loc[denied, "violations"].map(len).gt(0).all()
    counts = results["rule_decision"].value_counts().to_dict()
    assert counts == {"approve": 237, "deny": 62, "review": 31}
