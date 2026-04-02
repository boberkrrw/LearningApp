import streamlit as st
from datetime import datetime, timezone
from db.database import get_session
from db.models import Topic, Subtopic, Task, TaskType, TaskStatus, Progress, ProgressStatus, SessionHistory
from ai.claude_client import generate_task, evaluate_answer

st.title("Practice")

session = get_session()
topics = session.query(Topic).all()
topic_names = [t.name for t in topics]

selected_topic_name = st.selectbox("Select Topic", topic_names, key="practice_topic")
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
selected_idx = st.selectbox("Select Subtopic", range(len(subtopic_names)), format_func=lambda i: subtopic_names[i], index=preselected_idx, key="practice_subtopic")
selected_sub = subtopics[selected_idx]

progress = session.query(Progress).filter(Progress.subtopic_id == selected_sub.id).first()
st.caption(f"Status: **{progress.status.value}** | Completed: {progress.tasks_completed} | Attempted: {progress.tasks_attempted}")

st.divider()


def get_difficulty(prog):
    if prog.tasks_completed == 0:
        return 1
    elif prog.tasks_completed < 3:
        return 2
    elif prog.tasks_completed < 6:
        return 3
    elif prog.tasks_completed < 10:
        return 4
    return 5


difficulty = get_difficulty(progress)

# --- Generate task: only on button click, saves to DB ---
if st.button("🎯 Generate New Task"):
    with st.spinner("Generating task..."):
        weak_areas = progress.weak_areas if progress else None
        task_text = generate_task(selected_sub.name, selected_sub.description, difficulty, weak_areas)
        selected_sub.cached_task = task_text
        session.commit()
        # Clear previous evaluation state for this subtopic
        st.session_state.pop(f"eval_result_{selected_sub.id}", None)
        st.session_state.pop(f"task_evaluated_{selected_sub.id}", None)

# Load cached task from DB
session.refresh(selected_sub)
task_text = selected_sub.cached_task

if task_text:
    st.subheader(f"Task (Difficulty: {difficulty}/5)")
    st.markdown(task_text)

    st.divider()

    user_answer = st.text_area("Your Answer", height=200, key=f"answer_{selected_sub.id}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📤 Submit Answer", use_container_width=True):
            if user_answer.strip():
                with st.spinner("Claude is evaluating your answer..."):
                    result = evaluate_answer(task_text, user_answer, selected_sub.name)
                    st.session_state[f"eval_result_{selected_sub.id}"] = result
                    st.session_state[f"task_evaluated_{selected_sub.id}"] = True

                    task = Task(
                        subtopic_id=selected_sub.id,
                        description=task_text,
                        task_type=TaskType.HANDS_ON,
                        difficulty=difficulty,
                        status=TaskStatus.DONE if result["correct"] else TaskStatus.ACTIVE,
                        user_answer=user_answer,
                        ai_feedback=result["raw"],
                        completed_at=datetime.now(timezone.utc) if result["correct"] else None,
                    )
                    session.add(task)

                    progress.tasks_attempted += 1
                    if result["correct"]:
                        progress.tasks_completed += 1
                        if progress.tasks_completed >= 3 and progress.status != ProgressStatus.CONFIDENT:
                            progress.status = ProgressStatus.PRACTICED
                        if progress.tasks_completed >= 6:
                            progress.status = ProgressStatus.CONFIDENT
                    if result["weak_areas"] and result["weak_areas"].lower() != "none":
                        existing = progress.weak_areas or ""
                        progress.weak_areas = f"{existing}\n{result['weak_areas']}".strip()

                    history = SessionHistory(
                        subtopic_id=selected_sub.id,
                        activity_type="practice",
                        content=user_answer,
                        evaluation_result="correct" if result["correct"] else "incorrect",
                        weak_spots=result["weak_areas"],
                    )
                    session.add(history)
                    session.commit()
            else:
                st.warning("Please write an answer before submitting.")

    with col2:
        if st.button("⏭ Skip", use_container_width=True):
            task = Task(
                subtopic_id=selected_sub.id,
                description=task_text,
                task_type=TaskType.HANDS_ON,
                difficulty=difficulty,
                status=TaskStatus.SKIPPED,
            )
            session.add(task)
            history = SessionHistory(
                subtopic_id=selected_sub.id,
                activity_type="practice",
                content="Skipped",
                evaluation_result="skipped",
            )
            session.add(history)
            session.commit()
            st.info("Task skipped.")

    # Show evaluation result
    if st.session_state.get(f"task_evaluated_{selected_sub.id}") and f"eval_result_{selected_sub.id}" in st.session_state:
        result = st.session_state[f"eval_result_{selected_sub.id}"]
        if result["correct"]:
            st.success("Correct!")
        else:
            st.error("Incorrect")

        st.markdown("### Feedback")
        st.markdown(result["feedback"])

        if result["hint"]:
            st.markdown("### Hint")
            st.info(result["hint"])

        if result["weak_areas"] and result["weak_areas"].lower() != "none":
            st.markdown("### Weak Areas Identified")
            st.warning(result["weak_areas"])
else:
    st.caption("No task loaded yet. Click **Generate New Task** to get one.")

session.close()
