"""Run: python -m streamlit run app/app.py (from the repository root)."""
from collections import Counter
import os
from pathlib import Path
import re
import sys

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
# Streamlit prepends app/ to sys.path, which can shadow the app package with app.py.
sys.path = [str(ROOT), *[p for p in sys.path if p != str(ROOT)]]
from app.api_client import APIClient, Result

load_dotenv(ROOT / ".env", override=False)
client = APIClient(os.getenv("API_URL", "http://localhost:8000"))

# Only these courses currently have TV3 sample JSON. No invented course catalog.
COURSES = {"841020": "Cơ sở lập trình", "841108": "Cấu trúc dữ liệu và giải thuật", "841401": "Giải tích 1"}
BLOOM = {0: "Ngoài miền nhận thức", 1: "Nhớ", 2: "Hiểu", 3: "Áp dụng", 4: "Phân tích", 5: "Đánh giá", 6: "Sáng tạo"}
# Semantic field mapping; do not reuse the incorrect numeric labels in mock text.
SECTIONS = [
    ("general_info", "Thông tin tổng quát"), ("course_description", "Mô tả học phần"),
    ("course_objectives", "Mục tiêu học phần"), ("course_learning_outcomes", "Chuẩn đầu ra"),
    ("course_content", "Nội dung chi tiết"), ("learning_resources", "Học liệu"),
    ("teaching_schedule", "Hướng dẫn tổ chức dạy học"), ("course_policies", "Quy định"),
    ("assessment", "Phương pháp đánh giá"), ("course_staff", "Phụ trách học phần"),
]


def course_label(code):
    return f"{code} · {COURSES.get(code, 'Môn trong dữ liệu mẫu')}"


def show_chunks(data):
    chunks = data.get("retrieved_chunks", data.get("retrieved", []))
    for i, chunk in enumerate(chunks, 1):
        with st.expander(f"Đoạn {i} · {chunk.get('course_code', '')} · {chunk.get('section', '')}"):
            st.write(chunk.get("content", chunk.get("text", "")))
            st.caption(f"Mã đoạn: {chunk.get('chunk_id', '')}")


st.set_page_config(page_title="Syllabus SGU", page_icon="📚", layout="wide")
st.title("Tra cứu đề cương học phần")
st.caption("SGU · Kỹ thuật phần mềm")
st.warning("Bản thử nghiệm dùng API mock. Kết quả là dữ liệu minh họa, chưa dùng để quyết định học tập.")
with st.sidebar:
    st.header("Kết nối")
    st.caption(f"API: {client.base_url}")
    if st.button("Kiểm tra API", key="health"):
        result = client.request("/health", method="GET")
        if result.error:
            st.error(result.error)
        else:
            st.success(f"API sẵn sàng · {result.data.get('version', '')}")
    st.caption("Có 3 môn mẫu. Danh sách đầy đủ sẽ được bổ sung khi dữ liệu TV2 sẵn sàng.")

qa, pathway, analysis = st.tabs(["Hỏi đáp", "Lộ trình", "Phân tích đề cương"])
with qa:
    st.subheader("Bạn muốn tìm hiểu điều gì?")
    with st.form("ask_form"):
        selected = st.selectbox("Lọc theo môn", [None, *COURSES], format_func=lambda c: "Tất cả môn (mock)" if c is None else course_label(c), key="ask_course")
        question = st.text_area("Câu hỏi", placeholder="Môn Cơ sở lập trình có yêu cầu học trước không?", key="question")
        send = st.form_submit_button("Gửi câu hỏi", key="ask_submit")
    if send:
        st.session_state.pop("ask_result", None)
        if len(question.strip()) < 2:
            st.error("Vui lòng nhập câu hỏi có ít nhất 2 ký tự.")
        else:
            with st.spinner("Đang lấy câu trả lời…"):
                st.session_state.ask_result = (question.strip(), client.ask(question.strip(), selected))
    if "ask_result" in st.session_state:
        submitted_question, result = st.session_state.ask_result
        st.caption(f"Kết quả cho câu đã gửi: {submitted_question}")
        if result.error:
            st.error(result.error)
        else:
            st.write(result.data.get("answer", "API chưa trả câu trả lời."))
            st.markdown("**Nguồn trích dẫn**")
            for citation in result.data.get("citations", []):
                st.caption(f"{citation.get('course_code', '')} · {citation.get('section', '')}")
                st.write(citation.get("quote", ""))
        show_chunks(result.data)

with pathway:
    st.subheader("Phác lộ trình học")
    st.info("Lộ trình hiện là mẫu cố định từ backend; chưa tính theo lựa chọn của bạn.")
    with st.form("path_form"):
        targets = st.multiselect("Môn đích", list(COURSES), format_func=course_label, key="targets")
        completed = st.multiselect("Môn đã hoàn thành", list(COURSES), format_func=course_label, key="completed")
        credits = st.number_input("Tín chỉ tối đa mỗi kỳ", min_value=1, max_value=30, value=20, step=1)
        send_path = st.form_submit_button("Xem lộ trình mẫu", key="path_submit")
    if send_path:
        st.session_state.pop("path_result", None)
        if not targets:
            st.error("Chọn ít nhất một môn đích.")
        elif set(targets) & set(completed):
            st.error("Môn đích đang trùng môn đã hoàn thành. Hãy điều chỉnh lựa chọn.")
        else:
            with st.spinner("Đang lấy kế hoạch…"):
                st.session_state.path_result = (", ".join(targets), client.learning_path(targets, completed, int(credits)))
    if "path_result" in st.session_state:
        submitted_targets, result = st.session_state.path_result
        st.caption(f"Môn đích đã gửi: {submitted_targets}")
        if result.error:
            st.error(result.error)
        else:
            for term in result.data.get("plan", []):
                st.markdown(f"**Học kỳ {term.get('semester')} · {term.get('total_credits', 0)} tín chỉ**")
                st.write(" · ".join(course_label(code) for code in term.get("courses", [])))
            for warning in result.data.get("warnings", []):
                st.warning(warning)
            for suggestion in result.data.get("soft_suggestions", []):
                st.info(suggestion)

with analysis:
    st.subheader("Xem cấu trúc đề cương")
    st.caption("Mock chọn dữ liệu theo mã trong tên tệp. Thử 841020.pdf, 841108.pdf hoặc 841401.pdf; nội dung PDF chưa được OCR.")
    with st.form("analyze_form"):
        pdf = st.file_uploader("Chọn đề cương PDF (tối đa 10 MB)", type=["pdf"], max_upload_size=10, key="pdf")
        analyze = st.form_submit_button("Phân tích PDF", key="analyze_submit")
    if analyze:
        st.session_state.pop("analysis_result", None)
        if pdf is None:
            st.error("Vui lòng chọn PDF trước khi phân tích.")
        elif pdf.size > 10 * 1024 * 1024:
            st.error("Tệp vượt 10 MB. Chọn tệp nhỏ hơn.")
        elif not pdf.getvalue().startswith(b"%PDF-"):
            st.error("Tệp rỗng hoặc không có định dạng PDF.")
        else:
            match = re.search(r"\b(84\d{4})\b", pdf.name)
            expected = match.group(1) if match else None
            if expected not in COURSES:
                st.error("Mock chưa hỗ trợ tên tệp này. Chọn PDF có mã 841020, 841108 hoặc 841401 trong tên để tránh trả nhầm môn.")
            else:
                with st.spinner("Đang gửi PDF…"):
                    result = client.analyze(pdf.name, pdf.getvalue())
                    if not result.error and result.data.get("course_code") != expected:
                        result = Result(error="API trả môn khác với tệp đã gửi. Chưa hiển thị kết quả; cần TV3 kiểm tra.")
                    st.session_state.analysis_result = (pdf.name, result)
    if "analysis_result" in st.session_state:
        filename, result = st.session_state.analysis_result
        st.caption(f"Kết quả cho tệp đã gửi: {filename}")
        if result.error:
            st.error(result.error)
        else:
            data = result.data
            st.markdown(f"**{data.get('course_name', '')} · {data.get('course_code', '')}**")
            st.info("Các mục dưới đây được sắp theo mẫu SGU. Nội dung mock còn có số mục khác; mục Phụ trách học phần chưa có trường tương ứng trong API.")
            sections = data.get("sections", {})
            for index, (key, title) in enumerate(SECTIONS, 1):
                content = sections.get(key)
                with st.expander(f"{index}. {title} · {'Có dữ liệu mẫu' if content else 'API chưa cung cấp'}"):
                    st.write(content or "Chưa đủ dữ liệu để kết luận mục này thiếu trong PDF.")
            if data.get("missing_sections"):
                st.warning("API báo thiếu mục: " + ", ".join(map(str, data["missing_sections"])))
            clos = data.get("clos", [])
            if clos:
                st.markdown("**Chuẩn đầu ra học phần**")
                st.dataframe([{"CLO": c.get("clo_id"), "Nội dung": c.get("text"), "Bloom": BLOOM.get(c.get("bloom_level"), "Chưa phân loại"), "Độ tin cậy": c.get("confidence")} for c in clos], hide_index=True)
                counts = Counter(BLOOM[c["bloom_level"]] for c in clos if c.get("bloom_level") in BLOOM)
                if counts:
                    st.bar_chart(dict(Mức=list(counts), Số_CLO=list(counts.values())), x="Mức", y="Số_CLO")
