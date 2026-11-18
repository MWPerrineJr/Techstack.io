"""Load the expense policy and answer simple questions about it."""

from pathlib import Path
from typing import Any

import yaml

Policy = dict[str, Any]


def load_policy(path: Path) -> Policy:
    """Load the expense policy from a YAML file.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def city_tier(city: str, policy: Policy) -> str:
    """Return the lodging cap tier for a city (POL-2.2)."""
    high_cost = set(policy["city_tiers"]["high_cost"])
    return "high_cost" if city in high_cost else "standard"


def cap_usage(claim: dict[str, Any], policy: Policy) -> float:
    """Return (value, cap) for a capped category, else None.

    ``value`` is what the cap applies to: the nightly rate for
    Lodging, the per-person amount for Client Meals, and the full
    amount fir every other capped category.


    Raises:
        KeyError: If the category is not in the policy.
    """
    rules = policy["categories"][claim["category"]]
    amount = claim["amount"]
    match claim["category"]:
        case "Lodging":
            tier = city_tier(claim["city"], policy)
            return amount / claim["nights"], rules["nightly_cap"][tier]
        case "Meals":
            return amount, rules["daily_per_diem"]
        case "Client Meals":
            return amount / claim["attendees"], rules["per_person_cap"]
        case "Conference":
            return amount, rules["per_event_cap"]
        case "Home Office" | "Office Supplies":
            return amount, rules["per_purchase_cap"]
    return None
