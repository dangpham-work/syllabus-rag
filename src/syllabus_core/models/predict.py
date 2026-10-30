"""
predict.py
Pipeline inference: phân loại Bloom CLO và phân tích đề cương PDF (M2 + M1).

Dùng:
    from syllabus_core.models.predict import load_models, predict_bloom, analyze_pdf
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from syllabus_core.models.train_bloom import BLOOM_LABELS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Load models
# ---------------------------------------------------------------------------

def load_models(models_dir: str | Path = "models/") -> dict[str, Any]:
    """
    Load tất cả model đã huấn luyện vào dict.

    Returns
    -------
    dict với keys: section_clf, bloom_model, reranker, vectors, metadata
    """
    import pickle
    models_dir = Path(models_dir)
    result: dict[str, Any] = {}

    # Section classifier (M1) — từ TV2/Long
    section_pkl = models_dir / "section_clf.pkl"
    if section_pkl.exists():
        with section_pkl.open("rb") as f:
            result["section_clf"] = pickle.load(f)
        logger.info("Đã load section_clf từ %s", section_pkl)

    # Bloom classifier (M2)
    bloom_pkl = models_dir / "bloom_model.pkl"
    if bloom_pkl.exists():
        with bloom_pkl.open("rb") as f:
            result["bloom_model"] = pickle.load(f)
        logger.info("Đã load bloom_model từ %s", bloom_pkl)

    # Reranker (M3)
    reranker_txt = models_dir / "reranker.txt"
    reranker_pkl = models_dir / "reranker.pkl"
    if reranker_txt.exists():
        try:
            import lightgbm as lgb
            result["reranker"] = lgb.Booster(model_file=str(reranker_txt))
            logger.info("Đã load reranker từ %s", reranker_txt)
        except Exception as e:
            logger.warning("Không load được reranker.txt: %s", e)
    elif reranker_pkl.exists():
        with reranker_pkl.open("rb") as f:
            result["reranker"] = pickle.load(f)

    # Dense vectors (M3)
    vectors_npy = models_dir / "vectors.npy"
    if vectors_npy.exists():
        import numpy as np
        result["vectors"] = {"path": str(vectors_npy)}
        logger.info("Vectors path: %s", vectors_npy)

    # Metadata
    meta_yaml = models_dir / "metadata.yaml"
    if meta_yaml.exists():
        try:
            import yaml
            with meta_yaml.open(encoding="utf-8") as f:
                result["metadata"] = yaml.safe_load(f)
        except Exception:
            result["metadata"] = {}

    logger.info("Đã load %d models từ %s", len(result), models_dir)
    return result


# ---------------------------------------------------------------------------
# Bloom prediction
# ---------------------------------------------------------------------------

def predict_bloom(text: str, model: dict | Any) -> dict:
    """
    Phân loại một CLO vào mức Bloom.

    Parameters
    ----------
    text : chuỗi CLO tiếng Việt
    model : dict {clf, vectorizer, feature_type} từ load_models / train_bloom

    Returns
    -------
    dict: label, label_name, confidence, probabilities
    """
    import numpy as np
    from syllabus_core.features.build_features import (
        build_embedding_features,
        build_tfidf_features,
    )

    if isinstance(model, dict):
        clf = model.get("clf")
        vectorizer = model.get("vectorizer")
        feature_type = model.get("feature_type", "tfidf")
    else:
        # Có thể là sklearn model trực tiếp
        clf = model
        vectorizer = None
        feature_type = "tfidf"

    if clf is None:
        # Fallback rule-based
        from syllabus_core.models.train_bloom import predict_bloom_rule
        label = predict_bloom_rule(text)
        probs = {str(i): 0.1 for i in range(7)}
        probs[str(label)] = 0.5
        return {
            "label": label,
            "label_name": BLOOM_LABELS[label],
            "confidence": 0.5,
            "probabilities": probs,
        }

    if feature_type == "tfidf" and vectorizer:
        X, _ = build_tfidf_features([text], vectorizer=vectorizer)
    elif feature_type == "embedding":
        X = build_embedding_features([text])
    else:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from scipy.sparse import hstack
        X, _ = build_tfidf_features([text], vectorizer=vectorizer)

    proba = clf.predict_proba(X)[0]
    label = int(np.argmax(proba))
    if hasattr(clf, "classes_"):
        label = int(clf.classes_[np.argmax(proba)])

    return {
        "label": label,
        "label_name": BLOOM_LABELS.get(label, str(label)),
        "confidence": float(proba.max()),
        "probabilities": {
            str(int(clf.classes_[i]) if hasattr(clf, "classes_") else i): float(p)
            for i, p in enumerate(proba)
        },
    }


def predict_bloom_batch(texts: list[str], model) -> list[dict]:
    """Phân loại batch CLO."""
    return [predict_bloom(t, model) for t in texts]


# ---------------------------------------------------------------------------
# analyze_pdf
# ---------------------------------------------------------------------------

def analyze_pdf(
    pdf_path: str | Path,
    models: Optional[dict] = None,
) -> dict:
    """
    Pipeline đầy đủ: PDF → JSON đề cương 10 mục + bloom_label cho mỗi CLO.

    Parameters
    ----------
    pdf_path : đường dẫn file PDF hoặc đường dẫn JSON đã xử lý (để test)
    models : dict từ load_models()

    Returns
    -------
    dict JSON đề cương với bloom_label điền vào clos[], missing_sections, processing_time_s
    """
    t0 = time.time()
    pdf_path = Path(pdf_path)

    # 1. Thử import analyze_pdf từ TV2/Long nếu có
    try:
        from syllabus_core.data.make_dataset import analyze_pdf as _analyze_pdf_m1
        result = _analyze_pdf_m1(str(pdf_path))
    except (ImportError, Exception):
        # Fallback: đọc JSON mẫu nếu có, hoặc tạo synthetic
        result = _fallback_parse(pdf_path)

    # 2. Gán bloom_label cho từng CLO bằng M2
    bloom_model = models.get("bloom_model") if models else None
    version = "bloom-v1"
    if models and "metadata" in models:
        version = models["metadata"].get("m2_bloom_classifier", {}).get("version", "bloom-v1")

    for clo in result.get("clos", []):
        if bloom_model and clo.get("text"):
            pred = predict_bloom(clo["text"], bloom_model)
            clo["bloom_level"] = pred["label"]
            clo["bloom_name"] = pred["label_name"]
            clo["bloom_confidence"] = pred["confidence"]
        elif "bloom_level" not in clo:
            clo["bloom_level"] = None
            clo["bloom_name"] = None

    # 3. Thống kê missing sections
    expected_sections = {
        "general_info", "course_description", "course_objectives",
        "course_learning_outcomes", "course_content", "teaching_methods",
        "assessment", "learning_resources", "teaching_schedule", "course_policies",
    }
    sections = result.get("sections", {})
    missing = [s for s in expected_sections if not sections.get(s)]
    result["missing_sections"] = missing

    result["model_version"] = version
    result["processing_time_s"] = round(time.time() - t0, 3)
    return result


def _fallback_parse(pdf_path: Path) -> dict:
    """
    Fallback khi không có pipeline M1 thực:
    - Nếu có file JSON cùng tên → đọc
    - Nếu không → trả về dict trống có cấu trúc đúng
    """
    # Thử tìm JSON mẫu
    sample_dirs = [
        pdf_path.parent,
        Path("samples/syllabi"),
        Path("data/processed/syllabi"),
    ]
    course_code = pdf_path.stem.split("_")[0] if "_" in pdf_path.stem else pdf_path.stem[:6]

    for d in sample_dirs:
        for ext in (".json",):
            candidate = d / (course_code + ext)
            if candidate.exists():
                with candidate.open(encoding="utf-8") as f:
                    logger.info("Dùng JSON mẫu: %s", candidate)
                    return json.load(f)

    # Tạo dict trống hợp lệ
    logger.warning("Không parse được %s, trả dict trống.", pdf_path)
    return {
        "course_code": course_code,
        "course_name": f"Môn học {course_code}",
        "credits": 3,
        "prerequisites": [],
        "clos": [],
        "sections": {s: "" for s in [
            "general_info", "course_description", "course_objectives",
            "course_learning_outcomes", "course_content", "teaching_methods",
            "assessment", "learning_resources", "teaching_schedule", "course_policies",
        ]},
        "source_file": str(pdf_path),
        "ocr_confidence": 0.0,
    }


# ---------------------------------------------------------------------------
# classify_clo_endpoint — wrapper cho API
# ---------------------------------------------------------------------------

def classify_clo_endpoint(text: str, model) -> dict:
    """Wrapper gọi predict_bloom, dùng cho /classify-clo endpoint."""
    return predict_bloom(text, model)
