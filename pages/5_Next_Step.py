import json
import streamlit as st
from db.database import get_session
from db.models import Topic, Subtopic, Progress, ProgressStatus

st.title("Next Step")

session = get_session()

# Gather all subtopics with progress
subtopics = session.query(Subtopic).order_by(Subtopic.priority_score).all()

# Scoring: find the highest-priority subtopic that isn't Confident
def calculate_next_step_score(sub, progress):
    """Lower score = higher priority for next step."""
    score = sub.priority_score  # base: priority order

    if not progress or progress.status == ProgressStatus.NOT_STARTED:
        score -= 10  # boost not-started items
    elif progress.status == ProgressStatus.LEARNING:
        score -= 5
    elif progress.status == ProgressStatus.PRACTICED:
        score += 5
    elif progress.status == ProgressStatus.CONFIDENT:
        score += 100  # deprioritize confident items

    # Boost items with weak areas
    if progress and progress.weak_areas:
        score -= 8

    # Boost L4 requirements
    if sub.senior_level == "L4":
        score -= 3

    return score


candidates = []
for sub in subtopics:
    progress = session.query(Progress).filter(Progress.subtopic_id == sub.id).first()
    if progress and progress.status == ProgressStatus.CONFIDENT:
        continue
    score = calculate_next_step_score(sub, progress)
    topic = session.query(Topic).get(sub.topic_id)
    candidates.append((score, sub, progress, topic))

candidates.sort(key=lambda x: x[0])

if not candidates:
    st.success("🎉 You've reached Confident status on all subtopics! You're ready for the senior assessment.")
else:
    best_score, best_sub, best_progress, best_topic = candidates[0]
    status_label = best_progress.status.value if best_progress else "Not Started"

    # Determine reason
    reasons = []
    if best_sub.priority_score <= 4:
        reasons.append("This is a foundational topic (Tier 1) — other topics build on it.")
    elif best_sub.tier <= 2:
        reasons.append("This is a core data engineering topic (Tier 2) — essential for daily work.")
    if best_sub.senior_level == "L4":
        reasons.append(f"Requires mastery level (L4) for senior — needs extra depth.")
    if best_progress and best_progress.weak_areas:
        reasons.append(f"Has identified weak areas that need attention.")
    if status_label == "Not Started":
        reasons.append("You haven't started this subtopic yet.")
    elif status_label == "Learning":
        reasons.append("You've started learning but haven't practiced yet.")

    deps = json.loads(best_sub.dependencies) if best_sub.dependencies else []

    # Task card
    st.markdown("---")
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"{best_topic.name}")
        st.markdown(f"### {best_sub.name}")
        st.markdown(f"**Senior requirement:** {best_sub.senior_level} | **Current status:** {status_label}")
        st.markdown(f"**Priority:** #{best_sub.priority_score} | **Tier:** {best_sub.tier}")

        st.markdown("#### Why this is prioritized")
        for r in reasons:
            st.markdown(f"- {r}")

        if deps:
            st.markdown("#### Prerequisites")
            for dep in deps:
                dep_sub = session.query(Subtopic).filter(Subtopic.name == dep).first()
                if dep_sub and dep_sub.progress:
                    icon = "✅" if dep_sub.progress.status == ProgressStatus.CONFIDENT else "⚠️"
                    st.markdown(f"- {icon} {dep} ({dep_sub.progress.status.value})")
                else:
                    st.markdown(f"- ❓ {dep}")

    with col2:
        st.markdown("#### Estimated Time")
        level_map = {"L2": "short", "L3": "medium", "L4": "deep"}
        depth = level_map.get(best_sub.senior_level, "medium")

        if depth == "short":
            st.markdown("- 📖 Learn: ~20 min\n- 💪 Practice: ~30 min\n- 🔍 Evaluate: ~10 min")
        elif depth == "medium":
            st.markdown("- 📖 Learn: ~30 min\n- 💪 Practice: ~45 min\n- 🔍 Evaluate: ~15 min")
        else:
            st.markdown("- 📖 Learn: ~45 min\n- 💪 Practice: ~60 min\n- 🔍 Evaluate: ~20 min")

        st.markdown("#### Suggested Path")
        if status_label == "Not Started":
            st.markdown("1. Start with **Learn**\n2. Move to **Practice**\n3. Finish with **Evaluate**")
        elif status_label == "Learning":
            st.markdown("1. Continue with **Practice**\n2. Do **Evaluate** when ready")
        elif status_label == "Practiced":
            st.markdown("1. Do **Evaluate** for final check\n2. Or more **Practice** on weak areas")

    st.markdown("---")

    # Action buttons
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("📖 Learn", use_container_width=True):
            st.session_state["selected_subtopic_id"] = best_sub.id
            st.switch_page("pages/2_Learn.py")
    with col_b:
        if st.button("💪 Practice", use_container_width=True):
            st.session_state["selected_subtopic_id"] = best_sub.id
            st.switch_page("pages/3_Practice.py")
    with col_c:
        if st.button("🔍 Evaluate", use_container_width=True):
            st.session_state["selected_subtopic_id"] = best_sub.id
            st.switch_page("pages/4_Evaluate.py")

    # Show upcoming queue
    st.divider()
    st.subheader("Upcoming Queue")
    for i, (score, sub, prog, topic) in enumerate(candidates[1:8], 1):
        p_status = prog.status.value if prog else "Not Started"
        st.markdown(f"**{i}.** {topic.name} → {sub.name} — {p_status} (Tier {sub.tier}, {sub.senior_level})")

session.close()
