# Techstack.io Expense Reporter & Approval Tool — Session Log

Project folder (local): `~/Techstack.io`
Owner: Michael Perrine

---

## Session 1 — 2026-11-13

### Status
- Planning complete. All decisions made (see below).
- Project folder created (empty).
- **Not started yet.** Next action: Step 0 (project setup), then Step 1 (data generation + policy files).

### Project goal
An enterprise expense reporter and approval tool for the sample business **Techstack.io**:
- Synthetic expense data: 10 employees × 10 reports = 100 reports, 1–5 line items each (~300 claims)
- A standard expense policy (approved / denied / escalate)
- 25% of claims randomly out of policy (fixed seed; ground-truth labels kept)
- Built and tested in notebooks first, then shipped as an app that imports and processes expense reports
- Agentic AI review with human-in-the-loop (HITL) for questionable claims

### Decisions
| Topic | Decision |
|---|---|
| Language / harness | Python, LangChain + LangGraph |
| Primary reviewer model | OpenAI |
| Checker / verifier model | Anthropic. Re-checks every automatic approve/deny; a disagreement routes the claim to a human |
| Typed review | Jev (TypeSafe AI). Typed classification questions per claim, plus eval scoring; `jevals` library for gates. Project-specific API key to be created |
| Observability | Langfuse Cloud to start; self-hosted Langfuse in Docker later as a learning exercise |
| Data granularity | Line-item level; 25% of claims out of policy |
| Import formats | CSV, Excel, JSON (all three) |
| Additions | All of A–F approved (see below) |
| Learning mode | Michael writes all notebook code himself with detailed, cell-by-cell guidance. The app is built after the notebooks are complete |
| Working protocol | Human approval before any file is created or changed. For now, Michael saves files manually |

### Approved additions (A–F)
- **A. Synthetic receipts + OCR.** Generate receipt PDFs/images (some deliberately mismatched); a vision model extracts fields; a rule compares them to the claim.
- **B. Anomaly detection.** IsolationForest on per-employee spend features; the anomaly score feeds routing.
- **C. MLflow.** Track prompt versions, models, thresholds and eval metrics across runs.
- **D. Two-tier approval.** Manager review first, then Finance for items over $1,000 or manager overrides of the AI.
- **E. Docker.** Containerize the app (docker-compose); later, self-host Langfuse.
- **F. Notification drafts.** Agent drafts denial/return explanations citing policy. Stored only, never sent.

### Architecture
```
Upload (CSV / XLSX / JSON)
  → Ingest & validate (Pydantic)
  → Receipt OCR + match check (A)
  → Rules engine (hard policy checks → violation codes)
  → Anomaly score (B)
  → Jev typed checks (purpose specific? business vs personal? merchant matches category?)
  → OpenAI primary reviewer (decision, rationale, confidence, policy citation)
  → Anthropic checker (verifies auto decisions)
  → Router
       ├─ clean + confident + checker agrees → AUTO-APPROVE
       ├─ clear violation + checker agrees   → AUTO-DENY
       └─ ambiguous / low confidence / disagreement / >$1,000 → HUMAN REVIEW
             → Manager → Finance (D)
  → Notification draft (F)
  → Final decision + audit log (Langfuse traces, SQLite)
```
Principle: deterministic rules first (cheap, auditable); LLMs only for judgment calls.

### Synthetic data spec
- 10 employees across Engineering, Sales, Marketing, Finance, Ops (role, cost center, manager, home city)
- 10 reports each over a 6-month window; spending patterns vary by role
- 25% of claims out of policy, weighted across these violation types:
  over cap, prohibited category, missing receipt, late submission (>60 days), duplicate,
  split transaction, personal/weekend extension, unapproved premium class
- About 5% deliberately borderline claims to exercise HITL
- Hidden labels: `expected_decision`, `violation_type`

### Draft policy v1 (not yet saved as files)
**Approved (within limits)**
- Airfare: economy; business class only on flights over 6 hours, with pre-approval
- Lodging: $250/night standard, $350/night high-cost cities
- Meals: $75/day per diem when traveling; client meals $100/person with attendees and purpose
- Ground transport: rideshare, taxi, economy/mid-size rental, parking, tolls; mileage at current IRS rate (config value)
- Conferences/training: up to $2,000 per event, with pre-approval
- Software: pre-approved vendor list only
- Home office: $500/year

**Denied**
- Alcohol (unless part of client entertainment)
- Personal items, gift cards
- Fines
- Family travel
- Spa, gym, in-room entertainment
- Duplicates
- Submitted more than 60 days late
- Over $75 without a receipt

**Escalate to human**
- Single item over $1,000
- Within 10% of a cap
- Agent confidence < 0.75
- Vague purpose
- Merchant/category mismatch
- Primary and checker models disagree

Policy will be stored as `docs/expense_policy.md` (for agents to cite) and `config/policy.yaml` (for the rules engine).

### Build sequence
| # | Notebook | Covers |
|---|---|---|
| 00 | `00_setup.ipynb` | Environment, keys, Langfuse + model smoke test |
| 01 | `01_generate_data.ipynb` | Employees, reports, claims, labels |
| 02 | `02_generate_receipts.ipynb` | A: receipt PDFs/images |
| 03 | `03_policy_rules.ipynb` | YAML policy + rules engine |
| 04 | `04_anomaly_model.ipynb` | B: IsolationForest; C: MLflow |
| 05 | `05_agent_graph.ipynb` | LangGraph, Jev → OpenAI → Anthropic, HITL two-tier (D), notifications (F), Langfuse |
| 06 | `06_evaluation.ipynb` | Confusion matrix, false-approval rate, HITL rate, cost/latency; Langfuse datasets + MLflow |
| — | App | Streamlit: import, reviewer queues (manager/finance), dashboard, audit log |
| — | Docker (E) | Containerize app; then self-hosted Langfuse |

Key metric: **false approvals** (money leaking out), not plain accuracy.

---

## Step 0 — Project setup (to run)

### 1. Initialize
```bash
cd ~/Techstack.io
uv init --python 3.12 --name techstack-expense
mkdir -p notebooks data/raw data/receipts config docs src/expense_agent tests
```

### 2. Dependencies
```bash
# Core harness + models
uv add langchain langgraph langchain-openai langchain-anthropic
# Observability + typed review
uv add langfuse jevals
# Data + config
uv add pandas numpy faker pydantic pyyaml python-dotenv openpyxl
# Receipts (A) + ML (B, C)
uv add reportlab pillow scikit-learn mlflow
# App
uv add streamlit
# Notebook + testing (dev-only)
uv add --dev ipykernel ipytest pytest
```

### 3. `.env` (project root; never commit)
Template saved separately as `env.example`. Copy it to `.env` and fill in the values.
Langfuse US region host: `https://us.cloud.langfuse.com`. Confirm the correct host in your Langfuse project settings.

### 4. `.gitignore`
Template saved separately as `gitignore.txt`. Rename it to `.gitignore`.

### 5. `notebooks/00_setup.ipynb`. Select the `.venv` kernel, then run:

```python
# Cell 1 — load secrets and confirm nothing is missing
import os
from dotenv import load_dotenv

load_dotenv("../.env")

required = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY",
            "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "OPENAI_MODEL", "ANTHROPIC_MODEL"]
missing = [k for k in required if not os.getenv(k)]
print("Missing:", missing or "none ✅")
```

```python
# Cell 2 — Langfuse auth check
from langfuse import get_client

langfuse = get_client()
print("Langfuse auth:", langfuse.auth_check())
```

```python
# Cell 3 — call both models through LangChain, traced in Langfuse
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langfuse.langchain import CallbackHandler

handler = CallbackHandler()
primary = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0)
checker = ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL"), temperature=0)

for name, llm in [("primary", primary), ("checker", checker)]:
    reply = llm.invoke("Reply with exactly: OK", config={"callbacks": [handler]})
    print(name, "→", reply.content)

langfuse.flush()
```

**Done when:**
- No keys are missing
- Langfuse auth prints `True`
- Both models reply `OK`
- Two traces appear in Langfuse

The Jev connection is tested at the start of notebook 05.

---

## Policy + reference dataset (delivered 2026-11-13, saved manually)

| File | Save to | Purpose |
|---|---|---|
| `expense_policy.md` | `docs/` | Readable policy v1.0 with section IDs (POL-1.x …) that agents cite |
| `policy.yaml` | `config/` | Machine-readable limits; the single source of truth for numbers |
| `employees.csv` | `data/raw/` | 10 employees: title, department, home city, manager |
| `expense_reports.csv` / `.xlsx` / `.json` | `data/raw/` | Import files, **no labels**. CSV/XLSX are flat (one row per claim); JSON is nested reports → line_items |
| `ground_truth_labels.csv` | `data/raw/` | Answer key; join on `claim_id`. Never shown to the agent |

**Policy changes vs. the first draft:**
- Mileage now uses the actual 2026 IRS business rates: $0.725/mile Jan 1–Jun 30 and $0.76/mile from Jul 1 (a mid-year IRS revision). The rate depends on the expense date, which is a good test for the rules engine.
- Office supplies capped at $150 per purchase.
- Home office cap is $500 per purchase (no annual cap).
- Prohibited items have codes (ALCOHOL_NO_CLIENT, PERSONAL_ITEM, …).

**Dataset stats (seed 42):**
- 100 reports (10 per employee), **328 claims**
- **82 out of policy = 25.0%**
- Expected decisions: 228 approve / 82 deny / 18 review

| Violation type | Count |
|---|---|
| over_cap | 20 |
| prohibited_category | 20 |
| late_submission | 12 |
| missing_receipt | 12 |
| duplicate | 6 |
| personal_extension | 5 |
| premium_class | 5 |
| split_transaction | 2 |

- Review reasons: vague_purpose 12, near_cap 4 (16 borderline = 5%), high_value 2.
- Clean claims are generated below 90% of every cap, so they never trigger the near-cap rule by accident.

**Validation results:**
- 0 in-policy claims break a hard rule.
- All 6 duplicates are detectable by (employee, date, merchant, amount). A duplicate always copies an *earlier* line.
- Simple hard rules catch **51 of 82** violations. The other 31 need judgment: prohibited items hidden in descriptions (18), duplicates (6, need a cross-claim check), personal extensions (5), split purchases (2). **That gap is exactly why the agent exists.** Track it in notebook 06.

**Data dictionary (import files):**
- `report_id`, `claim_id` (`R-E001-01-L2` = employee E001, report 01, line 2), `line_no`
- `employee_id`, `employee_name`, `department`, `manager_id`, `report_title`, `submitted_date` (report-level)
- `expense_date`, `category`, `merchant`, `description`, `business_purpose`, `amount`, `currency`, `city`
- `nights` (lodging), `attendees` + `attendee_names` (client meals), `fare_class` + `flight_hours` (airfare), `rental_class`, `miles`
- `preapproved`, `receipt_attached` (booleans)

**Labels:** `in_policy`, `violation_type`, `expected_decision` (approve/deny/review), `review_reason`, `is_borderline`, `label_note` (human-readable explanation)

## Open items / next session
- [ ] Save the policy + data files into the project folders listed above
- [ ] Create project-specific TypeSafe (Jev) API key
- [ ] Run Step 0 and record any errors here
- [ ] Reply "go ahead" to begin `01_generate_data.ipynb`: Michael rebuilds the generator cell by cell and compares the output to this reference dataset (same 25% rate, label schema and validation checks)

## Session notes
_Add notes, errors and decisions from each working session below._

### Session 2 — 2026-11-14 — Step 0 complete
**Done**
- Project initialized with uv; pinned Python 3.12.12 (`.python-version` 3.12, `requires-python >=3.12`), name `techstack-expense`
- Policy + data files moved to `docs/`, `config/`, `data/raw/`
- Dependencies added; dev tools (ipykernel, ipytest, pytest, ruff, nbqa) in `dev` group only
- `.gitignore` merged (adds .env, .ipynb_checkpoints/, mlruns/, mlflow.db, data/receipts/, .DS_Store); `.env` verified untracked
- `notebooks/00_setup.ipynb` passes: keys present, Langfuse auth True, both models reply OK, 2 traces visible; `ruff check` + `ruff format` clean

**Errors and fixes**
- `uv init` had defaulted to Python 3.13 → edited `requires-python` first, then `uv python pin 3.12`, rebuilt `.venv`
- Langfuse 401 → SDK v5 uses `LANGFUSE_BASE_URL` (not `LANGFUSE_HOST`); account is EU (`https://cloud.langfuse.com`); fixed by generating a new key pair. `.env` edits need a kernel restart.
- `nbqa ruff format` fails (nbqa reads `format` as a path) → use ruff directly: `uv run ruff check notebooks` and `uv run ruff format --diff notebooks`

**Decisions**
- Models: primary `gpt-6-luna`, checker `claude-sonnet-5-5`
- GPT-6 Luna rejects temperature=0 (uses 1); Sonnet 5.5 has no temperature parameter → measure run-to-run consistency in notebook 06; rely on structured output in 05
- Run all `uv` commands in Mac Terminal only (a Linux shell would break `.venv`)

**Open items**
- [x] ruff check + ruff format clean
- [ ] Rename `LANGFUSE_HOST` → `LANGFUSE_BASE_URL` in `env.example`
- [ ] Optional: `uv remove --dev nbqa` (ruff handles notebooks natively)
- [ ] Decide on leftover `gitignore.txt`, `sessions_2.md`, `main.py`
- [ ] Next: `01_generate_data.ipynb`, cell 1 (imports, constants, seeded RNG, load policy.yaml)

### Session 2 (cont.) — 2026-11-14 — Notebook 01 started
**Done**
- `notebooks/01_generate_data.ipynb` created; title + purpose markdown cells
- Cell 1 complete: imports, constants (SEED, OUT_OF_POLICY_RATE, BORDERLINE_RATE, WINDOW_START/END, TODAY), `rng = random.Random(SEED)`, `load_policy()` with type hints + docstring + FileNotFoundError, `POLICY`, `CATEGORIES`, `HIGH_COST_CITIES` (set). Asserts pass.
- ruff check: only expected F401 (`timedelta`, `pd` — used in cells 2–3)

**Learned**
- Lambda assigned to a name violates PEP 8 (E731) → use `def`
- One seeded `random.Random` instance, never the global `random.seed`
- Fixed `TODAY` in the generator keeps data, labels and metrics reproducible; the live app uses an injected `as_of` date (default `date.today()`) and logs it with each decision for audit. Policy rules use dates stored on the claim, so they don't depend on today.
- Workflow: `ruff check` + `ruff format --diff`, fix, repeat until clean

**Open items**
- [ ] Cell 1: delete the blank first line (last `ruff format --diff` item)
- [ ] Next: cell 2 — load `data/raw/employees.csv` (`dtype=str`), `TRAVEL_PROB` dict, asserts: 10 rows, unique `employee_id`, all departments in `TRAVEL_PROB`, every `manager_id` exists or is `BOARD`

---

# Appendix — Full file contents
Every file created in Session 1, so this document can rebuild the project on its own.

### .env template
Fill in your keys. Never commit this file.
Save as: `.env`

````bash
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
TYPESAFE_API_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
OPENAI_MODEL=
ANTHROPIC_MODEL=
````

### .gitignore
Save as: `.gitignore`

````text
.env
.venv/
__pycache__/
.ipynb_checkpoints/
mlruns/
data/receipts/
````

### Expense policy (readable)
Save as: `docs/expense_policy.md`

````markdown
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
````

### Expense policy (config)
Save as: `config/policy.yaml`

````yaml
# Techstack.io Expense Policy — machine-readable config (v1.0)
# Single source of truth for all numeric limits. docs/expense_policy.md describes the same rules in prose.
version: "1.0"
effective_date: "2026-01-01"
currency: USD

submission:
  max_days_after_expense: 60          # POL-1.2
  receipt_required_over: 75.00        # POL-1.3

escalation:                           # POL-5
  high_value_threshold: 1000.00       # single item above this -> human review
  near_cap_pct: 0.10                  # within 10% below a cap -> human review
  min_agent_confidence: 0.75          # below this -> human review
  finance_review_threshold: 1000.00   # tier-2 (Finance) after manager

city_tiers:
  high_cost: ["New York, NY", "San Francisco, CA", "Boston, MA", "Seattle, WA", "Washington, DC", "Los Angeles, CA"]
  # every other city is "standard"

categories:
  Airfare:                            # POL-2.1
    allowed_fare_classes: ["Economy", "Premium Economy"]
    business_class_min_flight_hours: 6
    business_class_requires_preapproval: true
  Lodging:                            # POL-2.2
    nightly_cap:
      standard: 250.00
      high_cost: 350.00
  Meals:                              # POL-2.3 (traveler's own meals, per day)
    daily_per_diem: 75.00
  Client Meals:                       # POL-2.4
    per_person_cap: 100.00
    requires_attendees: true
  Ground Transport:                   # POL-2.5
    allowed_rental_classes: ["Economy", "Compact", "Mid-size"]
  Mileage:                            # POL-2.6 (IRS business rate, date-dependent)
    rates:
      - {from: "2026-01-01", to: "2026-06-30", rate: 0.725}
      - {from: "2026-07-01", to: "2026-12-31", rate: 0.76}
  Conference:                         # POL-2.7
    per_event_cap: 2000.00
    requires_preapproval: true
  Software:                           # POL-2.8
    approved_vendors: ["GitHub", "JetBrains", "Figma", "Notion", "Zoom", "Atlassian", "Slack", "OpenAI", "Anthropic"]
  Home Office:                        # POL-2.9
    per_purchase_cap: 500.00
  Office Supplies:                    # POL-2.10
    per_purchase_cap: 150.00

prohibited:                           # POL-3
  - {code: ALCOHOL_NO_CLIENT, text: "Alcohol not part of a client entertainment meal"}
  - {code: PERSONAL_ITEM,     text: "Personal items, including electronics for personal use"}
  - {code: GIFT_CARD,         text: "Gift cards or cash equivalents"}
  - {code: FINE,              text: "Traffic, parking, or other fines and penalties"}
  - {code: FAMILY_TRAVEL,     text: "Travel costs for spouses, family, or guests"}
  - {code: WELLNESS_ENTERTAINMENT, text: "Spa, gym, in-room movies, personal entertainment"}

violation_codes:                      # labels used in ground truth + rules engine
  over_cap: "Amount exceeds the category limit"
  prohibited_category: "Expense type is prohibited (POL-3)"
  missing_receipt: "No receipt for an item over the receipt threshold"
  late_submission: "Submitted more than 60 days after the expense date"
  duplicate: "Same employee, date, merchant and amount already claimed"
  split_transaction: "Purchase split across claims to stay under a cap"
  personal_extension: "Personal / weekend extension of a business trip"
  premium_class: "Business/first class without meeting policy conditions"
````

### Employees
Save as: `data/raw/employees.csv`

````csv
employee_id,employee_name,title,department,home_city,manager_id
E001,Priya Raman,Director of Engineering,Engineering,"Austin, TX",E010
E002,Kevin Ortiz,Senior Software Engineer,Engineering,"Austin, TX",E001
E003,Lena Brooks,ML Engineer,Engineering,"Denver, CO",E001
E004,Dana Whitfield,VP of Sales,Sales,"Chicago, IL",E010
E005,Jamal Carter,Account Executive,Sales,"Dallas, TX",E004
E006,Sofia Nguyen,Account Executive,Sales,"San Francisco, CA",E004
E007,Ethan Kim,Marketing Manager,Marketing,"New York, NY",E010
E008,Rachel Adler,Content Strategist,Marketing,"Seattle, WA",E007
E009,Tom Becker,Operations Manager,Operations,"San Antonio, TX",E010
E010,Marcus Hale,Chief Financial Officer,Finance,"San Antonio, TX",BOARD
````

### Large data files (not embedded)
`expense_reports.csv`, `expense_reports.xlsx`, `expense_reports.json` and `ground_truth_labels.csv` are too large to paste here. Save them from the chat downloads into `data/raw/`. If they're lost, rerun the reference generator below; it reproduces them exactly (seed 42):
```bash
uv run python scripts/generate_reference_data.py
uv run python scripts/validate.py
```

## Answer key — try notebook 01 before reading this
This is the reference code that produced the dataset. Build your own generator in `01_generate_data.ipynb` first, then compare.

### Reference data generator
Save as: `scripts/generate_reference_data.py`

````python
"""Reference generator for Techstack.io synthetic expense data.

Produces the answer-key dataset Michael's notebook 01 will be checked against.
Seeded for reproducibility. Reads limits from config/policy.yaml.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
OUT_OF_POLICY_RATE = 0.25
BORDERLINE_RATE = 0.05
WINDOW_START, WINDOW_END = date(2026, 5, 1), date(2026, 10, 31)
TODAY = date(2026, 11, 12)

rng = random.Random(SEED)
policy = yaml.safe_load((ROOT / "config/policy.yaml").read_text())
CAT = policy["categories"]
HIGH_COST = set(policy["city_tiers"]["high_cost"])

# ---------------------------------------------------------------- employees
EMPLOYEES = [
    # id,   name,            title,                       dept,          home city,           manager
    ("E001", "Priya Raman",   "Director of Engineering",   "Engineering", "Austin, TX",        "E010"),
    ("E002", "Kevin Ortiz",   "Senior Software Engineer",  "Engineering", "Austin, TX",        "E001"),
    ("E003", "Lena Brooks",   "ML Engineer",               "Engineering", "Denver, CO",        "E001"),
    ("E004", "Dana Whitfield","VP of Sales",               "Sales",       "Chicago, IL",       "E010"),
    ("E005", "Jamal Carter",  "Account Executive",         "Sales",       "Dallas, TX",        "E004"),
    ("E006", "Sofia Nguyen",  "Account Executive",         "Sales",       "San Francisco, CA", "E004"),
    ("E007", "Ethan Kim",     "Marketing Manager",         "Marketing",   "New York, NY",      "E010"),
    ("E008", "Rachel Adler",  "Content Strategist",        "Marketing",   "Seattle, WA",       "E007"),
    ("E009", "Tom Becker",    "Operations Manager",        "Operations",  "San Antonio, TX",   "E010"),
    ("E010", "Marcus Hale",   "Chief Financial Officer",   "Finance",     "San Antonio, TX",   "BOARD"),
]
TRAVEL_PROB = {"Sales": 0.7, "Marketing": 0.5, "Engineering": 0.3, "Operations": 0.4, "Finance": 0.3}

CITIES = ["New York, NY", "San Francisco, CA", "Boston, MA", "Seattle, WA", "Washington, DC",
          "Los Angeles, CA", "Austin, TX", "Dallas, TX", "Chicago, IL", "Denver, CO",
          "Atlanta, GA", "Phoenix, AZ", "Nashville, TN", "San Antonio, TX"]
CLIENTS = ["Acme Corp", "Globex", "Initech", "Umbrella Health", "Stark Logistics", "Wayne Financial",
           "Hooli", "Vandelay Industries", "Soylent Foods", "Cyberdyne Systems"]
CLIENT_PEOPLE = ["Alex Morgan", "Jordan Lee", "Taylor Reed", "Casey Patel", "Riley Chen",
                 "Morgan Diaz", "Avery Shah", "Quinn Foster", "Drew Kowalski", "Jamie Ito"]
CONFERENCES = ["AWS re:Invent", "SaaStr Annual", "Data + AI Summit", "Dreamforce",
               "Content Marketing World", "PyData Global", "Gartner Data & Analytics Summit"]
MERCHANTS = {
    "Airfare": ["Delta Air Lines", "United Airlines", "American Airlines", "Southwest Airlines", "Alaska Airlines"],
    "Lodging": ["Marriott", "Hilton", "Hyatt", "Courtyard by Marriott", "Hampton Inn", "Westin"],
    "Meals": ["Starbucks", "Panera Bread", "Chipotle", "Hotel Restaurant", "Sweetgreen", "Local Diner"],
    "Client Meals": ["Capital Grille", "Ruth's Chris Steak House", "Fogo de Chao", "Eddie V's", "Nobu", "The Mercer Kitchen"],
    "Ground Transport": ["Uber", "Lyft", "Yellow Cab", "Enterprise Rent-A-Car", "Hertz", "Airport Parking"],
    "Conference": ["Conference Registration"],  # replaced by event name
    "Software": policy["categories"]["Software"]["approved_vendors"],
    "Home Office": ["Amazon", "Best Buy", "IKEA", "Staples", "Apple Store"],
    "Office Supplies": ["Staples", "Office Depot", "Amazon", "Target"],
}
HOME_OFFICE_ITEMS = ["External monitor", "Ergonomic chair", "Standing desk converter", "Docking station",
                     "Webcam and headset", "Keyboard and mouse"]
SUPPLY_ITEMS = ["Notebooks and pens", "Printer ink", "Whiteboard markers", "Shipping supplies", "Desk organizers"]


def money(x: float) -> float:
    return round(x, 2)


def rand_date(start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def tier(city: str) -> str:
    return "high_cost" if city in HIGH_COST else "standard"


def mileage_rate(d: date) -> float:
    for r in CAT["Mileage"]["rates"]:
        if date.fromisoformat(r["from"]) <= d <= date.fromisoformat(r["to"]):
            return r["rate"]
    raise ValueError(d)


def blank(category: str, d: date, city: str) -> dict:
    return dict(expense_date=d, category=category, merchant="", description="", business_purpose="",
                amount=0.0, city=city, nights=None, attendees=None, attendee_names="", fare_class="",
                flight_hours=None, rental_class="", miles=None, preapproved=False, receipt_attached=True)


# ------------------------------------------------- clean (in-policy) line items
# Clean amounts stay below 90% of any cap so they never look "near cap".
def clean_item(category: str, d: date, city: str, purpose: str, nights: int = 1) -> dict:
    c = blank(category, d, city)
    c["business_purpose"] = purpose
    if category == "Airfare":
        c.update(merchant=rng.choice(MERCHANTS["Airfare"]), fare_class="Economy",
                 flight_hours=round(rng.uniform(1.2, 4.8), 1), amount=money(rng.uniform(180, 650)),
                 description=f"Round-trip economy airfare to {city}")
    elif category == "Lodging":
        cap = CAT["Lodging"]["nightly_cap"][tier(city)]
        nightly = rng.uniform(0.55 * cap, 0.89 * cap)
        c.update(merchant=rng.choice(MERCHANTS["Lodging"]), nights=nights, amount=money(nightly * nights),
                 description=f"Hotel, {nights} night(s) at ${nightly:,.2f}/night")
    elif category == "Meals":
        c.update(merchant=rng.choice(MERCHANTS["Meals"]), amount=money(rng.uniform(18, 0.89 * CAT["Meals"]["daily_per_diem"])),
                 description="Traveler meals for the day")
    elif category == "Client Meals":
        n = rng.randint(2, 5)
        client = rng.choice(CLIENTS)
        names = rng.sample(CLIENT_PEOPLE, n - 1)
        pp = rng.uniform(35, 0.89 * CAT["Client Meals"]["per_person_cap"])
        c.update(merchant=rng.choice(MERCHANTS["Client Meals"]), attendees=n,
                 attendee_names="; ".join(f"{p} ({client})" for p in names) + "; employee",
                 amount=money(pp * n), description=f"Client dinner with {client}, {n} attendees")
        c["business_purpose"] = f"Dinner with {client} team to discuss {rng.choice(['renewal', 'expansion', 'pilot results', 'Q4 roadmap', 'contract terms'])}"
    elif category == "Ground Transport":
        if rng.random() < 0.25:
            rc = rng.choice(CAT["Ground Transport"]["allowed_rental_classes"])
            c.update(merchant=rng.choice(["Enterprise Rent-A-Car", "Hertz"]), rental_class=rc,
                     amount=money(rng.uniform(120, 380)), description=f"{rc} rental car")
        else:
            c.update(merchant=rng.choice(["Uber", "Lyft", "Yellow Cab", "Airport Parking"]),
                     amount=money(rng.uniform(12, 85)), description="Ride to client site / airport")
    elif category == "Mileage":
        miles = rng.randint(20, 180)
        c.update(merchant="Personal vehicle", miles=miles, amount=money(miles * mileage_rate(d)),
                 description=f"{miles} business miles at ${mileage_rate(d)}/mile", receipt_attached=False)
    elif category == "Conference":
        conf = rng.choice(CONFERENCES)
        c.update(merchant=conf, preapproved=True,
                 amount=money(rng.uniform(300, 0.89 * CAT["Conference"]["per_event_cap"])),
                 description=f"{conf} registration")
        c["business_purpose"] = f"Attend {conf} for training and customer networking"
    elif category == "Software":
        v = rng.choice(MERCHANTS["Software"])
        c.update(merchant=v, amount=money(rng.uniform(10, 300)), description=f"{v} monthly subscription")
    elif category == "Home Office":
        item = rng.choice(HOME_OFFICE_ITEMS)
        c.update(merchant=rng.choice(MERCHANTS["Home Office"]),
                 amount=money(rng.uniform(40, 0.89 * CAT["Home Office"]["per_purchase_cap"])), description=item)
    elif category == "Office Supplies":
        c.update(merchant=rng.choice(MERCHANTS["Office Supplies"]),
                 amount=money(rng.uniform(8, 0.89 * CAT["Office Supplies"]["per_purchase_cap"])),
                 description=rng.choice(SUPPLY_ITEMS))
    # receipts: always for > threshold, mostly for small items
    thr = policy["submission"]["receipt_required_over"]
    if category != "Mileage":
        c["receipt_attached"] = True if c["amount"] > thr else rng.random() < 0.8
    return c


# --------------------------------------------------------------- reports
def build_reports():
    reports, claims = [], []
    for emp_id, name, title, dept, home, mgr in EMPLOYEES:
        for r in range(1, 11):
            report_id = f"R-{emp_id}-{r:02d}"
            travel = rng.random() < TRAVEL_PROB[dept]
            items: list[dict] = []
            if travel:
                dest = rng.choice([c for c in CITIES if c != home])
                start = rand_date(WINDOW_START, WINDOW_END - timedelta(days=40))
                while start.weekday() > 2:  # trips start Mon–Wed so they end on weekdays
                    start += timedelta(days=1)
                nights = rng.randint(1, 3)
                end = start + timedelta(days=nights)
                is_conf = dept in ("Engineering", "Marketing") and rng.random() < 0.4
                client = rng.choice(CLIENTS)
                purpose = (f"Attend conference in {dest}" if is_conf else f"On-site visit with {client} in {dest}")
                title_txt = purpose
                items.append(clean_item("Airfare", start, dest, purpose))
                items.append(clean_item("Lodging", start, dest, purpose, nights=nights))
                if is_conf:
                    items.append(clean_item("Conference", start, dest, purpose))
                for k in range(rng.randint(0, 2)):
                    items.append(clean_item("Meals", start + timedelta(days=min(k, nights)), dest, purpose))
                if dept == "Sales" and rng.random() < 0.7:
                    items.append(clean_item("Client Meals", start + timedelta(days=rng.randint(0, nights)), dest, purpose))
                if rng.random() < 0.5:
                    items.append(clean_item("Ground Transport", start, dest, purpose))
                items = items[:5]
                last = end
            else:
                month_end = rand_date(WINDOW_START + timedelta(days=25), WINDOW_END)
                title_txt = f"Local expenses through {month_end:%b %d, %Y}"
                pool = {
                    "Sales": ["Client Meals", "Client Meals", "Mileage", "Ground Transport", "Office Supplies"],
                    "Marketing": ["Software", "Client Meals", "Office Supplies", "Home Office", "Mileage"],
                    "Engineering": ["Software", "Software", "Home Office", "Office Supplies"],
                    "Operations": ["Mileage", "Office Supplies", "Home Office", "Ground Transport"],
                    "Finance": ["Software", "Office Supplies", "Mileage", "Client Meals"],
                }[dept]
                for _ in range(rng.randint(1, 4)):
                    cat = rng.choice(pool)
                    d = month_end - timedelta(days=rng.randint(0, 25))
                    purpose = {
                        "Client Meals": "",  # set inside clean_item
                        "Mileage": f"Drive to {rng.choice(CLIENTS)} office for meeting",
                        "Software": "Tool required for daily work",
                        "Home Office": "Remote work setup",
                        "Office Supplies": "Team office supplies",
                        "Ground Transport": f"Rideshare to {rng.choice(CLIENTS)} meeting",
                    }[cat]
                    items.append(clean_item(cat, d, home, purpose))
                last = max(i["expense_date"] for i in items)
            submitted = min(last + timedelta(days=rng.randint(2, 20)), TODAY)
            reports.append(dict(report_id=report_id, employee_id=emp_id, report_title=title_txt,
                                report_type="travel" if travel else "local", submitted_date=submitted))
            for n, it in enumerate(items, 1):
                it.update(report_id=report_id, employee_id=emp_id, line_no=n,
                          claim_id=f"{report_id}-L{n}", submitted_date=submitted,
                          in_policy=True, violation_type="", expected_decision="approve",
                          review_reason="", is_borderline=False, label_note="")
                claims.append(it)
    return reports, claims


# -------------------------------------------------------- violation injectors
PROHIBITED_TEMPLATES = [
    ("Meals", "Pinstripe Bar & Lounge", "Drinks with coworkers after work, no clients present", "ALCOHOL_NO_CLIENT", (45, 160)),
    ("Home Office", "Best Buy", "AirPods Pro for personal commute", "PERSONAL_ITEM", (180, 260)),
    ("Ground Transport", "City Parking Enforcement", "Parking ticket near client office", "FINE", (40, 120)),
    ("Lodging", "Hotel Spa", "Spa massage during trip", "WELLNESS_ENTERTAINMENT", (90, 220)),
    ("Lodging", "Marriott", "In-room movies", "WELLNESS_ENTERTAINMENT", (18, 40)),
    ("Airfare", "Delta Air Lines", "Airfare for spouse to join trip", "FAMILY_TRAVEL", (220, 560)),
    ("Office Supplies", "Amazon", "Amazon gift card for team member birthday", "GIFT_CARD", (50, 100)),
]
WEIGHTS = {"over_cap": 0.22, "prohibited_category": 0.20, "missing_receipt": 0.14, "late_submission": 0.12,
           "duplicate": 0.10, "split_transaction": 0.07, "personal_extension": 0.08, "premium_class": 0.07}


def replace(c: dict, new: dict) -> None:
    keep = {k: c[k] for k in ("report_id", "employee_id", "line_no", "claim_id", "submitted_date")}
    c.clear(); c.update(new); c.update(keep)


def inject(claims: list[dict], reports: dict) -> None:
    n = len(claims)
    k = round(OUT_OF_POLICY_RATE * n)
    selected = set(rng.sample(range(n), k))
    locked: set[int] = set()  # partners for duplicate/split — must stay clean
    by_report: dict[str, list[int]] = {}
    for i, c in enumerate(claims):
        by_report.setdefault(c["report_id"], []).append(i)

    for i in sorted(selected):
        c = claims[i]
        rep = reports[c["report_id"]]
        partners = [j for j in by_report[c["report_id"]] if j != i and j not in selected and j not in locked]
        options = dict(WEIGHTS)
        if rep["report_type"] != "travel":
            options.pop("personal_extension"); options.pop("premium_class")
        earlier = [j for j in partners if j < i]  # a duplicate always copies an EARLIER line
        if not earlier:
            options.pop("duplicate", None)
        if not partners:
            options.pop("split_transaction", None)
        if rep["report_type"] == "travel":
            options.pop("split_transaction", None)
        vtype = rng.choices(list(options), weights=list(options.values()))[0]
        d, city, purpose = c["expense_date"], c["city"], c["business_purpose"] or rep["report_title"]
        note = ""

        if vtype == "over_cap":
            cats = ["Lodging", "Meals", "Client Meals", "Conference"] if rep["report_type"] == "travel" \
                else ["Client Meals", "Home Office", "Office Supplies"]
            cat = rng.choice(cats)
            new = clean_item(cat, d, city, purpose, nights=c.get("nights") or 2)
            if cat == "Lodging":
                cap = CAT["Lodging"]["nightly_cap"][tier(city)]
                nightly = cap * rng.uniform(1.15, 1.6)
                new["amount"] = money(nightly * new["nights"])
                new["description"] = f"Hotel, {new['nights']} night(s) at ${nightly:,.2f}/night"
                note = f"nightly ${nightly:,.2f} > cap ${cap}"
            elif cat == "Meals":
                new["amount"] = money(CAT["Meals"]["daily_per_diem"] * rng.uniform(1.3, 2.4))
                note = f"daily meals ${new['amount']} > ${CAT['Meals']['daily_per_diem']}"
            elif cat == "Client Meals":
                pp = CAT["Client Meals"]["per_person_cap"] * rng.uniform(1.2, 1.9)
                new["amount"] = money(pp * new["attendees"])
                note = f"per person ${pp:,.2f} > ${CAT['Client Meals']['per_person_cap']}"
            elif cat == "Conference":
                new["amount"] = money(CAT["Conference"]["per_event_cap"] * rng.uniform(1.1, 1.6))
                note = f"${new['amount']} > event cap ${CAT['Conference']['per_event_cap']}"
            elif cat == "Home Office":
                new["amount"] = money(CAT["Home Office"]["per_purchase_cap"] * rng.uniform(1.2, 2.5))
                new["description"] = rng.choice(["Premium ergonomic chair", "Ultrawide 49-inch monitor", "Motorized standing desk"])
                note = f"${new['amount']} > ${CAT['Home Office']['per_purchase_cap']}"
            else:
                new["amount"] = money(CAT["Office Supplies"]["per_purchase_cap"] * rng.uniform(1.3, 2.5))
                note = f"${new['amount']} > ${CAT['Office Supplies']['per_purchase_cap']}"
            new["receipt_attached"] = True

        elif vtype == "prohibited_category":
            cat, merch, desc, code, (lo, hi) = rng.choice(PROHIBITED_TEMPLATES)
            new = blank(cat, d, city)
            new.update(merchant=merch, description=desc, business_purpose=purpose,
                       amount=money(rng.uniform(lo, hi)), receipt_attached=True)
            if cat == "Airfare":
                new.update(fare_class="Economy", flight_hours=round(rng.uniform(1.5, 4.5), 1))
            note = code

        elif vtype == "missing_receipt":
            new = dict(c)
            if new["category"] == "Mileage" or new["amount"] <= 75:
                new = clean_item(rng.choice(["Client Meals", "Home Office", "Conference"] if rep["report_type"] == "local"
                                            else ["Lodging", "Airfare"]), d, city, purpose, nights=2)
                if new["category"] == "Conference":
                    new["preapproved"] = True
            new["receipt_attached"] = False
            note = f"${new['amount']} with no receipt"

        elif vtype == "late_submission":
            new = dict(c)
            days_late = rng.randint(65, 120)
            new["expense_date"] = c["submitted_date"] - timedelta(days=days_late)
            new["description"] = new["description"] + " (missed in earlier report)"
            if new["category"] == "Mileage":
                new["amount"] = money(new["miles"] * mileage_rate(new["expense_date"]))
                new["description"] = f"{new['miles']} business miles at ${mileage_rate(new['expense_date'])}/mile (missed in earlier report)"
            note = f"submitted {days_late} days after expense"

        elif vtype == "duplicate":
            j = rng.choice(earlier); locked.add(j)
            new = {k: v for k, v in claims[j].items()}
            note = f"duplicate of {claims[j]['claim_id']}"

        elif vtype == "split_transaction":
            j = rng.choice(partners); locked.add(j)
            cap = CAT["Home Office"]["per_purchase_cap"]
            a1 = money(rng.uniform(300, 0.86 * cap))
            a2 = money(rng.uniform(max(cap + 40 - a1, 150), 0.86 * cap))
            merch = rng.choice(["Amazon", "Best Buy", "IKEA"])
            item = rng.choice(["Motorized standing desk", "Dual monitor setup", "Ergonomic workstation bundle"])
            p = blank("Home Office", d, city)
            p.update(merchant=merch, description=f"{item} (part 1 of 2)", business_purpose="Remote work setup",
                     amount=a1, receipt_attached=True)
            replace(claims[j], p)
            claims[j].update(in_policy=True, violation_type="", expected_decision="approve",
                             review_reason="", is_borderline=False, label_note="")
            new = dict(p); new.update(description=f"{item} (part 2 of 2)", amount=a2)
            note = f"split with {claims[j]['claim_id']}: total ${a1 + a2:,.2f} > ${cap}"

        elif vtype == "personal_extension":
            sat = d
            while sat.weekday() != 5:
                sat += timedelta(days=1)
            new = clean_item("Lodging", sat, city, purpose, nights=2)
            new["description"] = "Hotel, stayed Sat–Sun after trip ended to see the city"
            new["business_purpose"] = "Extended stay"
            note = "weekend nights after business trip"

        else:  # premium_class
            new = blank("Airfare", d, city)
            if rng.random() < 0.5:
                new.update(fare_class="Business", flight_hours=round(rng.uniform(2.0, 5.5), 1), preapproved=True)
                note = f"business class on {new['flight_hours']}h flight (< 6h)"
            else:
                new.update(fare_class=rng.choice(["Business", "First"]), flight_hours=round(rng.uniform(6.5, 11), 1),
                           preapproved=False)
                note = f"{new['fare_class']} class without pre-approval" if new["fare_class"] == "Business" \
                    else "first class is never reimbursed"
            new.update(merchant=rng.choice(MERCHANTS["Airfare"]), amount=money(rng.uniform(1200, 4800)),
                       description=f"Round-trip {new['fare_class'].lower()}-class airfare to {city}",
                       business_purpose=purpose, receipt_attached=True)

        replace(c, new)
        c.update(in_policy=False, violation_type=vtype, expected_decision="deny",
                 review_reason="", is_borderline=False, label_note=note)

    # ---------------------------------------------------- borderline (human review)
    clean_idx = [i for i, c in enumerate(claims) if c["in_policy"] and i not in locked]
    for i in rng.sample(clean_idx, round(BORDERLINE_RATE * n)):
        c = claims[i]
        caps = {"Meals": CAT["Meals"]["daily_per_diem"], "Home Office": CAT["Home Office"]["per_purchase_cap"],
                "Office Supplies": CAT["Office Supplies"]["per_purchase_cap"]}
        if c["category"] in caps and rng.random() < 0.6:
            c["amount"] = money(caps[c["category"]] * rng.uniform(0.92, 0.995))
            c["receipt_attached"] = True
            reason, note = "near_cap", f"${c['amount']} within 10% of ${caps[c['category']]}"
        elif c["category"] == "Lodging" and rng.random() < 0.6:
            cap = CAT["Lodging"]["nightly_cap"][tier(c["city"])]
            nightly = cap * rng.uniform(0.92, 0.995)
            c["amount"] = money(nightly * c["nights"])
            c["description"] = f"Hotel, {c['nights']} night(s) at ${nightly:,.2f}/night"
            reason, note = "near_cap", f"nightly ${nightly:,.2f} within 10% of ${cap}"
        else:
            c["business_purpose"] = rng.choice(["Business", "Meeting", "Misc", "Work stuff", "Team"])
            reason, note = "vague_purpose", "business purpose too vague"
        c.update(is_borderline=True, expected_decision="review", review_reason=reason, label_note=note)

    # high-value in-policy items -> review (POL-5.1)
    thr = policy["escalation"]["high_value_threshold"]
    for c in claims:
        if c["in_policy"] and c["amount"] > thr and c["expected_decision"] == "approve":
            c.update(expected_decision="review", review_reason="high_value", label_note=f"${c['amount']:,.2f} > ${thr:,.0f}")


# ----------------------------------------------------------------- export
IMPORT_COLS = ["report_id", "employee_id", "employee_name", "department", "manager_id", "report_title",
               "submitted_date", "claim_id", "line_no", "expense_date", "category", "merchant", "description",
               "business_purpose", "amount", "currency", "city", "nights", "attendees", "attendee_names",
               "fare_class", "flight_hours", "rental_class", "miles", "preapproved", "receipt_attached"]
LABEL_COLS = ["claim_id", "in_policy", "violation_type", "expected_decision", "review_reason",
              "is_borderline", "label_note"]


def main() -> None:
    reports, claims = build_reports()
    rep_by_id = {r["report_id"]: r for r in reports}
    inject(claims, rep_by_id)

    emp = pd.DataFrame(EMPLOYEES, columns=["employee_id", "employee_name", "title", "department", "home_city", "manager_id"])
    df = pd.DataFrame(claims).merge(emp[["employee_id", "employee_name", "department", "manager_id"]], on="employee_id")
    df["report_title"] = df["report_id"].map(lambda r: rep_by_id[r]["report_title"])
    df["currency"] = "USD"
    for col in ("expense_date", "submitted_date"):
        df[col] = pd.to_datetime(df[col]).dt.date.astype(str)
    for col in ("nights", "attendees", "miles"):
        df[col] = df[col].astype("Int64")
    df = df.sort_values(["report_id", "line_no"]).reset_index(drop=True)

    out = ROOT / "data/raw"
    out.mkdir(parents=True, exist_ok=True)
    emp.to_csv(out / "employees.csv", index=False)
    imp = df[IMPORT_COLS]
    imp.to_csv(out / "expense_reports.csv", index=False)
    imp.to_excel(out / "expense_reports.xlsx", index=False, sheet_name="claims")
    df[LABEL_COLS].to_csv(out / "ground_truth_labels.csv", index=False)

    # JSON: nested reports -> line_items (the shape an API/app upload would use)
    nested = []
    for rid, g in imp.groupby("report_id", sort=True):
        h = g.iloc[0]
        nested.append({
            "report_id": rid, "employee_id": h.employee_id, "employee_name": h.employee_name,
            "department": h.department, "manager_id": h.manager_id, "report_title": h.report_title,
            "submitted_date": h.submitted_date, "currency": "USD",
            "line_items": json.loads(g.drop(columns=["report_id", "employee_id", "employee_name", "department",
                                                     "manager_id", "report_title", "submitted_date", "currency"])
                                     .to_json(orient="records")),
        })
    (out / "expense_reports.json").write_text(json.dumps({"company": "Techstack.io", "reports": nested}, indent=2))

    # summary
    print(f"reports={df.report_id.nunique()}  claims={len(df)}  per-employee reports={df.groupby('employee_id').report_id.nunique().unique()}")
    print(f"out-of-policy rate={(~df.in_policy).mean():.3f}")
    print(df.expected_decision.value_counts().to_string())
    print(df.loc[~df.in_policy, "violation_type"].value_counts().to_string())
    print(df.review_reason.replace("", "-").value_counts().to_string())


if __name__ == "__main__":
    main()
````

### Dataset validator
Save as: `scripts/validate.py`

````python
import pandas as pd, yaml
from datetime import date
p = yaml.safe_load(open("config/policy.yaml")); C = p["categories"]; HC=set(p["city_tiers"]["high_cost"])
d = pd.read_csv("data/raw/expense_reports.csv").merge(pd.read_csv("data/raw/ground_truth_labels.csv"), on="claim_id")
def flags(r):
    f=[]; days=(pd.Timestamp(r.submitted_date)-pd.Timestamp(r.expense_date)).days
    if days>60: f.append("late")
    if r.amount>75 and not r.receipt_attached and r.category!="Mileage": f.append("receipt")
    cat=r.category
    if cat=="Lodging" and r.nights==r.nights and r.amount/r.nights > C["Lodging"]["nightly_cap"]["high_cost" if r.city in HC else "standard"]: f.append("cap")
    if cat=="Meals" and r.amount>75: f.append("cap")
    if cat=="Client Meals" and r.attendees==r.attendees and r.amount/r.attendees>100: f.append("cap")
    if cat=="Conference" and r.amount>2000: f.append("cap")
    if cat=="Home Office" and r.amount>500: f.append("cap")
    if cat=="Office Supplies" and r.amount>150: f.append("cap")
    if cat=="Airfare" and r.fare_class not in ("Economy","Premium Economy"): f.append("fare")
    return f
d["rf"]=d.apply(flags,axis=1)
clean=d[d.in_policy]
print("in-policy rows with hard-rule flags:", (clean.rf.str.len()>0).sum())
print(clean[clean.rf.str.len()>0][["claim_id","category","amount","rf"]])
dup=d.duplicated(["employee_id","expense_date","merchant","amount"],keep="first")
print("duplicates detected:",dup.sum(),"labeled:",(d.violation_type=="duplicate").sum(), "match:", set(d[dup].claim_id)==set(d[d.violation_type=="duplicate"].claim_id))
v=d[~d.in_policy]; print("violations caught by simple hard rules:", (v.rf.str.len()>0).sum(), "of", len(v))
print(v[v.rf.str.len()==0].violation_type.value_counts())
````
