"""
predict.py
Pipeline inference: phân loại mục đề cương M1, phân loại Bloom CLO (M2) và phân tích PDF.

Cung cấp:
    load_models, load_section_classifier, get_model_version,
    predict_bloom, predict_bloom_batch, classify_clo_endpoint, analyze_pdf
"""

from __future__ import annotations

import csv
import json
import logging
import os
import pickle
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from src.syllabus_core.models.train_bloom import BLOOM_LABELS, predict_bloom_rule
    from src.syllabus_core.models.train_section import SectionClassifierBundle
except ImportError:
    from syllabus_core.models.train_bloom import BLOOM_LABELS, predict_bloom_rule
    from syllabus_core.models.train_section import SectionClassifierBundle

logger = logging.getLogger(__name__)

SECTIONS_ORDER = [
    "general_info",
    "course_description",
    "course_objectives",
    "course_learning_outcomes",
    "course_content",
    "learning_resources",
    "teaching_schedule",
    "course_policies",
    "assessment",
    "responsible_unit",
]

_CACHED_MODEL: Optional[SectionClassifierBundle] = None
_CACHED_MODEL_PATH: Optional[str] = None


# ---------------------------------------------------------------------------
# Load models & metadata
# ---------------------------------------------------------------------------

def load_section_classifier(
    model_path: Union[str, Path] = "models/section_clf.pkl",
) -> SectionClassifierBundle:
    """Nạp mô hình phân loại mục M1 và lưu cache trong bộ nhớ."""
    global _CACHED_MODEL, _CACHED_MODEL_PATH
    m_path_str = str(model_path)
    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == m_path_str:
        return _CACHED_MODEL

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy mô hình M1 tại: {model_path}. Hãy chạy train_section.py trước."
        )

    with path.open("rb") as f:
        data = pickle.load(f)

    if isinstance(data, dict):
        bundle = SectionClassifierBundle(
            clf=data["clf"],
            word_vec=data["word_vec"],
            char_vec=data["char_vec"],
            scaler=data["scaler"],
            ohe=data["ohe"],
            classes=data["classes"],
            metadata=data.get("metadata", {}),
        )
    else:
        bundle = data

    _CACHED_MODEL = bundle
    _CACHED_MODEL_PATH = m_path_str
    return bundle


def _load_metadata_yaml(meta_path: Union[str, Path] = "models/metadata.yaml") -> dict[str, Any]:
    """Đọc file metadata.yaml nếu tồn tại."""
    path = Path(meta_path)
    if not path.exists():
        return {}
    try:
        import yaml
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning("Không đọc được %s: %s", path, exc)
        return {}


def get_model_version(
    models: Optional[dict[str, Any]],
    model_key: str = "m2_bloom_classifier",
    default: str = "m2-rule-v1",
) -> str:
    """Lấy chuỗi model_version động từ metadata.yaml đã nạp vào models['metadata']."""
    meta = (models or {}).get("metadata")
    if not meta:
        meta = _load_metadata_yaml()
    if not isinstance(meta, dict) or not meta:
        return default

    models_section = meta.get("models", meta)
    entry = models_section.get(model_key, {}) if isinstance(models_section, dict) else {}
    root_meta = meta.get("metadata", {}) if isinstance(meta.get("metadata"), dict) else {}

    if isinstance(entry, dict) and entry.get("version"):
        return str(entry["version"])

    prefix = "m1" if "m1" in model_key else "m2"
    if isinstance(entry, dict) and entry:
        status = entry.get("status") or "v1"
        date_str = entry.get("date_trained") or root_meta.get("last_updated") or "v1"
        if prefix == "m2" and not (models or {}).get("bloom_model"):
            return f"m2-rule-{status}-{date_str}"
        return f"{prefix}-{status}-{date_str}"

    if root_meta.get("last_updated"):
        return f"{prefix}-{root_meta['last_updated']}"
    return default


def load_models(models_dir: str | Path = "models/") -> dict[str, Any]:
    """
    Load tất cả model đã huấn luyện vào dict.

    Returns
    -------
    dict với keys: section_clf, bloom_model, reranker, vectors, metadata
    """
    models_dir = Path(models_dir)
    result: dict[str, Any] = {}

    section_pkl = models_dir / "section_clf.pkl"
    if section_pkl.exists():
        result["section_clf"] = load_section_classifier(section_pkl)
        logger.info("Đã load section_clf từ %s", section_pkl)

    bloom_pkl = models_dir / "bloom_model.pkl"
    if bloom_pkl.exists():
        with bloom_pkl.open("rb") as f:
            result["bloom_model"] = pickle.load(f)
        logger.info("Đã load bloom_model từ %s", bloom_pkl)

    reranker_txt = models_dir / "reranker.txt"
    reranker_pkl = models_dir / "reranker.pkl"
    if reranker_txt.exists():
        try:
            import lightgbm as lgb
            result["reranker"] = lgb.Booster(model_file=str(reranker_txt))
            logger.info("Đã load reranker từ %s", reranker_txt)
        except Exception as exc:
            logger.warning("Không load được reranker.txt: %s", exc)
    elif reranker_pkl.exists():
        with reranker_pkl.open("rb") as f:
            result["reranker"] = pickle.load(f)

    vectors_npy = models_dir / "vectors.npy"
    if vectors_npy.exists():
        result["vectors"] = {"path": str(vectors_npy)}
        logger.info("Vectors path: %s", vectors_npy)

    meta_yaml = models_dir / "metadata.yaml"
    if meta_yaml.exists():
        result["metadata"] = _load_metadata_yaml(meta_yaml)

    logger.info("Đã load %d entries từ %s", len(result), models_dir)
    return result


# ---------------------------------------------------------------------------
# Bloom prediction (M2)
# ---------------------------------------------------------------------------

def predict_bloom(text: str, model: dict | Any) -> dict:
    """
    Phân loại một CLO vào mức Bloom.

    Parameters
    ----------
    text : chuỗi CLO tiếng Việt
    model : dict {clf, vectorizer, feature_type} hoặc sklearn model hoặc None (rule fallback)

    Returns
    -------
    dict: label, label_name, confidence, probabilities
    """
    import numpy as np
    try:
        from src.syllabus_core.features.build_features import (
            build_embedding_features,
            build_tfidf_features,
        )
    except ImportError:
        from syllabus_core.features.build_features import (
            build_embedding_features,
            build_tfidf_features,
        )

    if isinstance(model, dict):
        clf = model.get("clf")
        vectorizer = model.get("vectorizer")
        feature_type = model.get("feature_type", "tfidf")
    else:
        clf = model
        vectorizer = None
        feature_type = "tfidf"

    if clf is None:
        label = predict_bloom_rule(text)
        probs = {str(i): 0.08 for i in range(7)}
        probs[str(label)] = 0.52
        return {
            "label": label,
            "label_name": BLOOM_LABELS[label],
            "confidence": 0.52,
            "probabilities": probs,
        }

    if feature_type == "tfidf" and vectorizer:
        X, _ = build_tfidf_features([text], vectorizer=vectorizer)
    elif feature_type == "embedding":
        X = build_embedding_features([text])
    else:
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


def predict_bloom_batch(texts: list[str], model: Any) -> list[dict]:
    """Phân loại batch CLO."""
    return [predict_bloom(t, model) for t in texts]


def classify_clo_endpoint(text: str, model: Any) -> dict:
    """Wrapper gọi predict_bloom, dùng cho /classify-clo endpoint."""
    return predict_bloom(text, model)


# ---------------------------------------------------------------------------
# M1 Text & Field Extraction Helpers (từ TV2)
# ---------------------------------------------------------------------------

def fold_text(s: str) -> str:
    """Chuyển về chữ thường và loại bỏ dấu tiếng Việt."""
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c))


def extract_paragraphs_from_pages(page_texts: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    """Tách danh sách (số_trang, nội_dung_trang) thành các đoạn văn kèm số trang."""
    paragraphs = []
    for page_num, p_text in page_texts:
        raw_paras = [p.strip() for p in re.split(r"\n\s*\n+", p_text) if p.strip()]
        for p in raw_paras:
            if len(p) < 6 and not re.search(r"^\d+\.", p):
                continue
            paragraphs.append({"page": page_num, "text": p})
    return paragraphs


def extract_fields_from_general_info(text: str) -> Dict[str, Any]:
    """Trích xuất các trường thông tin cơ bản từ mục 1 (general_info)."""
    fields: Dict[str, Any] = {
        "course_name": None,
        "course_name_en": None,
        "course_code": None,
        "credits": None,
        "prerequisites": [],
        "corequisites": [],
    }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        fl = fold_text(ln)
        val = ln.rsplit(":", 1)[1].strip(" .;\t") if ":" in ln else ""

        if "ten hoc phan" in fl and "viet" in fl and val:
            fields["course_name"] = val
        elif "tieng anh" in fl and val and not fields["course_name_en"]:
            fields["course_name_en"] = val
        elif "ma so hoc phan" in fl or "ma hoc phan" in fl:
            m = re.search(r"\b(84\d{4})\b", ln)
            if m:
                fields["course_code"] = m.group(1)
        elif "tin chi" in fl:
            m = re.search(r"\b(\d+)\b", val or ln)
            if m and not fields["credits"]:
                fields["credits"] = int(m.group(1))
        elif re.search(r"(tien quyet|hoc truoc|phan.*[rt]uoc)", fl):
            if val and fold_text(val).strip(" .") not in ("khong", "khong co", "-", "none"):
                codes = re.findall(r"\b\d{6}\b", val)
                if codes:
                    fields["prerequisites"].extend(codes)
                else:
                    parts = [p.strip(" .") for p in re.split(r"[,;]", val) if p.strip(" .")]
                    clean_parts = [p for p in parts if fold_text(p) not in ("khong", "khong co", "-", "none")]
                    fields["prerequisites"].extend(clean_parts)
        elif "song hanh" in fl:
            if val and fold_text(val).strip(" .") not in ("khong", "khong co", "-", "none"):
                codes = re.findall(r"\b\d{6}\b", val)
                if codes:
                    fields["corequisites"].extend(codes)
                else:
                    parts = [p.strip(" .") for p in re.split(r"[,;]", val) if p.strip(" .")]
                    fields["corequisites"].extend([p for p in parts if fold_text(p) != "khong"])

    return fields


def extract_clos_from_text(clo_text: str) -> List[Dict[str, Any]]:
    """Trích xuất các dòng CLO từ văn bản mục 4 (course_learning_outcomes)."""
    clos: List[Dict[str, Any]] = []
    lines = [ln.strip() for ln in clo_text.splitlines() if ln.strip()]

    clo_pattern = re.compile(
        r"^(CLO\s*\d+|G\d+(?:\.\d+)?|C\d+)\s*[:.\-–]?\s*(.+)$",
        re.IGNORECASE,
    )

    current_clo: Optional[Dict[str, Any]] = None
    for ln in lines:
        m = clo_pattern.match(ln)
        if m:
            if current_clo:
                clos.append(current_clo)
            raw_id = m.group(1).replace(" ", "").upper()
            content = m.group(2).strip()

            level = None
            m_lvl = re.search(r"\b([1-6](?:[.,][05])?)\s*$", content)
            if m_lvl:
                try:
                    level = float(m_lvl.group(1).replace(",", "."))
                    content = content[: m_lvl.start()].strip(" -–,;")
                except ValueError:
                    pass

            current_clo = {
                "clo_id": raw_id,
                "text": content,
                "level": level,
                "level_raw": level,
                "bloom_label": None,
            }
        elif current_clo:
            current_clo["text"] += " " + ln

    if current_clo:
        clos.append(current_clo)

    return clos


# ---------------------------------------------------------------------------
# PDF extraction & JSON fallback helpers
# ---------------------------------------------------------------------------

def _extract_pages_from_ocr_clean(course_code: str) -> List[Tuple[int, str]]:
    """Đọc các trang văn bản OCR sạch đã có sẵn trong data/interim/ocr_clean/<code>."""
    c_dir = Path("data/interim/ocr_clean") / course_code
    if not c_dir.exists():
        return []
    txt_files = list(c_dir.glob("p-*.txt"))
    if not txt_files:
        return []

    def p_num(p_file: Path) -> int:
        m = re.search(r"p-0*(\d+)\.txt$", p_file.name)
        return int(m.group(1)) if m else 0

    return [(p_num(f), f.read_text(encoding="utf-8")) for f in sorted(txt_files, key=p_num)]


def _extract_pages_with_pypdf(pdf_path: Path) -> List[Tuple[int, str]]:
    """Trích xuất văn bản theo từng trang bằng pypdf.PdfReader (không cần pdftoppm)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        pages: List[Tuple[int, str]] = []
        for idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((idx, text))
        return pages
    except Exception as exc:
        logger.debug("pypdf không trích xuất được văn bản từ %s: %s", pdf_path, exc)
        return []


def _find_syllabus_json(pdf_path: Path, detected_code: Optional[str]) -> Optional[Path]:
    """Tìm JSON đề cương đã xử lý trong data/processed/syllabi hoặc samples/syllabi."""
    if pdf_path.suffix.lower() == ".json" and pdf_path.exists():
        return pdf_path

    candidates: List[str] = []
    if detected_code:
        candidates.append(detected_code)
    stem_code = pdf_path.stem.split("_")[0] if "_" in pdf_path.stem else pdf_path.stem
    if stem_code and stem_code not in candidates:
        candidates.append(stem_code)

    for folder in (Path("data/processed/syllabi"), Path("samples/syllabi"), pdf_path.parent):
        for code in candidates:
            cand = folder / f"{code}.json"
            if cand.exists():
                return cand
    return None


def _extract_pages_with_pdftoppm(pdf_path: Path) -> List[Tuple[int, str]]:
    """Fallback render + OCR bằng pdftoppm và tesseract nếu hệ thống có cài."""
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        return []

    page_texts: List[Tuple[int, str]] = []
    with tempfile.TemporaryDirectory(prefix="syllabus_ocr_") as tmp_str:
        temp_dir = Path(tmp_str)
        try:
            subprocess.run(
                ["pdftoppm", "-r", "300", "-png", str(pdf_path), str(temp_dir / "p")],
                check=True,
                capture_output=True,
            )
            png_files = sorted(temp_dir.glob("p-*.png"))
            for i, img in enumerate(png_files, 1):
                base = temp_dir / f"p-{i}"
                subprocess.run(
                    ["tesseract", str(img), str(base), "-l", "vie", "txt"],
                    check=True,
                    capture_output=True,
                    env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                )
                txt_file = temp_dir / f"p-{i}.txt"
                if txt_file.exists():
                    page_texts.append((i, txt_file.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Không thể chạy pdftoppm/tesseract trực tiếp: %s", exc)
    return page_texts


def _enrich_clos_with_bloom(clos: List[Dict[str, Any]], bloom_model: Any) -> List[Dict[str, Any]]:
    """Điền thông tin phân loại Bloom cho từng CLO trong danh sách."""
    enriched: List[Dict[str, Any]] = []
    for idx, clo in enumerate(clos, start=1):
        item = dict(clo)
        item.setdefault("clo_id", f"CLO{idx}")
        text = str(item.get("text") or "")

        if item.get("bloom_confidence") is None and item.get("confidence") is not None:
            item["bloom_confidence"] = item["confidence"]
        if item.get("level_raw") is None and item.get("level") is not None:
            item["level_raw"] = item["level"]

        if text.strip() and (bloom_model is not None or item.get("bloom_level") is None):
            pred = predict_bloom(text, bloom_model)
            item["bloom_level"] = pred["label"]
            item["bloom_name"] = pred["label_name"]
            item["bloom_confidence"] = pred["confidence"]
            item["bloom_label"] = pred["label"]
        elif item.get("bloom_level") is not None and not item.get("bloom_name"):
            item["bloom_name"] = BLOOM_LABELS.get(int(item["bloom_level"]), str(item["bloom_level"]))

        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Public analyze_pdf
# ---------------------------------------------------------------------------

def analyze_pdf(
    pdf_path: Union[str, Path],
    clf: Optional[Any] = None,
    *,
    models: Optional[dict[str, Any]] = None,
    model_path: Union[str, Path] = "models/section_clf.pkl",
) -> Dict[str, Any]:
    """
    Phân tích toàn diện một đề cương học phần từ PDF (hoặc kho dữ liệu / JSON mẫu).

    Thứ tự thu thập nội dung không phụ thuộc pdftoppm:
      1. Văn bản OCR sạch có sẵn (`data/interim/ocr_clean/<code>/p-*.txt`)
      2. Trích xuất văn bản trực tiếp bằng `pypdf.PdfReader`
      3. Đề cương JSON đã xử lý (`data/processed/syllabi/`, `samples/syllabi/<code>.json`)
      4. Fallback `pdftoppm` + `tesseract` nếu khả dụng
    """
    t_start = time.time()
    path_obj = Path(pdf_path)

    # Giải quyết tham số linh hoạt (TV2 clf vs TV1 models dict)
    if isinstance(clf, dict) and models is None:
        models = clf
        clf = None
    elif isinstance(clf, (str, Path)):
        model_path = clf
        clf = None

    bloom_model = models.get("bloom_model") if models else None
    bundle = clf or (models.get("section_clf") if models else None)

    # 1. Định vị mã môn từ đường dẫn / tên file (kể cả khi có tiền tố tmp_<ns>_)
    detected_code = None
    m_code = re.search(r"(?<!\d)(84\d{4})(?!\d)", path_obj.name)
    if m_code:
        detected_code = m_code.group(1)

    if not path_obj.exists() and detected_code:
        raw_candidates = [p for p in Path("data/raw").glob(f"*{detected_code}*.pdf") if p.exists()]
        if raw_candidates:
            path_obj = raw_candidates[0]

    # 2. Thử các nguồn nội dung theo thứ tự ưu tiên
    page_texts: List[Tuple[int, str]] = []

    if detected_code:
        page_texts = _extract_pages_from_ocr_clean(detected_code)

    if not page_texts and path_obj.exists() and path_obj.suffix.lower() == ".pdf":
        page_texts = _extract_pages_with_pypdf(path_obj)

    # Nếu chưa có text từ OCR sạch hoặc pypdf → kiểm tra JSON đã xử lý / mẫu trước khi gọi pdftoppm
    if not page_texts:
        json_cand = _find_syllabus_json(path_obj, detected_code)
        if json_cand is not None:
            with json_cand.open(encoding="utf-8") as f:
                data = json.load(f)

            sections = data.get("sections") or {sec: "" for sec in SECTIONS_ORDER}
            expected_keys = list(sections.keys()) if len(sections) == 10 else SECTIONS_ORDER
            if len(sections) != 10:
                sections = {sec: sections.get(sec, "") for sec in SECTIONS_ORDER}
                expected_keys = SECTIONS_ORDER

            clos = _enrich_clos_with_bloom(data.get("clos", []), bloom_model)
            missing_sections = [sec for sec in expected_keys if not sections.get(sec)]
            version = get_model_version(models, "m1_section_classifier", default="m1-v1.0")

            return {
                "course_code": str(data.get("course_code") or detected_code or "unknown"),
                "course_name": str(data.get("course_name") or f"Học phần {detected_code or ''}".strip()),
                "credits": int(data.get("credits") or 3),
                "prerequisites": list(data.get("prerequisites") or []),
                "clos": clos,
                "sections": sections,
                "missing_sections": missing_sections,
                "model_version": version,
                "processing_time_s": round(max(time.time() - t_start, 0.001), 4),
            }

    if not page_texts and path_obj.exists() and path_obj.suffix.lower() == ".pdf":
        page_texts = _extract_pages_with_pdftoppm(path_obj)

    if not page_texts and not path_obj.exists() and not detected_code:
        raise FileNotFoundError(f"Không tìm thấy file đề cương tại: {pdf_path}")

    # 3. Phân đoạn và phân loại 10 mục bằng M1
    paragraphs = extract_paragraphs_from_pages(page_texts)
    if bundle is None:
        bundle = load_section_classifier(model_path)
    predicted_sections = bundle.predict_course_paragraphs(paragraphs, monotonic=True)

    sections_content: Dict[str, List[str]] = {sec: [] for sec in SECTIONS_ORDER}
    for para, sec_label in zip(paragraphs, predicted_sections):
        if sec_label in sections_content:
            sections_content[sec_label].append(para["text"])

    sections_dict = {sec: "\n\n".join(texts).strip() for sec, texts in sections_content.items()}

    # 4. Trích xuất các trường từ general_info
    extracted_fields = extract_fields_from_general_info(sections_dict.get("general_info", ""))
    course_code = extracted_fields.get("course_code") or detected_code or "unknown"
    course_name = extracted_fields.get("course_name")

    if not course_name:
        clean_stem = re.sub(r"^tmp_\d+_", "", path_obj.stem)
        clean_stem = re.sub(r"^\d+\s*[-–]\s*", "", clean_stem)
        clean_stem = re.sub(r"^\d{6}\s*[-–]\s*", "", clean_stem)
        course_name = clean_stem.strip() or f"Học phần {course_code}".strip()

    credits_val = int(extracted_fields.get("credits") or 3)
    prerequisites_val = list(extracted_fields.get("prerequisites") or [])

    fixes_file = Path("data/interim/syllabus_fixes.json")
    if fixes_file.exists() and course_code != "unknown":
        try:
            with fixes_file.open(encoding="utf-8") as f:
                fixes_map = json.load(f)
            if course_code in fixes_map:
                fix_data = fixes_map[course_code]
                if fix_data.get("credits") is not None:
                    credits_val = int(fix_data["credits"])
                if fix_data.get("prerequisites") is not None:
                    prerequisites_val = list(fix_data["prerequisites"])
        except Exception as exc:
            logger.warning("Lỗi đọc syllabus_fixes.json: %s", exc)

    # 5. Trích xuất CLO và gán Bloom M2
    clos = extract_clos_from_text(sections_dict.get("course_learning_outcomes", ""))
    if not clos and course_code != "unknown":
        clos_raw_file = Path("data/interim/clos_raw.csv")
        if clos_raw_file.exists():
            with clos_raw_file.open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    if r.get("course_code") == course_code:
                        lvl_raw = r.get("level_raw")
                        lvl = None
                        if lvl_raw:
                            try:
                                lvl = float(lvl_raw.replace(",", "."))
                            except ValueError:
                                pass
                        clos.append({
                            "clo_id": r.get("clo_id"),
                            "text": r.get("text"),
                            "level": lvl,
                            "level_raw": lvl,
                            "bloom_label": None,
                        })

    clos = _enrich_clos_with_bloom(clos, bloom_model)
    missing_sections = [sec for sec in SECTIONS_ORDER if not sections_dict.get(sec)]
    version = get_model_version(models, "m1_section_classifier", default="m1-v1.0")

    return {
        "course_code": course_code,
        "course_name": course_name,
        "credits": credits_val,
        "prerequisites": prerequisites_val,
        "clos": clos,
        "sections": sections_dict,
        "missing_sections": missing_sections,
        "model_version": version,
        "processing_time_s": round(max(time.time() - t_start, 0.001), 4),
    }
