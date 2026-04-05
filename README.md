# Data Engineer Senior-Level Prep App

A local Python learning application that helps you prepare for a senior-level data engineer assessment. Built with Streamlit, SQLite, and Claude AI (via AWS Bedrock).

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure AWS credentials

Copy `.env.example` to `.env` and set your AWS region:

```bash
cp .env.example .env
# Edit .env — set AWS_REGION to your Bedrock region (e.g. eu-central-1)
```

AWS credentials are read from `~/.aws/credentials` or environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`). The app uses `eu.anthropic.claude-sonnet-4-6` via Bedrock.

### 3. Seed the database

Reads the skill matrix `.xlsx` and populates SQLite with all topics, subtopics, dependencies, and priority scores:

```bash
python seed.py
```

### 4. Run the app

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## How it works

### Learning flow

The app follows a structured path through each subtopic:

```
Not Started → Learning → Practiced → Confident
```

1. **Learn** — Read an AI-generated explanation and curated resources. Click "Mark as Learned" to move to `Learning`.
2. **Practice** — Attempt AI-generated tasks. Completing 3 correct answers advances to `Practiced`; 6 advances to `Confident`. Difficulty scales automatically from 1→5 as you complete tasks.
3. **Evaluate** — Take a generated test (multiple-choice + text questions scaled to L2/L3/L4 depth). Scoring ≥ 80% marks the subtopic `Confident`.
4. **Next Step** — The app scores every non-Confident subtopic and recommends what to study next, factoring in priority tier, dependencies, weak areas, and spaced-repetition review due dates.

### Spaced repetition

Subtopics marked `Confident` are not forgotten. If a subtopic hasn't been practiced for **7 or more days**, it reappears as "Due for Review" on the Dashboard and is re-surfaced in the Next Step queue with elevated priority (`REVIEW_SCORE_BOOST = 15`). This threshold is controlled by `REVIEW_DAYS` in `utils.py`.

### Weak area tracking

Every time you submit a practice answer or complete an evaluation, Claude identifies specific weak areas in your response. These are:

- Deduplicated (case-insensitive) before saving so the list doesn't grow unbounded
- Stored as newline-separated strings on each `Progress` row
- Displayed as a bullet list per subtopic on the Dashboard
- Fed back into task generation so future practice targets your gaps

The "Clear All" button on the Dashboard removes all weak area feedback after a two-step confirmation. Each deletion is logged to `SessionHistory` for auditability.

### Next Step scoring

Each non-Confident subtopic receives a priority score (lower = higher priority):

| Condition | Score delta |
|---|---|
| Not Started | −10 |
| Learning | −5 |
| Practiced | +5 |
| Confident, review due (≥7 days) | −15 |
| Has weak areas | −8 |
| Senior level L4 | −3 |

The base score is the subtopic's `priority_score` (1–34 from the skill matrix). Foundational items (Tier 1, priority 1–4) can reach negative scores when review is due, ensuring they outrank any unstarted item.

---

## Pages

| Page | Purpose |
|---|---|
| **Dashboard** | Readiness % by topic (stacked bar chart), Due for Review list, Weak Areas summary, resume last session |
| **Learn** | AI explanation + curated resources for the selected subtopic; cached after first generation |
| **Practice** | Auto-generated tasks with difficulty scaling (1–5); AI evaluates each answer with feedback and weak-area identification |
| **Evaluate** | Generated test (L2: 3 MC + 2 text, L3: 5+3, L4: 6+4); MC graded instantly, text answers batch-evaluated by Claude |
| **Next Step** | Priority-scored recommendation with reasoning, estimated time, suggested path, and prerequisite status |

---

## Project structure

```
├── app.py                  # Streamlit entry point; initialises DB and defines navigation
├── seed.py                 # One-time seeder: reads skill matrix xlsx → populates SQLite
├── utils.py                # Shared utilities: REVIEW_DAYS, REVIEW_SCORE_BOOST, as_utc(), parse_weak_areas()
├── requirements.txt
├── .env.example
├── db/
│   ├── database.py         # SQLAlchemy engine, session factory, init_db()
│   └── models.py           # ORM models (see below)
├── ai/
│   └── claude_client.py    # Bedrock client; functions for explain, resources, task, evaluate, eval questions
└── pages/
    ├── 1_Dashboard.py      # Progress overview; joinedload-optimised queries
    ├── 2_Learn.py          # Content display; caches explanation + resources to DB
    ├── 3_Practice.py       # Task loop; difficulty scaling; answer evaluation
    ├── 4_Evaluate.py       # Test generation + submission; MC + AI-graded text
    └── 5_Next_Step.py      # Priority scoring; bulk-loaded dicts to avoid N+1 queries
```

### Database models

| Model | Purpose |
|---|---|
| `Topic` | Top-level category (e.g. "Programming & Scripting") |
| `Subtopic` | Individual competency with priority, tier, dependencies, cached AI content |
| `Progress` | Per-subtopic status, task counts, weak areas, `updated_at` (used for spaced repetition) |
| `Task` | Individual practice task attempt with user answer and AI feedback |
| `SessionHistory` | Audit log of every learn/practice/evaluate/clear action |
| `EvalQuestion` | Generated test questions (persisted, regenerated on demand) |
| `EvalAttempt` | Test submission results with score and weak spots |

### Key utilities (`utils.py`)

| Name | Type | Description |
|---|---|---|
| `REVIEW_DAYS` | constant | Days before a Confident subtopic is due for review (default 7) |
| `REVIEW_SCORE_BOOST` | constant | Score reduction applied to review-due items in the Next Step queue (default 15) |
| `as_utc(dt)` | function | Attaches UTC tzinfo to naive datetimes from SQLite; returns `None` if input is `None` |
| `parse_weak_areas(blob)` | function | Splits on `\n` and `,`, deduplicates case-insensitively, preserves insertion order |
