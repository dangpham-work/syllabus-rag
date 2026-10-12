"""Render đề cương PDF -> PNG 300 DPI bằng pdftoppm (poppler).

Dùng: python src/syllabus_core/data/pdf_to_images.py [mã_môn ...]
Không đưa mã môn = render mọi môn không trùng. Môn thiếu mã dùng khóa "stt<số thứ tự>".
Kết quả: data/interim/images/<khóa>/p-<trang>.png (pdftoppm tự thêm số 0 nếu >= 10 trang)
Chạy lại bỏ qua môn đã có ảnh (nếu một môn render dở thì phải xóa thư mục môn đó rồi chạy lại).
Log: mỗi môn một dòng (render mới hay bỏ qua, số ảnh so với số trang PDF, thời gian) và tổng kết cuối.
Một môn lỗi không làm dừng cả lần chạy; thoát với mã 1 nếu có môn lỗi hoặc lệch số trang.
"""
import csv
import re
import subprocess
import sys
import time
from pathlib import Path

RAW = Path("data/raw")
OUT = Path("data/interim/images")


def course_key(row):
    return row["course_code"] or "stt" + re.match(r"\d+", row["file_name"]).group()


def render(pdf, key, dpi=300):
    """Trả về (thư_mục_ảnh, True nếu vừa render mới, False nếu đã có ảnh)."""
    out = OUT / key
    if any(out.glob("*.png")):  # đã render, bỏ qua
        return out, False
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(out / "p")], check=True, capture_output=True)
    return out, True


def main(keys):
    with open(RAW / "inventory.csv", encoding="utf-8-sig") as f:  # -sig: chịu được file có BOM
        rows = [r for r in csv.DictReader(f) if not r["duplicate_of"]]
    todo = [(course_key(r), r) for r in rows if not keys or course_key(r) in keys]
    for k in sorted(keys - {key for key, _ in todo}):
        print(f"CẢNH BÁO: '{k}' không có trong bảng kê (hoặc là bản trùng), bỏ qua")
    print(f"Render {len(todo)} môn (300 DPI) -> {OUT}")

    t_all, new, kept, failed, mismatched = time.time(), 0, 0, [], []
    for i, (key, r) in enumerate(todo, 1):
        t0 = time.time()
        try:
            out, rendered = render(RAW / r["file_name"], key)
        except subprocess.CalledProcessError as e:
            failed.append(key)
            print(f"[{i:>2}/{len(todo)}] {key}: LỖI pdftoppm (mã {e.returncode}): {e.stderr.decode(errors='replace').strip()[:120]}")
            continue
        n = len(list(out.glob("*.png")))
        note = ""
        if str(n) != str(r["n_pages"]):
            mismatched.append(key)
            note = f"   <-- LỆCH: PDF có {r['n_pages']} trang"
        new, kept = new + rendered, kept + (not rendered)
        print(f"[{i:>2}/{len(todo)}] {key}: {'render mới' if rendered else 'đã có, bỏ qua':<14} {n}/{r['n_pages']} trang, "
              f"{time.time() - t0:.1f}s{note}")

    images = [p for key, _ in todo for p in (OUT / key).glob("*.png")]
    size_mb = sum(p.stat().st_size for p in images) / 1e6
    print(f"\nTổng kết: {len(todo)} môn | render mới {new} | đã có, bỏ qua {kept} | lỗi {len(failed)} | lệch số trang {len(mismatched)}")
    print(f"  {len(images)} ảnh, {size_mb:.0f} MB, mất {time.time() - t_all:.0f}s")
    if failed:
        print(f"  môn lỗi: {failed} (xóa thư mục môn đó trong {OUT} nếu render dở rồi chạy lại)")
    if mismatched:
        print(f"  môn lệch số trang: {mismatched}")
    sys.exit(1 if failed or mismatched else 0)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
