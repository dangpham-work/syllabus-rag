"""
app.py
Ứng dụng Streamlit demo 3 tab: Hỏi đáp, Lộ trình học, Phân tích đề cương.

Chạy:
    streamlit run app/app.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.api_client import APIClient  # noqa: E402

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

BLOOM_COLORS = {
    0: "#95a5a6", 1: "#3498db", 2: "#2ecc71",
    3: "#f39c12", 4: "#e74c3c", 5: "#9b59b6", 6: "#1abc9c",
}
BLOOM_NAMES = {
    0: "Ngoài miền", 1: "Nhớ", 2: "Hiểu",
    3: "Áp dụng", 4: "Phân tích", 5: "Đánh giá", 6: "Sáng tạo",
}


def get_api_url() -> str:
    return os.getenv("API_URL", "http://localhost:8000")


def get_client() -> APIClient:
    return APIClient(get_api_url())


st.set_page_config(
    page_title="Syllabus RAG — SGU",
    page_icon="📚",
    layout="wide",
)

client = get_client()
api_url = get_api_url()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🎓 Đại học Sài Gòn (SGU)")
    st.title("Syllabus RAG")
    st.caption("Hệ thống phân tích đề cương SGU")
    st.markdown("---")

    health_res = client.health()
    if not health_res.error and health_res.data:
        health = health_res.data
        st.success(f"🟢 API sẵn sàng — v{health.get('version', '?')}")
        models = health.get("models_loaded", [])
        if models:
            st.caption(f"Models: {', '.join(models)}")
    else:
        st.error("🔴 API chưa kết nối")
        st.caption(health_res.error or "")

    st.markdown("---")
    st.markdown(f"**API URL:** `{api_url}`")
    st.markdown("**Nhóm:** syllabus-rag | SGU 2026")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs(["💬 Hỏi đáp", "🗺️ Lộ trình học", "📄 Phân tích đề cương"])


# ============================================================
# Tab 1 — Hỏi đáp
# ============================================================

with tab1:
    st.header("💬 Hỏi đáp về đề cương môn học")
    st.caption("Đặt câu hỏi tiếng Việt — hệ thống trả lời có trích dẫn nguồn từ đề cương SGU.")

    with st.form("ask_form"):
        question = st.text_area(
            "Câu hỏi của bạn",
            placeholder="Ví dụ: Môn Công nghệ phần mềm có những chuẩn đầu ra nào?",
            height=100,
            key="question",
        )
        course_filter = st.text_input(
            "Lọc theo mã môn (tuỳ chọn)",
            placeholder="Ví dụ: 841047",
            key="course_filter",
        )
        submitted = st.form_submit_button(
            "🔍 Tìm kiếm",
            key="ask_submit",
            use_container_width=True,
        )

    if submitted:
        if not question.strip():
            st.warning("Vui lòng nhập câu hỏi.")
        else:
            with st.spinner("Đang tìm kiếm và sinh câu trả lời..."):
                res = client.ask(question.strip(), course_filter.strip() or None)

            data = res.data or {}
            chunks = data.get("retrieved_chunks") or data.get("retrieved") or []

            if res.error and not chunks:
                st.error(res.error)
            elif data or chunks:
                is_degraded = bool(res.error)
                if is_degraded:
                    st.warning(f"⚠️ {res.error} — hiển thị các đoạn đã truy xuất.")

                answer = data.get("answer")
                if answer:
                    st.markdown("### 📝 Câu trả lời")
                    st.markdown(answer)
                    provider = data.get("provider_used", "")
                    latency = data.get("latency_ms", 0)
                    st.caption(f"Provider: `{provider}` | Thời gian: {latency}ms")

                citations = data.get("citations", [])
                if citations:
                    st.markdown("### 📌 Nguồn trích dẫn")
                    for c in citations:
                        with st.expander(
                            f"{c.get('ref', '')} — {c.get('course_name', '')} | {c.get('section', '')}"
                        ):
                            st.write(c.get("text_snippet", ""))
                            st.caption(
                                f"Mã môn: `{c.get('course_code', '')}` | chunk: `{c.get('chunk_id', '')}`"
                            )

                if chunks:
                    with st.expander(
                        f"📦 Xem {len(chunks)} đoạn đã truy xuất",
                        expanded=is_degraded,
                    ):
                        for i, chunk in enumerate(chunks, 1):
                            rank = chunk.get("rank", i)
                            cname = chunk.get("course_name") or chunk.get("course_code") or "Đề cương"
                            sec = chunk.get("section", "")
                            score = chunk.get("score", 0.0)
                            st.markdown(f"**#{rank} | {cname} — {sec}** (score: {score:.3f})")
                            st.text(chunk.get("text", "")[:300])
                            st.divider()


# ============================================================
# Tab 2 — Lộ trình học
# ============================================================

with tab2:
    st.header("🗺️ Gợi ý lộ trình học")
    st.caption("Chọn môn đích và đánh dấu các môn đã học — hệ thống lên kế hoạch theo học kỳ.")

    col_a, col_b = st.columns([1, 1])

    with col_a:
        target_course = st.text_input(
            "🎯 Môn học đích",
            placeholder="Ví dụ: 841470",
            help="Nhập mã môn học bạn muốn đạt được",
            key="target_course",
        )

    with col_b:
        completed_raw = st.text_area(
            "✅ Môn đã học (mỗi mã trên một dòng hoặc phân cách bằng dấu phẩy)",
            placeholder="841020\n841401\n841108",
            height=100,
            key="completed_courses",
        )

    if st.button("📋 Lên lộ trình", key="path_submit", use_container_width=True):
        if not target_course.strip():
            st.warning("Vui lòng nhập mã môn đích.")
        else:
            completed = [
                item.strip()
                for item in completed_raw.replace(",", "\n").split("\n")
                if item.strip()
            ]

            with st.spinner("Đang tính toán lộ trình..."):
                res = client.learning_path(target_course.strip(), completed)

            if res.error:
                st.error(res.error)
            elif res.data:
                result = res.data
                plan = result.get("plan", [])
                warnings = result.get("warnings", [])
                suggestions = result.get("soft_suggestions", [])

                st.success(
                    f"✅ Kế hoạch: **{result.get('total_courses', 0)} môn** "
                    f"| **{result.get('total_credits', 0)} tín chỉ** "
                    f"| **{len(plan)} học kỳ**"
                )

                for w in warnings:
                    st.warning(w)

                if suggestions:
                    st.info("💡 Gợi ý:\n" + "\n".join(f"- {s}" for s in suggestions))

                for term in plan:
                    with st.expander(
                        f"📅 Học kỳ {term['term']} — {term['total_credits']} tín chỉ",
                        expanded=True,
                    ):
                        col_count = min(len(term["courses"]), 3) if term["courses"] else 1
                        cols = st.columns(col_count)
                        for i, course in enumerate(term["courses"]):
                            with cols[i % col_count]:
                                st.markdown(
                                    f"""
                                    <div style="padding:10px;border-radius:8px;background:#f0f2f6;margin:4px">
                                        <b>{course['name']}</b><br/>
                                        <code>{course['code']}</code> | {course['credits']} TC
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )


# ============================================================
# Tab 3 — Phân tích đề cương
# ============================================================

with tab3:
    st.header("📄 Phân tích đề cương PDF")
    st.caption("Upload file PDF đề cương — hệ thống trích xuất 10 mục và phân loại mức Bloom cho mỗi CLO.")

    uploaded = st.file_uploader("Chọn file PDF đề cương", type=["pdf"], key="pdf_uploader")

    if uploaded is not None:
        st.info(f"📎 File: **{uploaded.name}** ({uploaded.size // 1024} KB)")

        if st.button("🔬 Phân tích", key="analyze_submit", use_container_width=True):
            with st.spinner("Đang xử lý PDF (OCR → trích xuất → phân loại Bloom)..."):
                res = client.analyze_syllabus(uploaded.name, uploaded.getvalue())

            if res.error:
                st.error(res.error)
            elif res.data:
                result = res.data
                st.success(
                    f"✅ **{result.get('course_name', 'N/A')}** | "
                    f"Mã: `{result.get('course_code', 'N/A')}` | "
                    f"{result.get('credits', 0)} tín chỉ | "
                    f"Xử lý trong {result.get('processing_time_s', 0):.1f}s"
                )

                missing = result.get("missing_sections", [])
                if missing:
                    st.warning(f"⚠️ Thiếu {len(missing)} mục: {', '.join(missing)}")

                sections = result.get("sections", {})
                if sections:
                    st.markdown("### 📋 10 mục đề cương")
                    for i, (sec, text) in enumerate(sections.items(), 1):
                        with st.expander(f"Mục {i}: {sec}", expanded=(i <= 2)):
                            st.write(text[:500] + ("..." if text and len(text) > 500 else ""))

                clos = result.get("clos", [])
                if clos:
                    st.markdown("### 🎯 Chuẩn đầu ra (CLO) và mức Bloom")

                    df_clo = pd.DataFrame([
                        {
                            "CLO": c.get("clo_id", f"CLO{i+1}"),
                            "Nội dung": c.get("text", "")[:100],
                            "Mức Bloom": c.get("bloom_level", "?"),
                            "Tên mức": c.get("bloom_name", "?"),
                            "Tin cậy": (
                                f"{c.get('bloom_confidence', 0):.0%}"
                                if c.get("bloom_confidence")
                                else "N/A"
                            ),
                        }
                        for i, c in enumerate(clos)
                    ])
                    st.dataframe(df_clo, use_container_width=True)

                    bloom_counts = Counter(
                        c.get("bloom_level") for c in clos if c.get("bloom_level") is not None
                    )
                    chart_data = pd.DataFrame([
                        {"Mức Bloom": f"{lvl} - {BLOOM_NAMES.get(lvl, '')}", "Số CLO": cnt}
                        for lvl, cnt in sorted(bloom_counts.items())
                    ])
                    if not chart_data.empty:
                        st.markdown("**Phân bố mức Bloom:**")
                        st.bar_chart(chart_data.set_index("Mức Bloom"))
