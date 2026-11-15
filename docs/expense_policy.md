# Techstack.io Travel & Expense Policy

**Version:** 1.0  **Effective:** January 1, 2026  **Owner:** Finance (CFO)
Numeric limits in this document mirror `config/policy.yaml`. If the two ever disagree, the YAML file is authoritative and this document must be updated.

---

## POL-1 General Rules

**POL-1.1 Business purpose.** Every expense must have a specific business purpose: who, what, and why (e.g., "Dinner with Acme Corp CTO to discuss Q3 renewal"). Vague purposes such as "business," "meeting," or "misc" are sent to a human reviewer.

**POL-1.2 Timely submission.** Expenses must be submitted within **60 days** of the expense date. Later submissions are denied.

**POL-1.3 Receipts.** An itemized receipt is required for any expense over **$75.00**. Items over $75 without a receipt are denied.

**POL-1.4 No duplicates.** An expense may be claimed only once. Claims matching an earlier claim (same employee, date, merchant, and amount) are denied.

**POL-1.5 No splitting.** A single purchase may not be split across multiple claims to stay under a limit. Split claims are denied.

## POL-2 Allowable Expenses and Limits

| Ref | Category | Rule |
|---|---|---|
| POL-2.1 | **Airfare** | Economy or premium economy. Business class only for flights of **6+ hours** *and* with written pre-approval. First class is never reimbursed. |
| POL-2.2 | **Lodging** | Up to **$250/night** in standard cities and **$350/night** in high-cost cities (New York, San Francisco, Boston, Seattle, Washington DC, Los Angeles). Only nights required for business. |
| POL-2.3 | **Meals (travel)** | Traveler's own meals: up to **$75/day** while traveling overnight. |
| POL-2.4 | **Client Meals** | Up to **$100 per person**. Must list attendees, company, and business purpose. Alcohol is allowed only as part of a client meal. |
| POL-2.5 | **Ground Transport** | Rideshare, taxi, transit, parking, tolls. Rental cars: economy, compact, or mid-size. |
| POL-2.6 | **Mileage** | Personal vehicle reimbursed at the IRS business rate: **$0.725/mile** (Jan 1–Jun 30, 2026) and **$0.76/mile** (from Jul 1, 2026). |
| POL-2.7 | **Conferences & Training** | Up to **$2,000 per event**, with manager pre-approval. |
| POL-2.8 | **Software** | Approved vendors only: GitHub, JetBrains, Figma, Notion, Zoom, Atlassian, Slack, OpenAI, Anthropic. Others need IT approval. |
| POL-2.9 | **Home Office** | Equipment up to **$500 per purchase**. |
| POL-2.10 | **Office Supplies** | Up to **$150 per purchase**. |

## POL-3 Prohibited Expenses (always denied)

- POL-3.1 Alcohol that is not part of a client entertainment meal
- POL-3.2 Personal items, including electronics for personal use
- POL-3.3 Gift cards or cash equivalents
- POL-3.4 Traffic, parking, or other fines and penalties
- POL-3.5 Travel costs for spouses, family members, or guests
- POL-3.6 Spa, gym, in-room movies, or other personal entertainment
- POL-3.7 Personal or weekend extensions of a business trip (lodging, meals, transport for non-business days)

## POL-4 Decisions

Every expense line receives one of three decisions:

- **Approve:** within policy, with a clear business purpose.
- **Deny:** violates POL-1 or POL-3, or exceeds a POL-2 limit. The denial must cite the policy section.
- **Review:** routed to a human (see POL-5).

## POL-5 Human Review (Escalation)

An expense goes to a human reviewer if **any** of these apply:

- POL-5.1 A single item is over **$1,000**.
- POL-5.2 The amount is within **10% below** a category cap.
- POL-5.3 The business purpose is vague or missing.
- POL-5.4 The merchant does not match the stated category.
- POL-5.5 The AI reviewer's confidence is below **0.75**.
- POL-5.6 The primary AI reviewer and the verifier model disagree.
- POL-5.7 Anomaly detection flags the claim as unusual for that employee.

**Approval tiers:**
- Tier 1: the employee's manager.
- Tier 2: Finance, for items over $1,000, or when a manager approves against the AI recommendation.

## POL-6 Audit

All decisions, including AI rationale, model versions, and human overrides, are logged and retained for audit.
