# 10 đề cương đã lấy cho TV4

Ngày tải: 07/10/2026. Nguồn: [Drive nhóm](https://drive.google.com/drive/folders/156D2JvJ0WkuZ6eqOf86Jguii1v3OYR50).

Đã tải 10 PDF khác nhau (SHA256 không trùng), mở được và render được toàn bộ 86 trang. Đã xem trang đầu của từng PDF để đối chiếu tên, mã và khối kiến thức; ngày 09/10 đã đọc lướt 40 trang chọn lọc (trang 1, 2 và hai trang cuối mỗi PDF), không phải đọc kỹ toàn bộ 86 trang. Các trang đầu thể hiện mẫu ban hành năm 2020.

Bộ chọn phủ 4 khối được đánh dấu trong tài liệu: 2 đại cương, 2 cơ sở ngành, 4 ngành, 2 chuyên ngành. Ngày 09/10 đọc lại ảnh rõ hơn đã xác nhận Thực tập tốt nghiệp thuộc khối ngành và Thiết kế giao diện thuộc khối chuyên ngành; sửa ghi chú chưa xác định ngày 07/10.

| Mã trong tên tệp | Môn | Khối theo trang 1 | Trang | PDF local | Nguồn |
|---|---|---|---:|---|---|
| 841405 | Xác suất thống kê | Giáo dục đại cương | 8 | [Mở PDF](../data/raw/841405.pdf) | [Drive](https://drive.google.com/file/d/159OJFXw2kbNB76d8qWdl9Wxj2-NzR_HU/view) |
| 841401 | Giải tích 1 | Giáo dục đại cương | 10 | [Mở PDF](../data/raw/841401.pdf) | [Drive](https://drive.google.com/file/d/15KotDyndtFZBn7rODkFq7H8CddM5jNSC/view) |
| 841020 | Cơ sở lập trình | Cơ sở ngành | 8 | [Mở PDF](../data/raw/841020.pdf) | [Drive](https://drive.google.com/file/d/15LzU9EBnqa2ktaEJiau44dUpANpCAoun/view) |
| 841108 | Cấu trúc dữ liệu và giải thuật | Ngành | 10 | [Mở PDF](../data/raw/841108.pdf) | [Drive](https://drive.google.com/file/d/15ItMC60ertXhP1xhqebSHtnfYFVdPhS_/view) |
| 841404 | Mạng máy tính | Cơ sở ngành | 10 | [Mở PDF](../data/raw/841404.pdf) | [Drive](https://drive.google.com/file/d/15J6XSqLHH3u55PTu0hkgHwTBpk-J1cxm/view) |
| 841109 | Cơ sở dữ liệu | Ngành | 10 | [Mở PDF](../data/raw/841109.pdf) | [Drive](https://drive.google.com/file/d/15K7niJY1mbYLlZUeIYinmbWLob6YcVZR/view) |
| 841408 | Kiểm thử phần mềm | Chuyên ngành | 6 | [Mở PDF](../data/raw/841408.pdf) | [Drive](https://drive.google.com/file/d/15EvkSXdBoIEsq2Y_26MFoV7iH1cAuWO4/view) |
| 841047 | Công nghệ phần mềm | Ngành | 8 | [Mở PDF](../data/raw/841047.pdf) | [Drive](https://drive.google.com/file/d/15FBNuFM_eKvT9SDeLv5UB8rnPIgB6MPV/view) |
| 841070 | Thực tập tốt nghiệp | Ngành | 8 | [Mở PDF](../data/raw/841070.pdf) | [Drive](https://drive.google.com/file/d/15G42quStmExZHudtzPiRTdbi-rcJgx3Q/view) |
| 841481 | Thiết kế giao diện | Chuyên ngành | 8 | [Mở PDF](../data/raw/841481.pdf) | [Drive](https://drive.google.com/file/d/15A4GxuFi9xfuDpGZG_v6Wra0qV5BBEau/view) |

## Điểm cần TV2 kiểm tra

- Mạng máy tính: tên tệp ghi **841404**, nhưng mã học phần trên trang 1 là **841104**. Giữ tên lưu theo mã nguồn để dễ truy vết, chưa dùng mã này làm khóa chuẩn cho API hay JSON.
- Khối của Thực tập tốt nghiệp và Thiết kế giao diện đã xác nhận lại ngày 09/10 theo ô đánh dấu trang 1.
- Các thuật ngữ “học phần học trước” và “học phần tiên quyết” khác nhau trong mẫu. Giữ nguyên thuật ngữ khi ghi chú, không tự chuyển tất cả thành cạnh tiên quyết cứng.

## Bàn giao và bước đọc tiếp

- Inventory đầy đủ (nguồn, mã theo tên file và theo nội dung, số trang, SHA256): `data/raw/tv4_inventory.csv`.
- PDF và CSV nằm dưới data/raw/ nên được .gitignore loại khỏi Git; bản danh sách này có thể đưa vào PR.
- Đã soạn 32 câu hỏi nháp có trang/mục nguồn tại [question_ideas.md](question_ideas.md) ngày 09/10; chờ duyệt chéo trước khi dùng làm bộ gold.
- Không OCR lại toàn bộ trong phần việc TV4; phối hợp nhận OCR từ TV2 khi sẵn sàng.
