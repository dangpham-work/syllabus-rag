# Báo cáo Kỹ thuật – Hệ thống Phân tích Đề cương Môn học (Syllabus RAG)

**Dự án:** Syllabus RAG – Trường Đại học Sài Gòn (SGU)  
**Phiên bản:** v1.0  
**Ngày:** 08/11/2026  
**Nhóm thực hiện:**
- TV1 – Đăng (Tầng mô hình: M2 Bloom, M3 RAG, M4 Lộ trình, API)
- TV2 – Long (Tầng dữ liệu: OCR, trích xuất, gán nhãn M1)
- TV3 – Gia Khôi (Tầng API: FastAPI, schema, unit tests)
- TV4 – (Tầng ứng dụng: Streamlit, kịch bản demo, bộ câu hỏi)

---

## Mục lục

1. [Bài toán và Dữ liệu](#1-bài-toán-và-dữ-liệu)
2. [Kiến trúc và Thuật toán](#2-kiến-trúc-và-thuật-toán)
3. [Tham số và Cấu hình](#3-tham-số-và-cấu-hình)
4. [Kết quả Đánh giá](#4-kết-quả-đánh-giá)

---

## 1. Bài toán và Dữ liệu

### 1.1 Phát biểu bài toán

Đề cương môn học tại SGU tồn tại dưới dạng **PDF scan** với chất lượng OCR không đồng đều. Hệ thống cần giải quyết 4 bài toán con:

| Mô hình | Đầu vào | Đầu ra | Mục tiêu |
|---------|---------|--------|-----------|
| **M1 – Phân loại mục** | Đoạn văn từ đề cương | 1 trong 11 nhãn mục | Macro-F1 ≥ 0,85 |
| **M2 – Phân loại Bloom** | Câu chuẩn đầu ra (CLO) | Mức Bloom 0–6 | Macro-F1 ≥ 0,75 |
| **M3 – Hỏi đáp RAG** | Câu hỏi tiếng Việt | Câu trả lời có trích dẫn | Faithfulness ≥ 90% |
| **M4 – Lộ trình học** | Mã môn mục tiêu + môn đã học | Lịch học theo học kỳ | Không vi phạm tiên quyết |

### 1.2 Corpus dữ liệu

**Nguồn:** 54 đề cương môn học ngành CNTT, Trường Đại học Sài Gòn, định dạng PDF scan.

| Thống kê | Giá trị |
|----------|---------|
| Tổng số đề cương | 54 môn |
| Tổng số trang PDF | ~488 trang |
| Số đoạn văn sau tách mục | 5.693 đoạn |
| Phân chia tập M1 (train/val/test) | 38/8/8 môn (3.854 / 910 / 929 đoạn) |
| Số CLO (chuẩn đầu ra) | Trích từ bảng CLO, xem `data/interim/clos_raw.csv` |
| Số câu hỏi đánh giá M3 (synthetic) | 80 QA pairs |

### 1.3 Pipeline tiền xử lý dữ liệu

```
PDF scan → OCR (Tesseract + PaddleOCR kết hợp) → clean_text.py
         → split_sections.py (tách 10 mục) → make_dataset.py (JSON đề cương)
         → validate_json.py (kiểm tra schema) → extract_clos.py (bảng CLO)
```

**OCR (Quyết định D1 – 12/10/2026):**  
Dùng engine **kết hợp**: Tesseract đọc toàn bộ văn bản (CER 7,4%), PaddleOCR đọc số trình độ trong bảng CLO (36/36 đúng). Lý do: Tesseract vượt trội về chữ tiếng Việt; PaddleOCR vượt trội về nhận dạng số trình độ.

| Engine | CER bảng CLO | F1 cả trang | Số trình độ đúng | Thời gian |
|--------|-------------|------------|-----------------|-----------|
| Tesseract | **7,4%** | **84,9%** | 24/36 | ~1 phút |
| PaddleOCR | 16,2% | 57,1% | 36/36 | ~7,5 giờ |
| **Kết hợp** | **7,4%** | **84,9%** | **36/36** | ~1 phút + trang CLO |

**Tách mục (Quyết định D2 – 18/10/2026):**  
`split_sections.py` nhận diện 10 tiêu đề theo mẫu `<số>. <tên mục>` theo thứ tự, kết hợp luật lỏng cho các trường hợp OCR đọc sai số. Kết quả: **54/54 môn đủ 10 tiêu đề**.

**Gán nhãn M1:** Tiêu đề được tách ra khỏi CSV để mô hình không học từ chính tiêu đề. 54/54 môn có JSON hợp lệ theo `docs/schema_syllabus.json`.

---

## 2. Kiến trúc và Thuật toán

### 2.1 Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│                     Lớp trình bày (TV4)                         │
│         Streamlit app/app.py – 3 tab giao diện                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (requests)
┌───────────────────────────▼─────────────────────────────────────┐
│                     Lớp API (TV3)                               │
│    FastAPI api/main.py – 4 endpoint REST + Swagger /docs        │
│  POST /analyze-syllabus  POST /classify-clo                     │
│  POST /ask               POST /learning-path                    │
└──────┬─────────────────┬────────────┬──────────────────────┬────┘
       │                 │            │                      │
┌──────▼──────┐  ┌───────▼──────┐ ┌──▼──────────────┐ ┌────▼────┐
│ M1 Phân     │  │ M2 Phân      │ │ M3 RAG Pipeline │ │ M4 Lộ   │
│ loại mục    │  │ loại Bloom   │ │ Retrieval + LLM │ │ trình   │
│ TF-IDF +    │  │ E5-small +   │ │ BM25 + Dense    │ │ Topo    │
│ Autoregress │  │ LogReg       │ │ RRF + LambdaMART│ │ Sort +  │
└─────────────┘  └──────────────┘ └─────────────────┘ └─────────┘
```

### 2.2 M1 – Phân loại mục đề cương (11 lớp)

**Phương pháp:** TF-IDF + Đặc trưng vị trí + Giải mã tự hồi quy đơn điệu (Autoregressive Monotonic Decoding)

**11 lớp nhãn:**
`general_info`, `course_description`, `course_objectives`, `course_learning_outcomes`,
`course_content`, `learning_resources`, `teaching_schedule`, `course_policies`,
`assessment`, `responsible_unit`, `other`

**Đặc trưng:**
- TF-IDF từ (n-gram 1–2) + ký tự (n-gram 2–4)
- Vị trí đoạn trong đề cương (normalized position)
- Nhãn của đoạn trước (teacher forcing khi train, autoregressive khi infer)
- Giải mã: quét từ đầu đến cuối, nhãn không được đi lùi (monotonic constraint)

**Lý do chọn:** Quy trình đề cương SGU theo thứ tự cố định 1→10, ràng buộc đơn điệu loại bỏ hoàn toàn lỗi thứ tự không hợp lệ.

### 2.3 M2 – Phân loại mức Bloom (7 lớp, 0–6)

**Thang phân loại:** Bloom–Anderson & Krathwohl (2001), 7 lớp:
- 0: Ngoài miền (out-of-domain)
- 1: Nhớ (Remember)
- 2: Hiểu (Understand)
- 3: Áp dụng (Apply)
- 4: Phân tích (Analyze)
- 5: Đánh giá (Evaluate)
- 6: Sáng tạo (Create)

**Pipeline 3 mô hình (tăng dần độ phức tạp):**

| Mô hình | Phương pháp | Mục đích |
|---------|-------------|----------|
| B0 | Luật động từ hành động | Phát hiện lỗi gán nhãn |
| B1 | TF-IDF (1-2 từ, 2-4 ký tự) + LogReg + GridSearchCV | Baseline nhanh, giải thích được |
| B2 | `multilingual-e5-small` embedding + LogReg head | Tận dụng ngữ nghĩa tiếng Việt |

**Chiến lược đánh giá:** 5-fold StratifiedGroupKFold theo mã môn (tránh rò rỉ ngữ cảnh).

### 2.4 M3 – RAG Pipeline (Retrieval-Augmented Generation)

**Pipeline 3 bước:**

```
Câu hỏi → [1] First-stage Retrieval (RRF)
              BM25 top-30 ⊕ Dense (E5-small) top-30
         → [2] Reranker (LambdaMART, 8 đặc trưng)
              top-20 candidates → top-5 chunks
         → [3] LLM (Gemini / Groq fallback)
              System prompt + context + question → câu trả lời + trích dẫn [1][2]...
```

**8 đặc trưng reranker:**
1. BM25 score
2. Dense cosine similarity score
3. RRF score
4. Độ dài chunk (tokens)
5. Tỷ lệ overlap query–chunk (unigram)
6. Vị trí chunk trong section
7. Boolean: chunk có chứa course_code
8. TF-IDF cosine giữa query và chunk

**Chunking:** Mỗi chunk ~ 1 đoạn văn của một mục, kèm `context_prefix` = tên môn + tên mục.

**So sánh 6 cấu hình retrieval (Quyết định D5 – 29/10/2026):**

| Cấu hình | Recall@5 (ước tính) | Latency/query | Ghi chú |
|----------|--------------------|--------------|----|
| BM25 only | ~0,65 | <0,1 s | Baseline từ khóa |
| Dense only | ~0,72 | ~0,5 s | Baseline ngữ nghĩa |
| RRF | ~0,78 | ~0,6 s | Kết hợp không học |
| RRF + LogReg | ~0,83 | ~0,7 s | Học trọng số tuyến tính |
| **RRF + LambdaMART** | **~0,87** | **~0,8 s** | **Mô hình được chọn** |
| RRF + CrossEncoder | ~0,89 | ~20 s | Yêu cầu GPU |

### 2.5 M4 – Gợi ý lộ trình học (Đồ thị tiên quyết)

**Thuật toán:**
1. **Xây dựng đồ thị:** `PrerequisiteGraph` (DAG) từ trường `prerequisites` trong JSON đề cương.
2. **Sắp xếp topo:** Thuật toán Kahn (1962) với hàm ưu tiên `(recommended_semester, avg_bloom_level)` tăng dần.
3. **Phân bổ tín chỉ:** Greedy packing, tối đa 20 tín chỉ/học kỳ, đảm bảo tiên quyết đã xong trước.

**Input API:** `{course_code, completed_courses[], max_credits_per_term}` → **Output:** lịch học theo học kỳ.

---

## 3. Tham số và Cấu hình

Mọi siêu tham số đọc từ `config/params.yaml` (không viết cứng trong mã nguồn).

### 3.1 Tham số toàn cục

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `random_seed` | 42 | Dùng cho mọi notebook, chia fold, huấn luyện |
| OCR engine | `ket_hop` | Tesseract (chữ) + PaddleOCR (số trình độ) |
| OCR DPI | 300 | Độ phân giải ảnh đầu vào |

### 3.2 M1 – Phân loại mục

| Tham số | Giá trị |
|---------|---------|
| TF-IDF word n-gram | (1, 2) |
| TF-IDF char n-gram | (2, 4) |
| Classifier | Logistic Regression |
| Regularization C | 1.0 |
| Phân chia dữ liệu | 38 train / 8 val / 8 test môn |
| Mô hình lưu tại | `models/section_clf.pkl` |

### 3.3 M2 – Phân loại Bloom

| Tham số | Giá trị |
|---------|---------|
| Số fold CV | 5 (StratifiedGroupKFold theo môn) |
| Class weight | balanced |
| Embedding model (B2) | `intfloat/multilingual-e5-small` |
| PhoBERT max_len | 64 |
| PhoBERT batch_size | 16 |
| PhoBERT lr | 2e-5 |
| Mô hình lưu tại | `models/bloom_model.pkl` |

### 3.4 M3 – Retrieval & RAG

| Tham số | Giá trị |
|---------|---------|
| BM25 top-k | 30 |
| Dense top-k | 30 |
| RRF k | 60 |
| Số ứng viên vào reranker | 20 |
| Số chunks vào LLM (context_k) | 5 |
| Embedding model | `intfloat/multilingual-e5-small` |
| Reranker | LightGBM LambdaMART |
| Reranker n_estimators | 300 |
| Reranker learning_rate | 0,05 |
| LLM provider | Gemini (fallback: Groq) |
| LLM temperature | 0,2 |
| LLM max_tokens | 512 |
| Mô hình lưu tại | `models/reranker.txt` |

### 3.5 M4 – Lộ trình học

| Tham số | Giá trị |
|---------|---------|
| Số tín chỉ tối đa / học kỳ | 20 |
| Thuật toán | Kahn Topological Sort + Greedy Packing |

### 3.6 Cấu hình API & App

| Thành phần | Giá trị mặc định |
|-----------|-----------------|
| API host | `0.0.0.0:8000` |
| App URL | `http://localhost:8000` |
| Framework API | FastAPI + Uvicorn |
| Framework App | Streamlit |
| Biến môi trường | xem `.env.example` |

---

## 4. Kết quả Đánh giá

### 4.1 M1 – Phân loại mục đề cương

**Mục tiêu:** Macro-F1 ≥ 0,85 trên tập test.

| Mô hình | Val Accuracy | Val Macro-F1 | Test Accuracy | Test Macro-F1 |
|---------|-------------|-------------|--------------|--------------|
| Regex baseline | 1,00 | 1,00 | — | — |
| TF-IDF + LogReg (text only) | 0,7187 | 0,7766 | — | — |
| LinearSVC (text only) | 0,7154 | 0,7687 | — | — |
| **TF-IDF + Autoregressive LogReg** | **0,9374** | **0,9132** | **0,9107** | **0,9188** |

> ✅ **Test Macro-F1 = 0,9188 vượt mục tiêu 0,85.**

**Trích xuất trường mục 1** (trên 8 đề cương test):

| Trường | Rule thô (OCR trực tiếp) | Sau sửa tay (`syllabus_fixes.json`) |
|--------|------------------------|-------------------------------------|
| Mã môn | 1,00 | 1,00 |
| Số tín chỉ | 0,875 | **1,00** |
| Tiên quyết (Macro-F1) | 0,375 | **1,00** |
| CLO ID (Macro-F1) | 0,6544 | 0,6544 |
| Latency trung bình | 0,143 s/đề cương | 0,143 s/đề cương |

### 4.2 M2 – Phân loại mức Bloom

**Mục tiêu:** Macro-F1 ≥ 0,75 (5-fold CV).

| Mô hình | CV Macro-F1 (mean ± std) | Ghi chú |
|---------|--------------------------|---------|
| B0 – Rule động từ | Xem notebook 2.0 | Phát hiện nhãn sai |
| B1 – TF-IDF + LogReg | Xem notebook 2.0 | Baseline nhanh |
| B2 – E5-small + LogReg | Xem notebook 2.1 | Mô hình tốt nhất |

> ℹ️ Số liệu CV cụ thể trong `notebooks/modeling/2.0-dd-bloom-baseline.ipynb` và `2.1-dd-bloom-experiments.ipynb`. Cập nhật `results/metrics.json` sau khi chạy notebook trên dữ liệu gán nhãn hoàn chỉnh.

### 4.3 M3 – Truy xuất và RAG

**Mục tiêu Retrieval:** Recall@5 ≥ 0,85 trên 80 synthetic QA pairs.  
**Mục tiêu RAG:** Faithfulness ≥ 90% (đánh giá bằng LLM-as-judge hoặc review tay 50 câu).

**So sánh cấu hình Retrieval** (ước tính lý thuyết, chạy `notebooks/modeling/3.0-dd-retrieval.ipynb` và `3.1-dd-reranker.ipynb` để lấy số thực tế):

| Cấu hình | Recall@5 | MRR@10 | Latency |
|----------|---------|--------|---------|
| BM25 only | ~0,65 | — | <0,1 s |
| Dense only | ~0,72 | — | ~0,5 s |
| RRF | ~0,78 | — | ~0,6 s |
| RRF + LogReg | ~0,83 | — | ~0,7 s |
| **RRF + LambdaMART** | **~0,87** | — | **~0,8 s** |

**RAG end-to-end** (`notebooks/modeling/3.2-dd-rag-evaluation.ipynb`):

| Metric | Mục tiêu | Kết quả |
|--------|---------|---------|
| Faithfulness | ≥ 0,90 | Xem notebook 3.2 |
| Answer relevance | — | Xem notebook 3.2 |
| Context recall | — | Xem notebook 3.2 |
| Out-of-scope detection | — | Xem notebook 3.2 |
| Latency trung bình | — | Xem notebook 3.2 |

### 4.4 M4 – Lộ trình học

Đánh giá qua unit tests (`tests/test_planner.py`):

| Tiêu chí kiểm tra | Kết quả |
|-------------------|---------|
| Không vi phạm chu trình (cycle) | ✅ Pass |
| Thứ tự topo hợp lệ | ✅ Pass |
| Không vượt giới hạn tín chỉ/học kỳ | ✅ Pass |
| 30 truy vấn ngẫu nhiên không lỗi | ✅ Pass |

> ✅ **M4 không có model .pkl; đánh giá hoàn toàn qua unit tests.**

### 4.5 Hiệu năng API

| Endpoint | Phương thức | Trạng thái |
|----------|------------|-----------|
| `GET /health` | — | ✅ |
| `POST /api/v1/analyze-syllabus` | M1 pipeline | ✅ |
| `POST /api/v1/classify-clo` | M2 Bloom | ✅ |
| `POST /api/v1/ask` | M3 RAG | ✅ |
| `POST /api/v1/learning-path` | M4 Planner | ✅ |

**Tests:** 28 unit tests trong `tests/test_api.py` đều pass (mỗi endpoint: HTTP 200 với input hợp lệ, HTTP 422 với input sai kiểu).

---

## Phụ lục A – Cấu trúc Repository

```
syllabus-rag/
├── api/              # FastAPI app (TV3)
├── app/              # Streamlit app (TV4)
├── config/           # params.yaml
├── data/             # raw, interim, processed
├── docs/             # quyết định, schema, hướng dẫn, kịch bản demo
├── models/           # model pkl, metadata
├── notebooks/        # exploratory/, modeling/, inference/
├── reports/          # Báo cáo kỹ thuật (file này)
├── results/          # metrics.json
├── samples/          # input/output mẫu JSON
├── src/syllabus_core/# mã nguồn chính (data, models, retrieval, pathway)
├── tests/            # unit tests
├── requirements.txt  # thư viện khóa phiên bản
├── .env.example      # cấu hình môi trường mẫu
└── README.md         # hướng dẫn cài đặt và chạy
```

## Phụ lục B – Hướng dẫn tái lập

```bash
# 1. Cài đặt
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 2. Cấu hình
cp .env.example .env          # điền GEMINI_API_KEY hoặc GROQ_API_KEY

# 3. Chạy API
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 4. Chạy App (cửa sổ mới)
streamlit run app/app.py

# 5. Chạy tests
pytest tests/ -v

# 6. Tái lập notebook (theo thứ tự)
# notebooks/exploratory/1.0-tv2-data-collection.ipynb
# notebooks/exploratory/1.1-dd-eda.ipynb
# notebooks/exploratory/1.2-tv2-section-classifier.ipynb
# notebooks/modeling/2.0-dd-bloom-baseline.ipynb
# notebooks/modeling/2.1-dd-bloom-experiments.ipynb
# notebooks/modeling/2.2-dd-bloom-error-analysis.ipynb
# notebooks/modeling/3.0-dd-retrieval.ipynb
# notebooks/modeling/3.1-dd-reranker.ipynb
# notebooks/modeling/3.2-dd-rag-evaluation.ipynb
# notebooks/inference/4.0-dd-predict-demo.ipynb
```

## Phụ lục C – Quyết định Kỹ thuật Chính

| Mã | Tiêu đề | Ngày |
|----|---------|------|
| D1 | OCR kết hợp Tesseract + PaddleOCR | 12/10/2026 |
| D2 | Tách mục bằng luật tiêu đề + trích trường mục 1 | 18/10/2026 |
| D3 | M1: Autoregressive Monotonic Decoding | 25/10/2026 |
| D4 | M2: Pipeline B0/B1/B2 Bloom | 29/10/2026 |
| D5 | M3: RRF + LambdaMART reranker | 29/10/2026 |

Chi tiết: `docs/decisions.md`
