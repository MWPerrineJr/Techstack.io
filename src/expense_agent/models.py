"""Typed contracts shared by the rules, the agent and the app.

``Claim`` is the validated input. ``Violation`` (deny) and ``Flag``
(review) are the two kinds of rule finding; both cite a POL-x.y
section so every decision can be audited back to the policy.
"""

from datetime import date
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


ViolationCode = Literal[
    "over_cap",
    "prohibited_category",
    "missing_receipt",
    "late_submission",
    "duplicate",
    "split_transaction",
    "personal_extension",
    "premium_class",
]
FlagCode = Literal[
    "prohibited_hint",
    "unapproved_vendor",
    "high_value",
    "near_cap",
    "missing_purpose",
]
Decision = Literal["approve", "deny", "review"]

POLICY_REF_PATTERN = r"POL-\d+\. \d+$"



class Claim(BaseModel):
    """One submitted expense line item. Carries no labels."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    report_id: str
    claim_id: str
    employee_id: str
    department: str
    submitted_date: date
    expense_date: date
    category: str
    merchant: str
    description: str
    business_purpose: str |None = None
    amount: float = Field(gt=0)
    city: str |None = None
    nights: int | None = Field(default=None, ge=0)
    attendees: int | None = Field(default=None, ge=0)
    fare_class: str | None = None
    flight_hours: float | None = None
    rental_class: str | None = None
    miles: int | None = Field(default=None, ge=0)
    preapproved: bool | None = None
    receipt_attached: bool

    @field_validator("*", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        """Turn pandas NaN/<NA> and blank strings into None."""
        if isinstance(value, str):
            return value.strip() or None
        if value is not None and pd.isna(value):
            return None
        return value


class Finding(BaseModel):
    """Fields every rule finding shares: which claim,rule and why."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str
    policy_ref: str = Field(pattern=POLICY_REF_PATTERN)
    detail: str = Field(min_length=1)


class Violation(Finding):
    """A broken rule: the claim is denied (POL-4)."""

    code: ViolationCode


class Flag(Finding):
    """A reason for closer review (POL-5), not a denial."""

    code: FlagCode


def to_claims(df: pd.DataFrame) -> list[Claim]:
    """Validate every row into a Claim; fail loudly on a bad row."""
    return [Claim.model_validate(row) for row in df.to_dict("records")]


            
