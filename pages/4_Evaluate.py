import json
import streamlit as st
from datetime import datetime, timezone
from db.database import get_session
from db.models import Topic, Subtopic, Progress, ProgressStatus, SessionHistory, EvalQuestion, EvalAttempt
from ai.claude_client import generate_eval_questions, evaluate_text_answers

st.title("Evaluate")

session = get_session()
topics = session.query(Topic).all()
topic_names = [t.name for t in topics]

selected_topic_name = st.selectbox("Select Topic", topic_names, key="eval_topic")
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
selected_idx = st.selectbox(
    "Select Subtopic",
    range(len(subtopic_names)),
    format_func=lambda i: subtopic_names[i],
    index=preselected_idx,
    key="eval_subtopic",
)
selected_sub = subtopics[selected_idx]

progress = session.query(Progress).filter(Progress.subtopic_id == selected_sub.id).first()
mc_count, text_count = {"L2": (3, 2), "L3": (5, 3), "L4": (6, 4)}.get(selected_sub.senior_level, (5, 3))
total_q = mc_count + text_count

st.caption(
    f"Senior requirement: **{selected_sub.senior_level}** | "
    f"Test: {mc_count} multiple-choice + {text_count} text = **{total_q} questions**"
)
st.divider()

# Load existing questions from DB
questions = (
    session.query(EvalQuestion)
    .filter(EvalQuestion.subtopic_id == selected_sub.id)
    .order_by(EvalQuestion.position)
    .all()
)

# State keys
submitted_key = f"eval_submitted_{selected_sub.id}"
results_key = f"eval_results_{selected_sub.id}"


def clear_test_state():
    st.session_state.pop(submitted_key, None)
    st.session_state.pop(results_key, None)
    for q in questions:
        st.session_state.pop(f"eval_ans_{q.id}", None)


# Generate / regenerate test
col_gen, col_info = st.columns([1, 2])
with col_gen:
    gen_label = "🔄 Regenerate Test" if questions else "🎯 Generate Test"
    generate_clicked = st.button(gen_label, use_container_width=True)

if generate_clicked:
    with st.spinner(f"Generating {total_q} questions for {selected_sub.name}..."):
        raw = generate_eval_questions(selected_sub.name, selected_sub.description, selected_sub.senior_level)

        # Parse JSON — strip markdown fences if present
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean.split("```")[1]
            if raw_clean.startswith("json"):
                raw_clean = raw_clean[4:]
        try:
            parsed = json.loads(raw_clean.strip())
        except json.JSONDecodeError:
            st.error(
                "The AI response was truncated before it could be fully parsed. "
                "Click **Regenerate Test** to try again."
            )
            session.close()
            st.stop()

        # Delete old questions for this subtopic
        session.query(EvalQuestion).filter(EvalQuestion.subtopic_id == selected_sub.id).delete()

        for pos, q in enumerate(parsed):
            eq = EvalQuestion(
                subtopic_id=selected_sub.id,
                question_text=q["question"],
                question_type=q["type"],
                options=json.dumps(q.get("options")) if q.get("options") else None,
                correct_answer=q.get("correct"),
                model_answer=q.get("model_answer"),
                explanation=q.get("explanation", ""),
                position=pos,
            )
            session.add(eq)
        session.commit()
        clear_test_state()
        st.rerun()

# Reload after potential generation
questions = (
    session.query(EvalQuestion)
    .filter(EvalQuestion.subtopic_id == selected_sub.id)
    .order_by(EvalQuestion.position)
    .all()
)

if not questions:
    st.info("No test generated yet. Click **Generate Test** to create one.")
    session.close()
    st.stop()

# ── RESULTS VIEW ──────────────────────────────────────────────────────────────
if st.session_state.get(submitted_key):
    results = st.session_state.get(results_key, {})
    total = len(questions)
    correct = sum(1 for r in results.values() if r.get("correct"))
    score_pct = round(correct / total * 100)

    if score_pct >= 80:
        st.success(f"Score: {correct}/{total} ({score_pct}%)")
    elif score_pct >= 50:
        st.warning(f"Score: {correct}/{total} ({score_pct}%)")
    else:
        st.error(f"Score: {correct}/{total} ({score_pct}%)")

    st.divider()

    for i, q in enumerate(questions, 1):
        r = results.get(q.id, {})
        is_correct = r.get("correct", False)
        icon = "✅" if is_correct else "❌"
        verdict = r.get("verdict", "Correct" if is_correct else "Incorrect")

        with st.expander(f"{icon} Q{i}: {q.question_text[:80]}...", expanded=not is_correct):
            st.markdown(f"**{verdict}**")

            if q.question_type == "multiple_choice":
                opts = json.loads(q.options)
                user_ans = r.get("user_answer", "")
                for letter, text in opts.items():
                    if letter == q.correct_answer and letter == user_ans:
                        st.markdown(f"- **{letter}: {text}** ← your answer ✅")
                    elif letter == q.correct_answer:
                        st.markdown(f"- **{letter}: {text}** ← correct answer")
                    elif letter == user_ans:
                        st.markdown(f"- {letter}: {text} ← your answer ❌")
                    else:
                        st.markdown(f"- {letter}: {text}")
                st.info(f"**Explanation:** {q.explanation}")
            else:
                st.markdown(f"**Your answer:** {r.get('user_answer', '—')}")
                st.markdown(f"**Feedback:** {r.get('feedback', '')}")
                if r.get("weak_areas"):
                    st.warning(f"Weak areas: {r['weak_areas']}")

    st.divider()

    col_retry, col_notes_label = st.columns([1, 2])
    with col_retry:
        if st.button("🔁 Retake Test", use_container_width=True):
            clear_test_state()
            st.rerun()

    st.subheader("Personal Notes")
    notes = st.text_area("Add notes from this session", height=100, key=f"notes_{selected_sub.id}")
    if st.button("💾 Save Notes"):
        history = SessionHistory(
            subtopic_id=selected_sub.id,
            activity_type="evaluate",
            notes=notes,
        )
        session.add(history)
        session.commit()
        st.success("Notes saved!")

    session.close()
    st.stop()

# ── TEST-TAKING VIEW ──────────────────────────────────────────────────────────
st.subheader(f"Test: {selected_sub.name}")

with st.form(key=f"eval_form_{selected_sub.id}"):
    form_answers = {}

    for i, q in enumerate(questions, 1):
        st.markdown(f"**Q{i}. {q.question_text}**")

        if q.question_type == "multiple_choice":
            opts = json.loads(q.options)
            option_labels = [f"{k}: {v}" for k, v in opts.items()]
            choice = st.radio(
                f"q{q.id}",
                options=list(opts.keys()),
                format_func=lambda k, o=opts: f"{k}: {o[k]}",
                index=None,
                key=f"eval_ans_{q.id}",
                label_visibility="collapsed",
            )
            form_answers[q.id] = {"type": "multiple_choice", "answer": choice}
        else:
            answer = st.text_area(
                f"q{q.id}_text",
                placeholder="Write your answer here...",
                height=120,
                key=f"eval_ans_{q.id}",
                label_visibility="collapsed",
            )
            form_answers[q.id] = {"type": "text", "answer": answer}

        st.markdown("---")

    submitted = st.form_submit_button("📤 Submit All Answers", use_container_width=True)

if submitted:
    # Validate all questions answered
    unanswered = [
        i + 1 for i, q in enumerate(questions)
        if not form_answers.get(q.id, {}).get("answer")
    ]
    if unanswered:
        st.warning(f"Please answer all questions before submitting. Missing: Q{', Q'.join(map(str, unanswered))}")
    else:
        with st.spinner("Checking answers..."):
            results = {}

            # Check MC questions immediately
            for q in questions:
                if q.question_type == "multiple_choice":
                    user_ans = form_answers[q.id]["answer"]
                    correct = user_ans == q.correct_answer
                    results[q.id] = {
                        "correct": correct,
                        "verdict": "Correct" if correct else "Incorrect",
                        "user_answer": user_ans,
                        "feedback": q.explanation,
                        "weak_areas": "" if correct else q.question_text[:60],
                    }

            # Batch evaluate text questions with Claude
            text_questions = [q for q in questions if q.question_type == "text"]
            if text_questions:
                qa_payload = [
                    {
                        "question": q.question_text,
                        "model_answer": q.model_answer,
                        "explanation": q.explanation,
                        "user_answer": form_answers[q.id]["answer"],
                    }
                    for q in text_questions
                ]
                raw_evals = evaluate_text_answers(qa_payload, selected_sub.name)

                # Parse JSON response
                raw_clean = raw_evals.strip()
                if raw_clean.startswith("```"):
                    raw_clean = raw_clean.split("```")[1]
                    if raw_clean.startswith("json"):
                        raw_clean = raw_clean[4:]
                evals = json.loads(raw_clean.strip())

                for q, ev in zip(text_questions, evals):
                    results[q.id] = {
                        "correct": ev.get("correct", False),
                        "verdict": ev.get("verdict", "Incorrect"),
                        "user_answer": form_answers[q.id]["answer"],
                        "feedback": ev.get("feedback", ""),
                        "weak_areas": ev.get("weak_areas", ""),
                    }

            # Save attempt to DB
            total = len(questions)
            correct_count = sum(1 for r in results.values() if r["correct"])
            score_pct = round(correct_count / total * 100, 1)

            all_weak = ", ".join(
                r["weak_areas"] for r in results.values()
                if r.get("weak_areas")
            )

            attempt = EvalAttempt(
                subtopic_id=selected_sub.id,
                score_pct=score_pct,
                total_questions=total,
                correct_count=correct_count,
                answers=json.dumps({str(qid): r for qid, r in results.items()}),
                weak_spots=all_weak,
            )
            session.add(attempt)

            # Update progress weak areas
            if progress and all_weak:
                existing = progress.weak_areas or ""
                progress.weak_areas = f"{existing}\n{all_weak}".strip()

            # Update progress status based on score
            if progress and score_pct >= 80 and progress.status in (
                ProgressStatus.NOT_STARTED, ProgressStatus.LEARNING, ProgressStatus.PRACTICED
            ):
                progress.status = ProgressStatus.CONFIDENT

            history = SessionHistory(
                subtopic_id=selected_sub.id,
                activity_type="evaluate",
                evaluation_result=f"{correct_count}/{total} ({score_pct}%)",
                weak_spots=all_weak,
            )
            session.add(history)
            session.commit()

            st.session_state[results_key] = results
            st.session_state[submitted_key] = True
            st.rerun()

session.close()
