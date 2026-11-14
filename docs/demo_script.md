# Kịch bản Demo Sản phẩm (`Mốc 5`)

Tài liệu hướng dẫn trình diễn 5 tình huống sử dụng chính trên hệ thống Syllabus RAG (FastAPI backend + Streamlit frontend).

## Chuẩn bị trước buổi demo

1. Khởi động Backend API:
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```
2. Khởi động Frontend Streamlit (terminal khác):
   ```bash
   export API_URL=http://localhost:8000
   streamlit run app/app.py
   ```
3. Kiểm tra sidebar hiển thị `🟢 API sẵn sàng` trước khi trình bày.

---

## 5 tình huống trình diễn

### Tình huống 1 — Hỏi đáp tra cứu cụ thể (`POST /ask`)
- **Thao tác:** Vào tab **💬 Hỏi đáp**, nhập câu hỏi: `"Môn Cơ sở lập trình có bao nhiêu tín chỉ và học phần tiên quyết nào?"`, lọc mã môn `841020`, bấm **Tìm kiếm**.
- **Kết quả kỳ vọng:** Câu trả lời nêu số tín chỉ, tiên quyết kèm trích dẫn `[1]`, mở phần **Nguồn trích dẫn** và **Các đoạn đã truy xuất** để đối chiếu.

### Tình huống 2 — Hỏi đáp so sánh / tổng hợp nhiều môn (`POST /ask`)
- **Thao tác:** Để trống bộ lọc mã môn, nhập câu hỏi: `"So sánh chuẩn đầu ra giữa Cơ sở lập trình (841020) và Cấu trúc dữ liệu và giải thuật (841108)?"`.
- **Kết quả kỳ vọng:** Hệ thống truy xuất ngữ cảnh từ cả hai môn và tổng hợp so sánh có trích dẫn `[1]`, `[2]`.

### Tình huống 3 — Hỏi đáp câu ngoài phạm vi (`out_of_scope`)
- **Thao tác:** Nhập `"Lịch thi học kỳ 1 năm nay diễn ra vào ngày nào?"`.
- **Kết quả kỳ vọng:** Hệ thống từ chối trung thực (`"Đề cương không đề cập thông tin này."`), không bịa đặt thông tin.

### Tình huống 4 — Gợi ý lộ trình học (`POST /learning-path`)
- **Thao tác:** Chuyển sang tab **🗺️ Lộ trình học**, nhập mã môn đích `841470`, môn đã học `841020`, bấm **Lên lộ trình**.
- **Kết quả kỳ vọng:** Hiển thị kế hoạch theo từng học kỳ, đảm bảo môn tiên quyết luôn xếp trước môn phụ thuộc và không vượt quá 20 tín chỉ/học kỳ.

### Tình huống 5 — Phân tích đề cương PDF & phân loại Bloom CLO (`POST /analyze-syllabus`)
- **Thao tác:** Chuyển sang tab **📄 Phân tích đề cương**, tải lên tệp PDF mẫu (ví dụ `data/raw/29 - 841020 - Cơ sở lập trình.pdf`), bấm **Phân tích**.
- **Kết quả kỳ vọng:** Hiển thị thông tin chung, bảng 10 mục (kèm cảnh báo mục thiếu nếu có), bảng CLO với nhãn mức Bloom (0–6) và biểu đồ phân bố mức Bloom.

---

## Phương án dự phòng khi mất mạng / lỗi LLM API

- Hệ thống tích hợp sẵn **cache cục bộ** (`logs/rag_cache.json`) theo hash của câu hỏi và danh sách `chunk_id`.
- Chạy trước 5 câu hỏi demo một lần khi có mạng để lưu vào cache; khi mất mạng hoặc hết quota Gemini/Groq, hệ thống vẫn phục vụ câu trả lời từ cache hoặc trả HTTP `503` kèm các `retrieved_chunks` để người dùng kiểm chứng trực tiếp trên giao diện.
