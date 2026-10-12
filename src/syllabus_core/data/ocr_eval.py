"""Chấm OCR trên 5 đề cương khó có đáp án chuẩn (xem GT_DIR/README.md). Hai cách chấm, mỗi cách một log riêng:

1. Bảng CLO (`score`): so từng CLO trong đáp án với văn bản OCR của trang chứa CLO đó.
   Chỉ số: CER (tỉ lệ ký tự sai), CER bỏ dấu (chỉ tính sai chữ cái), level đúng theo 2 cách:
     chặt = số ngay sau câu CLO (bắt lỗi ở nhiều dòng); lỏng = số nằm gần câu CLO (cận trên, có thể đếm nhầm).
2. Toàn bộ chữ (`score_text`): so từng trang OCR với đáp án cả trang, không phụ thuộc thứ tự dòng.
   Chỉ số: độ phủ (từ đáp án mà OCR đọc ra), độ chính xác (từ OCR ra mà có trong đáp án), F1, độ phủ bỏ dấu,
   CER theo từng dòng đáp án (tìm dòng đó trong cả trang OCR).
   Chỉ chấm các trang đã có kết quả OCR; cột n_pages/n_pages_gold cho biết đã phủ bao nhiêu trang.

3. Số trình độ của engine kết hợp (`score_levels`): so danh sách số trong p-N.levels với level của đáp án theo thứ tự CLO.

Dùng: python src/syllabus_core/data/ocr_eval.py data/interim/ocr_trial_<engine>   (chấm một thư mục)
      python src/syllabus_core/data/ocr_eval.py --compare                          (so sánh các engine hiện có)
Thư mục OCR có dạng <thư_mục>/<mã_môn>/<trang>.txt.
"""
import csv
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

GT_DIR = Path("docs/ocr_ground_truth_5_hard_syllabi")  # đáp án chuẩn (được commit)
GOLD = GT_DIR / "clo_table_ground_truth.csv"
EVAL_DIR = Path("data/interim/ocr_gold")  # log điểm mỗi lần chạy: eval_<engine>_clo.csv, eval_<engine>_full.csv (cục bộ, không commit)
# 5 đề cương khó ghi cứng: chọn theo độ tin cậy Tesseract thấp + có bảng CLO
NAMES = {"841401": "Giải tích 1", "841468": "Chuyên đề J2EE", "841411": "Quản trị mạng",
         "841058": "Hệ điều hành mã nguồn mở", "841470": "Tương tác người máy"}


def norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()


def strip_tone(s):
    s = unicodedata.normalize("NFD", s).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def fuzzy(pat, text):
    """Khoảng cách sửa nhỏ nhất giữa pat và một đoạn con của text (Sellers); trả (khoảng cách, vị trí kết thúc)."""
    prev = [0] * (len(text) + 1)
    for i, a in enumerate(pat, 1):
        cur = [i]
        for j, b in enumerate(text, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a != b)))
        prev = cur
    end = min(range(len(prev)), key=prev.__getitem__)
    return prev[end], end


@lru_cache(maxsize=None)
def gold_rows():
    return list(csv.DictReader(open(GOLD, encoding="utf-8-sig")))


def page_number(path):
    """'p-02.png' / 'p-2.txt' -> 2 (pdftoppm thêm số 0 tùy theo số trang của PDF)."""
    return int(Path(path).stem.split("-")[1])


def clo_pages(code):
    """Các số trang chứa bảng CLO của môn (đọc từ cột page trong đáp án chuẩn)."""
    return {int(r["page"]) for r in gold_rows() if r["course_code"] == code}


def gold_pages(code):
    """{số trang: file đáp án cả trang} của môn."""
    d = next((GT_DIR / "page_text_ground_truth").glob(f"{code}_*"))
    return {int(p.stem.split("_")[1]): p for p in d.glob("page_*.txt")}


def score(ocr_dir, codes=None):
    """Chấm CLO từng môn (lọc theo codes nếu có); bỏ qua CLO mà trang OCR của nó chưa có."""
    out = []
    for code in NAMES:
        if codes and code not in codes:
            continue
        pages = {page_number(p): p for p in (Path(ocr_dir) / code).glob("p-*.txt")}
        d = dt = n = lv = lo = k = 0
        for r in (r for r in gold_rows() if r["course_code"] == code):
            if int(r["page"]) not in pages:
                continue
            ocr = norm(pages[int(r["page"])].read_text(encoding="utf-8"))
            g = norm(r["text"])
            dist, end = fuzzy(g, ocr)
            d, n, k = d + dist, n + len(g), k + 1
            dt += fuzzy(strip_tone(g), strip_tone(ocr))[0]
            m = re.search(r"\d(?:[.,]\d)?", ocr[end:end + 12])  # số trình độ ngay sau câu CLO
            lv += bool(m) and m.group().replace(",", ".") == r["level"]
            near = ocr[max(0, end - len(g) - 10):end + 12]
            lo += bool(re.search(rf"(?<![\w.,]){re.escape(r['level'])}(?![\w])(?!\.\d)", near))
        if k:
            out.append({"course_code": code, "n_clo": k, "level_strict": lv, "level_loose": lo,
                        "_n": n, "_d": d, "_dt": dt})
    return out


def words(s):
    return re.findall(r"\w+", norm(s).lower())


def score_text(ocr_dir, codes=None):
    """Chấm toàn bộ chữ từng môn trên các trang đã có kết quả OCR."""
    out = []
    for code in NAMES:
        if codes and code not in codes:
            continue
        gold = gold_pages(code)
        pages = {page_number(p): p for p in (Path(ocr_dir) / code).glob("p-*.txt")}
        r = dict.fromkeys(["n_pages", "gold_words", "ocr_words", "hit", "hit_no_tone", "_n", "_d", "_dt"], 0)
        for n, gp in gold.items():
            if n not in pages:
                continue
            raw = gp.read_text(encoding="utf-8")
            ocr = norm(pages[n].read_text(encoding="utf-8"))
            ocr_t = strip_tone(ocr)
            gw, ow = words(raw), words(ocr)
            r["n_pages"] += 1
            r["gold_words"] += len(gw)
            r["ocr_words"] += len(ow)
            r["hit"] += sum((Counter(gw) & Counter(ow)).values())
            r["hit_no_tone"] += sum((Counter(map(strip_tone, gw)) & Counter(map(strip_tone, ow))).values())
            for line in filter(None, map(norm, raw.splitlines())):
                r["_n"] += len(line)
                r["_d"] += fuzzy(line, ocr)[0]
                r["_dt"] += fuzzy(strip_tone(line), ocr_t)[0]
        if r["n_pages"]:
            out.append({"course_code": code, "n_pages_gold": len(gold), **r})
    return out


def with_rates(rows):
    """Thêm dòng TONG và các tỉ lệ CER cho mỗi dòng (khóa bắt đầu bằng _ là số đếm thô)."""
    if rows:
        rows = rows + [{"course_code": "TONG", **{k: sum(r[k] for r in rows) for k in rows[0] if k != "course_code"}}]
    return [{**r, "cer": r["_d"] / r["_n"], "cer_no_tone": r["_dt"] / r["_n"]} for r in rows]


def text_rates(rows):
    """with_rates + độ phủ, độ chính xác, F1 theo từ cho kết quả của score_text."""
    out = []
    for r in with_rates(rows):
        rec, prec = r["hit"] / r["gold_words"], r["hit"] / r["ocr_words"]
        out.append({**r, "recall": rec, "precision": prec, "f1": 2 * rec * prec / (rec + prec) if rec + prec else 0,
                    "recall_no_tone": r["hit_no_tone"] / r["gold_words"]})
    return out


def show(rows):
    for r in rows:
        print(f"{r['course_code']:>7}: {r['n_clo']:2} CLO | CER {r['cer']:6.1%} | CER bỏ dấu {r['cer_no_tone']:6.1%} "
              f"| level chặt {r['level_strict']}/{r['n_clo']} | level lỏng {r['level_loose']}/{r['n_clo']}")


def show_text(rows):
    for r in rows:
        print(f"{r['course_code']:>7}: {r['n_pages']:2}/{r['n_pages_gold']:2} trang | phủ {r['recall']:6.1%} "
              f"(bỏ dấu {r['recall_no_tone']:6.1%}) | chính xác {r['precision']:6.1%} | F1 {r['f1']:6.1%} "
              f"| CER dòng {r['cer']:6.1%} (bỏ dấu {r['cer_no_tone']:6.1%})")


def score_levels(ocr_dir, codes=None):
    """Chấm số trình độ của engine kết hợp: số thứ k trong p-N.levels so với level của CLO thứ k trên trang đó.
    Trang chưa ghép được (file rỗng hoặc số lượng không khớp số CLO) thì mọi CLO của trang tính là sai."""
    out = []
    for code in NAMES:
        if codes and code not in codes:
            continue
        sides = {page_number(p): p for p in (Path(ocr_dir) / code).glob("p-*.levels")}
        gold_pg = clo_pages(code)
        r = {"course_code": code, "n_clo": 0, "level_order": 0, "pages_clo": len(gold_pg), "pages_found": 0,
             "pages_aligned": 0, "pages_extra": len(set(sides) - gold_pg)}
        for pg in sorted(gold_pg):
            gold = [x["level"] for x in gold_rows() if x["course_code"] == code and int(x["page"]) == pg]
            r["n_clo"] += len(gold)
            if pg not in sides:
                continue
            r["pages_found"] += 1
            got = sides[pg].read_text(encoding="utf-8").split()
            if len(got) == len(gold):
                r["pages_aligned"] += 1
                r["level_order"] += sum(float(a) == float(b) for a, b in zip(got, gold))
        out.append(r)
    if out:
        out.append({"course_code": "TONG", **{k: sum(r[k] for r in out) for k in out[0] if k != "course_code"}})
    return out


def show_levels(rows):
    for r in rows:
        print(f"{r['course_code']:>7}: {r['level_order']:2}/{r['n_clo']:2} CLO đúng số trình độ | trang CLO tìm thấy "
              f"{r['pages_found']}/{r['pages_clo']}, ghép được {r['pages_aligned']} | trang nhận thừa {r['pages_extra']}")


COMPARED = ["tesseract", "paddleocr", "ket_hop"]
COMPARE_ROWS = [  # (khóa, nhãn, "%" nếu là tỉ lệ)
    ("n_pages", "Số trang chấm", ""), ("cer", "CER bảng CLO", "%"), ("cer_no_tone", "CER bỏ dấu", "%"),
    ("level_loose", "Level lỏng (từ văn bản)", ""), ("level_strict", "Level chặt (từ văn bản)", ""),
    ("level_order", "Level theo thứ tự (ghép)", ""), ("recall", "Độ phủ", "%"), ("recall_no_tone", "Độ phủ bỏ dấu", "%"),
    ("precision", "Độ chính xác", "%"), ("f1", "F1", "%"), ("cer_line", "CER dòng", "%")]


def compare(codes=None):
    """Chấm lại các thư mục data/interim/ocr_trial_<engine> hiện có, in bảng so sánh (dòng TONG) và lưu so_sanh_engine.csv.
    Engine kết hợp dùng văn bản Tesseract nên level lấy từ văn bản không có nghĩa với nó; nó có cột level theo thứ tự riêng."""
    res = {}
    for e in COMPARED:
        d = Path(f"data/interim/ocr_trial_{e}")
        clo, full = (with_rates(score(d, codes)), text_rates(score_text(d, codes))) if d.is_dir() else ([], [])
        if not (clo and full):
            continue
        c, f = clo[-1], full[-1]
        m = {"n_pages": f"{f['n_pages']}/{f['n_pages_gold']}", "cer": c["cer"], "cer_no_tone": c["cer_no_tone"],
             "recall": f["recall"], "recall_no_tone": f["recall_no_tone"], "precision": f["precision"], "f1": f["f1"],
             "cer_line": f["cer"]}
        if e == "ket_hop":
            lv = score_levels(d, codes)[-1]
            m["level_order"] = f"{lv['level_order']}/{lv['n_clo']}"
        else:
            m["level_loose"], m["level_strict"] = f"{c['level_loose']}/{c['n_clo']}", f"{c['level_strict']}/{c['n_clo']}"
        res[e] = m
    borrowed = ("level_loose", "level_strict")
    if "ket_hop" in res and "paddleocr" in res:  # số trình độ của kết hợp lấy từ PaddleOCR nên mượn điểm level của PaddleOCR
        for key in borrowed:
            res["ket_hop"][key] = res["paddleocr"][key]
    print(f"{'':27}" + "".join(f"{e:>12}" for e in res))
    for key, label, kind in COMPARE_ROWS:
        cells = []
        for e in res:
            v = res[e].get(key)
            cells.append("—" if v is None else f"{v:.1%}" if kind else f"{v}{'*' if e == 'ket_hop' and key in borrowed else ''}")
        print(f"{label:27}" + "".join(f"{c:>12}" for c in cells))
    if "ket_hop" in res and "paddleocr" in res:
        print("* ket_hop lấy số trình độ từ PaddleOCR nên dùng điểm level lỏng/chặt của PaddleOCR.")
    path = EVAL_DIR / "so_sanh_engine.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["engine"] + [k for k, _, _ in COMPARE_ROWS])
        w.writeheader()
        for e, m in res.items():
            w.writerow({"engine": e, **{k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()}})
    print(f"Đã lưu bảng so sánh vào {path}")
    return res


if __name__ == "__main__":
    if sys.argv[1] == "--compare":
        compare()
        raise SystemExit
    print("Bảng CLO:")
    show(with_rates(score(sys.argv[1])))
    print("\nToàn bộ chữ:")
    show_text(text_rates(score_text(sys.argv[1])))
    if any(Path(sys.argv[1]).glob("*/*.levels")):
        print("\nSố trình độ theo thứ tự (engine kết hợp):")
        show_levels(score_levels(sys.argv[1]))
