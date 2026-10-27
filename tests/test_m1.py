"""Kiểm thử tự động cho Module M1 (Phân loại mục và trích xuất cấu trúc đề cương).

Bao gồm:
  1. Kiểm tra tập chia đề cương (m1_split.csv) đủ 54 môn, 38 train, 8 val, 8 test.
  2. Kiểm tra mô hình models/section_clf.pkl nạp thành công và đủ 11 lớp.
  3. Kiểm tra cơ chế tự hồi quy predict_course_paragraphs.
  4. Kiểm tra hàm analyze_pdf trả về đúng schema.
  5. Kiểm tra metrics.json có chỉ số M1 và Macro-F1 >= 0.85.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.syllabus_core.models.predict import analyze_pdf, load_section_classifier
from src.syllabus_core.models.train_section import SectionClassifierBundle


def test_m1_split_valid():
    split_file = Path("data/processed/m1_split.csv")
    assert split_file.exists(), "Tệp data/processed/m1_split.csv không tồn tại"
    df = pd.read_csv(split_file)
    assert len(df) == 54, f"Số lượng môn trong split ({len(df)}) phải là 54"
    counts = df["split"].value_counts().to_dict()
    assert counts.get("test") == 8, f"Tập test phải có đúng 8 đề cương, thực tế: {counts.get('test')}"
    assert counts.get("val") == 8, f"Tập val phải có đúng 8 đề cương, thực tế: {counts.get('val')}"
    assert counts.get("train") == 38, f"Tập train phải có 38 đề cương, thực tế: {counts.get('train')}"


def test_m1_model_bundle_loading():
    model_path = Path("models/section_clf.pkl")
    assert model_path.exists(), "Tệp models/section_clf.pkl không tồn tại"
    bundle = load_section_classifier(model_path)
    assert isinstance(bundle, SectionClassifierBundle)
    assert len(bundle.classes) == 11, f"Mô hình phải có đúng 11 lớp nhãn, thực tế: {len(bundle.classes)}"
    expected_classes = {
        "general_info", "course_description", "course_objectives",
        "course_learning_outcomes", "course_content", "learning_resources",
        "teaching_schedule", "course_policies", "assessment",
        "responsible_unit", "other"
    }
    assert set(bundle.classes) == expected_classes


def test_predict_paragraphs_sequence():
    bundle = load_section_classifier("models/section_clf.pkl")
    labeled_file = Path("data/processed/sections_labeled.csv")
    if not labeled_file.exists():
        pytest.skip("Chưa có data/processed/sections_labeled.csv")
    df = pd.read_csv(labeled_file)
    sample_course = df[df["course_code"] == "841020"]
    paras = sample_course[["page", "text"]].to_dict(orient="records")
    preds = bundle.predict_course_paragraphs(paras, monotonic=True)
    assert len(preds) == len(paras)
    pred_set = set(preds)
    assert "general_info" in pred_set
    assert "assessment" in pred_set
    assert "course_learning_outcomes" in pred_set
    assert len(pred_set) >= 8


def test_analyze_pdf_structure():
    sample_pdf = Path("data/raw/29 - 841020 - Cơ sở lập trình.pdf")
    if not sample_pdf.exists():
        pytest.skip("Không tìm thấy file PDF mẫu 841020 trong data/raw")

    res = analyze_pdf(sample_pdf)
    assert isinstance(res, dict)
    required_keys = [
        "course_code", "course_name", "credits", "prerequisites",
        "clos", "sections", "missing_sections", "model_version", "processing_time_s"
    ]
    for k in required_keys:
        assert k in res, f"Thiếu trường {k} trong kết quả analyze_pdf"

    assert res["course_code"] == "841020"
    assert res["credits"] == 3
    assert isinstance(res["clos"], list)
    assert len(res["clos"]) > 0
    assert isinstance(res["sections"], dict)
    assert len(res["sections"]) == 10
    assert res["processing_time_s"] > 0


def test_metrics_json_recorded():
    metrics_path = Path("results/metrics.json")
    assert metrics_path.exists(), "Tệp results/metrics.json không tồn tại"
    with open(metrics_path, encoding="utf-8") as f:
        metrics = json.load(f)

    assert "m1_section_classifier" in metrics
    m1_clf = metrics["m1_section_classifier"]
    exp = m1_clf["experiments"]["m1_v1_autoregressive_logreg"]
    assert exp["test_macro_f1"] >= 0.85, f"Macro-F1 ({exp['test_macro_f1']}) phải >= 0.85"

    assert "m1_field_extraction" in metrics
    fields = metrics["m1_field_extraction"]
    assert fields["test_syllabi_count"] == 8
    assert fields["verified_extraction"]["course_code_accuracy"] == 1.0
