# Đáp án chuẩn (ground truth) để chấm OCR trên 5 đề cương khó

**Dùng để làm gì:** so chữ mà các engine OCR (Tesseract, PaddleOCR) đọc ra từ ảnh scan với bản gõ lại đúng nguyên văn, để tính tỷ lệ đọc sai và chọn engine. Thư mục này **không** phải bộ dữ liệu huấn luyện và **không** chứa toàn bộ 54 đề cương, chỉ có 5 đề cương khó đã chọn để thử nghiệm OCR.

Người phụ trách: TV2 (tầng dữ liệu). Kết quả so sánh engine sẽ nằm ở `docs/ocr_comparison.md`.

## 5 đề cương

| Mã môn | Tên môn | Số trang | Thư mục |
|---|---|---|---|
| 841401 | Giải tích 1 | 10 | `page_text_ground_truth/841401_giai_tich_1/` |
| 841468 | Chuyên đề J2EE | 6 | `page_text_ground_truth/841468_chuyen_de_j2ee/` |
| 841411 | Quản trị mạng | 12 | `page_text_ground_truth/841411_quan_tri_mang/` |
| 841058 | Hệ điều hành mã nguồn mở | 10 | `page_text_ground_truth/841058_he_dieu_hanh_ma_nguon_mo/` |
| 841470 | Tương tác người máy | 6 | `page_text_ground_truth/841470_tuong_tac_nguoi_may/` |

## Cấu trúc và quy ước đặt tên

```
ocr_ground_truth_5_hard_syllabi/
├── README.md                          file này
├── clo_table_ground_truth.csv         bảng chuẩn đầu ra học phần (CLO) của 5 môn, mỗi dòng một CLO
└── page_text_ground_truth/            toàn bộ chữ của từng trang, 44 file
    └── <mã_môn>_<tên_môn_không_dấu>/
        └── page_NN.txt                NN = số trang trong PDF (2 chữ số), ví dụ page_02.txt = trang 2
```

### `clo_table_ground_truth.csv` (UTF-8, có dòng tiêu đề)
| Cột | Ý nghĩa |
|---|---|
| `course_code`, `course_name` | mã và tên môn |
| `clo_id` | ký hiệu chuẩn đầu ra, ví dụ `G1` |
| `text` | mô tả chuẩn đầu ra, chép nguyên văn |
| `level` | "trình độ năng lực" đúng như in trong đề cương (ví dụ `3`, `3.5`, `5.0`), lưu dạng chữ |
| `page` | số trang PDF chứa dòng này (bảng CLO của Giải tích 1 kéo dài sang trang 3) |
| `verified` | `no` = chưa ai đối chiếu với ảnh, `yes` = đã đối chiếu |
| `verified_by` | tên người đối chiếu (để trống khi chưa kiểm) |
| `note` | chỗ chưa chắc chắn |

### `page_NN.txt`
Văn bản thuần, UTF-8. Quy tắc gõ:
- Chép đúng nguyên văn theo thứ tự đọc, **giữ cả lỗi chính tả gốc** (ví dụ "người dung", "Thiếp lập").
- Bảng được chép lần lượt từng ô; mỗi đoạn hoặc dòng của ô là một dòng.
- **Bỏ qua:** số trang, chữ ký, con dấu, chữ viết tay, vệt nhiễu do scan, ô chọn (checkbox).
- Trang trắng là file rỗng.
- Dòng chứa công thức toán, nếu có, được đánh dấu `~` ở đầu dòng để không chấm (hiện chưa gặp dòng nào).

## Trạng thái và độ tin cậy

**Toàn bộ là bản nháp đọc tay từ ảnh trang, chưa có người đối chiếu lại** (`verified = no`). Cần người đối chiếu với ảnh trước khi dùng số liệu chấm làm kết luận chính thức.

Các chỗ đã biết là chưa chắc:
- 841401 trang 1: ảnh mờ, số quyết định và ngày bị chữ viết tay đè lên.
- 841401 trang 2 (G9): chữ "hàm ẩn" bị mờ.
- 841401 trang 9: tên "TS. Phan Hoàng Chơ" bị cắt mép ảnh.
- 841411 trang 1: dòng "Quyết định số…" bị viết tay đè, chép theo mẫu in của các đề cương khác.

## Cách dùng trong code

- `src/syllabus_core/data/ocr_eval.py`: đọc `clo_table_ground_truth.csv` và chấm tỷ lệ lỗi ký tự (CER) cùng độ chính xác của cột `level` cho từng engine.
- `src/syllabus_core/data/ocr_run.py`: chạy engine OCR, tự gọi chấm điểm và ghi kết quả vào `data/interim/ocr_gold/eval_<engine>.csv` (cục bộ, không commit).
- Chữ trong `page_text_ground_truth/` đã sẵn sàng để đối chiếu từng trang, nhưng **chưa có script chấm nào dùng nó**; hiện mới chấm bảng CLO.

Ảnh nguồn: `data/interim/images/<mã_môn>/` do `pdf_to_images.py` tạo từ PDF trong `data/raw/` (không commit). `page_NN` tương ứng trang thứ NN của PDF.
