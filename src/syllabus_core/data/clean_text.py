"""Làm sạch chữ OCR từng trang: chuẩn hóa NFC, bỏ nhiễu và số trang, ghép dòng bị ngắt, sửa lỗi dấu theo từ điển.

Dùng: python src/syllabus_core/data/clean_text.py [--src data/interim/ocr] [--out data/interim/ocr_clean]
        [--raw data/interim/ocr_raw/tesseract] [--skip-vocab 841401 ...]
  --src         thư mục <mã_môn>/p-N.txt cần làm sạch
  --raw         thư mục <mã_môn>/p-N.tsv của Tesseract, nguồn của từ điển
  --skip-vocab  loại các môn này khỏi từ điển (chỉ để thử độ nhạy; mặc định dùng cả bộ vì từ điển chỉ lấy chữ OCR, không dùng
                đáp án, và chữ của chính môn đó giúp giữ lại các từ chuyên môn lặp lại nhiều lần)

Từ điển tự xây: các từ Tesseract đọc với độ tin cậy cao (conf >= 90) trên toàn bộ đề cương, đếm từ đơn và cặp hai từ liền nhau.
Một từ bị sửa thành từ cùng chữ cái gốc (bỏ hết dấu) khi cặp từ liền kề của từ mới xuất hiện nhiều hơn hẳn (ngữ cảnh), hoặc khi từ
đang xét chưa từng xuất hiện trong từ điển. Dựa vào ngữ cảnh vì nhiều lỗi ("học phân") vẫn là từ hợp lệ khi đứng riêng.
Ghép dòng thận trọng vì đề cương có nhiều danh sách mỗi mục một dòng: chỉ nối khi dòng sau bắt đầu bằng chữ thường.
"""
import argparse
import csv
import itertools
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from ocr_eval import strip_tone  # chạy như script nên import cùng thư mục

WORD = re.compile(r"[^\W\d_]+")  # chuỗi chữ cái (Unicode)
CORE = re.compile(r"\W*([^\W\d_]+)\W*")  # từ đã bỏ dấu câu dính hai đầu
MIN_CONF = 90  # chỉ lấy từ Tesseract tin cậy cao vào từ điển
CONTEXT_RATIO = 3  # ngữ cảnh của từ mới phải mạnh gấp ngần này lần từ đang xét
MIN_UNSEEN = 2  # từ chưa từng thấy chỉ bị thay bằng từ cùng chữ gốc xuất hiện ít nhất ngần này lần


def tsv_lines(path):
    """Các dòng chữ của một trang tsv: mỗi dòng là danh sách (từ, độ_tin_cậy)."""
    lines = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(row) >= 12 and row[0] == "5" and row[11].strip():
                lines[(row[2], row[3], row[4])].append((unicodedata.normalize("NFC", row[11]).strip(), float(row[10])))
    return list(lines.values())


class Vocab:
    def __init__(self, raw_dir, skip=()):
        self.uni, self.bi, self.skel, self.courses = Counter(), Counter(), defaultdict(list), set()
        for tsv in Path(raw_dir).glob("*/p-*.tsv"):
            if tsv.parent.name in skip:
                continue
            self.courses.add(tsv.parent.name)
            for line in tsv_lines(tsv):
                prev = None
                for w, conf in line:
                    m = CORE.fullmatch(w)
                    if conf < MIN_CONF or not m:
                        prev = None
                        continue
                    lw = m.group(1).lower()
                    self.uni[lw] += 1
                    if prev:
                        self.bi[(prev, lw)] += 1
                    prev = lw
        for w in self.uni:
            self.skel[strip_tone(w)].append(w)

    def fix(self, w, prev, nxt):
        """Sửa một từ theo ngữ cảnh (prev, nxt là từ liền trước và liền sau, chữ thường, có thể None)."""
        lw = w.lower()
        cands = self.skel.get(strip_tone(lw))
        if not cands or len(lw) < 2:  # token một ký tự thường là rác OCR, không sửa
            return w
        ctx = lambda c: self.bi[(prev, c)] + self.bi[(c, nxt)]
        best = max(cands, key=lambda c: (ctx(c), self.uni[c]))
        if best == lw:
            return w
        if (ctx(best) >= 2 and ctx(best) >= CONTEXT_RATIO * max(ctx(lw), 1)) or (self.uni[lw] == 0 and self.uni[best] >= MIN_UNSEEN):
            return best.upper() if w.isupper() and len(w) > 1 else best.capitalize() if w[0].isupper() else best
        return w


def fix_line(line, vocab, stats):
    ms = list(WORD.finditer(line))
    words = [m.group().lower() for m in ms]
    out, last = [], 0
    for i, m in enumerate(ms):
        prev = words[i - 1] if i else None
        nxt = words[i + 1] if i + 1 < len(words) else None
        new = vocab.fix(m.group(), prev, nxt)
        if new != m.group():
            stats["fixed_words"] += 1
            stats[(m.group().lower(), new.lower())] += 1  # khóa là cặp (từ cũ, từ mới) để thống kê các lỗi hay gặp
        out += [line[last:m.start()], new]
        last = m.end()
    return "".join(out) + line[last:]


def clean_page(text, vocab, stats=None):
    """Làm sạch chữ một trang. stats (Counter, tùy chọn) được cộng dồn: noise_lines, page_numbers, joined_lines, fixed_words."""
    stats = Counter() if stats is None else stats
    lines = [re.sub(r"\s+", " ", re.sub(r"[|¦_¬~]+", " ", l)).strip() for l in unicodedata.normalize("NFC", text).splitlines()]
    before = sum(1 for l in lines if l)
    lines = [l for l in lines if l == "" or re.search(r"[^\W_]", l)]  # bỏ dòng chỉ có ký tự lạ
    stats["noise_lines"] += before - sum(1 for l in lines if l)
    filled = [i for i, l in enumerate(lines) if l]
    for i in filled[:2] + filled[-2:]:  # số trang nằm ở đầu hoặc cuối trang
        if re.fullmatch(r"\d{1,3}", lines[i]):
            lines[i] = ""
            stats["page_numbers"] += 1
    out = []
    for l in lines:  # ghép dòng: chỉ nối khi dòng sau bắt đầu bằng chữ thường và dòng trước chưa hết câu
        if l and out and out[-1] and l[0].islower() and not re.search(r"[.:;?!]$", out[-1]):
            out[-1] += " " + l
            stats["joined_lines"] += 1
        else:
            out.append(l)
    text = "\n".join(fix_line(l, vocab, stats) for l in out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/interim/ocr")
    ap.add_argument("--out", default="data/interim/ocr_clean")
    ap.add_argument("--raw", default="data/interim/ocr_raw/tesseract")
    ap.add_argument("--skip-vocab", nargs="*", default=[], metavar="mã_môn")
    a = ap.parse_args()
    vocab = Vocab(a.raw, set(a.skip_vocab))
    print(f"Từ điển: {len(vocab.uni)} từ, {len(vocab.bi)} cặp từ, xây từ chữ Tesseract tin cậy cao (conf >= {MIN_CONF}) "
          f"của {len(vocab.courses)} môn" + (f" (loại {len(a.skip_vocab)} môn: {', '.join(a.skip_vocab)})" if a.skip_vocab else ""))
    pages = sorted(Path(a.src).glob("*/p-*.txt"))
    print(f"Làm sạch {len(pages)} trang của {len({p.parent.name for p in pages})} môn: {a.src} -> {a.out}\n")
    print(f"{'Môn':<8} {'Trang':>5} {'Dòng nhiễu':>10} {'Số trang':>9} {'Dòng ghép':>10} {'Từ sửa':>7}")
    total = Counter()
    for course, group in itertools.groupby(pages, key=lambda p: p.parent.name):
        st, n = Counter(), 0
        for p in group:
            dest = Path(a.out) / course / p.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(clean_page(p.read_text(encoding="utf-8"), vocab, st), encoding="utf-8")
            n += 1
        total.update(st)
        total["pages"] += n
        print(f"{course:<8} {n:>5} {st['noise_lines']:>10} {st['page_numbers']:>9} {st['joined_lines']:>10} {st['fixed_words']:>7}")
    print(f"\nTổng kết: {total['pages']} trang | bỏ {total['noise_lines']} dòng nhiễu, {total['page_numbers']} số trang | "
          f"ghép {total['joined_lines']} dòng | sửa {total['fixed_words']} từ")
    fixes = Counter({k: v for k, v in total.items() if isinstance(k, tuple)}).most_common(15)
    print("Các từ được sửa nhiều nhất: " + ", ".join(f"{old} -> {new} ({n})" for (old, new), n in fixes))
    print(f"Đã ghi {total['pages']} trang vào {a.out}")


if __name__ == "__main__":
    main()
