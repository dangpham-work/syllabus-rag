# TV4 – Bàn giao triển khai Mốc 1

Ngày: 09/10/2026. Nhánh: `feat/tv4-streamlit-milestone1`, tách từ nhánh chuẩn bị
sau khi merge main tại commit 1498bdb (có API TV3 từ PR #69).

## Sản phẩm đã làm

- [x] Wireframe 3 tab trong docs/wireframes/.
- [x] Streamlit 3 tab trong app/app.py; gọi HTTP qua app/api_client.py bằng requests.
- [x] API_URL từ môi trường hoặc .env; có health check, timeout, lỗi thân thiện.
- [x] Hỏi đáp hiển thị answer, citations, retrieved_chunks; hỗ trợ phần trích còn lại khi 503 có trả dữ liệu.
- [x] Lộ trình gửi target_courses/passed_courses/max_credits_per_semester; ghi rõ mock cố định.
- [x] Phân tích gửi multipart trường file; bảng 10 mục theo SGU, CLO, phân bố Bloom.
- [x] Chặn hiển thị nhầm môn khi tên tệp chưa được mock hỗ trợ hoặc response sai course_code.
- [x] 10 PDF đã tải; đọc lướt 40 trang chọn lọc (trang 1, 2 và hai trang cuối mỗi PDF).
- [x] 32 câu hỏi nháp đủ 4 loại, có trang/mục nguồn, trong docs/question_ideas.md.
- [x] Có kiểm thử app với HTTP thật tới mock API, luồng lỗi và giữ input.
- [ ] TV1/TV3/TV2 xác nhận schema và xử lý các khác biệt còn lại.
- [ ] Câu hỏi được thành viên khác review (bộ gold thuộc tuần sau).
- [ ] PR được review và TV1 merge. Các dấu x trên là bằng chứng triển khai local,
  chưa thay thế điều kiện nghiệm thu chung của nhóm.

## Hợp đồng đang dùng

Không sửa backend TV3 trong nhánh này. Bản tv4_api_contract_proposal.md và
samples/tv4_proposal/ là đề xuất lịch sử, không phải hợp đồng app đang chạy.

| Thành phần | Hợp đồng PR #69 |
|---|---|
| Base URL | Server root; health tại /health; nghiệp vụ tại /api/v1/* |
| /ask | question, course_code, top_k → answer, citations, retrieved_chunks |
| /learning-path | target_courses, passed_courses, max_credits_per_semester → plan (semester/courses/total_credits), soft_suggestions, warnings |
| /analyze-syllabus | multipart file → object trực tiếp, course_name, sections dạng object, clos có clo_id/bloom_level |
| Lỗi | detail có thể string, object hoặc array; giữ retrieved/retrieved_chunks nếu có |

## Điểm chờ phối hợp

1. TV3 + TV2: chốt mục 6–10 theo mẫu SGU, thêm thông tin phụ trách học phần;
   frontend hiện ánh xạ theo ý nghĩa và ghi chú số mục mock có thể chưa khớp.
2. TV3: xác thực file_path JSON; không âm thầm bỏ câu CLO sai kiểu hoặc trả môn
   khác khi thiếu fixture. App tránh đường file_path và chỉ upload 3 môn có fixture.
3. TV2: mã Mạng máy tính trong tên tệp khác nội dung (841404/841104).
4. TV3: JSON mock Cơ sở lập trình và Cấu trúc dữ liệu khác tài liệu gốc về học trước.
   Mock không dùng làm đáp án hoặc dữ liệu gán nhãn.
5. TV1 + TV2: Thực tập tốt nghiệp mục 1 ghi không tiên quyết nhưng mục 8 yêu cầu
   học trước 841048 và 841047. Giữ cả hai thông tin để đối chiếu.

## Demo nghiệm thu local

Kiểm tra lại trước khi mở PR ngày 10/10/2026: **34/34 test pass**,
`git diff --check` không có lỗi whitespace; origin/main không có commit mới
chưa tích hợp. Sản phẩm TV4 tuần 1 đã sẵn sàng để nhóm review; chưa đánh dấu
nghiệm thu cuối cùng trước khi có người duyệt và TV1 merge.

Bằng chứng ngày 09/10: `python -m pytest tests/ -q` đạt **34 passed**
(28 test backend + 6 ca TV4); còn một cảnh báo deprecation từ Starlette/httpx.
Đã mở app trong trình duyệt, gửi câu hỏi và upload PDF 841020 thật; đồng thời
kiểm tra HTTP với 3 PDF thật 841020/841108/841401, đều trả đúng mã fixture.
Ảnh chạy thực tế: [tv4-app.png](screenshots/tv4-app.png).
Đã kiểm tra 32 ID câu hỏi duy nhất. Đây chưa phải kết quả đánh giá độ đúng RAG.

1. Chạy backend và app theo README; kiểm tra API ở sidebar.
2. Hỏi về môn 841020; thấy câu trả lời, citation và đoạn gốc mock.
3. Chọn đích 841108, đã học 841020; thấy các học kỳ có nhãn minh họa.
4. Upload data/raw/841020.pdf; thấy bảng mục, CLO và biểu đồ; upload 841047.pdf
   thì app báo chưa hỗ trợ thay vì hiển thị môn 841020.
5. Gửi [simulate_external_failure] ở tab Hỏi đáp; thấy HTTP 503, không còn answer cũ.
6. Tắt backend, gửi câu hỏi mới; app báo không kết nối và giữ câu đã nhập.
