# Rubric đánh giá thủ công RAG (`M3`)

Tài liệu quy định thang điểm chấm tay câu trả lời của endpoint `POST /ask` (`RAGPipeline`), lưu kết quả vào `results/rag_human_eval.csv`.

## 1. Các tiêu chí chấm điểm

### A. Faithfulness — Trung thực với ngữ cảnh (0 / 1)
- **1 (Trung thực):** Mọi thông tin và con số trong câu trả lời đều có căn cứ trực tiếp trong các `retrieved_chunks` được trả về; không suy diễn hoặc bịa thêm kiến thức ngoài ngữ cảnh. Nếu câu hỏi ngoài phạm vi hoặc ngữ cảnh không đề cập và hệ thống từ chối đúng ("Đề cương không đề cập thông tin này."), tính là **1**.
- **0 (Ảo giác / Bịa đặt):** Có ít nhất một chi tiết sai lệch so với ngữ cảnh hoặc tự suy đoán thông tin không có trong đoạn trích.

### B. Correctness — Độ đúng và đầy đủ (0 / 1 / 2)
- **2 (Đúng hoàn toàn):** Trả lời đúng trọng tâm câu hỏi, đủ các ý chính có trong đề cương gốc (hoặc từ chối chính xác đối với câu `out_of_scope`).
- **1 (Đúng một phần):** Trả lời đúng hướng nhưng thiếu ý quan trọng (ví dụ chỉ nêu 2/4 CLO hoặc thiếu điều kiện tiên quyết).
- **0 (Sai):** Trả lời sai thông tin, nhầm môn học, hoặc không trả lời được dù ngữ cảnh có thông tin.

### C. Citation Accuracy — Trích dẫn đúng nguồn `[n]` (0 / 1)
- **1 (Đúng):** Mọi nhãn trích dẫn `[1]`, `[2]`... trong câu trả lời khớp đúng với `citations` và đoạn trích tương ứng thực sự chứa thông tin được trích dẫn.
- **0 (Sai / Thiếu):** Không ghi nguồn `[n]` khi sử dụng thông tin ngữ cảnh, hoặc gán nhầm số `[n]` sang đoạn không liên quan.

## 2. Ví dụ minh hoạ

| Tình huống | Faithfulness | Correctness | Citation | Ghi chú |
|---|---|---|---|---|
| Câu trả lời nêu đúng số tín chỉ (3 TC) và gắn `[1]` trỏ tới `general_info` chứa dòng "Số tín chỉ: 3". | 1 | 2 | 1 | Đạt chuẩn. |
| Câu trả lời nêu đúng 3 TC nhưng lại tự bổ sung "môn này học vào học kỳ 2" không có trong chunk. | 0 | 1 | 1 | Bị điểm 0 Faithfulness do suy diễn ngoài ngữ cảnh. |
| Câu hỏi ngoài phạm vi ("Học phí học kỳ này là bao nhiêu?") và hệ thống trả lời "Đề cương không đề cập thông tin này." | 1 | 2 | 1 | Từ chối đúng câu `out_of_scope`. |
| Trả lời đúng tên môn tiên quyết nhưng gắn `[2]` thay vì `[1]`. | 1 | 2 | 0 | Nhầm chỉ số nguồn trích dẫn. |
