"""Tách đoạn văn từ chữ OCR sạch và gán nhãn mục bằng regex theo tiêu đề "<số>. <tên mục>".

Dùng: python src/syllabus_core/data/split_sections.py [--src data/interim/ocr_clean] [--out data/processed/sections_labeled.csv]
  Xuất cột: course_code, para_id, page, text, section_regex, section_gold
  section_regex = nhãn do luật gán; section_gold = bản sao để người rà sửa tay (đoạn ở ranh giới hai mục ghi ra
  data/interim/sections_review.csv). Nếu CSV đã có thì giữ section_gold đã sửa của các đoạn trùng cả para_id lẫn nội dung.

Luật: 10 tiêu đề phải xuất hiện đúng thứ tự 1..10; tiêu đề k chỉ được tìm sau tiêu đề k-1. Nhờ vậy mục con như
"1. Đánh giá quá trình" trong mục 9 không bị nhận nhầm. Khớp trên chữ đã bỏ dấu để chịu được lỗi dấu của OCR.
Đoạn trước tiêu đề 1 (bìa) có nhãn "other". Dòng tiêu đề không đưa vào CSV (tránh rò nhãn cho mô hình M1).
"""
import argparse
import csv
import re
import unicodedata
from pathlib import Path

SECTIONS = ["general_info", "course_description", "course_objectives", "course_learning_outcomes", "course_content",
            "learning_resources", "teaching_schedule", "course_policies", "assessment", "responsible_unit"]
# Phần đầu tên mục (đã bỏ dấu, chữ thường); đủ ngắn để chịu lỗi OCR ở cuối dòng tiêu đề.
KEYS = ["thong tin tong", "mo ta hoc", "muc tieu", "chuan dau", "noi dung chi",
        "hoc lieu", "huon", "quy dinh", "phuong phap", "phu\\W"]
HEADINGS = [re.compile(rf"^\W*{k}\s*[.,:;)]?\s*{key}") for k, key in enumerate(KEYS, 1)]
# Lượt khớp lỏng cho mục bị lỡ: OCR đọc sai số mục ("3." thay "9.") hoặc dính nhiễu vào chữ. Số mục thay bằng tối đa 2 ký tự bất kỳ.
LOOSE = ["thong .{0,26}hoc phan", "mo ta .{0,3}hoc", "muc .{0,5}hoc phan", "chu.{1,3}n\\W*dau ra", "noi dung chi",
         "hoc\\s*(lieu)?\\s*:?\\s*$", "huon.{0,3}dan", "quy\\W{0,2}dinh\\W{0,2}.{0,8}(voi|doi)", "phuong phap .{0,6}gia", "phu .{0,6}trach"]
LOOSE = [re.compile(rf"^\W*[^\W_]{{0,2}}\W{{0,3}}{key}") for key in LOOSE]
MIN_CHARS = 8  # đoạn ngắn hơn (số trang, ký tự rác) bị bỏ


def fold(s):
    """Chữ thường, bỏ dấu tiếng Việt."""
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c))


def page_no(path):
    return int(re.search(r"p-0*(\d+)\.txt$", path.name).group(1))


def read_lines(course_dir):
    """Danh sách (trang, dòng) của cả đề cương, theo thứ tự trang."""
    out = []
    for p in sorted(course_dir.glob("p-*.txt"), key=page_no):
        out += [(page_no(p), ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    return out


def find_headings(lines):
    """{chỉ_số_dòng: số_mục} của các tiêu đề tìm được, theo thứ tự tăng dần, mỗi mục tối đa một lần.

    Tiêu đề mục k vắng (OCR hỏng) không làm kẹt: dòng khớp mục lớn hơn mục vừa tìm được vẫn được nhận."""
    found, last = {}, 0
    for i, (_, ln) in enumerate(lines):
        f = fold(ln)
        for k in range(last + 1, 11):
            if HEADINGS[k - 1].match(f):
                found[i], last = k, k
                break
    for k in [k for k in range(1, 11) if k not in found.values()]:
        lo = max([i for i, v in found.items() if v < k], default=-1)
        hi = min([i for i, v in found.items() if v > k], default=len(lines))
        for i in range(lo + 1, hi):
            if LOOSE[k - 1].match(fold(lines[i][1])):
                found[i] = k
                break
    return dict(sorted(found.items()))


def split_course(course_dir):
    """(đoạn, trang_tiêu_đề): đoạn = [{page, text, section}], trang_tiêu_đề = {tên_mục: trang}."""
    lines = read_lines(Path(course_dir))
    heads = find_headings(lines)
    paras, cur, cur_page, section = [], [], None, "other"
    skip = 0  # số dòng còn phải bỏ: phần ngoặc của tiêu đề bị ngắt xuống dòng sau

    def flush():
        text = "\n".join(cur).strip()
        if len(text) >= MIN_CHARS:
            paras.append({"page": cur_page, "text": text, "section": section})
        cur.clear()

    for i, (page, ln) in enumerate(lines):
        if i in heads:
            flush()
            section = SECTIONS[heads[i] - 1]
            skip = 3 if ln.count("(") > ln.count(")") else 0
            continue
        if skip and ")" not in ln and ln.strip():
            skip -= 1
            continue
        if skip and ")" in ln:
            skip = 0
            continue
        skip = 0
        if cur and page != cur_page:
            flush()
        if not ln.strip():
            flush()
            continue
        if not cur:
            cur_page = page
        cur.append(ln.strip())
    flush()
    return paras, {SECTIONS[k - 1]: lines[i][0] for i, k in heads.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default="data/interim/ocr_clean")
    ap.add_argument("--out", default="data/processed/sections_labeled.csv")
    ap.add_argument("--review", default="data/interim/sections_review.csv")
    a = ap.parse_args()

    old = {}
    if Path(a.out).exists():
        with open(a.out, encoding="utf-8-sig", newline="") as f:
            old = {(r["para_id"], r["text"]): r["section_gold"] for r in csv.DictReader(f)}

    rows, review = [], []
    for d in sorted(p for p in Path(a.src).iterdir() if p.is_dir()):
        paras, pages = split_course(d)
        miss = [s for s in SECTIONS if s not in pages]
        if miss:
            print(f"{d.name}: thiếu tiêu đề {miss}")
        for n, p in enumerate(paras, 1):
            pid = f"{d.name}-{n:03d}"
            rows.append({"course_code": d.name, "para_id": pid, "page": p["page"], "text": p["text"],
                         "section_regex": p["section"], "section_gold": old.get((pid, p["text"]), p["section"])})
            prev = paras[n - 2]["section"] if n > 1 else None
            nxt = paras[n]["section"] if n < len(paras) else None
            # Ranh giới: đoạn đầu/cuối của mục, hoặc đoạn rất ngắn; những đoạn này dễ gán sai nhất.
            if p["section"] != prev or p["section"] != nxt or len(p["text"]) < 30:
                review.append({"para_id": pid, "section_regex": p["section"], "prev": prev, "next": nxt,
                               "text": p["text"][:120].replace("\n", " ")})

    for path, data in ((a.out, rows), (a.review, review)):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    print(f"{len(rows)} đoạn / {len({r['course_code'] for r in rows})} môn -> {a.out}; {len(review)} đoạn cần rà -> {a.review}")


if __name__ == "__main__":
    main()
