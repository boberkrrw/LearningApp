# Data Engineer Senior-Level Prep App

A local Python learning application that helps you prepare for a senior-level data engineer assessment. Built with Streamlit, SQLite, and Claude AI.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API key

Copy `.env.example` to `.env` and add your Anthropic API key:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Seed the database

This reads the skill matrix xlsx and populates the SQLite database with all topics, subtopics, dependencies, and priority scores:

```bash
python seed.py
```

### 4. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Pages

- **Dashboard** — Progress overview, readiness %, weak areas, resume last session
- **Learn** — AI-powered explanations and curated resources per subtopic
- **Practice** — Generated tasks with difficulty scaling, answer evaluation, and feedback
- **Evaluate** — Deep review of longer solutions with structured feedback
- **Next Step** — AI-prioritized recommendation for what to study next

## Project Structure

```
├── app.py                 # Main Streamlit entry point
├── seed.py                # Database seeder (parses xlsx)
├── requirements.txt       # Python dependencies
├── .env.example           # API key template
├── db/
│   ├── database.py        # SQLAlchemy engine & session
│   └── models.py          # ORM models (Topic, Subtopic, Task, Progress, SessionHistory)
├── ai/
│   └── claude_client.py   # Anthropic SDK integration
└── pages/
    ├── 1_Dashboard.py
    ├── 2_Learn.py
    ├── 3_Practice.py
    ├── 4_Evaluate.py
    └── 5_Next_Step.py
```
