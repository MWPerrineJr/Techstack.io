"""Deterministic policy rules: one finding per broken rule.

Every rule cites its POL-x.y section and reads its numbers from
``config/policy.yaml``. A ``Violation`` denies a claim; a ``Flag``
sends it to review. ``run_rules`` returns one decision row per
claim: deny beats review beats approve (POL-4, POL-5).
"""

import logging
import re
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd

from expense_agent.models import (
    Claim,
    Decision,
    Finding,
    Flag,
    Violation,
)
from expense_agent.policy import Policy, cap_usage

logger = logging.getLogger(__name__)


type Rule[F] = Callable[[Claim, Policy], F | None]


CAP_POLICY_REFS: dict[str, str] = {
    "Lodging": "POL-2.2",
    "Meals": "POL-2.3",
    "Client Meals": "POL-2.4",
    "Conference": "POL-2.7",
    "Home Office": "POL-2.9",
    "Office Supplies": "POL-2.10",
}
CAP_UNITS: dict[str, str] = {"Lodging": "/night", "Client Meals": "/person"}
DUPLICATE_KEYS = ["employee_id", "expense_date", "merchant", "amount_cents"]
SPLIT_KEYS = ["employee_id", "expense_date", "merchant", "category"]
PURCHASE_CAP_KEYS = ("per_purchase_cap", "per_event_cap")
RESULT_COLUMNS = [
    "claim_id",
    "rule_decision",
    "violations",
    "flags",
    "policy_refs",
    "details",
]


def apply_rules[F](
    claims: list[Claim], rules: list[Rule[F]], policy: Policy
) -> list[F]:
    """Run every rule on every claim; keep all findings returned."""
    return [
        finding
        for claim in claims
        for rule in rules
        if (finding := rule(claim, policy)) is not None
    ]


# --- Single-claim deny rules (POL-1, POL-2) -----------------------------


def check_late(claim: Claim, policy: Policy) -> Violation | None:
    """Deny claims submitted more than N days after expense (POL-1.2)."""
    max_days = policy["submission"]["max_days_after_expense"]
    days = (claim.submitted_date - claim.expense_date).days
    if days <= max_days:
        return None
    return Violation(
        claim_id=claim.claim_id,
        code="late_submission",
        policy_ref="POL-1.2",
        detail=f"submitted {days} days after expense (limit {max_days})",
    )


def check_receipt(claim: Claim, policy: Policy) -> Violation | None:
    """Deny items over the receipt threshold with no receipt (POL-1.3)."""
    if claim.category == "Mileage":
        return None  # mileage is miles x rate; there is no receipt
    threshold = policy["submission"]["receipt_required_over"]
    if claim.amount <= threshold or claim.receipt_attached:
        return None
    return Violation(
        claim_id=claim.claim_id,
        code="missing_receipt",
        policy_ref="POL-1.3",
        detail=f"${claim.amount:,.2f} over ${threshold:,.2f} no receipt",
    )


def check_cap(claim: Claim, policy: Policy) -> Violation | None:
    """Deny amounts over their category cap (POL-2.x by category)."""
    if claim.category not in policy["categories"]:
        return None  # not a policy category; prohibited rules own it
    usage = cap_usage(claim.model_dump(), policy)
    if usage is None:
        return None  # uncapped category, or no nights/attendees
    value, cap = usage
    if round(value, 2) <= cap:
        return None
    unit = CAP_UNITS.get(claim.category, "")
    return Violation(
        claim_id=claim.claim_id,
        code="over_cap",
        policy_ref=CAP_POLICY_REFS[claim.category],
        detail=(
            f"{claim.category} ${value:,.2f}{unit} over cap ${cap:,.2f}{unit}"
        ),
    )


def check_fare_class(claim: Claim, policy: Policy) -> Violation | None:
    """Deny premium airfare outside policy conditions (POL-2.1)."""
    if claim.category != "Airfare" or claim.fare_class is None:
        return None
    rules = policy["categories"]["Airfare"]
    if claim.fare_class in rules["allowed_fare_classes"]:
        return None
    min_hours = rules["business_class_min_flight_hours"]
    long_enough = (
        claim.flight_hours is not None and claim.flight_hours >= min_hours
    )
    if claim.fare_class == "Business" and long_enough and claim.preapproved:
        return None
    return Violation(
        claim_id=claim.claim_id,
        code="premium_class",
        policy_ref="POL-2.1",
        detail=(
            f"{claim.fare_class} on {claim.flight_hours}h flight, "
            f"preapproved={claim.preapproved} "
            f"(needs Business, >= {min_hours}h, preapproved)"
        ),
    )


def check_rental_class(claim: Claim, policy: Policy) -> Violation | None:
    """Deny rental cars above the allowed classes (POL-2.5)."""
    if claim.category != "Ground Transport" or claim.rental_class is None:
        return None
    allowed = policy["categories"]["Ground Transport"][
        "allowed_rental_classes"
    ]
    if claim.rental_class in allowed:
        return None
    return Violation(
        claim_id=claim.claim_id,
        code="premium_class",
        policy_ref="POL-2.5",
        detail=f"rental class {claim.rental_class} not in {allowed}",
    )


def mileage_rate(expense_date: date, policy: Policy) -> float:
    """Return the IRS mileage rate in force on a date (POL-2.6).

    Raises:
        ValueError: If no configured rate band covers the date.
    """
    for band in policy["categories"]["Mileage"]["rates"]:
        start = date.fromisoformat(str(band["from"]))
        end = date.fromisoformat(str(band["to"]))
        if start <= expense_date <= end:
            return band["rate"]
    raise ValueError(f"No mileage rate configured for {expense_date}")


def check_mileage(claim: Claim, policy: Policy) -> Violation | None:
    """Deny mileage above miles x the dated rate (POL-2.6)."""
    if claim.category != "Mileage" or claim.miles is None:
        return None
    rate = mileage_rate(claim.expense_date, policy)
    allowed = round(claim.miles * rate, 2)
    if round(claim.amount, 2) <= allowed:
        return None
    return Violation(
        claim_id=claim.claim_id,
        code="over_cap",
        policy_ref="POL-2.6",
        detail=(
            f"${claim.amount:,.2f} > {claim.miles} mi x ${rate}/mi "
            f"= ${allowed:,.2f}"
        ),
    )


# --- Review flags (POL-2.8, POL-3) ----------------------------------------


def compile_prohibited(
    policy: Policy,
) -> list[tuple[dict[str, Any], re.Pattern[str]]]:
    """Build one case-insensitive, whole-word regex per POL-3 item."""
    compiled = []
    for item in policy["prohibited"]:
        words = "|".join(re.escape(word) for word in item["keywords"])
        pattern = re.compile(rf"\b(?:{words})s?\b", re.IGNORECASE)
        compiled.append((item, pattern))
    return compiled


def check_prohibited_hint(claim: Claim, policy: Policy) -> Flag | None:
    """Hint at a possible POL-3 item from merchant/description text."""
    text = f"{claim.merchant} {claim.description}"
    for item, pattern in compile_prohibited(policy):
        alcohol = item["code"] == "ALCOHOL_NO_CLIENT"
        if alcohol and claim.category == "Client Meals":
            continue
        if match := pattern.search(text):
            return Flag(
                claim_id=claim.claim_id,
                code="prohibited_hint",
                policy_ref=item["policy_ref"],
                detail=f"{item['code']}: matched {match.group(0)!r}",
            )
    return None


def check_software_vendor(claim: Claim, policy: Policy) -> Flag | None:
    """Flag software from a vendor that needs IT approval (POL-2.8)."""
    if claim.category != "Software":
        return None
    approved = policy["categories"]["Software"]["approved_vendors"]
    if claim.merchant in approved:
        return None
    return Flag(
        claim_id=claim.claim_id,
        code="unapproved_vendor",
        policy_ref="POL-2.8",
        detail=f"vendor {claim.merchant!r} needs IT approval",
    )


# --- Escalation flags (POL-5)---------------------------------------


def check_high_value(claim: Claim, policy: Policy) -> Flag | None:
    """Flag a single item over the high-value threshold (POL-5.1)."""
    threshold = policy["escalation"]["high_value_threshold"]
    if claim.amount <= threshold:
        return None
    return Flag(
        claim_id=claim.claim_id,
        code="high_value",
        policy_ref="POL-5.1",
        detail=f"${claim.amount:,.2f} over ${threshold:,.2f}",
    )


def check_near_cap(claim: Claim, policy: Policy) -> Flag | None:
    """Flag amounts within the near-cap band below a cap (POL-5.2)."""
    if claim.category not in policy["categories"]:
        return None  # same guard as check_cap: cap_usage raises KeyError
    usage = cap_usage(claim.model_dump(), policy)
    if usage is None:
        return None  # uncapped category, or no nights/attendees
    value, cap = usage
    value = round(value, 2)
    pct = policy["escalation"]["near_cap_pct"]
    lower = round(cap * (1 - pct), 2)
    if not lower <= value <= cap:
        return None  # under the band, or over cap (check_cap owns it)
    unit = CAP_UNITS.get(claim.category, "")
    return Flag(
        claim_id=claim.claim_id,
        code="near_cap",
        policy_ref="POL-5.2",
        detail=(
            f"{claim.category} ${value:,.2f}{unit} is "
            f"{value / cap:.0%} of cap ${cap:,.2f}{unit}"
        ),
    )


def check_missing_purpose(claim: Claim, policy: Policy) -> Flag | None:
    """Flag a claim with no business purpose (POL-5.3).

    Claim's validator already turns "" and whitespace into None, so
    None is the only case to check. ``policy`` is unused but kept so
    every rule has the same signature. A vague purpose needs
    judgement and is the agent's job (notebook 05).
    """
    if claim.business_purpose is not None:
        return None
    return Flag(
        claim_id=claim.claim_id,
        code="missing_purpose",
        policy_ref="POL-5.3",
        detail="no business purpose given",
    )


# --- Cross-claim deny rules (POL-1.4, POL-1.5)-------------------------------


def claims_frame(claims: list[Claim]) -> pd.DataFrame:
    """Return claims as a DataFrame, earliest submission first."""
    df = pd.DataFrame([claim.model_dump() for claim in claims])
    df["position"] = range(len(df))  # file order breaks same-day ties
    df["amount_cents"] = (df["amount"] * 100).round().astype(int)
    return df.sort_values(["submitted_date", "position"], kind="stable")


def check_duplicates(claims: list[Claim]) -> list[Violation]:
    """Deny repeats of an earlier claim; the first stands (POL-1.4)."""
    if len(claims) < 2:
        return []  # a duplicate needs two claims
    df = claims_frame(claims)
    df["original_id"] = df.groupby(DUPLICATE_KEYS)["claim_id"].transform(
        "first"
    )
    repeats = df[df.duplicated(DUPLICATE_KEYS, keep="first")]
    return [
        Violation(
            claim_id=row.claim_id,
            code="duplicate",
            policy_ref="POL-1.4",
            detail=f"same employee/date/merchant/amount as {row.original_id}",
        )
        for row in repeats.itertuples()
    ]


def purchase_caps(policy: Policy) -> dict[str, float]:
    """Map each category that has a single-purchase cap to the cap."""
    return {
        category: rules[key]
        for category, rules in policy["categories"].items()
        for key in PURCHASE_CAP_KEYS
        if key in rules
    }


def check_splits(
    claims: list[Claim], policy: Policy, skip_ids: set[str]
) -> list[Violation]:
    """Deny every part of a purchase split to dodge a cap (POL-1.5)."""
    if len(claims) < 2:
        return []  # a split needs at least two parts
    caps = purchase_caps(policy)
    df = claims_frame(claims)
    df = df[df["category"].isin(caps) & ~df["claim_id"].isin(skip_ids)]
    violations = []
    for _, group in df.groupby(SPLIT_KEYS):
        if len(group) < 2:
            continue
        cap = caps[group["category"].iloc[0]]
        total = group["amount"].sum()
        if total <= cap or (group["amount"] > cap).any():
            continue  # no dodge: fits the cap, or a part is over_cap
        part_ids = list(group["claim_id"])
        violations.extend(
            Violation(
                claim_id=claim_id,
                code="split_transaction",
                policy_ref="POL-1.5",
                detail=(
                    f"split with "
                    f"{', '.join(p for p in part_ids if p != claim_id)}: "
                    f"total ${total:,.2f} over cap ${cap:,.2f}"
                ),
            )
            for claim_id in part_ids
        )
    return violations


# --- Rules list and pipeline (POL-4, POL-5) -------------------------------
SINGLE_CLAIM_RULES: list[Rule[Violation]] = [
    check_late,
    check_receipt,
    check_cap,
    check_fare_class,
    check_rental_class,
    check_mileage,
]
FLAG_RULES: list[Rule[Flag]] = [check_prohibited_hint, check_software_vendor]
ESCALATION_RULES: list[Rule[Flag]] = [
    check_high_value,
    check_near_cap,
    check_missing_purpose,
]


def collect_findings(
    claims: list[Claim], policy: Policy
) -> tuple[list[Violation], list[Flag]]:
    """Run every rule group; return violations and flags separately."""
    violations = apply_rules(claims, SINGLE_CLAIM_RULES, policy)
    duplicates = check_duplicates(claims)
    duplicate_ids = {v.claim_id for v in duplicates}
    violations += duplicates
    violations += check_splits(claims, policy, skip_ids=duplicate_ids)
    flags = apply_rules(claims, FLAG_RULES + ESCALATION_RULES, policy)
    return violations, flags


def rule_decision(
    violation_codes: list[str], flag_codes: list[str]
) -> Decision:
    """Deny beats review beats approve (POL-4, POL-5)."""
    if violation_codes:
        return "deny"
    if flag_codes:
        return "review"
    return "approve"


def run_rules(claims: list[Claim], policy: Policy) -> pd.DataFrame:
    """Return one row per claim: rule decision plus every finding."""
    violations, flags = collect_findings(claims, policy)
    logger.info(
        "run_rules: %d claims, %d violations, %d flags",
        len(claims),
        len(violations),
        len(flags),
    )
    by_claim: dict[str, list[Finding]] = defaultdict(list)
    for finding in [*violations, *flags]:
        by_claim[finding.claim_id].append(finding)

    rows = []
    for claim in claims:
        findings = by_claim[claim.claim_id]
        violation_codes = [
            f.code for f in findings if isinstance(f, Violation)
        ]
        flag_codes = [f.code for f in findings if isinstance(f, Flag)]
        rows.append(
            {
                "claim_id": claim.claim_id,
                "rule_decision": rule_decision(violation_codes, flag_codes),
                "violations": violation_codes,
                "flags": flag_codes,
                "policy_refs": sorted({f.policy_ref for f in findings}),
                "details": [f.detail for f in findings],
            }
        )
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)
