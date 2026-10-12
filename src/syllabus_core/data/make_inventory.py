"""Lập bảng thống kê đề cương: data/raw/*.pdf -> data/raw/inventory.csv.

In từng file (STT, mã môn, số trang, tên môn, ghi chú: thiếu mã, trùng, không đọc được) rồi tổng kết.
"""
import csv
import re
from pathlib import Path

from pypdf import PdfReader

RAW = Path("data/raw")
# "30 - 841303 - Tên môn.pdf"; mã môn 6 số có thể thiếu (ví dụ "74 - Công nghệ .NET.pdf")
NAME_RE = re.compile(r"^(\d+) - (?:(\d{6}) - )?(.+)\.pdf$")


def count_pages(path):
    try:
        return len(PdfReader(path).pages)
    except Exception as e:  # file lỗi vẫn phải có dòng trong bảng kê
        print(f"  LỖI đọc {path.name}: {e}")
        return ""


def main():
    files = sorted(RAW.glob("*.pdf"))
    print(f"Quét {RAW}: {len(files)} file PDF")
    rows, skipped = [], []
    for p in files:
        m = NAME_RE.match(p.name)
        if not m:
            skipped.append(p.name)
            print(f"  BỎ QUA (tên không theo mẫu 'STT - mã - tên.pdf'): {p.name}")
            continue
        stt, code, name = m.groups()
        rows.append({"file_name": p.name, "course_code": code or "", "course_name": name,
                     "n_pages": count_pages(p), "duplicate_of": "", "_stt": int(stt)})

    # cùng mã môn: file STT nhỏ nhất là gốc, các file còn lại là bản trùng
    first = {}
    for r in sorted(rows, key=lambda r: r["_stt"]):
        if r["course_code"]:
            orig = first.setdefault(r["course_code"], r["file_name"])
            if orig != r["file_name"]:
                r["duplicate_of"] = orig

    ordered = sorted(rows, key=lambda r: r["_stt"])
    print(f"\n{'STT':>4} | {'Mã môn':<7} | {'Trang':>5} | Tên môn")
    for r in ordered:
        notes = []
        if not r["course_code"]:
            notes.append("THIẾU mã môn")
        if r["duplicate_of"]:
            notes.append(f"TRÙNG với '{r['duplicate_of']}'")
        if r["n_pages"] == "":
            notes.append("KHÔNG ĐỌC ĐƯỢC SỐ TRANG")
        print(f"{r['_stt']:>4} | {r['course_code'] or '-':<7} | {r['n_pages']!s:>5} | {r['course_name']}"
              + (f"   <-- {'; '.join(notes)}" if notes else ""))

    cols = ["file_name", "course_code", "course_name", "n_pages", "duplicate_of"]
    with open(RAW / "inventory.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(ordered)

    dups = [r for r in ordered if r["duplicate_of"]]
    no_code = [r for r in ordered if not r["course_code"]]
    unreadable = [r for r in ordered if r["n_pages"] == ""]
    pages = sum(r["n_pages"] for r in ordered if r["n_pages"] != "" and not r["duplicate_of"])
    print(f"\nTổng kết: {len(rows)} đề cương, {len(dups)} bản trùng, còn {len(rows) - len(dups)} môn khác nhau ({pages} trang, không tính bản trùng)")
    for r in dups:
        print(f"  trùng: STT {r['_stt']} '{r['file_name']}' = bản của '{r['duplicate_of']}'")
    print(f"  thiếu mã môn: {len(no_code)} {[r['file_name'] for r in no_code] or ''}")
    print(f"  không đọc được số trang: {len(unreadable)}; bỏ qua {len(skipped)} file không theo mẫu tên {skipped or ''}")
    print(f"Đã ghi {RAW / 'inventory.csv'}")


if __name__ == "__main__":
    main()
