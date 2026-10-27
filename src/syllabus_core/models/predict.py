"""Dự đoán và phân tích cấu trúc đề cương học phần (Module M1).

Cung cấp hàm:
    analyze_pdf(path: str | Path, model_path: str | Path = "models/section_clf.pkl") -> dict

Quy trình:
    PDF -> Kết xuất ảnh -> OCR -> Làm sạch văn bản -> Phân loại 11 mục (M1) -> Trích xuất trường -> JSON.
Đầu ra tuân thủ docs/schema_syllabus.json và schema API AnalyzeSyllabusResponse.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import re
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Import SectionClassifierBundle để pickle có thể load
from src.syllabus_core.models.train_section import SectionClassifierBundle

logger = logging.getLogger("syllabus_core.predict")

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


def load_section_classifier(model_path: Union[str, Path] = "models/section_clf.pkl") -> SectionClassifierBundle:
    """Nạp mô hình phân loại mục M1 và lưu cache trong bộ nhớ."""
    global _CACHED_MODEL, _CACHED_MODEL_PATH
    m_path_str = str(model_path)
    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == m_path_str:
        return _CACHED_MODEL

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy mô hình M1 tại: {model_path}. Hãy chạy train_section.py trước.")

    with open(path, "rb") as f:
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
            # Bỏ các đoạn quá ngắn là số trang hoặc nhiễu không có ý nghĩa
            if len(p) < 6 and not re.search(r"^\d+\.", p):
                continue
            paragraphs.append({
                "page": page_num,
                "text": p,
            })
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

        # Tên học phần tiếng Việt
        if "ten hoc phan" in fl and "viet" in fl and val:
            fields["course_name"] = val
        elif "tieng anh" in fl and val and not fields["course_name_en"]:
            fields["course_name_en"] = val
        # Mã học phần
        elif "ma so hoc phan" in fl or "ma hoc phan" in fl:
            m = re.search(r"\b(84\d{4})\b", ln)
            if m:
                fields["course_code"] = m.group(1)
        # Số tín chỉ
        elif "tin chi" in fl:
            m = re.search(r"\b(\d+)\b", val or ln)
            if m and not fields["credits"]:
                fields["credits"] = int(m.group(1))
        # Tiên quyết và học phần trước
        elif re.search(r"(tien quyet|hoc truoc|phan.*[rt]uoc)", fl):
            if val and fold_text(val).strip(" .") not in ("khong", "khong co", "-", "none"):
                codes = re.findall(r"\b\d{6}\b", val)
                if codes:
                    fields["prerequisites"].extend(codes)
                else:
                    parts = [p.strip(" .") for p in re.split(r"[,;]", val) if p.strip(" .")]
                    clean_parts = [p for p in parts if fold_text(p) not in ("khong", "khong co", "-", "none")]
                    fields["prerequisites"].extend(clean_parts)
        # Song hành
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

            # Thử tìm số trình độ ở cuối (ví dụ "3.0" hoặc "2.5")
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
                "bloom_label": None,
            }
        elif current_clo:
            current_clo["text"] += " " + ln

    if current_clo:
        clos.append(current_clo)

    return clos


def analyze_pdf(
    path: Union[str, Path],
    model_path: Union[str, Path] = "models/section_clf.pkl",
) -> Dict[str, Any]:
    """Phân tích toàn diện một đề cương học phần từ file PDF hoặc kho tri thức có sẵn.

    Trả về dict chuẩn theo AnalyzeSyllabusResponse và schema_syllabus.json.
    """
    t_start = time.time()
    pdf_path = Path(path)

    # 1. Định vị mã môn từ đường dẫn / tên file
    detected_code = None
    m_code = re.search(r"\b(84\d{4})\b", pdf_path.name)
    if m_code:
        detected_code = m_code.group(1)

    # Nếu file không tồn tại trực tiếp nhưng tìm thấy trong data/raw/
    if not pdf_path.exists():
        raw_candidates = list(Path("data/raw").glob(f"*{detected_code}*.pdf")) if detected_code else []
        if raw_candidates:
            pdf_path = raw_candidates[0]

    if not pdf_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file đề cương tại: {path}")

    # 2. Thu thập văn bản theo trang
    page_texts: List[Tuple[int, str]] = []

    # Ưu tiên tái sử dụng OCR sạch đã tiền xử lý nếu có sẵn trong data/interim/ocr_clean
    cached_clean_dir = None
    if detected_code:
        c_dir = Path("data/interim/ocr_clean") / detected_code
        if c_dir.exists() and any(c_dir.glob("p-*.txt")):
            cached_clean_dir = c_dir

    if cached_clean_dir:
        def p_num(p_file: Path) -> int:
            m = re.search(r"p-0*(\d+)\.txt$", p_file.name)
            return int(m.group(1)) if m else 0

        for f in sorted(cached_clean_dir.glob("p-*.txt"), key=p_num):
            page_texts.append((p_num(f), f.read_text(encoding="utf-8")))
    else:
        # Nếu chưa có OCR sạch, thực hiện render và OCR
        temp_dir = Path("/tmp/syllabus_ocr") / (detected_code or f"pdf_{int(time.time())}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Render ảnh bằng pdftoppm
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

    # 3. Phân đoạn văn bản
    paragraphs = extract_paragraphs_from_pages(page_texts)

    # 4. Phân loại mục bằng mô hình M1 (SectionClassifierBundle)
    bundle = load_section_classifier(model_path)
    predicted_sections = bundle.predict_course_paragraphs(paragraphs, monotonic=True)

    # 5. Gom nội dung theo 10 mục chuẩn
    sections_content: Dict[str, List[str]] = {sec: [] for sec in SECTIONS_ORDER}
    for para, sec_label in zip(paragraphs, predicted_sections):
        if sec_label in sections_content:
            sections_content[sec_label].append(para["text"])

    sections_dict = {sec: "\n\n".join(texts).strip() for sec, texts in sections_content.items()}

    # 6. Trích xuất các trường từ general_info
    gen_text = sections_dict.get("general_info", "")
    extracted_fields = extract_fields_from_general_info(gen_text)

    # Xác định mã môn và tên môn
    course_code = extracted_fields.get("course_code") or detected_code
    course_name = extracted_fields.get("course_name")

    # Bổ sung từ tên file nếu chưa trích được
    if not course_name:
        clean_stem = re.sub(r"^\d+\s*[-–]\s*", "", pdf_path.stem)
        clean_stem = re.sub(r"^\d{6}\s*[-–]\s*", "", clean_stem)
        course_name = clean_stem.strip() or f"Học phần {course_code or ''}".strip()

    credits_val = extracted_fields.get("credits") or 3
    prerequisites_val = extracted_fields.get("prerequisites") or []

    # Áp dụng các hiệu chỉnh đã xác thực trong syllabus_fixes.json nếu có
    fixes_file = Path("data/interim/syllabus_fixes.json")
    if fixes_file.exists() and course_code:
        try:
            with open(fixes_file, encoding="utf-8") as f:
                fixes_map = json.load(f)
            if course_code in fixes_map:
                fix_data = fixes_map[course_code]
                if "credits" in fix_data and fix_data["credits"] is not None:
                    credits_val = fix_data["credits"]
                if "prerequisites" in fix_data and fix_data["prerequisites"] is not None:
                    prerequisites_val = fix_data["prerequisites"]
        except Exception as exc:
            logger.warning("Lỗi đọc syllabus_fixes.json: %s", exc)

    # 7. Trích xuất CLO từ mục course_learning_outcomes
    clo_text = sections_dict.get("course_learning_outcomes", "")
    clos = extract_clos_from_text(clo_text)

    # Nếu trích xuất tự động qua text không có, kiểm tra clos_raw.csv có sẵn
    if not clos and course_code:
        clos_raw_file = Path("data/interim/clos_raw.csv")
        if clos_raw_file.exists():
            import csv
            with open(clos_raw_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
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
                            "bloom_label": None,
                        })

    # 8. Xác định missing_sections
    missing_sections = [sec for sec in SECTIONS_ORDER if not sections_dict.get(sec)]

    elapsed_s = time.time() - t_start

    result: Dict[str, Any] = {
        "course_code": course_code,
        "course_name": course_name,
        "credits": credits_val,
        "prerequisites": prerequisites_val,
        "clos": clos,
        "sections": sections_dict,
        "missing_sections": missing_sections,
        "model_version": "m1-v1.0",
        "processing_time_s": round(elapsed_s, 3),
    }

    return result
