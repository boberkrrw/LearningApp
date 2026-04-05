import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from db.database import get_session
from db.models import Topic, Subtopic, Progress, ProgressStatus, SessionHistory
from utils import parse_weak_areas

st.title("Dashboard")

session = get_session()

# Gather stats — single GROUP BY query instead of 4 separate COUNTs
subtopics = session.query(Subtopic).order_by(Subtopic.priority_score).all()
subtopics_by_id = {sub.id: sub for sub in subtopics}
total = len(subtopics)

status_counts = {s.value: 0 for s in ProgressStatus}
for status, count in session.query(Progress.status, func.count(Progress.id)).group_by(Progress.status).all():
    status_counts[status.value] = count

confident_count = status_counts.get("Confident", 0)
practiced_count = status_counts.get("Practiced", 0)
learning_count = status_counts.get("Learning", 0)
not_started_count = status_counts.get("Not Started", 0)

readiness = 0
if total > 0:
    readiness = round(((confident_count * 1.0 + practiced_count * 0.6 + learning_count * 0.2) / total) * 100, 1)

# Top metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Overall Readiness", f"{readiness}%")
col2.metric("Confident", confident_count)
col3.metric("Practiced", practiced_count)
col4.metric("Not Started", not_started_count)

st.divider()

# Per-topic progress chart — group subtopics in Python, no extra queries
topics = session.query(Topic).all()
subtopics_by_topic = defaultdict(list)
for sub in subtopics:
    subtopics_by_topic[sub.topic_id].append(sub)

topic_names_chart = []
confident_pcts = []
practiced_pcts = []
learning_pcts = []
not_started_pcts = []

for topic in topics:
    t_subs = subtopics_by_topic[topic.id]
    if not t_subs:
        continue
    t_total = len(t_subs)
    t_conf  = sum(1 for s in t_subs if s.progress and s.progress.status == ProgressStatus.CONFIDENT)
    t_prac  = sum(1 for s in t_subs if s.progress and s.progress.status == ProgressStatus.PRACTICED)
    t_learn = sum(1 for s in t_subs if s.progress and s.progress.status == ProgressStatus.LEARNING)
    # Derive not-started as remainder to guarantee bars always sum to 100%
    c_pct = round(t_conf  / t_total * 100)
    p_pct = round(t_prac  / t_total * 100)
    l_pct = round(t_learn / t_total * 100)
    ns_pct = 100 - c_pct - p_pct - l_pct
    topic_names_chart.append(topic.name)
    confident_pcts.append(c_pct)
    practiced_pcts.append(p_pct)
    learning_pcts.append(l_pct)
    not_started_pcts.append(ns_pct)

if topic_names_chart:
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Confident 🟢",   y=topic_names_chart, x=confident_pcts,   orientation="h", marker_color="#2ecc71"))
    fig.add_trace(go.Bar(name="Practiced 🟠",   y=topic_names_chart, x=practiced_pcts,   orientation="h", marker_color="#e67e22"))
    fig.add_trace(go.Bar(name="Learning 🟡",    y=topic_names_chart, x=learning_pcts,    orientation="h", marker_color="#f1c40f"))
    fig.add_trace(go.Bar(name="Not Started 🔴", y=topic_names_chart, x=not_started_pcts, orientation="h", marker_color="#e74c3c"))
    fig.update_layout(
        barmode="stack",
        xaxis=dict(title="% of Subtopics", range=[0, 100]),
        yaxis=dict(autorange="reversed"),
        height=max(200, len(topic_names_chart) * 42),
        margin=dict(l=0, r=0, t=10, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Progress by topic — reuses subtopics_by_topic, no extra queries
st.subheader("Progress by Topic")

for topic in topics:
    topic_subtopics = subtopics_by_topic[topic.id]
    if not topic_subtopics:
        continue

    topic_confident = sum(1 for s in topic_subtopics if s.progress and s.progress.status == ProgressStatus.CONFIDENT)
    topic_practiced = sum(1 for s in topic_subtopics if s.progress and s.progress.status == ProgressStatus.PRACTICED)
    topic_learning  = sum(1 for s in topic_subtopics if s.progress and s.progress.status == ProgressStatus.LEARNING)

    topic_total = len(topic_subtopics)
    topic_pct = round(((topic_confident + topic_practiced * 0.6 + topic_learning * 0.2) / topic_total) * 100)

    with st.expander(f"{topic.name} — {topic_pct}% ready ({topic_confident}/{topic_total} confident)"):
        for sub in sorted(topic_subtopics, key=lambda s: s.priority_score):
            status_label = sub.progress.status.value if sub.progress else "Not Started"
            status_colors = {
                "Not Started": "🔴",
                "Learning": "🟡",
                "Practiced": "🟠",
                "Confident": "🟢",
            }
            icon = status_colors.get(status_label, "⚪")
            st.markdown(f"{icon} **{sub.name}** — {status_label} (Senior req: {sub.senior_level})")

st.divider()

# Due for Review — push cutoff filter to SQL; SQLite stores datetimes as naive UTC
_now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
review_cutoff_naive = _now_naive - timedelta(days=7)

review_due_rows = (
    session.query(Progress)
    .filter(
        Progress.status == ProgressStatus.CONFIDENT,
        Progress.updated_at < review_cutoff_naive,
    )
    .all()
)

if review_due_rows:
    st.subheader("Due for Review")
    st.caption("These subtopics reached Confident status but haven't been practiced in over 7 days.")
    for p in review_due_rows:
        sub = subtopics_by_id.get(p.subtopic_id)
        if sub:
            updated_naive = p.updated_at or _now_naive
            days_ago = (_now_naive - updated_naive).days
            st.warning(f"🔁 **{sub.name}** — last reviewed {days_ago} day{'s' if days_ago != 1 else ''} ago")
    st.divider()

# Weak areas summary — deduped bullet list per subtopic, with Clear All
col_weak_hdr, col_weak_btn = st.columns([3, 1])
with col_weak_hdr:
    st.subheader("Weak Areas")

weak_progress = session.query(Progress).filter(Progress.weak_areas.isnot(None), Progress.weak_areas != "").all()

with col_weak_btn:
    clear_clicked = st.button("🗑 Clear All", key="clear_weak_areas", disabled=not weak_progress)

if clear_clicked:
    for p in weak_progress:
        p.weak_areas = None
    session.commit()
    st.rerun()

if weak_progress:
    for p in weak_progress:
        sub = subtopics_by_id.get(p.subtopic_id)
        if not sub:
            continue
        _parts = parse_weak_areas(p.weak_areas)
        if not _parts:
            continue
        with st.expander(f"**{sub.name}** — {len(_parts)} weak area{'s' if len(_parts) != 1 else ''}"):
            for _item in _parts:
                st.markdown(f"- {_item}")
else:
    st.info("No weak areas identified yet. Start practicing to get feedback!")

st.divider()

# Action buttons
col_a, col_b = st.columns(2)
with col_a:
    if st.button("🚀 Next Step", use_container_width=True):
        st.switch_page("pages/5_Next_Step.py")
with col_b:
    last_session = session.query(SessionHistory).order_by(SessionHistory.created_at.desc()).first()
    if last_session:
        sub = subtopics_by_id.get(last_session.subtopic_id) or session.query(Subtopic).get(last_session.subtopic_id)
        if sub:
            page_map = {"learn": "pages/2_Learn.py", "practice": "pages/3_Practice.py", "evaluate": "pages/4_Evaluate.py"}
            target = page_map.get(last_session.activity_type, "pages/2_Learn.py")
            if st.button(f"🔄 Resume: {sub.name} ({last_session.activity_type})", use_container_width=True):
                st.session_state["selected_subtopic_id"] = last_session.subtopic_id
                st.switch_page(target)
        else:
            st.button("🔄 Resume Last Session", use_container_width=True, disabled=True)
    else:
        st.button("🔄 Resume Last Session", use_container_width=True, disabled=True)

session.close()
