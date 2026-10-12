"""Chạy OCR. Hai chế độ:

1. Kiểm thử: OCR 5 đề cương khó để so sánh engine (minh chứng cho docs/ocr_comparison.md).
2. Chạy chính thức: OCR toàn bộ đề cương bằng engine kết hợp (Tesseract đọc chữ + PaddleOCR đọc số trình độ ở trang CLO).

Dùng:
  python src/syllabus_core/data/ocr_run.py                 -> menu chọn bằng phím mũi tên (← để quay lại câu trước)
  python src/syllabus_core/data/ocr_run.py <tesseract|paddleocr|ket_hop> [mã_môn ...] [--clo-only] [--fresh]   (kiểm thử)
  python src/syllabus_core/data/ocr_run.py --all [--fresh] [--yes]                                              (chính thức)
    ket_hop    : chữ lấy từ Tesseract, số trình độ lấy từ PaddleOCR (chạy trên trang CLO); kết quả vào ocr_trial_ket_hop,
                 dùng lại kết quả sẵn có của hai engine kia; chạy xong in bảng so sánh ba engine
    mã_môn     : chỉ các môn này (phải nằm trong 5 môn khó); bỏ trống = cả 5 môn
    --clo-only : chỉ OCR trang chứa bảng CLO (nhanh)
    --fresh    : xóa kết quả cũ của các trang đã chọn (hỏi xác nhận) rồi chạy lại từ đầu
    --all      : chạy chính thức, chỉ dùng engine ket_hop, ghi vào data/interim/ocr/<mã_môn>/ (kèm clo_pages_report.csv)
    --yes      : bỏ qua câu hỏi xác nhận thời gian PaddleOCR (cần khi chạy nền)
5 môn khó: NAMES trong ocr_eval.py; đáp án chuẩn: docs/ocr_ground_truth_5_hard_syllabi/ (xem README ở đó).
Kết quả OCR : kiểm thử: data/interim/ocr_trial_<engine>/<mã_môn>/<trang>.txt; chính thức: data/interim/ocr/<mã_môn>/<trang>.txt
              (kết quả từng engine của chế độ chính thức lưu ở data/interim/ocr_raw/<engine>/); trang đã có thì bỏ qua.
Điểm số     : (chỉ kiểm thử) in ra màn hình và thêm dòng vào data/interim/ocr_gold/eval_<engine>_clo.csv (bảng CLO)
              và eval_<engine>_full.csv (toàn bộ chữ), kèm ngày chạy. Chế độ chính thức không có đáp án nên không chấm điểm,
              chỉ tổng kết số trang CLO tìm thấy và ghép được.
"""
import argparse
import csv
import curses
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from ocr_eval import (EVAL_DIR, NAMES, clo_pages, compare, page_number, score, score_levels, score_text, show,
                      show_levels, show_text, text_rates, with_rates)  # chạy như script nên import cùng thư mục
from ocr_hybrid import is_clo_page, paddle_levels

IMAGES = Path("data/interim/images")
PADDLE_SEC_PER_PAGE = 56  # đo trên CPU 12 nhân, dùng để ước tính thời gian trước khi chạy nhiều trang


def tesseract(img, base):
    # txt = chữ, tsv = kèm độ tin cậy từng từ; 1 luồng/ảnh vì đã chạy song song nhiều ảnh
    subprocess.run(["tesseract", str(img), str(base), "-l", "vie", "txt", "tsv"], check=True,
                   capture_output=True, env={**os.environ, "OMP_THREAD_LIMIT": "1"})


_paddle = None  # mô hình nạp 1 lần; engine này chạy 1 luồng nên không tranh chấp


def paddleocr(img, base):
    global _paddle
    if _paddle is None:
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"  # bỏ bước kiểm tra mạng mỗi lần chạy
        from paddleocr import PaddleOCR  # nạp trễ để tesseract chạy được khi chưa cài paddle

        # enable_mkldnn=False: tránh lỗi oneDNN/PIR của paddlepaddle 3.x trên một số CPU
        _paddle = PaddleOCR(lang="vi", use_doc_orientation_classify=False, use_doc_unwarping=False,
                            use_textline_orientation=False, enable_mkldnn=False)
    lines = _paddle.predict(str(img))[0]["rec_texts"]
    base.with_suffix(".txt").write_text("\n".join(lines), encoding="utf-8")


OFFICIAL = Path("data/interim/ocr")  # kết quả chính thức (chế độ chạy chính thức)
RAW = Path("data/interim/ocr_raw")  # kết quả từng engine của chế độ chính thức, dùng lại khi chạy lại


def trial(engine, base):
    """Đường dẫn (không đuôi) của cùng trang trong thư mục kết quả của engine khác
    (thư mục ocr_trial_<engine> khi kiểm thử, ocr_raw/<engine> khi chạy chính thức)."""
    root = RAW / engine if OFFICIAL in base.parents else Path(f"data/interim/ocr_trial_{engine}")
    return root / base.parent.name / base.name


def neighbors(base):
    """Chữ Tesseract của tối đa 2 trang liền trước trang này: [(số_trang, chữ)], gần nhất trước."""
    m = re.fullmatch(r"p-(\d+)", base.name)
    n, width, out = int(m.group(1)), len(m.group(1)), []
    for k in (1, 2):
        f = trial("tesseract", base.with_name(f"p-{n - k:0{width}d}")).with_suffix(".txt")
        if n - k >= 1 and f.exists():
            out.append((n - k, f.read_text(encoding="utf-8")))
    return out


def clo_page(base, text):
    """Trang này có thể chứa bảng CLO không (xem ocr_hybrid.is_clo_page)."""
    return is_clo_page(text, page_number(base), neighbors(base))


def needs_paddle(job):
    """Trang CLO (theo văn bản Tesseract đã có) mà PaddleOCR chưa chạy."""
    _, base = job
    text = trial("tesseract", base).with_suffix(".txt").read_text(encoding="utf-8")
    return clo_page(base, text) and not trial("paddleocr", base).with_suffix(".txt").exists()


def ket_hop(img, base):
    """Chữ lấy từ Tesseract; riêng trang CLO lấy thêm số trình độ từ PaddleOCR (PaddleOCR chỉ chạy trên trang CLO).
    Ghi p-N.txt (= văn bản Tesseract) và, với trang CLO, p-N.levels (mỗi dòng một số, theo thứ tự CLO).
    Dùng lại kết quả sẵn có của hai engine nếu đã có."""
    base.parent.mkdir(parents=True, exist_ok=True)
    t, p = trial("tesseract", base), trial("paddleocr", base)
    if not t.with_suffix(".txt").exists():
        t.parent.mkdir(parents=True, exist_ok=True)
        tesseract(img, t)
    text = t.with_suffix(".txt").read_text(encoding="utf-8")
    if clo_page(base, text):
        if not p.with_suffix(".txt").exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            paddleocr(img, p)
        levels = paddle_levels(p.with_suffix(".txt").read_text(encoding="utf-8"))
        base.with_suffix(".levels").write_text("\n".join(levels), encoding="utf-8")
    base.with_suffix(".txt").write_text(text, encoding="utf-8")  # ghi cuối: có .txt nghĩa là trang đã xong


ENGINES = {"tesseract": (tesseract, os.cpu_count()), "paddleocr": (paddleocr, 1),
           "ket_hop": (ket_hop, 1)}  # (hàm, số luồng song song); ket_hop 1 luồng vì có thể gọi PaddleOCR
ENGINE_LABEL = {"ket_hop": "Kết hợp (Tesseract + PaddleOCR)"}  # tên hiện trong menu; mặc định là tên engine


def choose(title, options, back=False, start=0):
    """Trả về chỉ số được chọn, hoặc None nếu back=True và người dùng nhấn ← / Backspace."""
    def draw(scr):
        curses.curs_set(0)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_YELLOW, -1)
        i = start
        while True:
            scr.erase()
            scr.addstr(0, 0, title)
            for n, o in enumerate(options):
                scr.addstr(n + 2, 2, f"> {o}" if n == i else f"  {o}", curses.color_pair(1) if n == i else 0)
            k = scr.getch()
            if k in (curses.KEY_UP, ord("k")):
                i = (i - 1) % len(options)
            elif k in (curses.KEY_DOWN, ord("j")):
                i = (i + 1) % len(options)
            elif k in (10, 13, curses.KEY_ENTER):
                return i
            elif back and k in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, 8):
                return None
            elif k == ord("q"):
                raise SystemExit("Đã hủy.")
    return curses.wrapper(draw)


def fmt_time(s):
    return f"{int(s) // 60:02d}:{int(s) % 60:02d}"


def show_progress(done, total, t0, label):
    """Một dòng tiến độ: thanh, số trang, %, thời gian đã chạy, thời gian còn lại ước tính, trang vừa xong."""
    elapsed = time.time() - t0
    eta = fmt_time(elapsed / done * (total - done)) if done else "--:--"
    filled = 30 * done // total
    bar = "█" * filled + "░" * (30 - filled)
    line = f"{bar} {done}/{total} {done / total:4.0%} | đã chạy {fmt_time(elapsed)} | còn ~{eta} | {label}"
    if sys.stdout.isatty():
        print(f"\r\033[33m{line}\033[0m\033[K", end="\n" if done == total else "", flush=True)
    else:
        print(line, flush=True)


def run_jobs(jobs, fn, workers, label):
    """Chạy fn(ảnh, đường_dẫn_ra) cho từng trang với thanh tiến độ."""
    if not jobs:
        return
    print(f"\n{label}", flush=True)
    t0 = time.time()
    show_progress(0, len(jobs), t0, "đang khởi động")

    def work(job):
        job[1].parent.mkdir(parents=True, exist_ok=True)
        fn(*job)

    ex = ThreadPoolExecutor(workers)
    try:
        futs = {ex.submit(work, j): j for j in jobs}
        for n, f in enumerate(as_completed(futs), 1):
            f.result()  # để lỗi trong luồng ném ra ngoài
            show_progress(n, len(jobs), t0, f"{futs[f][1].parent.name}/{futs[f][1].name}")
    finally:
        ex.shutdown(cancel_futures=True)  # lỗi hoặc Ctrl+C thì bỏ các trang chưa chạy, không chờ hết


def report_all(out):
    """Tổng kết chế độ chính thức: trang CLO tìm thấy/ghép được; ghi clo_pages_report.csv để kiểm tra tay."""
    courses = sorted(p.name for p in out.iterdir() if p.is_dir() and not p.name.startswith("."))
    rows = [{"course_code": c, "page": page_number(p), "n_levels": len(p.read_text(encoding="utf-8").split())}
            for c in courses for p in sorted((out / c).glob("p-*.levels"), key=page_number)]
    for r in rows:
        r["aligned"] = r["n_levels"] > 0
    with open(out / "clo_pages_report.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["course_code", "page", "n_levels", "aligned"])
        w.writeheader()
        w.writerows(rows)
    bad = [f"{r['course_code']}/p{r['page']}" for r in rows if not r["aligned"]]
    none = [c for c in courses if not any(r["course_code"] == c for r in rows)]
    n_pages = sum(1 for c in courses for _ in (out / c).glob("p-*.txt"))
    print(f"\nTổng kết: {len(courses)} môn, {n_pages} trang. Trang CLO tìm thấy: {len(rows)}, ghép được số trình độ: "
          f"{len(rows) - len(bad)}.")
    print(f"Môn không tìm thấy trang CLO nào ({len(none)}): {', '.join(none) or 'không có'}")
    print(f"Trang CLO chưa ghép được ({len(bad)}): {', '.join(bad) or 'không có'}")
    print(f"Chi tiết ở {out / 'clo_pages_report.csv'} (nên kiểm tra tay các môn và trang ở trên).")


def menu():
    """Trả về (engine, courses, clo_only, fresh); courses=None nghĩa là chạy chính thức trên toàn bộ đề cương."""
    questions = [
        ("Chọn chế độ", ["Kiểm thử để đánh giá, chọn engine", "Chạy chính thức: OCR toàn bộ đề cương (engine kết hợp)"]),
        ("Chọn engine OCR", [ENGINE_LABEL.get(k, k) for k in ENGINES]),
        ("Chọn bộ đề cương", ["Cả 5 đề cương khó", "Chọn 1 trong 5 đề cương khó"]),
        ("Chọn đề cương", [f"{c} - {n}" for c, n in NAMES.items()]),
        ("Chọn số trang", ["Chỉ trang CLO (nhanh)", "Tất cả trang của các môn đã chọn"]),
        ("Xóa kết quả cũ của các trang đã chọn để chạy lại từ đầu?", ["Không, giữ kết quả cũ", "Có"]),
    ]
    a, stage = {}, 0  # a[bước] = chỉ số đã chọn

    def skipped(s):  # chạy chính thức bỏ qua bước 1-4; bước chọn từng đề cương chỉ hỏi khi chọn 1 môn
        return (s in (1, 2, 3, 4) and a.get(0) == 1) or (s == 3 and a.get(2) != 1)

    while stage < len(questions):
        r = choose(*questions[stage], back=stage > 0, start=a.get(stage, 0))
        if r is None:
            stage -= 1
            while skipped(stage):
                stage -= 1
            continue
        a[stage] = r
        stage += 1
        while stage < len(questions) and skipped(stage):
            stage += 1
    for s, (title, options) in enumerate(questions):  # curses xóa màn hình khi thoát, in lại để còn thấy
        if s in a and not skipped(s):
            print(f"{title} -> {options[a[s]]}")
    if a[0] == 1:
        return "ket_hop", None, False, a[5] == 1
    courses = set(NAMES) if a[2] == 0 else {list(NAMES)[a[3]]}
    return list(ENGINES)[a[1]], courses, a[4] == 0, a[5] == 1


META_COLS = ["run_at", "engine", "scope", "pages", "course_code"]
LOG_COLS = {  # kind -> các cột của eval_<engine>_<kind>.csv
    "clo": META_COLS + ["n_clo", "cer", "cer_no_tone", "level_strict", "level_loose", "run_seconds"],
    "full": META_COLS + ["n_pages", "n_pages_gold", "gold_words", "ocr_words", "recall", "recall_no_tone",
                         "precision", "f1", "cer", "cer_no_tone", "run_seconds"],
    "level": META_COLS + ["n_clo", "level_order", "pages_clo", "pages_found", "pages_aligned", "pages_extra",
                          "run_seconds"],  # chỉ engine ket_hop
}


def log_eval(engine, kind, courses, clo_only, rows, seconds):
    path = EVAL_DIR / f"eval_{engine}_{kind}.csv"
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS[kind], extrasaction="ignore")
        if new:
            w.writeheader()
        meta = {"run_at": datetime.now().isoformat(timespec="seconds"), "engine": engine,
                "scope": "5_mon_kho" if courses == set(NAMES) else "1_mon", "pages": "clo" if clo_only else "all",
                "run_seconds": round(seconds)}
        for r in rows:
            w.writerow({**meta, **{k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()}})
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("engine", nargs="?", choices=ENGINES)
    ap.add_argument("courses", nargs="*", choices=list(NAMES), metavar="mã_môn")
    ap.add_argument("--clo-only", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--all", action="store_true", help="chạy chính thức: OCR toàn bộ đề cương bằng ket_hop vào data/interim/ocr")
    ap.add_argument("--yes", action="store_true", help="bỏ qua câu hỏi xác nhận thời gian PaddleOCR (khi chạy nền)")
    a = ap.parse_args()
    if a.all:
        if a.courses or a.clo_only or a.engine not in (None, "ket_hop"):
            ap.error("--all chỉ dùng với engine ket_hop, không kèm mã môn hay --clo-only")
        engine, courses, clo_only, fresh = "ket_hop", None, False, a.fresh
    elif a.engine:
        engine, courses, clo_only, fresh = a.engine, set(a.courses) or set(NAMES), a.clo_only, a.fresh
    else:
        engine, courses, clo_only, fresh = menu()
    run, workers = ENGINES[engine]
    out = OFFICIAL if courses is None else Path(f"data/interim/ocr_trial_{engine}")

    jobs = [(img, out / img.parent.name / img.stem) for img in sorted(IMAGES.glob("*/*.png"))
            if (courses is None or img.parent.name in courses)
            and (not clo_only or page_number(img) in clo_pages(img.parent.name))]
    if not jobs:
        return print("Không có ảnh nào để OCR (đã chạy pdf_to_images.py chưa?).")

    if fresh:
        olds = [p for _, b in jobs for s in (".txt", ".tsv", ".levels") if (p := b.with_suffix(s)).exists()]
        if olds and input(f"Sẽ xóa {len(olds)} file kết quả cũ trong {out}. Gõ 'xoa' để đồng ý: ").strip() == "xoa":
            for p in olds:
                p.unlink()
        elif olds:
            print("Không xóa; trang đã có kết quả sẽ được bỏ qua.")

    pending = [j for j in jobs if not j[1].with_suffix(".txt").exists()]
    print(f"\n{engine}: OCR {len(pending)}/{len(jobs)} trang (bỏ qua {len(jobs) - len(pending)} trang đã có kết quả)", flush=True)
    t0 = time.time()

    def paddle_ok(n):  # cảnh báo thời gian khi PaddleOCR phải chạy nhiều trang
        mins = n * PADDLE_SEC_PER_PAGE // 60
        print(f"PaddleOCR sẽ chạy {n} trang, ước tính khoảng {mins} phút.", flush=True)
        return n <= 20 or a.yes or input("Tiếp tục? (y/N): ").lower() == "y"

    if engine == "ket_hop":
        # giai đoạn 1: Tesseract song song cho mọi trang chưa có; giai đoạn 2: PaddleOCR từng trang, chỉ trên trang CLO
        tess_jobs = [(img, trial("tesseract", b)) for img, b in pending if not trial("tesseract", b).with_suffix(".txt").exists()]
        run_jobs(tess_jobs, tesseract, os.cpu_count(), f"Giai đoạn 1/2: Tesseract trên {len(tess_jobs)} trang (chạy song song)")
        slow = [j for j in pending if needs_paddle(j)]
        for j in pending:  # trang không cần PaddleOCR chỉ việc ghép, gần như tức thì
            if j not in slow:
                ket_hop(*j)
        if slow and not paddle_ok(len(slow)):
            return print("Đã hủy.")
        run_jobs(slow, ket_hop, 1, f"Giai đoạn 2/2: PaddleOCR trên {len(slow)} trang CLO")
    else:
        if engine == "paddleocr" and not paddle_ok(len(pending)):
            return print("Đã hủy.")
        run_jobs(pending, run, workers, f"{engine}: {len(pending)} trang")
    secs = time.time() - t0
    print(f"\nHoàn tất trong {fmt_time(secs)} -> {out}")
    if courses is None:
        return report_all(out)

    clo_rows = with_rates(score(out, courses))
    full_rows = text_rates(score_text(out, courses))
    if not clo_rows:
        return print("Chưa có kết quả OCR của trang CLO nên chưa chấm điểm (chạy lại không dùng --clo-only nếu cần).")
    print("\nBảng CLO:")
    show(clo_rows)
    print("\nToàn bộ chữ:")
    show_text(full_rows)
    logs = [("clo", clo_rows), ("full", full_rows)]
    if engine == "ket_hop":
        level_rows = score_levels(out, courses)
        print("\nSố trình độ theo thứ tự (lấy từ PaddleOCR):")
        show_levels(level_rows)
        logs.append(("level", level_rows))
    for kind, rows in logs:
        print(f"Đã ghi điểm vào {log_eval(engine, kind, courses, clo_only, rows, secs)}")
    if engine == "ket_hop":
        print("\nSo sánh các engine (chấm lại từ các thư mục kết quả hiện có):")
        compare(courses)


if __name__ == "__main__":
    main()
