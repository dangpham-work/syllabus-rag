# So sánh engine OCR: Tesseract và PaddleOCR trên 5 đề cương khó

**Người phụ trách:** TV2 (tầng dữ liệu) · **Ngày chạy:** 11/10/2026 · **Trạng thái:** bản nháp, **đáp án chuẩn chưa được người kiểm tra** (xem mục 6).

## 1. Mục đích và kết luận ngắn

Chọn engine OCR cho bước biến 54 đề cương scan thành văn bản, để trích bảng CLO và các mục khác.

- **Tesseract đọc chữ tốt hơn rõ rệt**, cả ở bảng CLO (CER 7,4% so với 16,2%) lẫn cả trang (F1 theo từ 84,9% so với 57,1%), và nhanh hơn nhiều.
- **PaddleOCR đọc số trình độ tốt hơn**: đúng 36/36 CLO theo cách tính lỏng, trong khi Tesseract 24/36.
- Hướng được chọn (**đã chốt 12/10/2026**): dùng Tesseract cho toàn bộ chữ, riêng cột trình độ lấy từ PaddleOCR trên trang CLO (xem mục 7). Đã thử trên 5 môn khó, kết quả ở mục 9 (lạc quan, cần thử trên môn khác). `config/params.yaml` đã ghi `ocr.engine: ket_hop`.

## 2. Phương pháp

- **Dữ liệu:** 5 đề cương khó, 44 trang, ảnh 300 dpi (`pdftoppm`). Chọn theo độ tin cậy Tesseract thấp và có bảng CLO khó: 841401 Giải tích 1, 841468 Chuyên đề J2EE, 841411 Quản trị mạng, 841058 Hệ điều hành mã nguồn mở, 841470 Tương tác người máy.
- **Đáp án chuẩn:** `docs/ocr_ground_truth_5_hard_syllabi/` gồm bảng CLO (36 dòng) và chữ cả 44 trang.
- **Engine:** Tesseract 5.3.4 với gói `vie`; PaddleOCR 3.7.0 (`lang="vi"`, tắt `enable_mkldnn` vì lỗi oneDNN trên CPU này). Chạy trên CPU, không GPU.
- **Hai cách chấm** (`src/syllabus_core/data/ocr_eval.py`): chấm *bảng CLO* (so từng CLO với trang chứa nó) và chấm *toàn bộ chữ* (so cả trang, không phụ thuộc thứ tự dòng). Định nghĩa, công thức và ví dụ từng chỉ số ở mục 3.

## 3. Các chỉ số đánh giá

Ký hiệu: **đáp án** là bản gõ lại đúng nguyên văn từ ảnh (`ocr_ground_truth_5_hard_syllabi/`); **OCR** là chữ engine đọc ra. Mọi chỉ số dưới đây (trừ tốc độ) đều là so OCR với đáp án.

### 3.1 Khoảng cách sửa (nền tảng của CER)

Số thao tác ít nhất để biến chuỗi OCR thành chuỗi đáp án, mỗi thao tác tính 1: **thay** một ký tự, **xóa** một ký tự đọc thừa, **thêm** một ký tự đọc thiếu (khoảng cách Levenshtein). Gọi số này là D. Trong code là hàm `fuzzy()`, có thêm điểm khác: nó tìm đoạn con của văn bản OCR giống đáp án nhất, nên không cần cắt sẵn đúng đoạn.

### 3.2 CER (Character Error Rate, tỉ lệ lỗi ký tự)

```
CER = D / N          N = số ký tự của đáp án (tính cả dấu cách)
```

Càng thấp càng tốt, 0% là hoàn hảo. Ví dụ với đáp án `kiến thức` (N = 9):

| OCR đọc ra | D | CER |
|---|---|---|
| `kiến thức` | 0 | 0% |
| `kiên thức` (sai dấu `ế` thành `ê`) | 1 | 1/9 ≈ 11% |
| `kin thc` (rơi hai chữ `ế`, `ứ`) | 2 | 2/9 ≈ 22% |

Với tiếng Việt, `ế` là một ký tự, nên đọc sai hay rơi dấu đều tính là một lỗi.

**CER của cả nhóm** không phải trung bình các CER, mà là tổng lỗi chia tổng độ dài: `CER = (D1 + D2 + …) / (N1 + N2 + …)`. Dòng dài có trọng số lớn hơn dòng ngắn. Dòng `TONG` trong các bảng tính theo cách này.

### 3.3 CER bỏ dấu

Bỏ hết dấu tiếng Việt (và đổi `đ` thành `d`) ở cả hai bên rồi mới tính CER. Dùng để tách riêng lỗi dấu khỏi lỗi chữ cái. Với đáp án `kiến thức`: OCR `kiên thức` sau khi bỏ dấu thành `kien thuc`, trùng đáp án (`kien thuc`), nên CER bỏ dấu = 0% trong khi CER thường = 11%. Hiệu giữa CER và CER bỏ dấu cho biết bao nhiêu điểm lỗi là do dấu.

### 3.4 Level đúng, chặt và lỏng (chỉ cho bảng CLO)

Mỗi CLO có một số trình độ (ví dụ `5.0`). Hai cách kiểm tra OCR có đưa ra số đúng không:

- **Chặt:** lấy số đầu tiên xuất hiện ngay sau câu CLO trong văn bản OCR (trong 12 ký tự); đúng nếu bằng số trong đáp án.
- **Lỏng:** đúng nếu số trong đáp án xuất hiện đứng riêng ở bất kỳ chỗ nào quanh câu CLO (từ đầu câu trừ 10 ký tự đến cuối câu cộng 12 ký tự). Đây là **cận trên**: có thể đếm nhầm nếu số của CLO bên cạnh trùng giá trị.

```
level đúng = số CLO đúng / tổng số CLO       (ví dụ 24/36)
```

Ví dụ thật, CLO G1 của 841470, đáp án `5.0`:
- Tesseract đọc `… chính xác. 3.0`: số ngay sau câu là `3.0`, sai cả chặt lẫn lỏng.
- PaddleOCR đọc `… phân tích thit` / `5.0` / `k giao din mt cách chính xác.` / `G2`: số `5.0` đúng nhưng bị xuất chen vào giữa câu (do đọc từng ô bảng). Chặt sai (sau câu chỉ có `G2`, lấy ra `2`), lỏng **đúng** (`5.0` nằm trong khoảng quanh câu).

Nên lỏng trả lời "engine có đọc được số này không", chặt trả lời "số có nằm đúng chỗ trong văn bản không".

### 3.5 Độ phủ, độ chính xác, F1 (chấm toàn bộ chữ)

Tách đáp án và OCR của mỗi trang thành các **từ** (chuyển chữ thường, cắt theo dấu cách và dấu câu; số `5.0` tách thành `5` và `0`). Gọi **hit** là số từ khớp nhau, tính theo bội: một từ xuất hiện 3 lần trong đáp án thì khớp tối đa 3 lần.

```
độ phủ (recall)         R = hit / số từ của đáp án      -> OCR có bỏ sót không
độ chính xác (precision) P = hit / số từ OCR đọc ra      -> OCR có đọc thừa hoặc sai không
F1                      = 2·P·R / (P + R)               -> gộp hai số
độ phủ bỏ dấu           = như R nhưng bỏ dấu cả hai bên
```

Ví dụ: đáp án `hệ điều hành mã nguồn mở` (6 từ), OCR `hệ điêu hành mã nguồn` (5 từ). Từ khớp: `hệ`, `hành`, `mã`, `nguồn`, nên hit = 4 (`điêu` khác `điều`). R = 4/6 ≈ 66,7%; P = 4/5 = 80%; F1 = 2·0,8·0,667 / (0,8 + 0,667) ≈ 72,7%. Bỏ dấu thì `điêu` và `điều` cùng thành `dieu`, hit = 5, độ phủ bỏ dấu = 5/6 ≈ 83,3%.

Các số này cộng dồn theo từng môn rồi theo cả bộ (hit cộng hit, số từ cộng số từ), không lấy trung bình các tỉ lệ.

### 3.6 CER dòng (chấm toàn bộ chữ)

Với mỗi dòng của đáp án cả trang, tìm đoạn giống nhất trong **cả trang OCR** rồi tính D như mục 3.1. Cộng dồn: `CER dòng = Σ D / Σ N` theo độ dài ký tự. Cách này giống CER của bảng CLO nên so sánh được, và không phụ thuộc thứ tự dòng. Có bản bỏ dấu tương tự mục 3.3. Dòng rất ngắn (như số thứ tự) dễ khớp ngẫu nhiên ở đâu đó, nhưng vì cộng theo độ dài nên ảnh hưởng nhỏ.

### 3.7 Tốc độ

Số giây OCR một trang trên CPU 12 nhân, không phải so với đáp án. Quyết định OCR cả 54 môn mất vài phút hay vài giờ.

### 3.8 Level theo thứ tự (chỉ cho engine kết hợp)

Engine kết hợp không chèn số trình độ vào văn bản mà lưu thành danh sách theo thứ tự CLO của từng trang CLO (xem mục 9.1). Chỉ số này chấm danh sách đó: số thứ k trong danh sách so với level của CLO thứ k trên trang, theo đáp án.

```
level theo thứ tự = số CLO có số đúng / tổng số CLO       (so theo giá trị số: 4 và 4.0 coi như bằng nhau)
```

Ví dụ thật, 841470 trang 2 (5 CLO):

| Thứ tự | CLO | Số lấy ra | Đáp án | Đúng |
|---|---|---|---|---|
| 1 | G1 | 5.0 | 5.0 | có |
| 2 | G2 | 4.0 | 4.0 | có |
| 3 | G3 | 4.0 | 4.0 | có |
| 4 | G4 | 5.0 | 5.0 | có |
| 5 | G5 | 5.0 | 5.0 | có |

Được 5/5; cộng cả 5 môn là 36/36. Nếu số lượng số lấy ra khác số lượng CLO của trang thì trang đó không ghép được, danh sách để trống và mọi CLO của trang tính là sai.

Khác với level chặt/lỏng (mục 3.4, đọc số từ văn bản), chỉ số này không cần mã CLO được đọc đúng, nên **hai thước đo không so thẳng với nhau**. Nó chỉ có nghĩa với engine kết hợp, và giả định số lượng số khớp số lượng CLO, điều đúng trên 5 môn này nhưng chưa kiểm chứng trên môn khác.

### 3.9 Tóm tắt

| Chỉ số | Đo gì | Tốt khi |
|---|---|---|
| CER, CER bỏ dấu | tỉ lệ ký tự sai (bảng CLO) | thấp |
| Level đúng chặt/lỏng | số trình độ của CLO, đọc từ văn bản | cao |
| Level theo thứ tự | số trình độ của CLO, ghép theo thứ tự CLO (chỉ kết hợp) | cao |
| Độ phủ, độ phủ bỏ dấu | có bỏ sót từ không | cao |
| Độ chính xác | có đọc thừa hoặc sai từ không | cao |
| F1 | gộp độ phủ và độ chính xác | cao |
| CER dòng | tỉ lệ ký tự sai trên cả trang | thấp |
| Tốc độ | giây/trang | thấp |

## 4. Kết quả

### 4.1 Bảng CLO (36 CLO)

| | Tesseract | PaddleOCR |
|---|---|---|
| CER | **7,4%** | 16,2% |
| CER bỏ dấu | **5,7%** | 13,7% |
| Level đúng, lỏng | 24/36 | **36/36** |
| Level đúng, chặt | 9/36 | 8/36 |

Theo từng môn (CER, level lỏng):

| Môn | Số CLO | Tesseract | PaddleOCR |
|---|---|---|---|
| 841401 Giải tích 1 | 15 | 13,4% · 11/15 | 21,5% · 15/15 |
| 841468 Chuyên đề J2EE | 6 | 4,1% · 6/6 | 16,4% · 6/6 |
| 841411 Quản trị mạng | 4 | 4,6% · 1/4 | 9,5% · 4/4 |
| 841058 HĐH mã nguồn mở | 6 | 5,2% · 6/6 | 13,7% · 6/6 |
| 841470 Tương tác người máy | 5 | 0,9% · 0/5 | 16,3% · 5/5 |

### 4.2 Toàn bộ chữ (44 trang)

| | Tesseract | PaddleOCR |
|---|---|---|
| Độ phủ | **86,6%** | 57,3% |
| Độ phủ bỏ dấu | **91,1%** | 67,1% |
| Độ chính xác | **83,2%** | 56,8% |
| F1 | **84,9%** | 57,1% |
| CER dòng | **13,4%** | 18,7% |
| CER dòng bỏ dấu | **12,1%** | 16,1% |

Theo từng môn (F1 · CER dòng):

| Môn | Số trang | Tesseract | PaddleOCR |
|---|---|---|---|
| 841401 | 10 | 81,4% · 13,8% | 55,9% · 18,5% |
| 841468 | 6 | 85,2% · 12,0% | 55,0% · 16,7% |
| 841411 | 12 | 86,6% · 13,5% | 62,3% · 17,8% |
| 841058 | 10 | 86,5% · 17,9% | 54,4% · 23,9% |
| 841470 | 6 | 84,7% · 6,4% | 55,1% · 14,6% |

### 4.3 Tốc độ

| | Tesseract | PaddleOCR |
|---|---|---|
| Tốc độ | vài giây/trang, chạy song song 12 nhân (cả 488 trang ≈ 1 phút) | ≈ 56 giây/trang, 1 luồng (ước tính cả 488 trang ≈ 7,5 giờ) |

Lần chạy cuối của PaddleOCR hoàn thành phần còn lại của 44 trang hết 2171 giây (~36 phút).

## 5. Nhận xét

1. **Chữ:** Tesseract hơn ở cả hai cách chấm và ở cả 5 môn. Chênh lệch ở cả trang lớn hơn ở bảng CLO, nghĩa là PaddleOCR yếu hơn nhiều ở phần văn xuôi.
2. **Dấu tiếng Việt:** PaddleOCR rơi nhiều dấu ("kiến thức" thành "kin thc"). Bỏ dấu thì độ phủ của nó tăng 9,8 điểm (57,3% lên 67,1%), của Tesseract chỉ tăng 4,5 điểm. Một phần điểm thấp của PaddleOCR còn do nó xuất từng ô bảng thành từng dòng, làm lệch chỉ số theo từ và CER.
3. **Số trình độ:** PaddleOCR đọc đúng gần như hoàn toàn (36/36 lỏng), Tesseract hay sai số thập phân (ví dụ `5.0` đọc thành `3.0`). Đặc biệt ở 841470, Tesseract đọc chữ gần như hoàn hảo (CER 0,9%) nhưng không đúng số nào (0/5).
4. **Cách tính chặt cho điểm thấp ở cả hai engine** (9/36 và 8/36) nên chưa phân biệt được hai engine. Nguyên nhân chưa điều tra: có thể do bố cục bảng (số không nằm ngay sau câu CLO trong văn bản OCR), không hẳn do đọc sai.

## 6. Hạn chế

- **Đáp án chuẩn chưa được kiểm tra:** toàn bộ đọc tay từ ảnh trang (chưa đối chiếu lại), cột `verified = no`. Chỗ đã biết là mờ hoặc chưa chắc: trang 1 của 841401 (ảnh mờ, chữ viết tay đè), G9 "hàm ẩn", tên "Phan Hoàng Chơ" ở trang 9 bị cắt, dòng Quyết định ở trang 1 của 841411 bị viết tay đè. Đáp án sai thì điểm của cả hai engine lệch theo.
- **Mẫu nhỏ:** chỉ 5 đề cương (44 trang, 36 CLO), mỗi engine chạy một lần. Kết quả mang tính định hướng, chưa có khoảng tin cậy.
- **Chọn mẫu thiên lệch có chủ ý:** 5 môn là môn khó, không đại diện cho cả 54 môn. Chưa rõ hiệu quả trên đề cương dễ hơn.
- **Chỉ số theo từ nhạy với cách xuất dòng của engine** (xem nhận xét 2), nên chênh lệch F1 có thể phóng đại so với chênh lệch thực tế khi dùng văn bản.
- **Level "lỏng" là cận trên**, có thể đếm nhầm số nằm gần câu CLO.
- Chưa thử các biến thể: PaddleOCR với mô hình nhận dạng khác, Tesseract tiền xử lý ảnh, engine thứ ba (EasyOCR…).

## 7. Hướng đề xuất (chưa chốt)

Kết hợp để lấy ưu điểm của từng bên (đã thử trên 5 môn khó, xem mục 9):

- Tesseract đọc toàn bộ chữ của 54 đề cương (nhanh, chính xác chữ và dấu).
- Cột trình độ của bảng CLO lấy từ nguồn khác: PaddleOCR chỉ chạy trên trang CLO (khoảng 1 đến 2 trang/môn, tương đương 1 đến 2 giờ cho 54 môn), hoặc Tesseract chạy riêng cho cột trình độ với bộ ký tự chỉ có chữ số. Cách thứ hai rẻ hơn, nên thử trước.

Đã chốt dùng engine kết hợp (12/10/2026): `config/params.yaml` ghi `ocr.engine: ket_hop` và quyết định được ghi ở `docs/decisions.md` (D1).

## 8. Cách tái hiện

Chạy ở thư mục gốc repo (cần ảnh trang trong `data/interim/images/`, tạo bằng `pdf_to_images.py`):

```
.venv/bin/python src/syllabus_core/data/ocr_run.py              # menu chọn engine, phạm vi
.venv/bin/python src/syllabus_core/data/ocr_run.py tesseract    # hoặc chạy trực tiếp bằng tham số
.venv/bin/python src/syllabus_core/data/ocr_eval.py data/interim/ocr_trial_<engine>   # chấm lại, không OCR lại
```

Kết quả OCR ở `data/interim/ocr_trial_<engine>/`; điểm từng lần chạy ở `data/interim/ocr_gold/eval_<engine>_clo.csv` và `eval_<engine>_full.csv` (cục bộ, không commit). Các số trong báo cáo lấy từ lần chạy 11/10/2026 (mục 9: 12/10/2026).

## 9. Engine kết hợp Tesseract + PaddleOCR (thử ngày 12/10/2026)

Mục 5 cho thấy hai engine mạnh ở hai việc khác nhau, nên đã thử ghép chúng. Mục này là kết quả thử trên cùng 5 đề cương khó, 44 trang, 36 CLO, chấm bằng cùng bộ chỉ số ở mục 3.

### 9.1 Cách làm

- **Chữ:** lấy toàn bộ từ Tesseract. Văn bản của mỗi trang kết hợp chính là văn bản Tesseract.
- **Nhận trang CLO** từ văn bản Tesseract (so sánh sau khi bỏ dấu để chịu được lỗi dấu): trang có tiêu đề mục 4 ("chuẩn đầu ra học phần") hoặc cụm tiêu đề cột ("chuẩn đầu ra" cùng "trình độ"/"năng lực"/"mô tả") ở 4 trang đầu, hoặc có hai mã CLO liên tiếp (G3, G4), hoặc là trang nối tiếp của bảng (tối đa 2 trang sau trang CLO, dừng khi gặp tiêu đề mục 5). Quy tắc ban đầu chỉ nhận đúng cụm "mô tả chuẩn đầu ra" hoặc "trình độ năng lực" và bỏ sót trang CLO của khoảng 10 trong 54 môn khi chạy toàn bộ, nên đã nới như trên.
- **Số trình độ:** chỉ trên trang CLO mới chạy PaddleOCR. PaddleOCR xuất mã CLO (`G1`) và số trình độ (`5.0`) mỗi thứ một dòng theo thứ tự hàng, nên số thứ k trong vùng bảng là trình độ của CLO thứ k. Vùng bảng tính từ mã CLO đầu tiên đến tiêu đề "5. Nội dung…" (hoặc hết trang).
  - Nếu số lượng số nhiều hơn số mã CLO đúng 1 và số cuối nằm ở dòng cuối vùng thì đó là số trang ở chân trang, bỏ đi.
  - Nếu số lượng số vẫn khác số mã CLO thì trang đó **không ghép được**: danh sách rỗng, mọi CLO của trang tính là sai, không đoán.
- **Vì sao lưu số riêng thay vì chèn vào văn bản Tesseract:** Tesseract đọc thiếu hoặc sai mã CLO (thấy 10/13, 5/6, 4/6, 4/5 mã ở các trang CLO) và để số ở giữa dòng, nên không căn chỉnh số vào đúng câu một cách tin cậy. Mỗi trang kết hợp gồm `p-N.txt` (văn bản) và, riêng trang CLO, `p-N.levels` (mỗi dòng một số, theo thứ tự CLO).
- **Chỉ số mới, "level theo thứ tự"** (định nghĩa và ví dụ ở mục 3.8): số thứ k trong `p-N.levels` so với level của CLO thứ k trên trang đó trong đáp án. Khác với level chặt/lỏng ở mục 3.4 là đọc từ văn bản, nên **hai thước đo không so thẳng với nhau**.
- **Code:** `src/syllabus_core/data/ocr_hybrid.py` (nhận trang CLO, lấy số), hàm `ket_hop()` trong `ocr_run.py`, hàm `score_levels()` và `compare()` trong `ocr_eval.py`.

### 9.2 Kết quả

| | Tesseract | PaddleOCR | Kết hợp |
|---|---|---|---|
| CER bảng CLO | **7,4%** | 16,2% | **7,4%** |
| CER bỏ dấu | **5,7%** | 13,7% | **5,7%** |
| Level lỏng (từ văn bản) | 24/36 | 36/36 | 36/36* |
| Level chặt (từ văn bản) | 9/36 | 8/36 | 8/36* |
| Level theo thứ tự | — | — | **36/36** |
| Độ phủ | **86,6%** | 57,3% | **86,6%** |
| Độ phủ bỏ dấu | **91,1%** | 67,1% | **91,1%** |
| Độ chính xác | **83,2%** | 56,8% | **83,2%** |
| F1 | **84,9%** | 57,1% | **84,9%** |
| CER dòng | **13,4%** | 18,7% | **13,4%** |

\* Số trình độ của engine kết hợp lấy từ PaddleOCR nên level lỏng/chặt dùng đúng điểm của PaddleOCR. Riêng level chặt (8/36) chỉ để tham chiếu: nó tính trên văn bản PaddleOCR, còn engine kết hợp không chèn số vào văn bản mà lưu thành danh sách theo thứ tự (dòng "Level theo thứ tự"). Dấu `—` nghĩa là chỉ số không áp dụng cho engine đó.

Số trình độ theo thứ tự đúng ở cả 5 môn: 841401 15/15, 841468 6/6, 841411 4/4, 841058 6/6, 841470 5/5. Nhận trang CLO tìm đúng 6/6 trang CLO, ghép được cả 6, và nhận thừa 2 trong 38 trang còn lại (841411 và 841058, mỗi môn một trang ngay sau trang CLO; số trình độ không ghép được nên bị bỏ, chỉ tốn thêm một trang PaddleOCR).

### 9.3 Nhận xét

1. Kết hợp lấy chữ của Tesseract (CER 7,4%, F1 84,9%) và số trình độ đúng hết trên 5 môn này. So với Tesseract riêng, số trình độ đúng tăng từ 24/36 (lỏng) lên 36/36; so với PaddleOCR riêng, CER giảm từ 16,2% xuống 7,4%.
2. Cột chữ của kết hợp trùng Tesseract vì văn bản chính là của Tesseract. Điểm cộng của kết hợp không phải đọc số tốt hơn PaddleOCR (số lấy từ chính PaddleOCR), mà là **có chữ tốt và số tốt cùng lúc**, điều mà không engine nào đơn lẻ làm được.
3. **Chi phí thấp:** PaddleOCR chỉ chạy ở 8 trang trong 44 trang (6 trang CLO và 2 trang nối tiếp), tức khoảng 8 phút thay vì 36 phút. Với 54 môn, lần chạy chính thức cần PaddleOCR trên khoảng 100 trang (xem mục 11), cỡ 1,5 giờ thay vì ~7,5 giờ nếu chạy PaddleOCR cả bộ.

### 9.4 Hạn chế riêng của kết quả này

- **36/36 là kết quả "đã biết đáp án", lạc quan.** Quy tắc bỏ số trang ở chân trang được thêm sau khi thấy hai trang (841411, 841058) bị lỗi trên chính 5 môn dùng để chấm, và cách nhận trang CLO cũng chỉnh trên 5 môn này. Độ tin cậy thật chỉ biết được khi thử trên các môn khác.
- **Dễ vỡ khi lệch số lượng:** lệch một mã CLO hoặc một số (ví dụ PaddleOCR đọc `G1` thành `Gl`, hoặc bảng có ô trống) thì cả trang không ghép được. Cách xử lý chọn bỏ trống chứ không đoán, nên lỗi sẽ lộ ra thay vì ghi sai số.
- **Nhận trang CLO dựa vào tiêu đề và mã CLO của Tesseract:** trang CLO mà mọi dấu hiệu đều bị đọc hỏng thì không được đưa cho PaddleOCR. Quy tắc đã phải nới một lần sau khi chạy toàn bộ, nên có thể còn môn bị sót (log của `extract_clos.py` liệt kê các môn không tìm thấy CLO).
- **Chưa gắn số vào từng câu CLO.** Hiện mới có danh sách số theo thứ tự; việc ghép câu CLO (từ Tesseract) với số thứ k để tạo `clos_raw.csv` là bước sau.
- **Tốc độ thật của engine kết hợp chưa đo:** cột `run_seconds` trong log bằng 0 vì lần chạy dùng lại kết quả OCR đã có. Con số ~6 phút ở 9.3 là ước tính từ tốc độ ~56 giây/trang của PaddleOCR.
- Các hạn chế ở mục 6 (đáp án chưa kiểm tra, mẫu nhỏ, chọn mẫu khó) vẫn áp dụng.

### 9.5 Cách tái hiện

```
.venv/bin/python src/syllabus_core/data/ocr_run.py ket_hop        # hoặc chọn "Kết hợp" trong menu
.venv/bin/python src/syllabus_core/data/ocr_eval.py --compare     # in lại bảng so sánh ba engine
```

Kết quả ở `data/interim/ocr_trial_ket_hop/` (`p-N.txt`, `p-N.levels`); điểm ở `data/interim/ocr_gold/eval_ket_hop_clo.csv`, `eval_ket_hop_full.csv`, `eval_ket_hop_level.csv`; bảng so sánh mới nhất ở `so_sanh_engine.csv` (cục bộ, không commit).

## 10. Làm sạch chữ OCR (`clean_text.py`)

Chữ Tesseract còn nhiều lỗi dấu ("học phân", "khỗi kiễn"), ký tự rác và dòng bị ngắt. `clean_text.py` chuẩn hóa NFC, bỏ ký tự kẻ bảng và số trang, ghép dòng bị ngắt (chỉ khi dòng sau bắt đầu bằng chữ thường), và sửa lỗi dấu bằng từ điển tự xây từ các từ Tesseract đọc với độ tin cậy cao (conf ≥ 90) của cả 54 môn, dựa vào cặp từ liền nhau vì nhiều lỗi vẫn là từ hợp lệ khi đứng riêng ("học phân" → "học phần").

**Kết quả trên 5 môn có đáp án** (chữ Tesseract, trước và sau làm sạch):

| | Trước | Sau |
|---|---|---|
| CER bảng CLO | 7,4% | **6,0%** |
| F1 theo từ, cả trang | 84,9% | **87,9%** |
| Độ phủ | 86,6% | **89,4%** |
| CER dòng | 13,4% | **12,7%** |

Chạy toàn bộ 488 trang: bỏ 87 dòng nhiễu và 24 số trang, ghép 3431 dòng, sửa 3544 từ. Trong 477 chỗ sửa trên 5 môn có đáp án (khi chưa bỏ qua token một ký tự): 299 sửa đúng, 10 sửa sai làm hỏng chữ đã đúng, 168 không phân định được. Các từ sửa nhiều nhất: `phân→phần`, `kiên→kiến`, `sô→số`, `thông→thống`.

**Hạn chế:** từ điển chỉ biết các từ xuất hiện trong chính bộ đề cương, nên từ chuyên môn hiếm có thể bị sửa nhầm; sửa nhầm chủ yếu xảy ra ở từ chuyên ngành chỉ xuất hiện ở một môn. Điểm trên chỉ đo trên 5 môn khó.

## 11. Trích bảng CLO (`extract_clos.py`) và `clos_raw.csv`

**Cách làm:** PaddleOCR đọc đúng mã CLO và số trình độ nhưng rơi dấu; Tesseract đọc chữ tốt nhưng hay sai mã và số. Mã và số trình độ nằm giữa chiều cao hàng nên số dòng chữ phía trên bằng số dòng phía dưới (±1); một quy hoạch động chọn đồng thời mọi điểm cắt giữa các hàng, rồi chữ PaddleOCR của từng hàng được căn theo từng từ (không dấu) sang chữ Tesseract đã làm sạch để lấy lại chữ có dấu. Trang CLO là trang có tiêu đề bảng CLO hoặc trang nối tiếp đánh số liền ngay sau trang trước (G7 rồi G8), dừng khi gặp tiêu đề mục 5.

**Kết quả trên 5 môn có đáp án (36 CLO), chấm bản tự động trước khi sửa tay:** đúng 36/36 mã CLO, 36/36 số trình độ, CER chữ 4,0%. Thuật toán và các ngưỡng được chỉnh khi nhìn chính các môn này (và 841047) nên con số lạc quan.

**Chạy toàn bộ 54 môn:**
- Tự động: 420 CLO của 54/54 môn, 378 hàng `ocr_ok = true`, 42 hàng cần kiểm tra tay (ở 10 môn: bảng bị cắt giữa trang, chữ trống, khung hàng không đối xứng).
- Sửa tay: 125 hàng được gõ lại theo ảnh trang (3 hàng lấy từ đáp án chuẩn), 9 hàng bị xóa. Kết quả cuối `clos_raw.csv`: **411 CLO của 54/54 môn, tất cả `ocr_ok = true`**. Các chỗ sửa tay lưu riêng ở `data/interim/clos_manual_fixes.csv` và được áp tự động mỗi lần chạy lại; bản tự động nằm ở `clos_raw_auto.csv`.
- **Lưu ý về chất lượng:** các hàng sửa tay được đọc từ ảnh trang nên có thể đọc nhầm ở chỗ ảnh mờ, 4 hàng chỉ bỏ ký tự rác theo suy luận chưa đối chiếu ảnh, và `ocr_ok` ở hàng tự động chỉ nghĩa là thuật toán không nghi ngờ. Sau khi sửa các hàng bị đánh dấu, hai lượt quét các hàng còn lại (tìm ký tự lạ, và hàng bắt đầu bằng chữ thường là dấu hiệu đoạn nối tiếp từ trang trước bị gán nhầm) đã phát hiện và sửa thêm khoảng 40 hàng; lỗi dấu nhỏ không để lại ký tự lạ thì chưa phát hiện được (ước lượng khoảng 4% ký tự sai theo điểm trên 5 môn có đáp án).

**Phát hiện về dữ liệu nguồn (cần báo TV1 và nhóm):**
1. **Số trình độ không thống nhất:** gặp `1`, `2`, `3`, `4`, `5`, thập phân dấu chấm (`2.5`, `3.5`, `4.5`, `5.0`), thập phân dấu phẩy (`2,0`, `2,5`, `3,0`) và **danh sách nhiều mức** (`3,4`, `4,5`, `2,3,4,5` ở 841324). `level_raw` giữ nguyên như in; chưa quy đổi sang thang Bloom.
2. **841423:** cột "Trình độ năng lực" ghi lại mã CLO (`G1`…`G7`) thay vì số, nên `level_raw` để trống.
3. **841479:** cột "Trình độ năng lực" để trống hoàn toàn trong đề cương.
4. **841428:** file PDF có 16 trang nhưng từ trang 7 là đề cương của một môn khác ("Lập trình Game", bảng CLO game 2D ở trang 8) bị dính vào; 9 hàng CLO đó đã bị loại khỏi `clos_raw.csv`.
5. **Mã môn in trên đề cương khác tên file** ở 841073 (in 841482), 841404 (841104), 841412 (841448); có thể là Tesseract đọc nhầm số, cần đối chiếu PDF.
