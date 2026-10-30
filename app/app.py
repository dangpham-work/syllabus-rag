"""
app.py
Ứng dụng Streamlit demo 3 tab: Hỏi đáp, Lộ trình học, Phân tích đề cương.

Chạy:
    streamlit run app/app.py
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Syllabus RAG — SGU",
    page_icon="📚",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(endpoint: str, **kwargs):
    try:
        r = requests.get(f"{API_URL}{endpoint}", timeout=10, **kwargs)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "❌ Không kết nối được API. Hãy chắc chắn uvicorn đang chạy."
    except Exception as e:
        return None, f"❌ Lỗi: {e}"


def api_post(endpoint: str, json_data=None, files=None, timeout=30):
    try:
        r = requests.post(
            f"{API_URL}{endpoint}",
            json=json_data,
            files=files,
            timeout=timeout,
        )
        if r.status_code == 503:
            data = r.json()
            return data, "⚠️ LLM không khả dụng — hiển thị đoạn truy xuất."
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "❌ Không kết nối được API. Hãy chắc chắn uvicorn đang chạy."
    except Exception as e:
        return None, f"❌ Lỗi: {e}"


BLOOM_COLORS = {
    0: "#95a5a6", 1: "#3498db", 2: "#2ecc71",
    3: "#f39c12", 4: "#e74c3c", 5: "#9b59b6", 6: "#1abc9c",
}
BLOOM_NAMES = {
    0: "Ngoài miền", 1: "Nhớ", 2: "Hiểu",
    3: "Áp dụng", 4: "Phân tích", 5: "Đánh giá", 6: "Sáng tạo",
}


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.image("https://www.sgu.edu.vn/sites/default/files/logo_sgu.png", width=100)
    st.title("Syllabus RAG")
    st.caption("Hệ thống phân tích đề cương SGU")
    st.markdown("---")

    # Health check
    health, err = api_get("/health")
    if health:
        st.success(f"🟢 API sẵn sàng — v{health.get('version', '?')}")
        models = health.get("models_loaded", [])
        if models:
            st.caption(f"Models: {', '.join(models)}")
    else:
        st.error("🔴 API chưa kết nối")
        st.caption(err or "")

    st.markdown("---")
    st.markdown(f"**API URL:** `{API_URL}`")
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
        )
        course_filter = st.text_input(
            "Lọc theo mã môn (tuỳ chọn)",
            placeholder="Ví dụ: 841047",
        )
        submitted = st.form_submit_button("🔍 Tìm kiếm", use_container_width=True)

    if submitted:
        if not question.strip():
            st.warning("Vui lòng nhập câu hỏi.")
        else:
            with st.spinner("Đang tìm kiếm và sinh câu trả lời..."):
                payload = {"question": question}
                if course_filter.strip():
                    payload["course_filter"] = course_filter.strip()
                result, err = api_post("/ask", json_data=payload)

            if err and result is None:
                st.error(err)
            elif result:
                if err:
                    st.warning(err)

                # Câu trả lời
                st.markdown("### 📝 Câu trả lời")
                answer = result.get("answer", "Không có câu trả lời.")
                st.markdown(answer)

                provider = result.get("provider_used", "")
                latency = result.get("latency_ms", 0)
                st.caption(f"Provider: `{provider}` | Thời gian: {latency}ms")

                # Citations
                citations = result.get("citations", [])
                if citations:
                    st.markdown("### 📌 Nguồn trích dẫn")
                    for c in citations:
                        with st.expander(f"{c.get('ref', '')} — {c.get('course_name', '')} | {c.get('section', '')}"):
                            st.write(c.get("text_snippet", ""))
                            st.caption(f"Mã môn: `{c.get('course_code', '')}` | chunk: `{c.get('chunk_id', '')}`")

                # Retrieved chunks
                chunks = result.get("retrieved_chunks", [])
                if chunks:
                    with st.expander(f"📦 Xem {len(chunks)} đoạn đã truy xuất"):
                        for chunk in chunks:
                            st.markdown(f"**#{chunk.get('rank')} | {chunk.get('course_name')} — {chunk.get('section')}** (score: {chunk.get('score', 0):.3f})")
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
        )

    with col_b:
        completed_raw = st.text_area(
            "✅ Môn đã học (mỗi mã trên một dòng hoặc phân cách bằng dấu phẩy)",
            placeholder="841020\n841401\n841108",
            height=100,
        )

    if st.button("📋 Lên lộ trình", use_container_width=True):
        if not target_course.strip():
            st.warning("Vui lòng nhập mã môn đích.")
        else:
            # Parse completed courses
            completed = []
            for item in completed_raw.replace(",", "\n").split("\n"):
                item = item.strip()
                if item:
                    completed.append(item)

            with st.spinner("Đang tính toán lộ trình..."):
                result, err = api_post("/learning-path", json_data={
                    "target_course": target_course.strip(),
                    "completed_courses": completed,
                })

            if err and result is None:
                st.error(err)
            elif result:
                plan = result.get("plan", [])
                warnings = result.get("warnings", [])
                suggestions = result.get("soft_suggestions", [])

                st.success(
                    f"✅ Kế hoạch: **{result.get('total_courses', 0)} môn** "
                    f"| **{result.get('total_credits', 0)} tín chỉ** "
                    f"| **{len(plan)} học kỳ**"
                )

                if warnings:
                    for w in warnings:
                        st.warning(w)

                if suggestions:
                    st.info("💡 Gợi ý:\n" + "\n".join(f"- {s}" for s in suggestions))

                # Hiển thị kế hoạch theo học kỳ
                for term in plan:
                    with st.expander(f"📅 Học kỳ {term['term']} — {term['total_credits']} tín chỉ", expanded=True):
                        cols = st.columns(len(term["courses"]) if term["courses"] else 1)
                        for i, course in enumerate(term["courses"]):
                            with cols[i % len(cols)]:
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

    uploaded = st.file_uploader("Chọn file PDF đề cương", type=["pdf"])

    if uploaded is not None:
        st.info(f"📎 File: **{uploaded.name}** ({uploaded.size // 1024} KB)")

        if st.button("🔬 Phân tích", use_container_width=True):
            with st.spinner("Đang xử lý PDF (OCR → trích xuất → phân loại Bloom)..."):
                result, err = api_post(
                    "/analyze-syllabus",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                    timeout=60,
                )

            if err and result is None:
                st.error(err)
            elif result:
                # Header
                st.success(
                    f"✅ **{result.get('course_name', 'N/A')}** | "
                    f"Mã: `{result.get('course_code', 'N/A')}` | "
                    f"{result.get('credits', 0)} tín chỉ | "
                    f"Xử lý trong {result.get('processing_time_s', 0):.1f}s"
                )

                # Missing sections
                missing = result.get("missing_sections", [])
                if missing:
                    st.warning(f"⚠️ Thiếu {len(missing)} mục: {', '.join(missing)}")

                # Sections table
                sections = result.get("sections", {})
                if sections:
                    st.markdown("### 📋 10 mục đề cương")
                    for i, (sec, text) in enumerate(sections.items(), 1):
                        with st.expander(f"Mục {i}: {sec}", expanded=(i <= 2)):
                            st.write(text[:500] + ("..." if text and len(text) > 500 else ""))

                # CLO table + Bloom chart
                clos = result.get("clos", [])
                if clos:
                    st.markdown("### 🎯 Chuẩn đầu ra (CLO) và mức Bloom")

                    # Table
                    import pandas as pd
                    df_clo = pd.DataFrame([{
                        "CLO": c.get("clo_id", f"CLO{i+1}"),
                        "Nội dung": c.get("text", "")[:100],
                        "Mức Bloom": c.get("bloom_level", "?"),
                        "Tên mức": c.get("bloom_name", "?"),
                        "Tin cậy": f"{c.get('bloom_confidence', 0):.0%}" if c.get("bloom_confidence") else "N/A",
                    } for i, c in enumerate(clos)])
                    st.dataframe(df_clo, use_container_width=True)

                    # Bloom distribution chart
                    from collections import Counter
                    bloom_counts = Counter(c.get("bloom_level") for c in clos if c.get("bloom_level") is not None)
                    chart_data = pd.DataFrame([
                        {"Mức Bloom": f"{lvl} - {BLOOM_NAMES.get(lvl, '')}", "Số CLO": cnt}
                        for lvl, cnt in sorted(bloom_counts.items())
                    ])
                    if not chart_data.empty:
                        st.markdown("**Phân bố mức Bloom:**")
                        st.bar_chart(chart_data.set_index("Mức Bloom"))
