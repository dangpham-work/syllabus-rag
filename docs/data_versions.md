# Quản lý phiên bản dữ liệu (`data/`)

Thư mục `data/interim/` và `data/processed/` được loại trừ khỏi Git qua `.gitignore` và lưu trữ bản đóng gói trên Google Drive của nhóm.

## Phiên bản `v1` (Mốc 2 – Tuần 2)

| Thành phần | Mô tả | Nguồn / Trạng thái |
|---|---|---|
| `data/raw/` | 54 đề cương PDF scan gốc + `inventory.csv` (đã đánh dấu cặp trùng 48/82, 62/81) | Có sẵn trong repo |
| `data/interim/ocr/` | Kết quả OCR engine kết hợp (Tesseract + PaddleOCR trên trang CLO) | Lưu trên Drive nhóm (`data_v1.zip`) |
| `data/processed/syllabi/` | 54 tệp JSON đề cương hợp lệ theo `docs/schema_syllabus.json` (trong repo giữ 3 tệp mẫu `841020`, `841108`, `841401`) | Đạt 54/54 hợp lệ qua `validate_json.py` (ghi nhận tại D2) |
| `m1_split.csv` | Chia 54 môn theo mã học phần (38 train / 8 val / 8 test, `seed=42`) | Có sẵn tại gốc repo (`m1_split.csv`) |
| `data_v1.zip` MD5 | Checksum gói `data/processed/` trên Drive nhóm | *Chờ TV2 cập nhật checksum MD5 từ Drive nhóm* |

## Quy ước cập nhật
- Mọi chỉnh sửa dữ liệu sau Mốc 2 tạo phiên bản mới (`v1.1`, `v1.2`, ...) kèm lý do và cập nhật bảng này; không ghi đè ngầm dữ liệu đã đóng băng.
