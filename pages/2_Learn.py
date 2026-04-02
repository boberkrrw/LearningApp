import streamlit as st
from db.database import get_session
from db.models import Topic, Subtopic, Progress, ProgressStatus, SessionHistory
from ai.claude_client import explain_subtopic, suggest_resources

st.title("Learn")

session = get_session()
topics = session.query(Topic).all()
topic_names = [t.name for t in topics]

selected_topic_name = st.selectbox("Select Topic", topic_names)
selected_topic = next(t for t in topics if t.name == selected_topic_name)

subtopics = session.query(Subtopic).filter(
    Subtopic.topic_id == selected_topic.id
).order_by(Subtopic.priority_score).all()

preselected_idx = 0
if "selected_subtopic_id" in st.session_state:
    for i, sub in enumerate(subtopics):
        if sub.id == st.session_state["selected_subtopic_id"]:
            preselected_idx = i
            break

subtopic_names = [f"{s.name} ({s.senior_level})" for s in subtopics]
selected_idx = st.selectbox("Select Subtopic", range(len(subtopic_names)), format_func=lambda i: subtopic_names[i], index=preselected_idx)
selected_sub = subtopics[selected_idx]

st.info(f"**Description:** {selected_sub.description}")
st.caption(f"Senior requirement: **{selected_sub.senior_level}** | Priority: {selected_sub.priority_score} | Tier: {selected_sub.tier}")

st.divider()

# --- Explanation section ---
if st.button("📖 Generate / Refresh Explanation"):
    with st.spinner("Claude is preparing the explanation..."):
        explanation = explain_subtopic(selected_sub.name, selected_sub.description, selected_sub.senior_level)
        selected_sub.cached_explanation = explanation
        history = SessionHistory(
            subtopic_id=selected_sub.id,
            activity_type="learn",
            content=explanation,
        )
        session.add(history)
        session.commit()

# Reload from DB to get latest cached value
session.refresh(selected_sub)
if selected_sub.cached_explanation:
    st.markdown(selected_sub.cached_explanation)
else:
    st.caption("No explanation loaded yet. Click the button above to generate one.")

st.divider()

# --- Resources section ---
if st.button("🔗 Generate / Refresh Resources"):
    with st.spinner("Finding resources..."):
        resources = suggest_resources(selected_sub.name)
        selected_sub.cached_resources = resources
        session.commit()

session.refresh(selected_sub)
if selected_sub.cached_resources:
    st.markdown(selected_sub.cached_resources)
else:
    st.caption("No resources loaded yet. Click the button above to generate them.")

st.divider()

# Mark as learned
col1, col2 = st.columns(2)
with col1:
    if st.button("✅ Mark as Learned → Go to Practice", use_container_width=True):
        progress = session.query(Progress).filter(Progress.subtopic_id == selected_sub.id).first()
        if progress and progress.status in (ProgressStatus.NOT_STARTED, ProgressStatus.LEARNING):
            progress.status = ProgressStatus.LEARNING
            session.commit()
        st.session_state["selected_subtopic_id"] = selected_sub.id
        st.switch_page("pages/3_Practice.py")

with col2:
    current_progress = session.query(Progress).filter(Progress.subtopic_id == selected_sub.id).first()
    if current_progress:
        st.caption(f"Current status: **{current_progress.status.value}**")

session.close()
