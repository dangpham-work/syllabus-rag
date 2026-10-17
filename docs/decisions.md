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
