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
