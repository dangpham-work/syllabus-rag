"""Hai hàm cho engine kết hợp (Tesseract đọc chữ + PaddleOCR đọc số trình độ), xem ket_hop() trong ocr_run.py.

is_clo_page   : văn bản Tesseract của một trang có phải trang chứa bảng CLO không.
paddle_levels : lấy danh sách số trình độ theo thứ tự CLO từ văn bản PaddleOCR của trang CLO.

PaddleOCR xuất bảng thành từng ô: mã CLO ("G1") và số trình độ ("5.0") mỗi thứ đứng riêng một dòng, theo thứ tự hàng.
Nên số thứ k trong vùng bảng là trình độ của CLO thứ k. Tesseract thì hay đọc sai mã CLO nên không dùng để ghép.
Quy tắc được chỉnh trên chính 5 đề cương khó dùng để chấm, nên điểm trên 5 môn này là lạc quan; cần thử trên môn khác.
"""
import re

from ocr_eval import strip_tone  # chạy như script nên import cùng thư mục

CLO_ID = re.compile(r"(?m)^\W*G\s?(\d{1,2})\b")  # mã CLO ở đầu dòng trong văn bản Tesseract
HEADING = re.compile(r"mô tả chuẩn đầu ra|trình độ năng lực", re.I)  # tiêu đề cột của bảng CLO
# tiêu đề mục 4 hoặc cụm tiêu đề cột, so trên chữ đã bỏ dấu để chịu được lỗi dấu của Tesseract
TITLE = re.compile(r"chuan\s+dau\s+ra\s+hoc\s+phan|chuan\s+dau\s+ra.*?(trinh\s+do|nang\s+luc|mo\s+ta\s+chuan)"
                   r"|(trinh\s+do|nang\s+luc).*?chuan\s+dau\s+ra", re.S)
END_TITLE = re.compile(r"noi\s+dung\s+chi\s+tiet")  # tiêu đề mục 5: hết bảng CLO
EARLY_PAGES = 4  # bảng CLO (mục 4) nằm ở vài trang đầu; trang sau đó chỉ nhận khi có mã G liên tiếp
P_ID = re.compile(r"^G\s?\d{1,2}$")  # dòng chỉ có mã CLO (PaddleOCR)
# dòng chỉ có số trình độ: một số ("3"), số thập phân dùng dấu chấm ("3.5"), hoặc danh sách nhiều mức cách nhau bằng dấu phẩy ("4,5", "2,3,4,5")
P_LEVEL = re.compile(r"^\d(?:\.\d)?(?:,\d(?:\.\d)?)*$")
SECTION_5 = re.compile(r"^5[.,]\s")  # "5. Nội dung chi tiết": hết bảng CLO


def page_skeleton(text):
    """Chữ thường, bỏ dấu, gộp khoảng trắng."""
    return re.sub(r"\s+", " ", strip_tone(text).lower())


def _has_table_clue(text, page):
    ids = [int(m.group(1)) for m in CLO_ID.finditer(text)]
    early = page is not None and page <= EARLY_PAGES and bool(TITLE.search(page_skeleton(text)))
    return bool(HEADING.search(text)) or any(b == a + 1 for a, b in zip(ids, ids[1:])) or early


def is_clo_page(tess_text, page=None, prev=()):
    """Trang có thể chứa bảng CLO: có tiêu đề hoặc cụm tiêu đề cột (ở vài trang đầu), hoặc hai mã CLO liên tiếp (G3, G4).
    page và prev (danh sách (số_trang, chữ_Tesseract) của tối đa 2 trang liền trước, gần nhất trước) để nhận thêm trang nối tiếp:
    bảng thường tràn sang trang sau tiêu đề mà không có tiêu đề riêng. Trang trước phải là trang CLO và chưa gặp tiêu đề mục 5."""
    if _has_table_clue(tess_text, page):
        return True
    if page is None or page > EARLY_PAGES + 1:
        return False
    return any(_has_table_clue(t, p) and not any(END_TITLE.search(page_skeleton(x)) for _, x in prev[:k])
               for k, (p, t) in enumerate(prev, 1))


def paddle_levels(paddle_text):
    """Danh sách số trình độ theo thứ tự CLO; rỗng nếu số lượng số không khớp số lượng mã CLO (không ghép được)."""
    lines = [l.strip() for l in paddle_text.splitlines()]
    start = next((i for i, l in enumerate(lines) if P_ID.match(l)), None)
    if start is None:
        return []
    end = next((i for i in range(start, len(lines)) if SECTION_5.match(lines[i])), len(lines))
    region = lines[start:end]
    n_ids = sum(bool(P_ID.match(l)) for l in region)
    levels = [l for l in region if P_LEVEL.match(l)]  # giữ nguyên như in (không đổi dấu phẩy thành dấu chấm)
    if len(levels) == n_ids + 1 and P_LEVEL.match(region[-1]):  # bảng chạy hết trang nên dính số trang ở chân trang
        levels.pop()
    return levels if len(levels) == n_ids else []
