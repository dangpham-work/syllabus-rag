# Nhật ký quyết định

Mỗi quyết định kỹ thuật quan trọng của dự án ghi một mục: bối cảnh, quyết định, lý do, hạn chế. Mục mới thêm ở cuối.

## D1. Engine OCR: kết hợp Tesseract và PaddleOCR (12/10/2026)

**Người quyết định:** TV2 (tầng dữ liệu) · **Trạng thái:** đã chốt; xem lại nếu kiểm tra trên môn khác cho kết quả khác.

### Bối cảnh
Cần biến 54 đề cương scan thành văn bản để trích bảng CLO và các mục khác. Hai engine miễn phí chạy được trên CPU: Tesseract (gói `vie`) và PaddleOCR. So sánh trên 5 đề cương khó (44 trang, 36 CLO) chấm bằng đáp án chuẩn: chi tiết ở `docs/ocr_comparison.md`.

### Quyết định
Dùng **engine kết hợp** (`ocr.engine: ket_hop` trong `config/params.yaml`):
- **Chữ** của mọi trang lấy từ Tesseract.
- **Số trình độ** của bảng CLO lấy từ PaddleOCR, chỉ chạy trên các trang được nhận là trang CLO, ghép theo thứ tự CLO.

Chạy bằng `src/syllabus_core/data/ocr_run.py --all` (hoặc chọn "Chạy chính thức" trong menu). Kết quả vào `data/interim/ocr/<mã_môn>/` (`p-N.txt` là chữ, `p-N.levels` là số trình độ ở trang CLO).

### Lý do
| | Tesseract | PaddleOCR | Kết hợp |
|---|---|---|---|
| CER bảng CLO | 7,4% | 16,2% | **7,4%** |
| F1 theo từ, cả trang | 84,9% | 57,1% | **84,9%** |
| Số trình độ đúng (lỏng) | 24/36 | 36/36 | **36/36** (theo thứ tự) |
| Thời gian | ~1 phút / 488 trang | ~7,5 giờ / 488 trang | ~1 phút + PaddleOCR trên trang CLO |

Tesseract đọc chữ và dấu tiếng Việt tốt hơn rõ rệt và nhanh hơn nhiều; PaddleOCR đọc số trình độ tốt hơn nhưng rơi nhiều dấu và chậm. Kết hợp lấy phần tốt của từng bên và chỉ chạy PaddleOCR trên một phần nhỏ số trang (8/44 ở 5 môn thử, gồm cả trang nối tiếp của bảng).

### Hạn chế và rủi ro
- **Đáp án chuẩn chưa được người kiểm tra** (`verified = no`), toàn bộ số liệu dựa trên nó.
- **36/36 là kết quả "đã biết đáp án"**: quy tắc nhận trang CLO và bỏ số trang ở chân trang được chỉnh trên chính 5 môn dùng để chấm, nên lạc quan. Chưa thử trên môn khác.
- **Ghép theo thứ tự dễ vỡ khi lệch số lượng**: lệch một mã CLO hoặc một số thì cả trang không ghép được; khi đó danh sách số trình độ để trống chứ không đoán. `clo_pages_report.csv` liệt kê các trang này để kiểm tra tay.
- Chưa thử các biến thể rẻ hơn (Tesseract chạy riêng cho cột trình độ, tiền xử lý ảnh, PaddleOCR với mô hình nhận dạng khác, engine thứ ba).

### Hệ quả
- `docs/ocr_comparison.md` là báo cáo đầy đủ (phương pháp, chỉ số, bảng số liệu, hạn chế).
- Bước tiếp theo: làm sạch văn bản (`clean_text.py`), gắn số trình độ vào từng câu CLO để tạo `clos_raw.csv`, và kiểm tra tay các môn không tìm thấy trang CLO.

## D2. Tách mục bằng luật tiêu đề và trích trường mục 1 (18/10/2026)

**Người quyết định:** TV2 (tầng dữ liệu) · **Trạng thái:** đã chốt cho dữ liệu v1; xem lại nếu thêm đề cương khác mẫu trường.

### Bối cảnh
Tuần 2 cần JSON đề cương 10 mục cho mọi môn và `sections_labeled.csv` (≥ 1.000 đoạn) để TV4 soạn câu hỏi, TV1 chạy BM25 và huấn luyện M1.

### Quyết định
- `split_sections.py`: 10 tiêu đề `<số>. <tên mục>` phải xuất hiện đúng thứ tự 1 đến 10, khớp trên chữ đã bỏ dấu. Mục con như "1. Đánh giá quá trình" trong mục 9 không bị nhận nhầm vì tên không trùng. Mục bị lỡ do OCR đọc sai số mục ("3." thay "9.") được tìm lại bằng luật lỏng trong khoảng giữa hai tiêu đề đã có. Kết quả: 54/54 môn đủ 10 tiêu đề; `section_pages` của 841047 khớp 10/10 với ví dụ điền tay.
- Dòng tiêu đề **không** đưa vào CSV để mô hình M1 không học từ chính tiêu đề. Đoạn trước tiêu đề 1 (bìa) có nhãn `other`.
- `make_dataset.py`: mã môn lấy từ tên file; tên môn lấy từ tên file (sạch dấu hơn OCR); `clos` lấy từ `clos_raw.csv`; `level` = số thập phân của `level_raw` ("2,5" là 2,5; danh sách "3,4" lấy mức cao nhất).
- Số tín chỉ, số tiết, khối kiến thức, tiên quyết: luật trên chữ OCR **chỉ đúng một phần** (so với ảnh: tín chỉ 47/54, khối kiến thức 28/54, đủ 5 loại số tiết 20/54, tiên quyết 39/54) nên cả 54 môn được đọc lại từ ảnh trang 1 và ghi ở `data/interim/syllabus_fixes.json`, tự áp lại mỗi lần chạy.
- Trọng số đánh giá không có trường trong schema đã chốt ở Mốc 1: chữ gốc nằm ở `sections.assessment`. Thêm trường cần báo cả nhóm.

### Hạn chế
- Phần đối chiếu ảnh do một người làm, chưa có người thứ hai kiểm. `provenance.verified = false`.
- `section_gold` chưa được rà tay toàn bộ; đoạn ở ranh giới ghi ở `data/interim/sections_review.csv`.
- Lịch giảng (mục 7) bị tách thành rất nhiều đoạn ngắn (khoảng 1/3 số đoạn) vì mỗi ô bảng là một dòng OCR, làm lệch phân bố lớp của M1.
- Hai môn không mã (STT 74, 80) có mã in trên trang là 841467 và 841068; schema giữ `course_code = null` cho đến khi nhóm quyết định.

### Hệ quả
- `validate_json.py` báo 54/54 hợp lệ. Cần `jsonschema` (chưa thêm vào `requirements.txt`, chờ nhóm đồng ý).

## D3. Mô hình phân loại 11 mục M1 và đóng gói pipeline analyze_pdf (25/10/2026)

**Người quyết định:** TV2 (tầng dữ liệu) · **Trạng thái:** đã chốt cho phiên bản v1; sẵn sàng cho tầng API và Đánh giá.

### Bối cảnh
Tuần 3 cần mô hình học máy M1 phân loại đoạn văn OCR vào 11 lớp (10 mục chuẩn SGU và 1 mục "other" cho bìa/ký tự rác) đạt Macro-F1 ≥ 0,85 trên tập kiểm thử độc lập, khắc phục nhược điểm của luật regex khi OCR làm mất tiêu đề hoặc văn bản tràn trang. Đồng thời cần đóng gói hàm `analyze_pdf(path) -> dict` để tầng API (TV3) nạp vào `/analyze-syllabus` và tầng ứng dụng (TV4) tích hợp demo.

### Quyết định
1. **Phân chia dữ liệu (`data/processed/m1_split.csv`):** 54 đề cương được chia theo mã học phần thành 38 huấn luyện (train), 8 kiểm định (val), và 8 kiểm thử (test) với `random_seed: 42`. Cách chia này đảm bảo không rò rỉ dữ liệu giữa các đề cương có cùng từ vựng, văn phong.
2. **Kiến trúc mô hình M1:**
   - Đặc trưng văn bản: TF-IDF từ (n-gram 1–2, 10.000 chiều) và ký tự (n-gram 2–4, 10.000 chiều).
   - Đặc trưng vị trí: số trang, tỷ lệ trang tương đối, chỉ số đoạn, tỷ lệ vị trí đoạn, độ dài ký tự và số dòng.
   - Ngữ cảnh thứ tự: nhãn của đoạn liền trước (`prev_section`, one-hot).
   - Phân loại bằng Logistic Regression (`C = 5.0`, `class_weight = "balanced"`).
   - Giải mã tự hồi quy (Autoregressive decoding) kết hợp ràng buộc đơn điệu thứ tự mục (mục sau không đi lùi so với mục trước, trừ nhãn "other").
3. **Đóng gói pipeline `analyze_pdf` (`src/syllabus_core/models/predict.py`):**
   - Tiếp nhận tệp PDF (hoặc đường dẫn), kết xuất ảnh, OCR, làm sạch, phân đoạn văn bản, phân loại mục bằng `section_clf.pkl`, và trích xuất các trường thông tin (`course_code`, `course_name`, `credits`, `prerequisites`, `clos`, `sections`, `missing_sections`, `model_version`, `processing_time_s`).
   - Tái sử dụng bộ nhớ cache văn bản sạch khi khả dụng để tối ưu tốc độ phản hồi (~0,14 giây/đề cương).

### Lý do
- Mô hình đạt **Accuracy = 0,9107** và **Macro-F1 = 0,9188** trên 8 đề cương tập Test (929 đoạn), vượt xa chỉ tiêu tối thiểu của đề cương (0,85).
- Thử nghiệm PhoBERT-base trên CPU ước tính mất ~1,5 giờ cho 5 epoch, trong khi Logistic Regression chỉ mất vài giây huấn luyện và phản hồi cực nhanh (~0,14s), phù hợp tối đa cho việc nạp trên CPU của máy chủ REST API.
- Đánh giá trên 8 đề cương test: trích xuất đúng 100% mã môn học, 100% số tín chỉ và tiên quyết (với dữ liệu đã hiệu chỉnh).

### Hạn chế và rủi ro
- Bảng kế hoạch giảng dạy (mục 7) và nội dung chi tiết (mục 5) chiếm số lượng đoạn lớn nhất, một số đoạn ngắn không dấu hiệu vẫn phụ thuộc vào nhãn đoạn trước.
- Trích xuất bảng CLO trên các đề cương OCR mờ nhiều cột vẫn cần đối chiếu bảng thô `clos_raw.csv`.

### Hệ quả
- Mô hình được lưu tại `models/section_clf.pkl`.
- Toàn bộ thí nghiệm, bảng so sánh và ma trận nhầm lẫn được trình bày đầy đủ tại notebook `notebooks/exploratory/1.2-tv2-section-classifier.ipynb`.
- Số liệu đánh giá chính thức được ghi vào `results/metrics.json`.
- Hàm `analyze_pdf` đã sẵn sàng để TV3 import vào endpoint `/analyze-syllabus`.

## D4. Kiến trúc mô hình phân loại Bloom M2 (28/10/2026)

**Người quyết định:** TV1 (tầng mô hình) · **Trạng thái:** đã chốt cho phiên bản v1; xem xét nâng lên embedding đa ngôn ngữ khi đủ dữ liệu.

### Bối cảnh
Tuần 3–4 cần mô hình M2 phân loại CLO vào 7 lớp Bloom (0–6) đạt Macro-F1 ≥ 0,75 trên 5-fold CV theo môn. Dữ liệu đầu vào là `data/processed/clos_labeled.csv` (CLO từ 54 đề cương SGU, đã gán nhãn thủ công). Thách thức: dữ liệu không cân bằng lớp (Lớp 3 chiếm ~40%, Lớp 0/Lớp 6 rất ít).

### Quyết định
**Kiến trúc M2 theo 3 giai đoạn (B0 → B1 → B2):**

1. **B0 – Rule-based baseline:** Tra cứu danh sách động từ hành động định nghĩa trong `docs/labeling_guideline_bloom.md`. Không cần dữ liệu huấn luyện; dùng để đặt ngưỡng tối thiểu.

2. **B1 – TF-IDF + Logistic Regression (5-fold CV theo môn):**
   - Đặc trưng: TF-IDF từ (n-gram 1–2, 5.000 chiều) + ký tự (n-gram 2–4, 3.000 chiều).
   - Cân bằng lớp: `class_weight = "balanced"`.
   - Tìm siêu tham số: `C ∈ {0.1, 0.5, 1.0, 5.0, 10.0}` qua GridSearchCV.
   - Phân chia 5-fold **theo mã môn** (không chia theo CLO) để tránh rò rỉ ngữ cảnh đề cương.

3. **B2 – Multilingual E5 embedding + LogReg đầu:**
   - Embedding: `intfloat/multilingual-e5-small` (model nhỏ nhất, 118M tham số, cân bằng chất lượng và tốc độ CPU).
   - Fallback: TF-IDF + SVD (50 chiều) khi model chưa tải được.
   - Kết hợp embedding với đặc trưng từ vựng B1 (feature concatenation).

**Lưu mô hình tốt nhất:** `models/bloom_model.pkl`.

### Lý do
- **B0** giúp phát hiện lỗi gán nhãn: CLO nào B0 dự đoán khác nhãn thủ công nhiều hơn 2 lớp → cần xem lại.
- **B1** nhanh, đủ tốt, dễ giải thích — phù hợp với kế hoạch 5 tuần không có GPU.
- **B2** sử dụng embedding đa ngôn ngữ để tận dụng context ngữ nghĩa tiếng Việt mà TF-IDF bỏ qua. Dùng model nhỏ nhất (`e5-small`) để chạy CPU trong thời gian hợp lý (<5 phút/lần).
- Phân chia 5-fold theo môn: tương đồng với cách M1 chia (theo mã môn), đảm bảo đánh giá tổng quát hoá thực tế.

### Hạn chế và rủi ro
- Dữ liệu gán nhãn thủ công (~200-400 CLO) có thể chưa đủ để B2 vượt B1 đáng kể.
- Lớp 0 (Out-of-domain) và Lớp 6 (Sáng tạo) có ít mẫu, F1 per-class có thể thấp.
- `multilingual-e5-small` cần kết nối internet lần đầu tải; môi trường offline phải dùng fallback TF-IDF+SVD.

### Hệ quả
- Notebook `notebooks/modeling/2.0-dd-bloom-baseline.ipynb`: B0 + B1 kết quả.
- Notebook `notebooks/modeling/2.1-dd-bloom-experiments.ipynb`: B1 tuning + B2.
- Notebook `notebooks/modeling/2.2-dd-bloom-error-analysis.ipynb`: phân tích lỗi.
- Số liệu ghi vào `results/metrics.json` dưới key `m2_bloom`.
- Hàm `predict_bloom(text) -> dict` export từ `src/syllabus_core/models/predict.py`.

## D5. Chiến lược retrieval M3: RRF + LambdaMART reranker (29/10/2026)

**Người quyết định:** TV1 (tầng mô hình) · **Trạng thái:** đã chốt cho phiên bản v1; xem xét CrossEncoder nếu có GPU.

### Bối cảnh
Tuần 4 cần hệ thống retrieval M3 phục vụ RAG: nhận câu hỏi tiếng Việt về đề cương SGU, trả về top-k chunks liên quan. Mục tiêu: Recall@5 ≥ 0,85 và Faithfulness ≥ 90%. Cần so sánh 6 cấu hình (BM25, Dense, RRF, RRF+LogReg, RRF+LambdaMART, RRF+CrossEncoder).

### Quyết định
**Hệ thống retrieval 3 bước:**

1. **First-stage retrieval:** RRF (Reciprocal Rank Fusion) kết hợp BM25 (top-30) và Dense (top-30, model `intfloat/multilingual-e5-small`). RRF k=60. Trả về top-20 candidates.

2. **Reranker (second-stage):** LambdaMART (`lightgbm` objective=`lambdarank`) với 8 đặc trưng:
   - BM25 score, Dense cosine score, RRF score
   - Độ dài chunk (tokens), Tỷ lệ overlap query-chunk (unigram)
   - Vị trí chunk trong section, Boolean: chunk có chứa course_code không
   - TF-IDF cosine giữa query và chunk

3. **Final output:** Top-5 chunks sau rerank → đưa vào LLM để sinh câu trả lời.

**Lý do chọn LambdaMART:**
- Không cần GPU (CPU-friendly), huấn luyện trên ~80 synthetic QA pairs.
- Tốt hơn LogReg trên bộ dữ liệu nhỏ có ranking objective.
- CrossEncoder (PhoBERT-based) cần GPU hoặc quá chậm trên CPU (~20s/query).

**Lưu model:** `models/reranker.txt` (LightGBM text format).

### Lý do so với các lựa chọn khác

| Cấu hình | Recall@5 (est.) | Latency/query | Ưu điểm | Nhược điểm |
|---------|----------------|--------------|---------|-----------|
| BM25 only | ~0,65 | <0,1s | Không cần model | Bỏ qua ngữ nghĩa |
| Dense only | ~0,72 | ~0,5s | Ngữ nghĩa tốt | Bỏ qua từ khóa |
| RRF | ~0,78 | ~0,6s | Kết hợp tốt nhất 2 cách | Không học được từ dữ liệu |
| RRF+LambdaMART | **~0,87** | ~0,8s | Tốt nhất không cần GPU | Cần synthetic QA data |
| RRF+CrossEncoder | ~0,89 | ~20s/query | Tốt nhất tổng thể | Quá chậm trên CPU |

### Hạn chế và rủi ro
- 80 synthetic QA pairs là dữ liệu nhỏ; Recall@5 thực tế có thể thấp hơn ước tính.
- LambdaMART có thể overfit nếu QA pairs không đa dạng đủ về chủ đề.
- CrossEncoder để trong repo dưới dạng config option để chuyển sang khi có GPU.

### Hệ quả
- `src/syllabus_core/retrieval/index.py`: BM25Index + DenseIndex + build_chunks.
- `src/syllabus_core/retrieval/hybrid.py`: RRF + 6 configs.
- `src/syllabus_core/retrieval/rag.py`: RAGPipeline end-to-end.
- `src/syllabus_core/models/train_reranker.py`: LambdaMART training script.
- Notebooks: `3.0-dd-retrieval.ipynb`, `3.1-dd-reranker.ipynb`, `3.2-dd-rag-evaluation.ipynb`.
- Số liệu ghi vào `results/metrics.json` dưới key `m3_retrieval` và `m3_rag`.
