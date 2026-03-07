"""
Quiz Creator - Admin Panel Page
Allows admins to build quizzes with a visual editor
"""
import streamlit as st
import json
import asyncio
from datetime import datetime
from utils.helpers import generate_id, build_quiz_record, build_question_record, format_json_message
from utils.config import config


def render():
    st.markdown("## ✏️ Quiz Creator")
    st.caption("Build a new quiz with questions, options, and timers.")

    # ── Quiz Metadata ──────────────────────────────────────────────────────────
    st.markdown("### 📋 Quiz Details")
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Quiz Title *", placeholder="e.g. Present Simple Test")
        created_by = st.text_input("Created By", value="admin")
    with col2:
        description = st.text_area("Description", placeholder="Brief description of this quiz...", height=100)
        time_per_q = st.slider("⏱ Seconds per Question", 10, 120, 30, step=5)

    st.divider()

    # ── Question Builder ───────────────────────────────────────────────────────
    st.markdown("### ❓ Questions")

    if "questions" not in st.session_state:
        st.session_state.questions = []

    # Add question form
    with st.expander("➕ Add New Question", expanded=len(st.session_state.questions) == 0):
        q_type = st.selectbox("Question Type", [
            "multiple_choice", "true_false", "fill_in_blank"
        ], format_func=lambda x: {
            "multiple_choice": "📋 Multiple Choice (4 options)",
            "true_false": "✅ True / False",
            "fill_in_blank": "✍️ Fill in the Blank"
        }[x])

        q_text = st.text_area("Question Text *", placeholder="Enter your question here...", height=80)

        image_url = st.text_input("Image URL (optional)", placeholder="https://...")

        options = []
        correct_index = 0

        if q_type == "multiple_choice":
            st.markdown("**Answer Options:**")
            col_a, col_b = st.columns(2)
            with col_a:
                opt_a = st.text_input("A)", placeholder="Option A")
                opt_b = st.text_input("B)", placeholder="Option B")
            with col_b:
                opt_c = st.text_input("C)", placeholder="Option C")
                opt_d = st.text_input("D)", placeholder="Option D")
            options = [opt_a, opt_b, opt_c, opt_d]

            correct_label = st.radio("✅ Correct Answer", ["A", "B", "C", "D"], horizontal=True)
            correct_index = {"A": 0, "B": 1, "C": 2, "D": 3}[correct_label]

        elif q_type == "true_false":
            options = ["True", "False"]
            correct_tf = st.radio("✅ Correct Answer", ["True", "False"], horizontal=True)
            correct_index = 0 if correct_tf == "True" else 1

        elif q_type == "fill_in_blank":
            answer_text = st.text_input("Correct Answer *", placeholder="The exact correct answer")
            options = [answer_text, "", "", ""]
            correct_index = 0

        explanation = st.text_input("💡 Explanation (shown after answer)", placeholder="Optional explanation...")

        if st.button("➕ Add Question", type="primary", use_container_width=True):
            if not q_text.strip():
                st.error("Question text is required!")
            elif q_type == "multiple_choice" and not all(options[:2]):
                st.error("At least options A and B are required!")
            elif q_type == "fill_in_blank" and not options[0]:
                st.error("Correct answer is required!")
            else:
                clean_options = [o for o in options if o.strip()]
                st.session_state.questions.append({
                    "text": q_text.strip(),
                    "type": q_type,
                    "options": clean_options,
                    "correct_index": correct_index,
                    "explanation": explanation.strip(),
                    "image_url": image_url.strip()
                })
                st.success(f"✅ Question {len(st.session_state.questions)} added!")
                st.rerun()

    # ── Question List ──────────────────────────────────────────────────────────
    if st.session_state.questions:
        st.markdown(f"**{len(st.session_state.questions)} Question(s) Added:**")
        for i, q in enumerate(st.session_state.questions):
            with st.container():
                col1, col2, col3 = st.columns([0.05, 0.85, 0.1])
                with col1:
                    st.markdown(f"**{i+1}**")
                with col2:
                    q_type_icons = {
                        "multiple_choice": "📋",
                        "true_false": "✅",
                        "fill_in_blank": "✍️"
                    }
                    icon = q_type_icons.get(q.get("type", ""), "❓")
                    st.markdown(f"{icon} {q['text'][:80]}{'...' if len(q['text']) > 80 else ''}")
                    if q.get("explanation"):
                        st.caption(f"💡 {q['explanation'][:60]}")
                with col3:
                    if st.button("🗑", key=f"del_q_{i}", help="Delete question"):
                        st.session_state.questions.pop(i)
                        st.rerun()
                st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Clear All Questions", use_container_width=True):
                st.session_state.questions = []
                st.rerun()
    else:
        st.info("📝 No questions added yet. Use the form above to add questions.")

    st.divider()

    # ── Import from JSON ───────────────────────────────────────────────────────
    with st.expander("📥 Import Questions from JSON"):
        st.caption("Paste a JSON array of questions to bulk import.")
        json_input = st.text_area("JSON Input", height=200, placeholder='''[
  {
    "text": "What is 2+2?",
    "type": "multiple_choice",
    "options": ["3", "4", "5", "6"],
    "correct_index": 1,
    "explanation": "Basic arithmetic"
  }
]''')
        if st.button("📥 Import JSON"):
            try:
                imported = json.loads(json_input)
                if isinstance(imported, list):
                    for q in imported:
                        if "text" in q and "options" in q:
                            st.session_state.questions.append(q)
                    st.success(f"✅ Imported {len(imported)} questions!")
                    st.rerun()
                else:
                    st.error("Expected a JSON array of questions.")
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

    st.divider()

    # ── Preview JSON ───────────────────────────────────────────────────────────
    with st.expander("👁 Preview Generated JSON"):
        if title and st.session_state.questions:
            quiz_id = generate_id("quiz")
            preview = {
                "quiz": build_quiz_record(quiz_id, title, description, created_by,
                                          len(st.session_state.questions), time_per_q),
                "questions": [
                    build_question_record(quiz_id, i, q["text"], q["options"],
                                          q["correct_index"], q.get("type", "multiple_choice"),
                                          q.get("explanation", ""), q.get("image_url", ""))
                    for i, q in enumerate(st.session_state.questions)
                ]
            }
            st.json(preview)
        else:
            st.info("Fill in quiz title and add at least one question to preview.")

    # ── Submit ─────────────────────────────────────────────────────────────────
    st.markdown("### 🚀 Save Quiz")

    can_submit = bool(title.strip() and st.session_state.questions)
    if not can_submit:
        st.warning("⚠️ Please enter a quiz title and add at least one question before saving.")

    if st.button("💾 Save Quiz to Database", type="primary",
                 use_container_width=True, disabled=not can_submit):
        with st.spinner("Saving quiz to Telegram database..."):
            try:
                # Store in session state for the DB writer to pick up
                quiz_id = generate_id("quiz")
                quiz_data = {
                    "id": quiz_id,
                    "title": title.strip(),
                    "description": description.strip(),
                    "created_by": created_by.strip() or "admin",
                    "questions": st.session_state.questions,
                    "time_per_question": time_per_q,
                    "created_at": datetime.utcnow().isoformat() + "Z"
                }

                # Store pending quiz for DB writer
                if "pending_quizzes" not in st.session_state:
                    st.session_state.pending_quizzes = []
                st.session_state.pending_quizzes.append(quiz_data)

                st.success(f"✅ Quiz **{title}** queued for saving! ID: `{quiz_id}`")
                st.info("💡 The quiz will be saved to the Telegram DB group when the bot processes it. Use the bot's admin commands to trigger a sync if needed.")
                st.code(f"Quiz ID: {quiz_id}\nTitle: {title}\nQuestions: {len(st.session_state.questions)}\nTime per Q: {time_per_q}s")

                # Show the JSON that would be sent
                st.markdown("**Records to be stored:**")
                records = []
                q_record = build_quiz_record(quiz_id, title, description, created_by or "admin",
                                              len(st.session_state.questions), time_per_q)
                records.append(q_record)
                for i, q in enumerate(st.session_state.questions):
                    records.append(build_question_record(
                        quiz_id, i, q["text"], q["options"],
                        q["correct_index"], q.get("type", "multiple_choice"),
                        q.get("explanation", ""), q.get("image_url", "")
                    ))
                st.json(records)

                # Clear form
                st.session_state.questions = []

            except Exception as e:
                st.error(f"❌ Error: {e}")
