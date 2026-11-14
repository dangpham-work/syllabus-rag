# Từ điển dữ liệu (`data/`)

Tài liệu mô tả cấu trúc các tệp dữ liệu trong `data/` theo `docs/schema_syllabus.json` và mã nguồn `src/syllabus_core/`.

## 1. `data/raw/`

- `*.pdf`: Các tệp PDF scan đề cương chi tiết học phần ngành CNTT – Trường Đại học Sài Gòn (SGU).
- `inventory.csv`: Bảng kiểm kê do `src/syllabus_core/data/make_inventory.py` tạo.
  - `file_name`: Tên tệp PDF gốc.
  - `course_code`: Mã học phần 6 chữ số (rỗng nếu tên tệp không ghi mã).
  - `course_name`: Tên học phần tiếng Việt.
  - `n_pages`: Số trang PDF.
  - `duplicate_of`: Tên tệp gốc nếu là bản trùng lặp (để trống nếu là bản chính).

## 2. `data/interim/` (gitignored, lưu trên Drive nhóm)

- `ocr/<course_code>/p-N.txt`, `p-N.levels`: Văn bản OCR thô từng trang và số trình độ bảng CLO từ engine kết hợp (Tesseract + PaddleOCR).
- `ocr_clean/<course_code>/p-N.txt`: Văn bản sau khi làm sạch bằng `clean_text.py`.
- `clos_raw.csv`: Bảng CLO thô tách từ mục 4 (`course_code`, `clo_id`, `text`, `level_raw`, `page`, `ocr_ok`).
- `sections_labeled.csv`: Tập đoạn văn bản đã gán nhãn mục (`course_code`, `para_id`, `page`, `text`, `section_regex`, `section_gold`).
- `syllabus_fixes.json`: Các hiệu chỉnh thủ công cho trường mục 1 (`credits`, `prerequisites`, v.v.).

## 3. `data/processed/`

- `syllabi/<course_code>.json`: JSON đề cương chuẩn hoá theo `docs/schema_syllabus.json`:
  - `course_code` (`string | null`), `course_name` (`string`), `course_name_en` (`string | null`)
  - `credits` (`integer`, 1–12), `knowledge_block` (`dai_cuong | co_so_nganh | nganh | chuyen_nganh | null`)
  - `hours` (`theory`, `exercises`, `practice`, `group_activity`, `self_study`)
  - `prerequisites` (`list[str]`), `corequisites` (`list[str]`)
  - `clos`: Danh sách `{clo_id, text, details, level_raw, level, page, ocr_ok, bloom_level, bloom_name, confidence}`
  - `sections`: 10 mục chuẩn (`general_info`, `course_description`, `course_objectives`, `course_learning_outcomes`, `course_content`, `learning_resources`, `teaching_schedule`, `course_policies`, `assessment`, `responsible_unit`)
  - `section_pages`, `source_file`, `n_pages`, `provenance`
- `m1_split.csv` (bản gốc cũng được lưu tại gốc repo `m1_split.csv`): Chia 54 đề cương cho M1 (`course_code`, `split` ∈ `train | val | test`, tỷ lệ 38/8/8, `random_seed = 42`).
- `clos_labeled.csv` *(dữ liệu gán nhãn Bloom)*: Cột `course_code`, `clo_id`, `text`, `bloom_level` (0–6).
- `qa_eval.jsonl` *(bộ câu hỏi đánh giá M3)*: Mỗi dòng JSON gồm `qid`, `question`, `type`, `gold_course`, `gold_section`, `gold_chunk_ids`, `split` (`train`/`test`).
- `chunks.jsonl`: Tập đoạn trích cho M3 (`chunk_id`, `course_code`, `course_name`, `section`, `text`, `context_prefix`, `metadata`).
