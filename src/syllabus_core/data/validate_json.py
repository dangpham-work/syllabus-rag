"""Kiểm mọi JSON đề cương theo docs/schema_syllabus.json.

Dùng: python src/syllabus_core/data/validate_json.py [--dir data/processed/syllabi] [--schema docs/schema_syllabus.json]
  In từng lỗi (tên file, đường dẫn trường, lý do) và tỷ lệ hợp lệ; thoát mã 1 nếu còn file lỗi.
  Ngoài schema còn kiểm: tên file khớp course_code (môn thiếu mã đặt tên stt<số>.json, course_code = null)
  và mã CLO không trùng nhau trong một đề cương.
  Cần thư viện jsonschema (chưa có trong requirements.txt, đang chờ nhóm đồng ý).
"""
import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def validate_all(json_dir, schema_path):
    """{tên_file: [lỗi]} cho mọi *.json trong thư mục; danh sách rỗng = hợp lệ."""
    validator = Draft202012Validator(json.loads(Path(schema_path).read_text(encoding="utf-8")))
    result = {}
    for path in sorted(Path(json_dir).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        errs = [f"{'/'.join(map(str, e.absolute_path)) or '(gốc)'}: {e.message[:120]}" for e in validator.iter_errors(doc)]
        code = doc.get("course_code")
        if (code or path.stem) != path.stem and not (code is None and path.stem.startswith("stt")):
            errs.append(f"tên file {path.name} không khớp course_code {code}")
        ids = [c.get("clo_id") for c in doc.get("clos", [])]
        if len(ids) != len(set(ids)):
            errs.append("clos: có clo_id trùng nhau")
        result[path.name] = errs
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default="data/processed/syllabi")
    ap.add_argument("--schema", default="docs/schema_syllabus.json")
    a = ap.parse_args()
    result = validate_all(a.dir, a.schema)
    for name, errs in result.items():
        for e in errs:
            print(f"{name}: {e}")
    ok = sum(not e for e in result.values())
    print(f"{ok}/{len(result)} file hợp lệ ({100 * ok / max(len(result), 1):.0f}%)")
    sys.exit(0 if ok == len(result) else 1)


if __name__ == "__main__":
    main()
