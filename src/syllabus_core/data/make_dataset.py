"""Dựng JSON đề cương cho mọi môn: trích trường bằng luật từ mục 1, ghép bảng CLO và 10 mục đã tách.

Dùng: python src/syllabus_core/data/make_dataset.py [--src data/interim/ocr_clean] [--out data/processed/syllabi]
        [--clos data/interim/clos_raw.csv] [--inventory data/raw/inventory.csv] [--fixes data/interim/syllabus_fixes.json]
  Xuất data/processed/syllabi/<mã_môn>.json (môn thiếu mã: stt74.json, stt80.json) theo docs/schema_syllabus.json.
  Môn trùng (cột duplicate_of của inventory.csv) bỏ qua. Trường nào luật không đọc được thì để theo quy ước schema
  (null / mảng rỗng / vắng) và in cảnh báo; sửa tay đặt trong --fixes: {"<mã_môn>": {"credits": 3, ...}}, ghi đè sau cùng.
  Kiểm bằng validate_json.py.
"""
import argparse
import csv
import difflib
import json
import re
from pathlib import Path

from split_sections import SECTIONS, fold, split_course

BLOCKS = {  # nhãn đã bỏ dấu của từng khối kiến thức
    "dai_cuong": "kien thuc giao duc dai cuong", "co_so_nganh": "kien thuc co so nganh",
    "chuyen_nganh": "kien thuc chuyen nganh", "nganh": "kien thuc nganh"}
HOURS = {"theory": "ly thuyet", "exercises": "thao luan", "practice": "thuc hanh",
         "group_activity": "hoat dong nhom", "self_study": "tu hoc"}


def after_colon(line):
    return line.rsplit(":", 1)[1].strip(" .;\t") if ":" in line else ""


def first_int(s):
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None


def parse_level(raw):
    """level_raw -> số. "2,0"/"2,5" là số thập phân; danh sách như "3,4" hay "2,3,4,5" lấy mức cao nhất."""
    if not raw or not raw.strip():
        return None
    toks = re.split(r"[,;]", raw.strip())
    try:
        if len(toks) == 2 and toks[1] in ("0", "5"):
            return float(".".join(toks))
        return max(float(t) for t in toks)
    except ValueError:
        return None


def course_list(v):
    """Chuỗi tiên quyết/song hành -> danh sách mã (nếu có mã 6 số) hoặc tên học phần."""
    if not v or fold(v).strip(" .") in ("khong", "khong co", "-"):
        return []
    codes = re.findall(r"\b\d{6}\b", v)
    return codes or [p.strip(" .") for p in re.split(r"[;,]", v) if p.strip(" .") and fold(p).strip(" .") != "khong"]


def general_fields(lines):
    """Các trường lấy từ mục 1 (danh sách dòng chữ OCR sạch). Nhãn khớp trên chữ bỏ dấu, giá trị lấy từ dòng gốc."""
    f = [(fold(ln), ln) for ln in lines]
    out = {}
    for fl, ln in f:
        v = after_colon(ln)
        if "ten hoc phan" in fl and "viet" in fl and v:
            out["name_ocr"] = v
        elif "tieng anh" in fl and v:
            out["course_name_en"] = v
        elif "ma so hoc phan" in fl:
            m = re.search(r"\b\d{6}\b", fl)
            if m:
                out["code_ocr"] = m.group()
        elif "tin chi" in fl or fl.lstrip("-+ ").startswith(("so tin", "o tin")):
            out["credits"] = first_int(v)
        elif fl.lstrip("-+ ").startswith("so tiet"):
            for k, label in HOURS.items():
                if label in fl and first_int(v) is not None:
                    out.setdefault("hours", {})[k] = first_int(v)
        elif "tien quyet" in fl or "hoc truoc" in fl:
            out.setdefault("prerequisites", []).extend(course_list(v))  # "tiên quyết" và "học trước" gộp chung
        elif "song hanh" in fl:
            out["corequisites"] = course_list(v)
    # Khối kiến thức: ô được đánh dấu có chữ "x" ngay trước nhãn ("Ix] Kiến thức cơ sở ngành").
    text = " ".join(fl for fl, _ in f)
    start = text.find("thuoc khoi")
    seg = text[start:text.find("so tin chi", start)] if start >= 0 else ""
    marked = [k for k, label in BLOCKS.items() for m in re.finditer(label, seg)
              if "x" in seg[max(0, m.start() - 4):m.start()] and not (k == "nganh" and seg[max(0, m.start() - 7):m.start()] == "co so ")]
    out["knowledge_block"] = marked[0] if len(marked) == 1 else None
    return out


def read_inventory(path):
    """{khóa_môn: dòng} của các môn không trùng; khóa là mã môn hoặc stt<số> khi thiếu mã."""
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not r["duplicate_of"]:
                out[r["course_code"] or "stt" + re.match(r"\d+", r["file_name"]).group()] = r
    return out


def read_clos(path):
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            raw, lv = r["level_raw"].strip(), parse_level(r["level_raw"])
            out.setdefault(r["course_code"], []).append({
                "clo_id": r["clo_id"], "text": r["text"], "level_raw": raw or None,
                "level": None if lv is None else (int(lv) if lv == int(lv) else lv),
                "page": int(r["page"]) if r["page"] else None, "ocr_ok": r["ocr_ok"] == "True"})
    return out


def build_course(key, src_dir, inv, clos):
    """(JSON đề cương dạng dict, danh sách cảnh báo) của một môn."""
    warn = []
    paras, pages = split_course(Path(src_dir) / key)
    sections = {}
    for s in SECTIONS:
        txt = "\n".join(p["text"] for p in paras if p["section"] == s)
        sections[s] = txt if (txt or s in pages) else None  # "" = có tiêu đề nhưng trống; None = không thấy tiêu đề
        if s not in pages:
            warn.append(f"thiếu tiêu đề mục {s}")
    gen = general_fields(sections["general_info"].splitlines() if sections["general_info"] else [])

    code = key if key.isdigit() else None
    if gen.get("code_ocr") and gen["code_ocr"] != code:
        warn.append(f"mã in trên trang {gen['code_ocr']} khác mã tên file {code}")
    name, ocr_name = inv["course_name"], gen.get("name_ocr", "")  # tên trong tên file sạch dấu hơn OCR
    if not ocr_name:
        warn.append("không đọc được tên học phần, dùng tên file")
    elif difflib.SequenceMatcher(None, fold(ocr_name), fold(name)).ratio() < 0.6:
        warn.append(f"tên OCR '{ocr_name}' khác tên file '{name}'")

    doc = {"course_code": code, "course_name": name, "course_name_en": gen.get("course_name_en"),
           "credits": gen.get("credits"), "knowledge_block": gen["knowledge_block"], "hours": gen.get("hours", {}),
           "prerequisites": gen.get("prerequisites", []), "corequisites": gen.get("corequisites", []),
           "clos": clos.get(key, []), "sections": sections, "section_pages": {s: pages.get(s) for s in SECTIONS},
           "source_file": inv["file_name"], "n_pages": int(inv["n_pages"]),
           "provenance": {"method": "ocr_pipeline", "verified": False,
                          "note": "Sinh tự động từ OCR (Tesseract + PaddleOCR), trường trích bằng luật; chưa đối chiếu ảnh gốc."}}
    if not doc["clos"]:
        warn.append("không có CLO")
    if doc["credits"] is None:
        warn.append("không đọc được số tín chỉ")
    return doc, warn


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default="data/interim/ocr_clean")
    ap.add_argument("--out", default="data/processed/syllabi")
    ap.add_argument("--clos", default="data/interim/clos_raw.csv")
    ap.add_argument("--inventory", default="data/raw/inventory.csv")
    ap.add_argument("--fixes", default="data/interim/syllabus_fixes.json")
    a = ap.parse_args()

    fixes = json.loads(Path(a.fixes).read_text(encoding="utf-8")) if Path(a.fixes).exists() else {}
    inv, clos = read_inventory(a.inventory), read_clos(a.clos)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    n_warn = 0
    for key in sorted(inv):
        doc, warn = build_course(key, a.src, inv[key], clos)
        doc.update(fixes.get(key, {}))
        for w in warn:
            print(f"{key}: {w}")
        n_warn += bool(warn)
        (Path(a.out) / f"{key}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(inv)} môn -> {a.out}; {n_warn} môn có cảnh báo")


if __name__ == "__main__":
    main()
