"""Trích bảng chuẩn đầu ra (CLO) của mọi đề cương thành data/interim/clos_raw.csv
(cột: course_code, clo_id, text, level_raw, ocr_ok, page, note; note là lý do cần kiểm tra tay).

Dùng: python src/syllabus_core/data/extract_clos.py [--out data/interim/clos_raw.csv] [--fixes data/interim/clos_manual_fixes.csv] [--check]
  --check  chấm với đáp án chuẩn của 5 môn khó (mã CLO, số trình độ, CER của chữ)
  --fixes  các chỗ sửa tay (cột: course_code, clo_id, text, level_raw, page, action). Nếu file tồn tại thì mỗi lần chạy áp lên kết quả
           tự động, nên chạy lại không mất công sửa tay. Kết quả tự động (chưa sửa) luôn lưu thêm ở clos_raw_auto.csv.
Đọc: data/interim/ocr/<mã>/p-N.levels (trang CLO do engine kết hợp tìm ra), data/interim/ocr_raw/paddleocr (khung hàng),
      data/interim/ocr_clean/<mã>/p-N.txt (chữ Tesseract đã làm sạch bằng clean_text.py, dùng làm nội dung CLO).

Cách làm: PaddleOCR đọc đúng mã CLO và số trình độ nhưng rơi dấu; Tesseract đọc chữ tốt nhưng hay sai mã và số.
  1. PaddleOCR cho khung: mã CLO và số trình độ mỗi thứ một dòng, theo thứ tự hàng bảng. Chúng nằm giữa chiều cao hàng nên số dòng
     chữ phía trên mã xấp xỉ số dòng chữ phía dưới mã; từ đó chia các dòng chữ cho từng hàng (chọn trong ±1 theo dấu hiệu hết câu).
  2. Chữ của từng hàng của PaddleOCR được căn sang chữ Tesseract (so khớp theo chữ cái không dấu) để lấy lại chữ có dấu đúng.
ocr_ok = true khi số trình độ ghép được, khung hàng nhất quán (số dòng đối xứng) và mỗi hàng căn được phần lớn chữ.
Trang CLO không ghép được vẫn cho ra các dòng (mã CLO từ PaddleOCR, chữ và số trình độ trống, ocr_ok = false) để sửa tay.
"""
import argparse
import csv
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from ocr_eval import fuzzy, gold_rows, norm, page_number, strip_tone  # chạy như script nên import cùng thư mục
from ocr_hybrid import END_TITLE, P_ID, P_LEVEL, SECTION_5, page_skeleton

HEADER = re.compile(r"\(\s*\d\s*\)|ky hi|chu.?n d.?u ra|mo t.? chu|trinh d|nang l|nng l")  # ô tiêu đề cột (đã bỏ dấu)
HEADING = re.compile(r"chuan dau ra|trinh do nang luc|mo ta chuan")  # nhận biết trang có bảng CLO (chữ Tesseract đã bỏ dấu)
TESS_ID = re.compile(r"^[\W_]{0,3}[GgCcd]\s?[0-9IlOoSs]{1,2}\b[\W_]*")  # mã CLO đầu hàng trong chữ Tesseract (cho phép đọc sai nhẹ)
COLUMNS = ["course_code", "clo_id", "text", "level_raw", "ocr_ok", "page", "note"]  # note: lý do cần kiểm tra tay (trống nếu ocr_ok)
COURSE_DIR = re.compile(r"\d{6}|stt\d+")  # tên thư mục môn (bỏ qua thư mục rác như .ruff_cache)
CARRY_PAGES = 4  # trang có tiêu đề bảng CLO cộng các trang nối tiếp (ngần này trừ 1) được nhận, dừng sớm khi gặp tiêu đề mục 5
MIN_TEXT_CHARS = 12  # hàng có chữ ngắn hơn mức này coi như chưa căn được
MIN_MATCH = 0.5  # tỉ lệ từ PaddleOCR của hàng căn được sang Tesseract tối thiểu
MIN_SIM = 0.5  # hai từ (đã bỏ dấu) giống nhau từ mức này mới coi là một cặp
GAP_PADDLE = -0.6  # phạt khi một từ PaddleOCR không có đối ứng bên Tesseract
GAP_TESS = -0.1  # phạt khi bỏ qua một từ Tesseract thừa giữa chừng (mã, số trình độ đọc sai; đầu và cuối được bỏ tự do)


def skeleton(text):
    """Chuỗi chữ-số không dấu, chữ thường, và chỉ số trong text của từng ký tự."""
    s, idx = [], []
    for i, ch in enumerate(text):
        for b in strip_tone(ch).lower():
            if b.isalnum():
                s.append(b)
                idx.append(i)
    return "".join(s), idx


def split_rows(region):
    """Chia vùng bảng PaddleOCR thành các hàng. Trả về (danh_sách_hàng, nhất_quán) với mỗi hàng là (clo_id, số, [dòng chữ])."""
    kinds = ["id" if P_ID.match(l) else "lv" if P_LEVEL.match(l) else "t" for l in region]
    ids = [i for i, k in enumerate(kinds) if k == "id"]
    lvs = [i for i, k in enumerate(kinds) if k == "lv"]
    if len(lvs) == len(ids) + 1 and kinds[-1] == "lv":  # số trang ở chân trang
        lvs.pop()
    # cột trình độ ghi lại mã CLO (G1, G2...) thay vì số: mỗi mã xuất hiện hai lần liền nhau và không có số nào
    coded = not lvs and len(ids) >= 2 and len(ids) % 2 == 0 and all(region[ids[i]] == region[ids[i + 1]] for i in range(0, len(ids), 2))
    if coded:
        ids, lvs = ids[0::2], ids[1::2]  # mã thứ hai đóng vai ô trình độ
    n = len(ids)
    if n == 0:
        return [], False, False
    if len(lvs) != n:  # số lượng số không khớp mã: chỉ giữ mã, không chia chữ
        return [(re.sub(r"\s", "", region[i]), "", []) for i in ids], False, False
    lo = [min(a, b) for a, b in zip(ids, lvs)]
    hi = [max(a, b) for a, b in zip(ids, lvs)]
    rows = [[] for _ in range(n)]
    groups = [[] for _ in range(n + 1)]  # groups[k]: dòng chữ nằm giữa dấu hiệu hàng k-1 và hàng k
    for i, kind in enumerate(kinds):
        if kind != "t":
            continue
        k = sum(1 for h in hi if h < i)  # số hàng đã kết thúc dấu hiệu trước dòng này
        if k < n and lo[k] < i < hi[k]:  # dòng nằm giữa mã và số của cùng hàng: thuộc hàng đó
            rows[k].append(i)
        else:
            groups[k].append(i)
    mids = [len(rows[k]) for k in range(n)]  # số dòng chữ nằm giữa mã và số trình độ (đúng giữa chiều cao hàng)
    cuts, ok = choose_cuts(region, groups, mids)
    rows[0] += groups[0]  # chữ phía trên mã đầu tiên
    for k in range(1, n):
        rows[k - 1] += groups[k][:cuts[k - 1]]
        rows[k] += groups[k][cuts[k - 1]:]
    rows[n - 1] += groups[n]
    return [(re.sub(r"\s", "", region[ids[k]]), "" if coded else region[lvs[k]], [region[i] for i in sorted(rows[k])])
            for k in range(n)], ok, coded


def choose_cuts(region, groups, mids):
    """Chọn, với mỗi nhóm dòng chữ nằm giữa hai hàng liền kề, bao nhiêu dòng đầu thuộc hàng trên (phần còn lại thuộc hàng dưới).
    Mã và số trình độ nằm giữa chiều cao hàng nên mỗi hàng gần đối xứng: số dòng phía dưới = phía trên (+1 nếu không có dòng nào
    kẹp giữa mã và số). Chọn đồng thời mọi điểm cắt có tổng lệch đối xứng nhỏ nhất (quy hoạch động theo số dòng phía trên của hàng);
    dòng bắt đầu bằng chữ thường là phần nối tiếp nên không thể mở đầu hàng mới. Trả về (danh_sách_điểm_cắt, nhất_quán)."""
    n = len(mids)

    def asym(upper, lower, mid):  # độ lệch so với dạng đối xứng; lệch quá 1 dòng là bất thường
        diff = abs(lower - upper - (0.5 if mid == 0 else 0))
        return diff if diff <= 1 else 1 + 4 * (diff - 1)

    def cue(g, lower):
        return 3.0 if lower < len(g) and region[g[lower]][:1].islower() else 0.0

    states = {len(groups[0]): (0.0, [])}  # số dòng phía trên mã hàng đang xét -> (chi phí, các điểm cắt đã chọn)
    for k in range(n - 1):
        g, nxt = groups[k + 1], {}
        for upper, (cost, path) in states.items():
            for lower in range(len(g) + 1):
                c = cost + asym(upper, lower, mids[k]) + cue(g, lower)
                if len(g) - lower not in nxt or c < nxt[len(g) - lower][0]:
                    nxt[len(g) - lower] = (c, path + [lower])
        states = nxt
    final = {u: c + asym(u, len(groups[n]), mids[n - 1]) for u, (c, _) in states.items()}
    upper = min(final, key=final.get)
    ok = all(asym(u, l, m) <= 1 for u, l, m in zip(_uppers(groups, states[upper][1]), states[upper][1] + [len(groups[n])], mids))
    return states[upper][1], ok


def _uppers(groups, cuts):
    """Số dòng phía trên mã của từng hàng khi đã biết các điểm cắt."""
    ups = [len(groups[0])]
    for k, lower in enumerate(cuts):
        ups.append(len(groups[k + 1]) - lower)
    return ups


def sim(a, b):
    """Độ giống (0..1) giữa hai từ đã bỏ dấu."""
    if a == b:
        return 1.0
    if abs(len(a) - len(b)) > 4 or not set(a) & set(b):
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def align(pw, tw):
    """Căn từng từ PaddleOCR (pw) sang từ Tesseract (tw) theo thứ tự, bỏ được từ Tesseract thừa (mã, số trình độ đọc sai...).
    Trả về danh sách chỉ số trong tw (hoặc None nếu từ PaddleOCR không có đối ứng), một phần tử cho mỗi từ của pw."""
    P, T = len(pw), len(tw)
    F = [[0.0] * (T + 1) for _ in range(P + 1)]  # F[i][j]: điểm tốt nhất khi đã xử lý i từ pw và j từ tw; đầu và cuối của tw bỏ tự do
    back = [[0] * (T + 1) for _ in range(P + 1)]  # 0 = ghép chéo, 1 = bỏ từ pw, 2 = bỏ từ tw
    for i in range(1, P + 1):
        F[i][0], back[i][0] = F[i - 1][0] + GAP_PADDLE, 1
        for j in range(1, T + 1):
            s = sim(pw[i - 1], tw[j - 1])
            options = (F[i - 1][j - 1] + (2 * s - 1 if s >= MIN_SIM else -1.0), F[i - 1][j] + GAP_PADDLE, F[i][j - 1] + GAP_TESS)
            k = max(range(3), key=options.__getitem__)
            F[i][j], back[i][j] = options[k], k
    j = max(range(T + 1), key=lambda x: F[P][x])
    out, i = [None] * P, P
    while i > 0 and j >= 0:
        k = back[i][j]
        if k == 0 and j > 0:
            if sim(pw[i - 1], tw[j - 1]) >= MIN_SIM:
                out[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif k == 1 or j == 0:
            i -= 1
        else:
            j -= 1
    return out


def tidy(text):
    """Bỏ mã CLO đầu hàng, số trình độ đọc sai chen vào chữ, ký tự lạ."""
    text = TESS_ID.sub("", text.strip())
    toks = [t for t in text.split() if not re.fullmatch(r"[GgCcd][0-9IlOoSs]{1,2}", t) and not re.fullmatch(r"[\W_]+|[lIjJøØ]", t)]
    while toks and re.fullmatch(r"[1-5](?:[.,][05])?", toks[0]):  # số trình độ của hàng trước dính ở đầu
        toks.pop(0)
    for i, t in enumerate(toks):  # đúng một số trình độ chen giữa chữ của hàng (ô trình độ nằm giữa chiều cao hàng)
        if re.fullmatch(r"[1-5](?:[.,][05])?", t) and i and not re.search(r"(?i)(loại|mục|chương|bài|phần|cấp|bậc|pha|lớp)$", toks[i - 1]):
            del toks[i]
            break
    if len(toks) > 1 and len(toks[-1]) <= 3 and not re.search(r"[.!?]$", toks[-2]):
        toks.pop()  # số trình độ bị đọc sai dính cuối hàng (ví dụ "Agile ng")
    return " ".join(toks)


def extract_page(pad_text, tess_text, levels):
    """Các dòng CLO của một trang: [(clo_id, text, level_raw, ocr_ok)]."""
    lines = [l.strip() for l in pad_text.splitlines()]
    first = next((i for i, l in enumerate(lines) if P_ID.match(l)), None)
    if first is None:
        return []
    hdr = max((i for i, l in enumerate(lines[:first]) if len(l) <= 28 and HEADER.search(strip_tone(l).lower())), default=-1)
    end = next((i for i in range(first, len(lines)) if SECTION_5.match(lines[i])), len(lines))
    rows, consistent, coded = split_rows(lines[hdr + 1:end])
    if not rows:
        return []
    aligned = coded or (bool(levels) and len(levels) == len(rows))  # coded: đề cương không ghi số trình độ
    t_end = next((m.start() for m in re.finditer(r"(?m)^\W*5[.,]\s", tess_text)), len(tess_text))
    tw = tess_text[:t_end].split()  # từ Tesseract (giữ dấu câu), so sánh theo dạng bỏ dấu
    tkey = [skeleton(w)[0] for w in tw]
    pw, owner = [], []  # từ PaddleOCR của mọi hàng nối liền theo thứ tự hàng, và hàng chứa từng từ
    for r, (_, _, txt) in enumerate(rows):
        for w in " ".join(txt).split():
            if skeleton(w)[0]:
                pw.append(skeleton(w)[0])
                owner.append(r)
    pos = align(pw, tkey) if pw and tkey else []
    out = []
    for r, (cid, _, _) in enumerate(rows):
        hits = [pos[i] for i in range(len(pw)) if owner[i] == r and pos[i] is not None]
        total = sum(1 for o in owner if o == r)
        text = norm(tidy(" ".join(tw[min(hits):max(hits) + 1]))) if hits else ""
        frac = len(hits) / max(total, 1)
        reasons = []
        if not aligned:
            reasons.append("chưa ghép được số trình độ")
        if not consistent:
            reasons.append("khung hàng không đối xứng")
        if len(text) < MIN_TEXT_CHARS:
            reasons.append("chữ trống hoặc quá ngắn")
        elif frac < MIN_MATCH:
            reasons.append(f"chữ chỉ căn được {frac:.0%}")
        note = "; ".join(reasons) or ("đề cương không ghi số trình độ (cột trình độ ghi lại mã CLO)" if coded else "")
        out.append((cid, text, "" if coded or not aligned else levels[r], not reasons, note))
    return out


def clo_number(clo_id):
    """Số trong mã CLO ("G12" -> 12), -1 nếu không có."""
    m = re.search(r"\d+", clo_id)
    return int(m.group()) if m else -1


def has_clo_header(pad_text, tess_text):
    """Trang có tiêu đề bảng CLO: Tesseract đọc ra "chuẩn đầu ra"/"trình độ năng lực", hoặc PaddleOCR có từ 2 ô tiêu đề cột
    ("Ký hiệu", "Trình độ", "(1)"...) nằm trước mã CLO đầu tiên."""
    if HEADING.search(strip_tone(tess_text).lower()):
        return True
    lines = [l.strip() for l in pad_text.splitlines()]
    first = next((i for i, l in enumerate(lines) if P_ID.match(l)), len(lines))
    return sum(1 for l in lines[:first] if len(l) <= 28 and HEADER.search(strip_tone(l).lower())) >= 2


def extract_all(ocr_dir, clean_dir, pad_dir):
    """Trả về (các_dòng_CLO, trang_CLO_đã_dùng {môn: [trang]}, trang_bị_loại [(môn, trang)], danh_sách_môn)."""
    rows, used, rejected = [], {}, []
    courses = sorted(p.name for p in Path(ocr_dir).iterdir() if p.is_dir() and COURSE_DIR.fullmatch(p.name))
    for course in courses:
        carry, last = 0, 0  # carry: số trang nối tiếp còn được nhận sau trang có tiêu đề bảng CLO; last: số của CLO cuối đã trích
        for page_file in sorted(Path(ocr_dir, course).glob("p-*.txt"), key=page_number):
            name = page_file.stem
            pad, cln, lv = Path(pad_dir, course, name + ".txt"), Path(clean_dir, course, name + ".txt"), page_file.with_suffix(".levels")
            if not (lv.exists() and pad.exists() and cln.exists()):
                carry = 0
                continue
            tess_text, pad_text = cln.read_text(encoding="utf-8"), pad.read_text(encoding="utf-8")
            levels = lv.read_text(encoding="utf-8").split()
            header = has_clo_header(pad_text, tess_text)
            if not (header or carry > 0):  # trang nhận nhầm (ví dụ bảng lịch dạy có cột CĐR "G1, G2")
                rejected.append((course, page_number(page_file)))
                carry = 0
                continue
            page_rows = extract_page(pad_text, tess_text, levels)
            if not header and page_rows and clo_number(page_rows[0][0]) != last + 1:  # trang nối tiếp phải đánh số tiếp trang trước
                rejected.append((course, page_number(page_file)))
                carry = 0
                continue
            carry = CARRY_PAGES if header else carry
            if page_rows:
                last = clo_number(page_rows[-1][0])
                used.setdefault(course, []).append(page_number(page_file))
            rows += [{"course_code": course, "clo_id": c, "text": t, "level_raw": v, "ocr_ok": ok, "page": page_number(page_file),
                      "note": note} for c, t, v, ok, note in page_rows]
            carry = 0 if END_TITLE.search(page_skeleton(tess_text)) else carry - 1
    return rows, used, rejected, courses


def check(rows):
    """So với đáp án chuẩn của 5 môn: mã CLO, số trình độ, và CER của chữ (tính bằng fuzzy của ocr_eval)."""
    by = {}
    for r in rows:
        by.setdefault(r["course_code"], []).append(r)
    tot = n_id = n_lv = n_ok = d = n = 0
    for gold in gold_rows():
        got = next((r for r in by.get(gold["course_code"], []) if r["clo_id"] == gold["clo_id"]), None)
        tot += 1
        if not got:
            continue
        n_id += 1
        n_lv += got["level_raw"] == gold["level"] or (got["level_raw"].replace(".", "", 1).isdigit() and float(got["level_raw"]) == float(gold["level"]))
        n_ok += bool(got["ocr_ok"])
        g = norm(gold["text"])
        if got["text"]:
            d += fuzzy(g, got["text"])[0]
            n += len(g)
    print(f"Đáp án {tot} CLO: tìm thấy mã {n_id} | số trình độ đúng {n_lv} | ocr_ok = true: {n_ok} | "
          f"CER chữ {d / n:.1%}" if n else "Không có chữ để chấm")


def write_csv(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def apply_fixes(rows, path):
    """Áp các chỗ sửa tay lên kết quả tự động. File sửa có cột: course_code, clo_id, text, level_raw, page, action, note (note tùy chọn).
    action trống = đặt lại hàng (sửa nếu đã có, thêm nếu chưa có); action = delete = xóa hàng (hàng giả).
    Hàng được sửa có ocr_ok = True và note ghi là sửa tay. Trả về (rows, số_sửa, số_thêm, số_xóa)."""
    if not Path(path).exists():
        return rows, 0, 0, 0
    fixed = added = deleted = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for fx in csv.DictReader(f):
            fx_page = (fx.get("page") or "").strip()  # nếu có trang thì chỉ khớp hàng ở trang đó (môn có thể lặp mã G1, G2... ở trang khác)
            idx = [i for i, r in enumerate(rows) if r["course_code"] == fx["course_code"] and r["clo_id"] == fx["clo_id"]
                   and (not fx_page or str(r["page"]) == fx_page)]
            if (fx.get("action") or "").strip() == "delete":
                for i in reversed(idx):
                    del rows[i]
                    deleted += 1
                continue
            page = int(fx["page"]) if (fx.get("page") or "").strip() else (rows[idx[0]]["page"] if idx else "")
            new = {"course_code": fx["course_code"], "clo_id": fx["clo_id"], "text": fx["text"], "level_raw": fx["level_raw"],
                   "ocr_ok": True, "page": page,
                   "note": "sửa tay từ ảnh (chưa người kiểm tra)" + (f"; {fx['note'].strip()}" if (fx.get("note") or "").strip() else "")}
            for i in reversed(idx[1:]):  # bỏ hàng lặp cùng mã
                del rows[i]
            if idx:
                rows[idx[0]] = new
                fixed += 1
            else:
                rows.append(new)
                added += 1
    rows.sort(key=lambda r: (r["course_code"], clo_number(r["clo_id"])))
    return rows, fixed, added, deleted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", default="data/interim/ocr")
    ap.add_argument("--clean", default="data/interim/ocr_clean")
    ap.add_argument("--paddle", default="data/interim/ocr_raw/paddleocr")
    ap.add_argument("--out", default="data/interim/clos_raw.csv")
    ap.add_argument("--fixes", default="data/interim/clos_manual_fixes.csv", help="file các chỗ sửa tay (nếu có thì áp lên kết quả tự động)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    rows, used, rejected, courses = extract_all(a.ocr, a.clean, a.paddle)
    auto_path = Path(a.out).with_name(Path(a.out).stem + "_auto" + Path(a.out).suffix)
    write_csv(auto_path, rows)  # bản tự động, trước khi áp chỗ sửa tay
    auto_rows = [dict(r) for r in rows]  # --check chấm bản tự động (bản đã sửa tay có chỗ lấy từ đáp án nên không công bằng)
    rows, n_fixed, n_added, n_deleted = apply_fixes(rows, a.fixes)
    print(f"Trích CLO từ {len(courses)} môn ({a.ocr}); bản tự động: {auto_path}")
    if Path(a.fixes).exists():
        print(f"Áp chỗ sửa tay từ {a.fixes}: sửa {n_fixed} hàng, thêm {n_added}, xóa {n_deleted}")
    print()
    print(f"{'Môn':<8} {'Trang CLO':<10} {'CLO':>4} {'ocr_ok':>7}  Ghi chú")
    for c in courses:
        mine = [r for r in rows if r["course_code"] == c]
        ok = sum(bool(r["ocr_ok"]) for r in mine)
        notes = []
        skipped = [p for cc, p in rejected if cc == c]
        if skipped:
            notes.append(f"bỏ qua trang {', '.join(map(str, skipped))} (không có tiêu đề bảng CLO)")
        if not mine:
            notes.append("KHÔNG tìm thấy CLO")
        elif ok < len(mine):
            notes.append(f"{len(mine) - ok} hàng cần kiểm tra tay")
        print(f"{c:<8} {', '.join(map(str, used.get(c, []))) or '-':<10} {len(mine):>4} {ok:>3}/{len(mine):<3}  {'; '.join(notes)}")

    write_csv(a.out, rows)
    flagged = [r for r in rows if not r["ocr_ok"]]
    no_clo = [c for c in courses if not any(r["course_code"] == c for r in rows)]
    levels = Counter(r["level_raw"] for r in rows if r["level_raw"])
    print(f"\nTổng kết: {len(rows)} CLO của {len(courses) - len(no_clo)}/{len(courses)} môn | ocr_ok = true: {len(rows) - len(flagged)} | "
          f"cần kiểm tra tay: {len(flagged)}")
    print(f"Môn không tìm thấy CLO ({len(no_clo)}): {', '.join(no_clo) or 'không có'}"
          + (" (mở data/interim/images/<môn>/ tìm trang có bảng chuẩn đầu ra)" if no_clo else ""))
    print("Số trình độ gặp (level_raw): " + ", ".join(f"{v} ({n})" for v, n in sorted(levels.items(), key=lambda x: (float(x[0].split(',')[0]), x[0]))))
    if flagged:
        print(f"\nHàng cần kiểm tra tay ({len(flagged)}), mở data/interim/images/<môn>/p-<trang>.png để đối chiếu:")
        for r in flagged:
            print(f"  {r['course_code']} trang {r['page']} {r['clo_id']}: {r['note']}")
    print(f"\nĐã ghi {len(rows)} CLO -> {a.out} (sửa tay xong thì đổi ocr_ok thành True)")
    if a.check:
        print("Chấm bản tự động (trước khi sửa tay):")
        check(auto_rows)


if __name__ == "__main__":
    main()
