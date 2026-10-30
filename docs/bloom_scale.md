# Thang đo Bloom Anderson & Krathwohl và đối chiếu SGU

> **Phiên bản:** v1.0 · **Ngày:** 01/10/2026 · **Tác giả:** TV1 (Đăng – Tầng mô hình)

---

## 1. Giới thiệu

### 1.1 Thang đo Bloom (Anderson & Krathwohl, 2001)

Thang đo Bloom phiên bản sửa đổi (Anderson & Krathwohl, 2001) là khung phân loại mục tiêu nhận thức được sử dụng rộng rãi nhất trong giáo dục đại học. Khung này gồm **6 cấp độ** sắp xếp từ thấp đến cao theo mức độ tư duy:

| Cấp | Tên tiếng Anh | Tên tiếng Việt |
|-----|--------------|---------------|
| 1   | Remember     | Nhớ           |
| 2   | Understand   | Hiểu          |
| 3   | Apply        | Áp dụng       |
| 4   | Analyze      | Phân tích     |
| 5   | Evaluate     | Đánh giá      |
| 6   | Create       | Sáng tạo      |

Mỗi cấp độ mô tả loại hoạt động nhận thức mà người học có thể thực hiện được sau khi hoàn thành khoá học/môn học.

### 1.2 Lý do chọn thang Bloom cho dự án Syllabus RAG

- **Chuẩn quốc tế:** Được ABET, AUN-QA, CDIO và hầu hết các cơ sở GDĐH dùng để kiểm định chương trình.
- **Đồng nhất với SGU:** Đề cương SGU sử dụng "mức trình độ năng lực" (Mức 1–6) ánh xạ 1:1 sang Bloom 1–6.
- **Khả năng tự động hoá:** Danh sách động từ hành động per-level cho phép xây dựng rule-based baseline và đặc trưng cho mô hình ML.

### 1.3 Thêm lớp 0 – "Ngoài miền" (Out-of-domain)

Thực tế đề cương SGU có các CLO mang tính thái độ, kỹ năng mềm hoặc chỉ là chú thích (ví dụ: "Có ý thức trách nhiệm với cộng đồng"). Những CLO này **không thuộc** thang nhận thức Bloom. Dự án bổ sung **lớp 0 – Ngoài miền** để xử lý trường hợp này.

---

## 2. Bảng chi tiết 7 lớp (0–6)

### Lớp 0 – Ngoài miền (Out-of-domain)

**Mô tả:** CLO mang tính thái độ, tình cảm, đạo đức hoặc kỹ năng mềm không thuộc nhận thức Bloom. Thường là động từ trạng thái hoặc mệnh đề về phẩm chất cá nhân.

| Nhóm | Ví dụ động từ/cụm từ điển hình |
|------|-------------------------------|
| Thái độ | có ý thức, tôn trọng, nhiệt tình, chủ động, trách nhiệm |
| Tình cảm | yêu thích, trân trọng, đồng cảm, quan tâm |
| Đạo đức | trung thực, liêm chính, công bằng |
| Kỹ năng mềm | giao tiếp hiệu quả, làm việc nhóm, quản lý thời gian |
| Chú thích | không phải CLO thực (chú thích OCR, ký tự rác) |

**Ví dụ SGU:**
- "Có ý thức bảo vệ quyền sở hữu trí tuệ phần mềm"
- "Tôn trọng các chuẩn mực đạo đức nghề nghiệp CNTT"

---

### Lớp 1 – Nhớ (Remember)

**Mô tả:** Ghi nhớ, nhận ra và tái hiện thông tin đã học. Mức tư duy thấp nhất.

**Động từ hành động (≥ 10):**
`xác định`, `liệt kê`, `nhắc lại`, `trình bày`, `nêu`, `định nghĩa`, `ghi nhớ`, `nhận ra`, `phát biểu`, `chỉ ra`, `đặt tên`, `kể tên`, `sắp xếp theo thứ tự`, `phân biệt (nhận diện)`, `lặp lại`

**Đặc điểm nhận dạng:**
- Câu CLO thường bắt đầu bằng "Trình bày được...", "Nêu được...", "Liệt kê..."
- Không yêu cầu giải thích hay xử lý thêm

**Ví dụ SGU:**
- "Trình bày được các khái niệm cơ bản về mạng máy tính"
- "Liệt kê các loại cấu trúc dữ liệu cơ bản"
- "Nêu định nghĩa và phân loại hệ cơ sở dữ liệu"

---

### Lớp 2 – Hiểu (Understand)

**Mô tả:** Nắm bắt ý nghĩa, diễn giải, tóm tắt và giải thích thông tin bằng lời của mình.

**Động từ hành động (≥ 10):**
`giải thích`, `mô tả`, `diễn giải`, `phân loại`, `tóm tắt`, `so sánh`, `minh họa`, `nhận xét`, `suy luận`, `dự đoán`, `biểu đạt lại`, `phân biệt (hiểu)`, `lý giải`, `chứng minh (lý thuyết)`, `ước lượng`

**Đặc điểm nhận dạng:**
- Câu CLO thường chứa "giải thích", "mô tả", "so sánh"
- Yêu cầu hiểu bản chất, không chỉ nhớ tên

**Ví dụ SGU:**
- "Giải thích được nguyên lý hoạt động của giao thức TCP/IP"
- "Mô tả quá trình biên dịch và thực thi chương trình C"
- "So sánh các mô hình phát triển phần mềm"

---

### Lớp 3 – Áp dụng (Apply)

**Mô tả:** Sử dụng kiến thức/quy trình đã học vào tình huống mới, cụ thể.

**Động từ hành động (≥ 10):**
`áp dụng`, `thực hiện`, `sử dụng`, `lập trình`, `viết code`, `cài đặt`, `triển khai`, `xây dựng`, `giải (bài toán)`, `tính toán`, `vận dụng`, `thao tác`, `thực hành`, `thi công`, `hoàn thành (bài tập)`

**Đặc điểm nhận dạng:**
- Câu CLO thường chứa "áp dụng", "thực hiện", "viết chương trình"
- Ngữ cảnh: bài tập, lab, dự án nhỏ

**Ví dụ SGU:**
- "Áp dụng thuật toán sắp xếp để giải các bài toán thực tế"
- "Viết chương trình Python xử lý chuỗi ký tự"
- "Cài đặt cấu trúc cây nhị phân tìm kiếm bằng ngôn ngữ Java"

---

### Lớp 4 – Phân tích (Analyze)

**Mô tả:** Chia nhỏ thông tin thành các thành phần, xác định mối quan hệ, so sánh và đánh giá cấu trúc.

**Động từ hành động (≥ 10):**
`phân tích`, `so sánh (sâu)`, `phân loại (sâu)`, `kiểm tra`, `lập luận`, `đối chiếu`, `phân rã`, `xác định (quan hệ)`, `suy diễn`, `chỉ ra (điểm yếu)`, `biện luận`, `bóc tách`, `truy vết lỗi`, `đánh giá (cấu trúc)`, `khái quát hóa`

**Đặc điểm nhận dạng:**
- Câu CLO yêu cầu "phân tích", "so sánh ưu/nhược điểm", "xác định nguyên nhân"
- Thường liên quan đến đánh giá nhiều lựa chọn thiết kế

**Ví dụ SGU:**
- "Phân tích ưu và nhược điểm của các thuật toán tìm kiếm"
- "So sánh mô hình quan hệ và mô hình phi quan hệ trong cơ sở dữ liệu"
- "Xác định nguyên nhân và cách khắc phục lỗi trong chương trình"

---

### Lớp 5 – Đánh giá (Evaluate)

**Mô tả:** Đưa ra phán quyết dựa trên tiêu chí rõ ràng; biện hộ cho một lựa chọn.

**Động từ hành động (≥ 10):**
`đánh giá`, `nhận định`, `phê bình`, `bảo vệ (quan điểm)`, `lựa chọn (và lý giải)`, `kiểm định`, `phán xét`, `chứng minh (thực nghiệm)`, `thẩm định`, `xác nhận`, `phản bác`, `kết luận`, `xếp hạng`, `ưu tiên`, `biện hộ`

**Đặc điểm nhận dạng:**
- Câu CLO chứa "đánh giá", "nhận xét", "lựa chọn phương pháp tối ưu"
- Yêu cầu đưa ra tiêu chí và bảo vệ lựa chọn

**Ví dụ SGU:**
- "Đánh giá chất lượng thiết kế hệ thống phần mềm theo tiêu chuẩn ISO 9126"
- "Lựa chọn và lý giải cấu trúc dữ liệu phù hợp cho bài toán cụ thể"
- "Kiểm định hiệu năng hệ thống theo các chỉ số KPI đã xác định"

---

### Lớp 6 – Sáng tạo (Create)

**Mô tả:** Kết hợp các yếu tố thành một sản phẩm/giải pháp mới, đề xuất kế hoạch hoặc thiết kế hoàn chỉnh.

**Động từ hành động (≥ 10):**
`thiết kế`, `xây dựng (hệ thống)`, `phát triển`, `sáng tạo`, `đề xuất`, `lập kế hoạch`, `soạn thảo`, `tổng hợp`, `tạo ra`, `tích hợp`, `khởi tạo`, `cải tiến`, `mô hình hóa`, `nghiên cứu và phát triển`, `hiện thực hoá`

**Đặc điểm nhận dạng:**
- Câu CLO chứa "thiết kế", "phát triển hệ thống", "xây dựng giải pháp"
- Thường là sản phẩm đồ án lớn, nghiên cứu

**Ví dụ SGU:**
- "Thiết kế và cài đặt hệ thống quản lý thư viện theo mô hình MVC"
- "Phát triển ứng dụng web đáp ứng yêu cầu của khách hàng thực"
- "Đề xuất giải pháp cải tiến hiệu năng cho hệ thống hiện có"

---

## 3. Đối chiếu "Mức trình độ năng lực SGU" với thang Bloom

Đề cương môn học SGU sử dụng cột "Mức trình độ" (ký hiệu số 1–6) trong bảng CLO. Bảng dưới đây xác lập ánh xạ 1:1 giữa thang SGU và thang Bloom sửa đổi:

| Mức SGU | Bloom Level | Tên VN      | Tên EN    | Ghi chú |
|---------|-------------|-------------|-----------|---------|
| (0)     | 0           | Ngoài miền  | Out-of-domain | Bổ sung thêm; không có trong thang SGU gốc |
| 1       | 1           | Nhớ         | Remember  | Hoàn toàn tương đương |
| 2       | 2           | Hiểu        | Understand | Hoàn toàn tương đương |
| 3       | 3           | Áp dụng     | Apply     | Hoàn toàn tương đương |
| 4       | 4           | Phân tích   | Analyze   | Hoàn toàn tương đương |
| 5       | 5           | Đánh giá    | Evaluate  | Hoàn toàn tương đương |
| 6       | 6           | Sáng tạo   | Create    | Hoàn toàn tương đương |

### 3.1 Lưu ý về "mức thập phân"

Một số đề cương SGU ghi mức trình độ dưới dạng số thập phân, ví dụ "2,5" hoặc "3-4". Quy tắc xử lý:

| Giá trị OCR | Quy tắc | Bloom Level |
|-------------|---------|-------------|
| `2,5` / `2.5` | Làm tròn lên | 3 |
| `3,4` (danh sách) | Lấy mức cao nhất | 4 |
| `3-4` (khoảng) | Lấy mức cao nhất | 4 |
| Rỗng / OCR lỗi | Nhãn mặc định | 0 (Out-of-domain) |

### 3.2 CLO thái độ trong bảng SGU

Nhiều đề cương SGU có cột "Thái độ" riêng hoặc trộn CLO thái độ vào bảng CLO chính. Mô hình M2 gán nhãn 0 cho những CLO này trước khi đưa vào retrieval.

---

## 4. Kết luận và 5 quy tắc tóm tắt

### 4.1 Kết luận

Thang Bloom Anderson & Krathwohl (2001) là khung chuẩn phù hợp nhất để phân loại chuẩn đầu ra học phần (CLO) của Trường Đại học Sài Gòn. Ánh xạ 1:1 giữa mức trình độ SGU (1–6) và Bloom (1–6) giúp tự động hóa việc kiểm tra chất lượng đề cương mà không cần sửa đổi hệ thống phân loại gốc. Lớp 0 bổ sung để xử lý CLO ngoài miền nhận thức.

### 4.2 5 Quy tắc vàng khi gán nhãn Bloom

> **Quy tắc 1 – Ưu tiên động từ, không phải ngữ cảnh:**
> Bloom level được xác định bởi **động từ hành động** trong câu CLO, không phải chủ đề môn học. "Trình bày" luôn là lớp 1 dù CLO nói về AI hay Triết học.

> **Quy tắc 2 – Động từ mạnh nhất quyết định:**
> Khi CLO có nhiều động từ, lấy động từ có Bloom level **cao nhất**. Ví dụ: "Phân tích và trình bày" → Lớp 4 (Phân tích).

> **Quy tắc 3 – Tách thái độ ra lớp 0:**
> Mọi CLO mang tính phẩm chất (có trách nhiệm, trung thực...) → Lớp 0, không phân loại vào 1–6.

> **Quy tắc 4 – Không nâng Bloom theo độ khó môn:**
> Môn Nhập môn có thể có CLO lớp 3–4 nếu yêu cầu "viết code" hay "thiết kế". Lớp Bloom không phụ thuộc vào cấp độ môn học.

> **Quy tắc 5 – Ưu tiên Bloom thấp hơn khi không chắc:**
> Khi không phân biệt được giữa Lớp 3 và Lớp 4, chọn Lớp 3 (Áp dụng). Mô hình có thể học tinh chỉnh sau khi có thêm dữ liệu nhãn từ người chuyên môn.

---

## Tài liệu tham khảo

1. Anderson, L. W., & Krathwohl, D. R. (Eds.). (2001). *A taxonomy for learning, teaching, and assessing: A revision of Bloom's taxonomy of educational objectives*. Longman.
2. Bloom, B. S. (1956). *Taxonomy of educational objectives: The classification of educational goals. Handbook I: Cognitive domain*. McKay.
3. Trường Đại học Sài Gòn. (2023). *Hướng dẫn xây dựng đề cương môn học theo chuẩn AUN-QA*. SGU Internal Document.
4. Churches, A. (2008). *Bloom's Digital Taxonomy*. Educational Origami.
