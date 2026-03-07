"""
Quiz Editor - Admin Panel Page
Edit and manage existing quizzes
"""
import streamlit as st
import json
from datetime import datetime


def render(db_records: list):
    st.markdown("## 📝 Quiz Editor")
    st.caption("View, edit, or delete existing quizzes.")

    # Filter quizzes from DB records
    quizzes = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
    questions_all = [r for r in db_records if r.get("type") == "QUESTION"]

    if not quizzes:
        st.info("📭 No quizzes found in the database. Create one in the **Quiz Creator** tab!")
        return

    # ── Quiz Selection ─────────────────────────────────────────────────────────
    quiz_map = {q["id"]: q for q in quizzes}
    quiz_options = {q["id"]: f"{q.get('title', 'Untitled')} ({q['id']})" for q in quizzes}

    selected_id = st.selectbox(
        "Select Quiz to Edit",
        options=list(quiz_options.keys()),
        format_func=lambda x: quiz_options[x]
    )

    if not selected_id:
        return

    quiz = quiz_map[selected_id]
    quiz_questions = sorted(
        [q for q in questions_all if q.get("quiz_id") == selected_id],
        key=lambda x: x.get("index", 0)
    )

    st.divider()

    # ── Quiz Info ──────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Questions", len(quiz_questions))
    col2.metric("Time per Question", f"{quiz.get('time_per_question', 30)}s")
    col3.metric("Created By", quiz.get("created_by", "?"))
    col4.metric("Status", "✅ Active" if quiz.get("active", True) else "❌ Deleted")

    st.divider()

    # ── Edit Quiz Metadata ─────────────────────────────────────────────────────
    with st.expander("✏️ Edit Quiz Metadata"):
        new_title = st.text_input("Title", value=quiz.get("title", ""))
        new_desc = st.text_area("Description", value=quiz.get("description", ""), height=80)
        new_time = st.slider("Seconds per Question", 10, 120,
                              quiz.get("time_per_question", 30), step=5)

        if st.button("💾 Save Changes", key="save_meta"):
            st.info("🔄 Quiz metadata updates are written as new records in the Telegram DB.")
            st.json({
                "type": "QUIZ",
                "id": selected_id,
                "title": new_title,
                "description": new_desc,
                "time_per_question": new_time,
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "active": True
            })
            st.success("✅ Update record generated. Sync with bot to apply.")

    # ── Question List ──────────────────────────────────────────────────────────
    st.markdown(f"### ❓ Questions ({len(quiz_questions)})")

    if not quiz_questions:
        st.warning("No questions found for this quiz.")
    else:
        for i, q in enumerate(quiz_questions):
            with st.expander(f"Q{i+1}: {q.get('text', '')[:70]}{'...' if len(q.get('text',''))>70 else ''}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Type:** {q.get('question_type', 'multiple_choice')}")
                    st.markdown(f"**Question:** {q.get('text', '')}")

                    options = q.get("options", [])
                    correct_i = q.get("correct_index", 0)
                    opt_labels = ["A", "B", "C", "D"]
                    for j, opt in enumerate(options):
                        marker = "✅" if j == correct_i else "  "
                        label = opt_labels[j] if j < len(opt_labels) else str(j+1)
                        st.markdown(f"{marker} **{label})** {opt}")

                    if q.get("explanation"):
                        st.info(f"💡 {q['explanation']}")
                    if q.get("image_url"):
                        st.caption(f"🖼 Image: {q['image_url']}")

                with col2:
                    st.markdown(f"**Index:** {q.get('index', i)}")

    # ── Delete Quiz ────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🗑️ Danger Zone")

    with st.expander("⚠️ Delete This Quiz"):
        st.warning(f"This will soft-delete quiz **{quiz.get('title')}**. It won't be listed anymore but data is preserved.")
        confirm = st.text_input("Type the quiz title to confirm deletion:")
        if st.button("🗑️ Delete Quiz", type="primary"):
            if confirm == quiz.get("title"):
                # Generate deletion record
                del_record = {
                    "type": "QUIZ",
                    "id": selected_id,
                    "title": quiz.get("title"),
                    "active": False,
                    "deleted_at": datetime.utcnow().isoformat() + "Z"
                }
                st.json(del_record)
                st.error(f"☠️ Quiz **{quiz.get('title')}** marked for deletion. Sync with bot to apply.")
            else:
                st.error("Title doesn't match. Deletion cancelled.")

    # ── Export ─────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📥 Export Quiz")

    export_data = {
        "quiz": quiz,
        "questions": quiz_questions
    }
    export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
    st.download_button(
        "📥 Download as JSON",
        data=export_json,
        file_name=f"quiz_{selected_id}.json",
        mime="application/json",
        use_container_width=True
    )
