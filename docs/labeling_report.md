# Báo cáo gán nhãn dữ liệu (`M1` & `M2` & `M3`)

## 1. Dữ liệu phân loại mục đề cương (`M1`)

Số liệu xác nhận từ `results/metrics.json` và `docs/decisions.md` (D2, D3):
- **Tổng số đề cương:** 54 môn (~488 trang PDF scan).
- **Tổng số đoạn văn sau tách mục:** 5.693 đoạn (11 lớp: 10 mục chuẩn SGU + `other`).
- **Phân chia tập M1 (`m1_split.csv`, `seed=42`):**
  - Train: 38 môn (3.854 đoạn)
  - Validation: 8 môn (910 đoạn)
  - Test: 8 môn (929 đoạn)

## 2. Dữ liệu gán nhãn Bloom (`M2 – clos_labeled.csv`)

- **Thang nhãn:** 7 lớp Bloom–Anderson & Krathwohl (`0` Ngoài miền đến `6` Sáng tạo), chi tiết tại `docs/bloom_scale.md` và `docs/labeling_guideline_bloom.md` v1.1.
- **Quy trình gán:** Mỗi CLO được 2 thành viên gán độc lập qua Google Sheet; phân xử các câu bất đồng trước khi xuất `clos_labeled.csv`.
- **Tổng số CLO & Cohen's kappa:** *Chờ TV1 cập nhật sau khi xuất `data/processed/clos_labeled.csv` và chạy `notebooks/exploratory/1.1-dd-eda.ipynb`.*

## 3. Bộ câu hỏi đánh giá RAG (`M3 – qa_eval.jsonl`)

- **Bản nháp Mốc 1:** 32 câu hỏi (4 loại: Tra cứu, Nội dung, So sánh, Tiên quyết & học trước) trên 10 đề cương tại `docs/question_ideas.md`.
- **Tập đánh giá đầy đủ (120 train / 80 test) & `rag_human_eval.csv`:** *Chờ TV4/TV1 bổ sung tệp `data/processed/qa_eval.jsonl` và kết quả chấm tay 50 câu theo `docs/rag_rubric.md`.*
