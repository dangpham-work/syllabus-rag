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
