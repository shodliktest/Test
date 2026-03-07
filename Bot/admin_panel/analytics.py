"""
Analytics - Admin Panel Page
Displays quiz statistics, participation, and score analytics
"""
import streamlit as st
from collections import defaultdict
from datetime import datetime


def render(db_records: list):
    st.markdown("## 📊 Analytics Dashboard")
    st.caption("Detailed statistics, participation metrics, and performance insights.")

    # Parse records by type
    quizzes = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
    sessions = [r for r in db_records if r.get("type") == "SESSION"]
    scores = [r for r in db_records if r.get("type") == "USER_SCORE"]
    results = [r for r in db_records if r.get("type") == "RESULT"]

    # ── Top-Level Metrics ──────────────────────────────────────────────────────
    st.markdown("### 🌐 Platform Overview")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📚 Total Quizzes", len(quizzes))
    c2.metric("🎮 Quiz Sessions", len(sessions))
    c3.metric("👥 Total Attempts", len(scores))

    unique_users = len(set(s.get("user_id") for s in scores))
    c4.metric("🙋 Unique Players", unique_users)

    avg_score_all = 0
    if scores:
        avg_score_all = sum(s.get("score", 0) for s in scores) / len(scores)
    c5.metric("📈 Avg Score", f"{avg_score_all:.1f}%")

    st.divider()

    if not quizzes:
        st.info("📭 No data yet. Create and run some quizzes to see analytics here!")
        return

    # ── Quiz Selector ──────────────────────────────────────────────────────────
    quiz_map = {q["id"]: q for q in quizzes}
    quiz_labels = {q["id"]: q.get("title", q["id"]) for q in quizzes}

    selected_quiz_id = st.selectbox(
        "📚 Select Quiz for Detailed Analytics",
        options=["all"] + list(quiz_labels.keys()),
        format_func=lambda x: "🌍 All Quizzes" if x == "all" else quiz_labels.get(x, x)
    )

    st.divider()

    # ── Filter by quiz ─────────────────────────────────────────────────────────
    if selected_quiz_id == "all":
        filtered_scores = scores
        filtered_sessions = sessions
        view_title = "All Quizzes"
    else:
        filtered_scores = [s for s in scores if s.get("quiz_id") == selected_quiz_id]
        filtered_sessions = [s for s in sessions if s.get("quiz_id") == selected_quiz_id]
        view_title = quiz_labels.get(selected_quiz_id, selected_quiz_id)

    st.markdown(f"### 📋 Stats: {view_title}")

    # ── Key Metrics ────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎮 Sessions Run", len(filtered_sessions))
    col2.metric("👥 Participants", len(filtered_scores))
    col3.metric("🙋 Unique Players", len(set(s.get("user_id") for s in filtered_scores)))

    if filtered_scores:
        avg = sum(s.get("score", 0) for s in filtered_scores) / len(filtered_scores)
        high = max(s.get("score", 0) for s in filtered_scores)
        col4.metric("🏆 Top Score", f"{high:.0f}%")
    else:
        col4.metric("🏆 Top Score", "N/A")

    st.divider()

    # ── Score Distribution ─────────────────────────────────────────────────────
    if filtered_scores:
        st.markdown("#### 📊 Score Distribution")

        buckets = defaultdict(int)
        bucket_labels = ["0-20", "21-40", "41-60", "61-80", "81-100"]
        for s in filtered_scores:
            score = s.get("score", 0)
            if score <= 20:
                buckets["0-20"] += 1
            elif score <= 40:
                buckets["21-40"] += 1
            elif score <= 60:
                buckets["41-60"] += 1
            elif score <= 80:
                buckets["61-80"] += 1
            else:
                buckets["81-100"] += 1

        bar_data = {label: buckets[label] for label in bucket_labels}

        import streamlit as st
        col_bars = st.columns(5)
        max_count = max(bar_data.values()) if bar_data.values() else 1
        colors = ["#ff6b6b", "#ffa94d", "#ffd43b", "#74c0fc", "#69db7c"]
        for i, (label, count) in enumerate(bar_data.items()):
            with col_bars[i]:
                pct = (count / len(filtered_scores) * 100) if filtered_scores else 0
                st.metric(label, count, f"{pct:.1f}%")

        # Pass rate
        pass_count = sum(1 for s in filtered_scores if s.get("score", 0) >= 60)
        pass_rate = (pass_count / len(filtered_scores) * 100) if filtered_scores else 0
        st.progress(pass_rate / 100, text=f"Pass Rate (≥60%): {pass_rate:.1f}% — {pass_count}/{len(filtered_scores)} passed")

    st.divider()

    # ── Top Performers ─────────────────────────────────────────────────────────
    st.markdown("#### 🏆 Top Performers")

    if filtered_scores:
        # Best score per user
        best_scores = {}
        for s in filtered_scores:
            uid = s.get("user_id")
            score = s.get("score", 0)
            if uid not in best_scores or score > best_scores[uid]["score"]:
                best_scores[uid] = s

        top_users = sorted(best_scores.values(), key=lambda x: x.get("score", 0), reverse=True)[:10]
        rank_emojis = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]

        for i, u in enumerate(top_users):
            name = u.get("username") or u.get("first_name", f"User {u.get('user_id', '?')}")
            score = u.get("score", 0)
            correct = u.get("correct", 0)
            total = u.get("total", 0)

            col1, col2, col3, col4 = st.columns([0.5, 3, 1.5, 1.5])
            with col1:
                st.markdown(f"**{rank_emojis[i]}**")
            with col2:
                st.markdown(f"**{name}**")
            with col3:
                st.markdown(f"✅ {correct}/{total}")
            with col4:
                st.markdown(f"**{score:.0f}%**")
    else:
        st.info("No participant data for this quiz yet.")

    st.divider()

    # ── Session History ────────────────────────────────────────────────────────
    st.markdown("#### 📅 Session History")

    if filtered_sessions:
        for s in reversed(filtered_sessions[-10:]):
            sid = s.get("id", "?")
            quiz_title = s.get("quiz_title", "?")
            group = s.get("group_title", "?")
            started = s.get("started_at", "")[:16].replace("T", " ")

            # Count participants for this session
            session_scores = [sc for sc in scores if sc.get("session_id") == sid]
            avg_s = 0
            if session_scores:
                avg_s = sum(sc.get("score", 0) for sc in session_scores) / len(session_scores)

            col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])
            with col1:
                st.caption(f"📅 {started}")
                st.markdown(f"**{quiz_title[:30]}**")
            with col2:
                st.caption("Group")
                st.markdown(f"👥 {group[:25]}")
            with col3:
                st.metric("Players", len(session_scores))
            with col4:
                st.metric("Avg Score", f"{avg_s:.0f}%")
            st.divider()
    else:
        st.info("No session history for this quiz yet.")

    # ── Export ─────────────────────────────────────────────────────────────────
    st.markdown("#### 📥 Export Analytics")
    import json, csv, io

    if filtered_scores:
        # CSV export
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["user_id", "username", "first_name",
                                                      "quiz_id", "session_id", "correct",
                                                      "total", "score", "recorded_at"])
        writer.writeheader()
        for s in filtered_scores:
            writer.writerow({
                "user_id": s.get("user_id", ""),
                "username": s.get("username", ""),
                "first_name": s.get("first_name", ""),
                "quiz_id": s.get("quiz_id", ""),
                "session_id": s.get("session_id", ""),
                "correct": s.get("correct", 0),
                "total": s.get("total", 0),
                "score": s.get("score", 0),
                "recorded_at": s.get("recorded_at", "")
            })

        st.download_button(
            "📥 Export Scores as CSV",
            data=output.getvalue(),
            file_name=f"quiz_results_{selected_quiz_id}.csv",
            mime="text/csv",
            use_container_width=True
        )
