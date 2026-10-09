# syllabus-rag
Hệ thống phân tích đề cương môn học kết hợp RAG: Trích xuất cấu trúc đề cương PDF scan, phân loại chuẩn đầu ra Bloom, hỏi đáp có trích dẫn và gợi ý lộ trình học (Trường ĐH Sài Gòn - SGU).

---

## Chạy API (FastAPI Backend - TV3)

Tầng API cung cấp các RESTful endpoints phục vụ trích xuất đề cương, phân loại chuẩn đầu ra (CLO), hỏi đáp RAG và gợi ý lộ trình học tập.

### 1. Cài đặt môi trường

Yêu cầu: Python >= 3.10 (khuyến nghị Python 3.12).

```bash
# Tạo môi trường ảo
python3 -m venv .venv

# Kích hoạt môi trường ảo
# Trên macOS / Linux:
source .venv/bin/activate
# Trên Windows:
# .venv\Scripts\activate

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### 2. Khởi chạy máy chủ API (Development Server)

Khởi chạy máy chủ FastAPI với Uvicorn:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Sau khi khởi chạy:
- **API Base URL**: `http://127.0.0.1:8000`
- **Tài liệu Swagger UI tương tác**: `http://127.0.0.1:8000/docs`
- **Tài liệu ReDoc**: `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json`

### 3. Danh sách Endpoints (Tuần 1 - Mốc 1)

| Phương thức | Đường dẫn (URL) | Mô tả | Định dạng dữ liệu mẫu |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Kiểm tra tình trạng hoạt động của API | `{"status": "ok", "service": "syllabus-rag-api"}` |
| `POST` | `/api/v1/analyze-syllabus` | Trích xuất 10 mục của đề cương (File upload hoặc JSON `file_path`) | Xem `samples/analyze_syllabus_request.json` |
| `POST` | `/api/v1/classify-clo` | Phân loại mức Bloom (0-6) cho CLO (`text` hoặc `texts`) | Xem `samples/classify_clo_request.json` |
| `POST` | `/api/v1/ask` | Hỏi đáp RAG có trích dẫn nguồn bằng chứng | Xem `samples/ask_request.json` |
| `POST` | `/api/v1/learning-path` | Gợi ý lộ trình học theo kỳ kèm môn tiên quyết & tín chỉ | Xem `samples/learning_path_request.json` |

### 4. Kiểm thử nhanh bằng `curl`

Kiểm tra Health Check:
```bash
curl -X GET http://127.0.0.1:8000/health
```

Phân loại mức độ Bloom cho CLO:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/classify-clo \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Áp dụng cấu trúc rẽ nhánh để giải quyết bài toán cơ bản."]}'
```

Hỏi đáp RAG:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Môn Cơ sở lập trình có môn tiên quyết không?", "course_code": "841020"}'
```

Gợi ý lộ trình học:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/learning-path \
  -H "Content-Type: application/json" \
  -d '{"target_courses": ["841108"], "passed_courses": ["841020"]}'
```

### 5. Chạy Unit Tests

```bash
pytest tests/ -v
```

## Chạy app TV4 (Streamlit, Mốc 1)

Sau khi cài `requirements.txt`, mở hai terminal tại thư mục gốc dự án.
Trên Windows PowerShell:

```powershell
# Terminal 1: backend mock TV3
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2: app TV4
$env:API_URL = "http://localhost:8000"
.\.venv\Scripts\python.exe -m streamlit run app/app.py --server.address 127.0.0.1
```

Mở http://localhost:8501. `API_URL` là gốc server, **không kèm /api/v1**;
app tự thêm tiền tố cho endpoint nghiệp vụ. Có thể đặt biến này trong `.env`
ở thư mục gốc; biến môi trường đã đặt được ưu tiên. Không cần khóa Gemini/Groq
để chạy mock. Trên macOS/Linux dùng `.venv/bin/python` và `export API_URL=...`.

- Hỏi đáp: chọn một trong 3 môn mẫu hoặc tất cả, gửi câu hỏi, xem nguồn và đoạn trích.
- Lộ trình: chọn môn đích và môn đã học không trùng nhau, xem kế hoạch mẫu.
- Phân tích: upload PDF thật có mã 841020, 841108 hoặc 841401 trong tên, tối đa 10 MB.
  Ví dụ `data/raw/841020.pdf`; nếu chưa có dữ liệu, tải từ
  [danh sách nguồn](docs/tv4_selected_syllabi.md). Không đổi tên PDF môn khác chỉ để khớp mock.
- Sidebar có nút kiểm tra API. Tắt backend để thử lỗi kết nối; input vẫn được giữ.

### Giới hạn của bản thử nghiệm

Backend chưa OCR hay chạy mô hình thật; lộ trình là fixture cố định. App luôn
hiển thị nhãn mock và chặn PDF có mã chưa hỗ trợ để tránh fallback sai môn.
Schema TV3 mục 6–10 đang chờ thống nhất: app sắp theo ý nghĩa trường về thứ tự
SGU, giữ nguyên nội dung nguồn và báo mục Phụ trách chưa được API cung cấp.
Trường chưa có dữ liệu không được tự coi là mục thiếu trong PDF.

32 câu hỏi nháp nằm trong [docs/question_ideas.md](docs/question_ideas.md).
Checklist và các điểm chờ nhóm xác nhận: [docs/tv4_milestone1.md](docs/tv4_milestone1.md).

Kiểm thử riêng TV4 (tự bật/tắt một API test ở cổng trống; không cần API chạy sẵn):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tv4_app.py -q
```

Các kiểm thử giao diện dùng [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).
