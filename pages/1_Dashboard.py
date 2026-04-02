import streamlit as st
import plotly.graph_objects as go
from sqlalchemy import func
from db.database import get_session
from db.models import Topic, Subtopic, Progress, ProgressStatus, SessionHistory

st.title("Dashboard")

session = get_session()

# Gather stats
subtopics = session.query(Subtopic).order_by(Subtopic.priority_score).all()
total = len(subtopics)

status_counts = {}
for s in ProgressStatus:
    count = session.query(Progress).filter(Progress.status == s).count()
    status_counts[s.value] = count

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

# Progress by topic
st.subheader("Progress by Topic")

topics = session.query(Topic).all()
for topic in topics:
    topic_subtopics = session.query(Subtopic).filter(Subtopic.topic_id == topic.id).all()
    if not topic_subtopics:
        continue

    topic_confident = 0
    topic_practiced = 0
    topic_learning = 0
    for sub in topic_subtopics:
        if sub.progress:
            if sub.progress.status == ProgressStatus.CONFIDENT:
                topic_confident += 1
            elif sub.progress.status == ProgressStatus.PRACTICED:
                topic_practiced += 1
            elif sub.progress.status == ProgressStatus.LEARNING:
                topic_learning += 1

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

# Weak areas summary
st.subheader("Weak Areas")
weak_progress = session.query(Progress).filter(Progress.weak_areas.isnot(None), Progress.weak_areas != "").all()
if weak_progress:
    for p in weak_progress:
        sub = session.query(Subtopic).get(p.subtopic_id)
        st.warning(f"**{sub.name}**: {p.weak_areas}")
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
        sub = session.query(Subtopic).get(last_session.subtopic_id)
        page_map = {"learn": "pages/2_Learn.py", "practice": "pages/3_Practice.py", "evaluate": "pages/4_Evaluate.py"}
        target = page_map.get(last_session.activity_type, "pages/2_Learn.py")
        if st.button(f"🔄 Resume: {sub.name} ({last_session.activity_type})", use_container_width=True):
            st.session_state["selected_subtopic_id"] = last_session.subtopic_id
            st.switch_page(target)
    else:
        st.button("🔄 Resume Last Session", use_container_width=True, disabled=True)

session.close()
