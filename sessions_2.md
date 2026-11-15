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
