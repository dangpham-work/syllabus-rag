"""api/main.py
Ứng dụng FastAPI - Tầng API/Backend (Project 1 - TV3).
Đồ án: "Hệ thống phân tích đề cương môn học kết hợp RAG" (Trường ĐH Sài Gòn).

Bao gồm 5 endpoints và xử lý thống nhất mã lỗi (400, 422, 503) theo yêu cầu Tuần 2:
1. GET  /health: Kiểm tra trạng thái dịch vụ (Health Check).
2. POST /api/v1/analyze-syllabus: Phân tích và trích xuất 10 mục của đề cương PDF scan (nạp JSON thật).
3. POST /api/v1/classify-clo: Phân loại mức độ Bloom (0-6) cho chuẩn đầu ra (CLO).
4. POST /api/v1/ask: Hỏi đáp có trích dẫn nguồn trên dữ liệu đề cương (RAG).
5. POST /api/v1/learning-path: Gợi ý kế hoạch/lộ trình học tập theo tiên quyết & tín chỉ.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI,
    APIRouter,
    Request,
    UploadFile,
    File,
    Form,
    HTTPException,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.schemas import (
    HealthResponse,
    CLOItem,
    SyllabusSections,
    AnalyzeSyllabusRequest,
    AnalyzeSyllabusResponse,
    ClassifyCLORequest,
    CLOClassificationItem,
    ClassifyCLOResponse,
    AskRequest,
    CitationItem,
    RetrievedChunkItem,
    AskResponse,
    LearningPathRequest,
    SemesterPlanItem,
    LearningPathResponse,
    BLOOM_LEVEL_NAMES,
)

# ==============================================================================
# 1. CẤU HÌNH GHI NHẬT KÝ (LOGGING TO LOGS/API.LOG)
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
SAMPLES_DIR = BASE_DIR / "samples"
PROCESSED_SYLLABI_DIR = BASE_DIR / "data" / "processed" / "syllabi"
SAMPLE_SYLLABI_DIR = SAMPLES_DIR / "syllabi"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "api.log"

logger = logging.getLogger("syllabus-rag-api")
logger.setLevel(logging.INFO)

# Định dạng nhật ký chi tiết
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)

# Ghi ra console
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
if not logger.handlers:
    logger.addHandler(console_handler)

# Ghi ra tệp logs/api.log có cơ chế xoay vòng (Rotating: tối đa 5MB/file, lưu 3 bản backup)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)


# ==============================================================================
# 2. KHỞI TẠO ỨNG DỤNG FASTAPI
# ==============================================================================
app = FastAPI(
    title="Syllabus RAG API",
    description=(
        "Hệ thống phân tích đề cương môn học kết hợp RAG - Trường ĐH Sài Gòn (SGU).\n\n"
        "**Thành viên 3 (TV3)** phụ trách Tầng API/Backend.\n"
        "- Trích xuất cấu trúc đề cương PDF scan (10 mục chuẩn) từ dữ liệu thực tế.\n"
        "- Phân loại Chuẩn đầu ra (CLO) theo thang đo Bloom 7 mức (0-6).\n"
        "- Hỏi đáp RAG có trích dẫn minh chứng nguồn tin cậy.\n"
        "- Gợi ý lộ trình học tập tối ưu ràng buộc tiên quyết.\n"
        "- Hệ thống quản lý lỗi tập trung: 400 (Bad Request), 422 (Unprocessable PDF/Schema), 503 (External Error)."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Cấu hình CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# 3. MIDDLEWARE GHI NHẬT KÝ MỌI REQUEST VÀ ĐO LATENCY
# ==============================================================================
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """Ghi lại vết mọi yêu cầu gửi đến API và thời gian xử lý vào logs/api.log."""
    start_time = time.time()
    client_host = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path

    try:
        response = await call_next(request)
        process_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            "%s %s | Client: %s | Status: %d | Latency: %.2fms",
            method,
            path,
            client_host,
            response.status_code,
            process_time_ms,
        )
        return response
    except Exception as exc:
        process_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            "%s %s | Client: %s | EXCEPTION: %s | Latency: %.2fms",
            method,
            path,
            client_host,
            exc,
            process_time_ms,
        )
        raise exc


# ==============================================================================
# 4. HÀM TIỆN ÍCH NẠP DỮ LIỆU JSON MÔN HỌC THẬT (MỐC 2)
# ==============================================================================
def _find_course_code_from_string(text: str) -> Optional[str]:
    """Trích xuất mã môn học (6 chữ số, ví dụ: 841020, 841401) từ tên tệp hoặc đường dẫn."""
    match = re.search(r"\b(84\d{4})\b", text)
    return match.group(1) if match else None


def load_real_syllabus_json(course_code: str) -> Optional[Dict[str, Any]]:
    """Tìm và nạp tệp JSON thật của môn học từ samples/syllabi hoặc data/processed/syllabi."""
    target_filename = f"{course_code}.json"

    # 1. Tìm trong samples/syllabi/
    p1 = SAMPLE_SYLLABI_DIR / target_filename
    if p1.exists():
        try:
            with open(p1, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Không thể đọc %s: %s", p1, e)

    # 2. Tìm trong data/processed/syllabi/
    p2 = PROCESSED_SYLLABI_DIR / target_filename
    if p2.exists():
        try:
            with open(p2, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Không thể đọc %s: %s", p2, e)

    return None


# ==============================================================================
# 5. ENDPOINTS CHÍNH
# ==============================================================================

# --- GET /health ---
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Kiểm tra trạng thái hoạt động của hệ thống",
    tags=["Health Check"],
)
def health_check() -> HealthResponse:
    """Kiểm tra dịch vụ API có đang hoạt động bình thường hay không."""
    return HealthResponse(
        status="ok",
        service="syllabus-rag-api",
        version="v0.2-milestone2",
        timestamp=datetime.now(timezone.utc),
    )


api_v1_router = APIRouter(prefix="/api/v1")


# --- POST /api/v1/analyze-syllabus ---
@api_v1_router.post(
    "/analyze-syllabus",
    response_model=AnalyzeSyllabusResponse,
    summary="Phân tích và trích xuất cấu trúc 10 mục của đề cương học phần",
    description=(
        "Nhận file PDF scan đề cương qua **File Upload (multipart/form-data)** "
        "hoặc nhận đường dẫn `file_path` qua **JSON body / Form-data**.\n\n"
        "Kiểm tra và xử lý mã lỗi:\n"
        "- **HTTP 422**: Tệp tải lên bị rỗng (0 bytes), hỏng định dạng, hoặc thiếu thông tin đầu vào.\n"
        "- Nạp tệp JSON thật theo mã môn học nếu có trong kho tri thức."
    ),
    tags=["Syllabus Analysis"],
)
async def analyze_syllabus(
    raw_request: Request,
    file: Optional[UploadFile] = File(
        None,
        description="Tệp PDF đề cương scan tải lên trực tiếp (multipart/form-data)",
    ),
    file_path: Optional[str] = Form(
        None,
        description="Đường dẫn tệp PDF trên máy chủ (nếu gửi qua form-data)",
    ),
) -> AnalyzeSyllabusResponse:
    """Trích xuất cấu trúc đề cương học phần có kết nối dữ liệu thật."""
    resolved_file_path = file_path

    # Đọc từ JSON body nếu client gửi Content-Type: application/json
    content_type = raw_request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await raw_request.json()
            if isinstance(body, dict):
                resolved_file_path = body.get("file_path")
        except Exception as exc:
            logger.warning("Lỗi đọc JSON body: %s", exc)

    # Kiểm tra thiếu input
    if not file and not (resolved_file_path and resolved_file_path.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Yêu cầu không hợp lệ: Vui lòng tải lên tệp PDF đề cương qua 'file' "
                "hoặc cung cấp đường dẫn 'file_path' qua JSON/form-data."
            ),
        )

    # Kiểm tra tính toàn vẹn khi upload file trực tiếp
    if file:
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            logger.warning("Tải lên tệp rỗng (0 bytes): %s", file.filename)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Tệp PDF tải lên bị rỗng (0 bytes). Không thể đọc và trích xuất OCR.",
            )
        # Kiểm tra magic bytes của PDF
        if not file_bytes.startswith(b"%PDF-"):
            logger.warning("Tệp không đúng định dạng PDF: %s", file.filename)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Tệp tải lên không phải định dạng PDF hợp lệ (không chứa header %PDF-).",
            )
        file_source = file.filename or "uploaded.pdf"
    else:
        file_source = resolved_file_path.strip()

    logger.info("Xử lý phân tích đề cương từ nguồn: %s", file_source)

    # Tìm mã môn học từ tên file hoặc đường dẫn (ví dụ 841020, 841401, 841108)
    detected_code = _find_course_code_from_string(file_source)

    # Thử nạp JSON thật của môn tương ứng
    if detected_code:
        real_data = load_real_syllabus_json(detected_code)
        if real_data:
            logger.info("Đã nạp thành công dữ liệu JSON thật cho môn %s", detected_code)
            return AnalyzeSyllabusResponse(**real_data)

    # Nếu không tìm thấy môn cụ thể, nạp file mẫu mặc định (Cơ sở lập trình 841020)
    sample_default = SAMPLES_DIR / "analyze_syllabus_response.json"
    if sample_default.exists():
        with open(sample_default, "r", encoding="utf-8") as f:
            data = json.load(f)
            return AnalyzeSyllabusResponse(**data)

    # Fallback dữ liệu nội bộ
    fallback_sections = SyllabusSections(
        general_info=f"1. Thông tin chung học phần: {file_source}",
        course_description="2. Mô tả tóm tắt học phần: Nội dung tổng quan học phần.",
        course_objectives="3. Mục tiêu học phần: Nắm vững kiến thức.",
        course_learning_outcomes="4. Chuẩn đầu ra học phần: CLO1, CLO2.",
        course_content="5. Nội dung chi tiết học phần: Các chương mục.",
        teaching_methods="6. Phương pháp dạy và học: Lý thuyết và thực hành.",
        assessment="7. Đánh giá học phần: Quá trình và thi kết thúc.",
        learning_resources="8. Tài liệu học tập: Giáo trình ĐH Sài Gòn.",
        teaching_schedule="9. Kế hoạch giảng dạy: 15 tuần.",
        course_policies="10. Quy định học phần: Chuyên cần.",
    )
    return AnalyzeSyllabusResponse(
        course_code=detected_code or "841020",
        course_name="Cơ sở lập trình",
        credits=3,
        prerequisites=[],
        clos=[
            CLOItem(clo_id="CLO1", text="Hiểu cú pháp cơ bản", bloom_level=2),
            CLOItem(clo_id="CLO2", text="Vận dụng giải bài toán", bloom_level=3),
        ],
        sections=fallback_sections,
        missing_sections=[],
        model_version="v0.2-milestone2",
    )


# --- POST /api/v1/classify-clo ---
def _mock_predict_bloom(text: str) -> tuple[int, float, Dict[int, float]]:
    """Giả lập mô hình phân loại Bloom (0-6) dựa trên từ khóa tiếng Việt."""
    lower_text = text.lower()

    if any(k in lower_text for k in ["sáng tạo", "thiết kế", "xây dựng", "phát triển hệ thống", "chế tạo"]):
        predicted_level = 6
    elif any(k in lower_text for k in ["đánh giá", "nhận xét", "phê phán", "thẩm định", "so định"]):
        predicted_level = 5
    elif any(k in lower_text for k in ["phân tích", "so sánh", "phân loại", "đo lường", "độ phức tạp"]):
        predicted_level = 4
    elif any(k in lower_text for k in ["áp dụng", "vận dụng", "cài đặt", "thực hiện", "viết chương trình", "giải quyết"]):
        predicted_level = 3
    elif any(k in lower_text for k in ["hiểu", "trình bày", "giải thích", "mô tả", "phân biệt", "nêu"]):
        predicted_level = 2
    elif any(k in lower_text for k in ["nhớ", "nhận biết", "liệt kê", "nhắc lại"]):
        predicted_level = 1
    else:
        predicted_level = 3

    confidence = 0.88
    remaining_prob = 1.0 - confidence
    other_prob = round(remaining_prob / 6.0, 4)
    probs: Dict[int, float] = {}
    for i in range(7):
        if i == predicted_level:
            probs[i] = round(confidence, 4)
        else:
            probs[i] = other_prob

    diff = round(1.0 - sum(probs.values()), 4)
    probs[predicted_level] = round(probs[predicted_level] + diff, 4)

    return predicted_level, confidence, probs


@api_v1_router.post(
    "/classify-clo",
    response_model=List[CLOClassificationItem],
    summary="Phân loại mức độ tư duy Bloom cho một hoặc nhiều chuẩn đầu ra (CLO)",
    description="Nhận vào một câu CLO hoặc danh sách câu CLO. Trả về kết quả phân loại 7 mức Bloom.",
    tags=["CLO Classification"],
)
def classify_clo(payload: ClassifyCLORequest) -> List[CLOClassificationItem]:
    """Phân loại mức độ Bloom cho các câu chuẩn đầu ra (CLO)."""
    texts = payload.get_clo_texts()
    logger.info("Nhận yêu cầu phân loại %d câu CLO", len(texts))

    results: List[CLOClassificationItem] = []
    for idx, text in enumerate(texts, start=1):
        level, conf, probs = _mock_predict_bloom(text)
        item = CLOClassificationItem(
            clo_id=f"CLO{idx}",
            text=text,
            bloom_level=level,
            bloom_name=BLOOM_LEVEL_NAMES.get(level, "Chưa phân loại"),
            confidence=conf,
            probabilities=probs,
            model_version="v0.2-milestone2",
        )
        results.append(item)

    return results


# --- POST /api/v1/ask ---
@api_v1_router.post(
    "/ask",
    response_model=AskResponse,
    summary="Hỏi đáp về đề cương học phần với trích dẫn bằng chứng (RAG)",
    description=(
        "Nhận câu hỏi và mã môn học.\n\n"
        "Xử lý lỗi:\n"
        "- **HTTP 400**: Mã môn học không đúng quy cách 6 chữ số.\n"
        "- **HTTP 503**: Mô phỏng lỗi dịch vụ AI/LLM ngoài bị gián đoạn."
    ),
    tags=["Q&A (RAG)"],
)
def ask_question(payload: AskRequest) -> AskResponse:
    """Mock trả lời câu hỏi kèm trích dẫn nguồn RAG (kết nối dữ liệu thật)."""
    question = payload.question

    # Kiểm tra mã lỗi 503: Mô phỏng dịch vụ LLM ngoài gặp lỗi kết nối/rate limit
    if "[simulate_external_failure]" in question:
        logger.error("Kích hoạt lỗi mô phỏng: Dịch vụ ngoài LLM (Gemini/Groq) không khả dụng (503)")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dịch vụ mô hình ngôn ngữ lớn (LLM Provider) hiện không khả dụng. Vui lòng thử lại sau.",
        )

    # Kiểm tra mã lỗi 400: Kiểm tra mã môn học có hợp lệ không (nếu được cung cấp)
    if payload.course_code:
        if not re.match(r"^\d{6}$", payload.course_code):
            logger.warning("Mã môn học không hợp lệ: %s", payload.course_code)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã môn học '{payload.course_code}' không hợp lệ. Mã môn học tại SGU phải gồm đúng 6 chữ số.",
            )

    course_code = payload.course_code or "841020"
    logger.info("Nhận câu hỏi RAG: '%s' (mã môn: %s, top_k: %d)", question, course_code, payload.top_k)

    # Nạp dữ liệu thật nếu có
    real_course = load_real_syllabus_json(course_code)
    if real_course:
        course_name = real_course.get("course_name", "Học phần SGU")
        gen_info = real_course.get("sections", {}).get("general_info", "")
        prereqs = real_course.get("prerequisites", [])

        if prereqs:
            prereq_str = f"yêu cầu học phần tiên quyết là: {', '.join(prereqs)}"
        else:
            prereq_str = "không yêu cầu học phần tiên quyết bắt buộc"

        answer_text = (
            f"Theo đề cương chi tiết học phần {course_name} (mã môn {course_code} - Trường ĐH Sài Gòn), "
            f"học phần này {prereq_str}. "
            f"Thông tin trích xuất: {gen_info.splitlines()[0] if gen_info else ''}"
        )

        citations = [
            CitationItem(
                course_code=course_code,
                section="general_info",
                chunk_id=f"{course_code}_sec1_chunk0",
                quote=gen_info[:150] if gen_info else f"Mã môn: {course_code}",
            )
        ]

        retrieved = [
            RetrievedChunkItem(
                chunk_id=f"{course_code}_sec1_chunk0",
                course_code=course_code,
                section="general_info",
                content=gen_info or f"Học phần: {course_name}",
                score=0.942,
            )
        ]

        return AskResponse(
            answer=answer_text,
            citations=citations,
            retrieved_chunks=retrieved[: payload.top_k],
            llm_provider="mock",
        )

    # Fallback nếu không có môn cụ thể trong kho
    sample_file = SAMPLES_DIR / "ask_response.json"
    if sample_file.exists():
        with open(sample_file, "r", encoding="utf-8") as f:
            return AskResponse(**json.load(f))

    return AskResponse(
        answer=f"Hệ thống RAG đã nhận câu hỏi về môn {course_code}.",
        citations=[],
        retrieved_chunks=[],
        llm_provider="mock",
    )


# --- POST /api/v1/learning-path ---
@api_v1_router.post(
    "/learning-path",
    response_model=LearningPathResponse,
    summary="Gợi ý lộ trình học tập tối ưu theo điều kiện tiên quyết và tín chỉ",
    description=(
        "Nhận danh sách môn học mục tiêu và môn đã hoàn thành.\n\n"
        "Xử lý lỗi:\n"
        "- **HTTP 400**: Môn mục tiêu bị trùng lặp với môn đã hoàn thành (xung đột logic)."
    ),
    tags=["Learning Path Planner"],
)
def generate_learning_path(payload: LearningPathRequest) -> LearningPathResponse:
    """Mock tính toán lộ trình học tập có kiểm tra ràng buộc nghiệp vụ."""
    target_set = set(payload.target_courses)
    passed_set = set(payload.passed_courses)

    # Kiểm tra mã lỗi 400: Xung đột logic nghiệp vụ
    intersect = target_set.intersection(passed_set)
    if intersect:
        logger.warning("Xung đột môn học giữa target và passed: %s", intersect)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Yêu cầu không hợp lệ: Các môn học {list(intersect)} đã nằm trong danh sách đã tích lũy (passed_courses), "
                "không thể đặt làm môn học mục tiêu cần học lại."
            ),
        )

    logger.info(
        "Lập lộ trình: targets=%s, passed=%s, max_credits=%d",
        payload.target_courses,
        payload.passed_courses,
        payload.max_credits_per_semester,
    )

    # Nạp mẫu lộ trình
    sample_file = SAMPLES_DIR / "learning_path_response.json"
    if sample_file.exists():
        with open(sample_file, "r", encoding="utf-8") as f:
            return LearningPathResponse(**json.load(f))

    plan = [
        SemesterPlanItem(semester=1, courses=payload.target_courses[:2], total_credits=6),
    ]
    return LearningPathResponse(
        plan=plan,
        soft_suggestions=["Hoàn thành các môn tiên quyết đúng tiến độ."],
        warnings=[],
    )


# Gắn router vào ứng dụng
app.include_router(api_v1_router)
