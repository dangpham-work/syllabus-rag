# syllabus-rag

Hệ thống phân tích đề cương môn học kết hợp RAG cho Trường Đại học Sài Gòn (SGU — Mốc 5): trích xuất cấu trúc đề cương PDF, phân loại chuẩn đầu ra Bloom, hỏi đáp có trích dẫn nguồn và gợi ý lộ trình học theo tiên quyết.

---

## 1. Kiến trúc & Cấu trúc thư mục

```text
syllabus-rag/
├── api/                        # FastAPI backend (REST endpoints & Pydantic v2 schemas)
│   ├── main.py
│   └── schemas.py
├── app/                        # Giao diện Streamlit 3 tab & HTTP client
│   ├── api_client.py
│   └── app.py
├── config/
│   └── params.yaml             # Cấu hình tham số M3 retrieval & LLM
├── data/
│   ├── external/               # DanhMuc_KyThuatPhanMem.xlsx (từ Drive, nếu có)
│   ├── interim/                # Dữ liệu OCR trung gian
│   ├── processed/syllabi/      # Đề cương JSON đã chuẩn hoá (mẫu sẵn: 841020, 841108, 841401)
│   └── raw/                    # PDF gốc (symlink/dữ liệu Drive ngoài git)
├── docs/                       # Tài liệu thiết kế, schema, guideline gán nhãn
├── models/
│   ├── metadata.yaml           # Metadata & version của các mô hình M1/M2/M3
│   └── section_clf.pkl         # Mô hình M1 phân loại 11 mục đề cương
├── notebooks/                  # Notebooks khám phá, huấn luyện & suy luận
├── reports/
│   ├── technical_report.md     # Báo cáo kỹ thuật Mốc 5
│   └── figures/
├── results/
│   ├── latency.json            # Đo độ trễ thực tế (20 requests/endpoint)
│   └── metrics.json            # Chỉ số đánh giá M1/M2/M3
├── samples/                    # Request/Response JSON mẫu & syllabi mẫu
├── src/syllabus_core/          # Mã nguồn lõi: data, features, models, retrieval, pathway, evaluation, visualization
├── tests/                      # Bộ kiểm thử tự động
│   ├── test_m1.py
│   ├── test_planner.py
│   ├── test_api.py
│   └── test_tv4_app.py
├── m1_split.csv                # Bảng chia 54 môn (38 train / 8 val / 8 test)
├── pytest.ini
├── requirements.txt
└── .env.example
```

---

## 2. Cài đặt môi trường (`.venv` + `requirements.txt`)

Yêu cầu Python 3.12 (hoặc >= 3.10).

```bash
# Tạo và kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows PowerShell

# Cài đặt thư viện
pip install -r requirements.txt

# Tạo tệp cấu hình biến môi trường
cp .env.example .env
```

### Lưu ý về dữ liệu Google Drive và API keys (`.env`)

- **Dữ liệu Drive**: Bộ PDF đề cương gốc (`data/raw/*.pdf`), file gán nhãn đầy đủ (`data/processed/sections_labeled.csv`), toàn bộ 54 JSON đề cương và `data/external/DanhMuc_KyThuatPhanMem.xlsx` được lưu ngoài repo trên Google Drive (theo `.gitignore`). Trong repo chỉ đóng gói sẵn `m1_split.csv`, 3 đề cương JSON mẫu (`841020.json`, `841108.json`, `841401.json`) trong `data/processed/syllabi/` và `samples/syllabi/`, cùng artifact `models/section_clf.pkl`. Các test phụ thuộc file PDF/CSV trên Drive sẽ tự động `skip` nếu thiếu tệp ngoài repo.
- **API keys trong `.env`**:
  - `GEMINI_API_KEY` (mặc định) và `GROQ_API_KEY` (dự phòng) dùng cho `/ask` khi gọi LLM thật.
  - Khi cả hai khóa để trống, `RAGPipeline` mặc định chạy ở chế độ `mock` (`RAG_ALLOW_MOCK_FALLBACK=true`) để vẫn có thể thử nghiệm và kiểm thử cục bộ. Nếu đặt `RAG_ALLOW_MOCK_FALLBACK=false` (hoặc khi provider lỗi không có fallback), `/ask` sẽ trả HTTP `503` kèm `retrieved_chunks` và `retrieved` để giao diện hiển thị đoạn truy xuất.
  - `API_URL` mặc định là `http://localhost:8000` (gốc server, không kèm tiền tố `/api/v1`).

---

## 3. Khởi chạy Backend (FastAPI) & Frontend (Streamlit)

Mở 2 terminal tại thư mục gốc `syllabus-rag/`:

**Terminal 1 — FastAPI API:**

```bash
.venv/bin/python3 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

**Terminal 2 — Streamlit App (3 tab: Hỏi đáp, Lộ trình học, Phân tích đề cương):**

```bash
API_URL=http://127.0.0.1:8000 .venv/bin/python3 -m streamlit run app/app.py --server.address 127.0.0.1
```

Truy cập `http://127.0.0.1:8501`.

---

## 4. Danh sách FastAPI Routes & Schemas (`api/main.py`, `api/schemas.py`)

| Phương thức | Đường dẫn | Request | Response chính |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | — | `HealthResponse`: `status`, `version`, `models_loaded` |
| `POST` | `/classify-clo` | `CLOClassifyRequest`: `{text}` hoặc `{texts}` | `CLOClassifyResponse`: `results[]` (`text`, `label`, `label_name`, `confidence`, `probabilities`, `model_version`), `model_version` |
| `POST` | `/classify-clo/batch` | `CLOClassifyBatchRequest`: `{texts}` | `CLOClassifyResponse`: `results[]`, `model_version` |
| `POST` | `/analyze-syllabus` | `multipart/form-data` (`file`: PDF) | `SyllabusAnalysisResponse`: `course_code`, `course_name`, `credits`, `prerequisites`, `clos[]`, `sections{}`, `missing_sections[]`, `model_version`, `processing_time_s` |
| `POST` | `/ask` | `AskRequest`: `{question, course_filter?}` | `200`: `AskResponse` (`answer`, `citations[]`, `retrieved_chunks[]`, `provider_used`, `latency_ms`)<br>`503`: `{error, retrieved_chunks[], retrieved[]}` |
| `POST` | `/learning-path` | `LearningPathRequest`: `{target_course, completed_courses[]}` | `LearningPathResponse`: `target_course`, `plan[]` (`term`, `courses[]`, `total_credits`), `warnings[]`, `soft_suggestions[]`, `total_courses`, `total_credits` |
| `GET` | `/courses` | — | `CourseListResponse`: `courses[]` (`CourseSummary`), `total` |
| `GET` | `/courses/{course_code}` | Path `course_code` | `CourseDetailResponse`: `code`, `name`, `credits`, `prerequisites[]`, `dependents[]`, `avg_bloom_level`, `recommended_semester`, `clos[]`, `sections{}` (`404` nếu không tồn tại) |

### Kiểm thử nhanh bằng `curl`

```bash
# 1. Health check
curl -s http://127.0.0.1:8000/health

# 2. Phân loại CLO đơn lẻ & batch
curl -s -X POST http://127.0.0.1:8000/classify-clo \
  -H "Content-Type: application/json" \
  -d '{"text": "Áp dụng UML để mô hình hoá hệ thống phần mềm"}'

curl -s -X POST http://127.0.0.1:8000/classify-clo/batch \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Liệt kê các kiểu dữ liệu", "Thiết kế kiến trúc MVC"]}'

# 3. Hỏi đáp RAG
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Học phần Cơ sở lập trình có yêu cầu học phần tiên quyết nào không?", "course_filter": "841020"}'

# 4. Gợi ý lộ trình học
curl -s -X POST http://127.0.0.1:8000/learning-path \
  -H "Content-Type: application/json" \
  -d '{"target_course": "841108", "completed_courses": ["841401"]}'

# 5. Danh sách & chi tiết môn học
curl -s http://127.0.0.1:8000/courses
curl -s http://127.0.0.1:8000/courses/841020
```

Các JSON request/response mẫu đầy đủ nằm trong thư mục `samples/`.

---

## 5. Chạy kiểm thử (`pytest`)

Chạy toàn bộ bộ test từ thư mục `syllabus-rag/`:

```bash
.venv/bin/python3 -m pytest tests/ -v
```

Hoặc chạy riêng từng nhóm:

```bash
.venv/bin/python3 -m pytest tests/test_m1.py tests/test_planner.py -v
.venv/bin/python3 -m pytest tests/test_api.py -v
.venv/bin/python3 -m pytest tests/test_tv4_app.py -v
```
