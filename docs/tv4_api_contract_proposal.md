# Đề xuất hợp đồng API từ TV4 đến TV3

Ngày: 07/10/2026. Trạng thái: **DRAFT – chưa được TV3/TV1 xác nhận**.

Căn cứ: Bảng 5.1, mục 5.2 đề cương; nhiệm vụ tuần 1 trong checklist 5 tuần.
Tên endpoint và các trường cấp cao theo đề cương. Cấu trúc lồng nhau, giới hạn,
quy ước lỗi dưới đây là đề xuất để hai bên thống nhất, chưa phải schema chính thức.

## Phạm vi tuần 1

App gọi HTTP bằng requests, đọc API_URL từ môi trường (ví dụ http://localhost:8000).
Backend trả mock cố định. Không cần mô hình hoặc khóa LLM để demo tuần 1.
Ba tab gọi /ask, /learning-path và /analyze-syllabus. /classify-clo có mẫu riêng
để thống nhất hợp đồng; không tạo tab thứ tư trong tuần 1.

Các ví dụ trong `samples/tv4_proposal/` là dữ liệu giả để kiểm tra giao diện,
không phải thông tin môn học đã xác minh. Không dùng làm dữ liệu đánh giá RAG.

## Quy ước chung đề xuất

- Mã môn là string; văn bản UTF-8; tên trường snake_case.
- Thành công trả 200; danh sách không có kết quả trả [] thay vì null.
- /ask và /learning-path nhận application/json; upload PDF dùng multipart/form-data.
- citations[].id khớp số nguồn [n] trong answer; chunk_id khớp retrieved[].chunk_id.
- section là số mục 1–10; page là số trang PDF tính từ 1, cho phép null nếu chưa biết.
- Dữ liệu giả có is_mock: true; khi nối API thật phải tắt cờ và bỏ nhãn mock trên app.
- Danh sách môn: tạm dùng danh sách mẫu chung do TV2/TV3 cung cấp; chưa tự thêm endpoint /courses.

## Các endpoint

| Endpoint | Request | Response app cần |
|---|---|---|
| GET /health | Không body | status, model_version, is_mock |
| POST /ask | question: string không rỗng; course_code: string hoặc null; top_k: integer, mặc định 5 | answer: string; citations: array; retrieved: array |
| POST /learning-path | target: string; completed: string[]; max_credits: integer dương, mặc định 20 | plan: array theo học kỳ; soft_suggestions: array; warnings: string[] |
| POST /analyze-syllabus | Trường file chứa PDF; tên trường **file cần TV3 xác nhận** | syllabus: object; missing_sections: integer[] |
| POST /classify-clo | Một câu: {"text":"..."}; nhiều câu đề xuất {"texts":["..."]} | Một câu trả object; nhiều câu đề xuất {"results":[...]} giữ thứ tự input |

Chi tiết response:

- citation: id, chunk_id, course_code, course_name, section, page, source_file.
- retrieved: chunk_id, course_code, section, page, text, score.
- plan item: term, courses[{course_code, course_name, credits}], total_credits.
- soft_suggestion: before, after, reason. Đây là gợi ý, không phải tiên quyết bắt buộc.
- syllabus: course_code, name_vi, sections[{number,title,text}], clos[{id,text,
  bloom_label,label_name,confidence}], source_file. Các trường khác theo schema của TV2.
- sections chỉ chứa mục tìm thấy; app luôn dựng khung 10 mục và đánh dấu mục thiếu.
- Chưa phân loại CLO: bloom_label, label_name, confidence đều null.
- Kết quả phân loại: label 0–6, label_name, confidence 0–1, probabilities có khóa
  "0"…"6", tổng xác suất bằng 1 trong sai số làm tròn; model_version.

## Lỗi và trạng thái giao diện

Đề cương nêu 400 cho đầu vào không hợp lệ và 422 cho PDF không đọc được;
checklist tuần 1 yêu cầu 422 khi input sai kiểu. Đề xuất phân biệt:

| Tình huống | HTTP | App xử lý |
|---|---|---|
| Sai kiểu hoặc thiếu trường | 422 (validation FastAPI) | Hiển thị lỗi trường nhập |
| Đúng kiểu nhưng sai nghiệp vụ, ví dụ mã môn không tồn tại | 400 | Hiển thị hướng dẫn sửa |
| PDF không đọc được | 422 | Đề nghị chọn PDF khác |
| Dịch vụ ngoài không khả dụng | 503 | Thông báo, vẫn hiện retrieved nếu có |
| Không kết nối được hoặc timeout | Không có HTTP response | Báo API chưa sẵn sàng; giữ dữ liệu nhập |

Lỗi nghiệp vụ đề xuất: {"detail":{"code":"...","message":"..."},"retrieved":[]}.
Lỗi validation FastAPI có detail là array; app cần xử lý cả array và object.
Giao diện có 4 trạng thái: chưa gửi, đang chờ, có kết quả, lỗi; tránh hiện kết quả cũ
như thể thuộc request mới. Khi 503 không có answer, không tự tạo câu trả lời thay backend.

## Các điểm cần TV3 trả lời trước khi chốt ngày 08/10

- [ ] Đồng ý tên trường upload `file`?
- [ ] /analyze-syllabus bọc JSON trong `syllabus` hay trả trực tiếp? Đồng bộ schema TV2.
- [ ] Đồng ý cấu trúc citations/retrieved/plan và cách đánh số nguồn?
- [ ] Request nhiều CLO dùng `texts` hay định dạng khác?
- [ ] Đồng ý phân biệt 400/422/503 như trên?
- [ ] Cung cấp URL API mock, cách chạy, danh sách mã môn mẫu và thời điểm sẵn sàng.
- [ ] Có cần giới hạn top_k, dung lượng PDF, thời gian chờ? TV3 đề xuất con số trước khi triển khai.

## Kiểm tra chung TV3 + TV4

1. /health báo sẵn sàng; cả hai dùng cùng bộ mẫu.
2. Gửi câu hỏi từ tab Hỏi đáp; đối chiếu answer và số nguồn.
3. Chọn môn đích, môn đã học; đối chiếu học kỳ và tổng tín chỉ.
4. Upload PDF bằng multipart; hiển thị mục thiếu và CLO từ response.
5. Tắt API hoặc trả lỗi mock; app báo lỗi và giữ input.
6. Ghi kết luận vào docs/decisions.md sau khi TV1/TV3 thống nhất; cập nhật mẫu
   theo schema chính thức. Không đánh dấu đã chốt chỉ vì có tài liệu đề xuất này.

## Tin nhắn soạn sẵn gửi TV3

> Mình phụ trách TV4. Mình đã phác 3 tab và chuẩn bị bản đề xuất API ở
> docs/tv4_api_contract_proposal.md, mẫu JSON ở samples/tv4_proposal/.
> Nhờ bạn review giúp tên trường upload PDF, cấu trúc response phân tích đề cương,
> citations/retrieved, plan và quy ước lỗi 400/422/503. Bạn cho mình URL/cách chạy
> API mock và danh sách môn mẫu để nối app nhé. Mình đề xuất chốt cùng TV1/TV2
> ngày 08/10; tuần 1 chỉ cần mock đúng schema. Những trường chi tiết trong bản này
> là đề xuất của mình, bạn comment lại chỗ cần sửa giúp mình.
