# TV4 – Công việc ngày 07/10/2026

## Sản phẩm

- Bản phác 3 tab: `docs/wireframes/01-hoi-dap.png`, `02-lo-trinh.png`,
  `03-phan-tich.png`; nguồn dựng ảnh: `render_wireframes.ps1`.
- Đề xuất trao đổi TV3: `docs/tv4_api_contract_proposal.md`.
- Ví dụ request/response: `samples/tv4_proposal/`.

Các bản phác là thiết kế giao diện, chưa phải ứng dụng chạy và chưa gọi API.
Các dữ liệu ví dụ đều là mock. Tài liệu hợp đồng đang chờ review, chưa được chốt.

## Lấy 10 đề cương – đã tải và kiểm tra

Nguồn do người dùng cung cấp:
https://drive.google.com/drive/folders/156D2JvJ0WkuZ6eqOf86Jguii1v3OYR50

Đã lưu 10 PDF tại data/raw/, có 86 trang render được và SHA256 không trùng.
Đã đối chiếu trang đầu, chọn được các môn thuộc 4 khối kiến thức. Xem danh sách
và lưu ý dữ liệu trong [tv4_selected_syllabi.md](tv4_selected_syllabi.md).
Inventory đầy đủ ở data/raw/tv4_inventory.csv, không thay inventory chung của TV2.

Cần TV2 đối chiếu mã Mạng máy tính (tên file 841404 / nội dung 841104) và khối
của hai môn chưa đánh dấu rõ. PDF và inventory không được đưa vào Git theo .gitignore.

Bước tiếp theo: đọc các mục 1, 2, 4, 5, 6, 9 của mỗi môn; ghi nguồn trang cho
ít nhất 30 ý tưởng câu hỏi thuộc tra cứu, nội dung, so sánh, tiên quyết.
Chưa đánh dấu hoàn thành việc đọc lướt toàn bộ hoặc soạn câu hỏi.

## Trạng thái bàn giao

- [x] Có ảnh phác 3 tab, đã kiểm tra bố cục.
- [x] Có đủ 10 PDF từ nguồn cung cấp và đã xác minh mở được.
- [x] Có inventory 10 môn và ghi chú khối kiến thức, điểm cần đối chiếu.
- [x] Có bản đề xuất API, ví dụ JSON hợp lệ và tin nhắn sẵn để người dùng gửi TV3.
- [ ] TV3 đã nhận nội dung trao đổi (soạn sẵn chưa đồng nghĩa đã gửi).
- [ ] TV3/TV1 phản hồi và chốt hợp đồng.
- [ ] PR được review và merge (chưa thực hiện trong công việc phác thảo).
