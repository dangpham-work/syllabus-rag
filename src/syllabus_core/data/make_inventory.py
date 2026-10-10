"""Lap bang thong ke de cuong: data/raw/*.pdf -> data/raw/inventory.csv."""
import csv
import re
from pathlib import Path

from pypdf import PdfReader

RAW = Path("data/raw")
# "30 - 841303 - Ten mon.pdf"; ma mon 6 so co the thieu (vd "74 - Cong nghe. NET.pdf")
NAME_RE = re.compile(r"^(\d+) - (?:(\d{6}) - )?(.+)\.pdf$")


def count_pages(path):
    try:
        return len(PdfReader(path).pages)
    except Exception as e:  # file loi van phai co dong trong bang ke
        print(f"LOI doc {path.name}: {e}")
        return ""


def main():
    rows, skipped = [], []
    for p in sorted(RAW.glob("*.pdf")):
        m = NAME_RE.match(p.name)
        if not m:
            skipped.append(p.name)
            continue
        stt, code, name = m.groups()
        rows.append({"file_name": p.name, "course_code": code or "", "course_name": name,
                     "n_pages": count_pages(p), "duplicate_of": "", "_stt": int(stt)})

    # cung ma mon: file STT nho nhat la goc, cac file con lai la ban trung
    first = {}
    for r in sorted(rows, key=lambda r: r["_stt"]):
        if r["course_code"]:
            orig = first.setdefault(r["course_code"], r["file_name"])
            if orig != r["file_name"]:
                r["duplicate_of"] = orig

    cols = ["file_name", "course_code", "course_name", "n_pages", "duplicate_of"]
    with open(RAW / "inventory.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["_stt"]))
    print(f"{len(rows)} dong; bo qua {len(skipped)} file: {skipped}")


if __name__ == "__main__":
    main()
