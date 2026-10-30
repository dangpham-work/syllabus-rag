"""
schemas.py
Pydantic v2 schemas cho tất cả request/response của Syllabus RAG API.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field("ok", description="Trạng thái API")
    version: str = Field("1.0.0", description="Phiên bản API")
    models_loaded: list[str] = Field(default_factory=list, description="Các model đã load")


# ---------------------------------------------------------------------------
# /classify-clo
# ---------------------------------------------------------------------------

class CLOClassifyRequest(BaseModel):
    text: Optional[str] = Field(None, description="Một câu CLO cần phân loại")
    texts: Optional[list[str]] = Field(None, description="Batch nhiều câu CLO")

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v):
        if v is not None and not v.strip():
            raise ValueError("text không được để trống")
        return v

    @field_validator("texts")
    @classmethod
    def texts_not_empty(cls, v):
        if v is not None:
            if len(v) == 0:
                raise ValueError("texts không được rỗng")
            for t in v:
                if not t.strip():
                    raise ValueError("Mỗi phần tử trong texts không được rỗng")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"text": "Áp dụng UML để mô hình hoá hệ thống phần mềm"},
                {"texts": ["Liệt kê các kiểu dữ liệu", "Thiết kế kiến trúc MVC"]},
            ]
        }
    }


class BloomProbabilities(BaseModel):
    ngoai_mien: float = Field(alias="0", default=0.0)
    nho: float = Field(alias="1", default=0.0)
    hieu: float = Field(alias="2", default=0.0)
    ap_dung: float = Field(alias="3", default=0.0)
    phan_tich: float = Field(alias="4", default=0.0)
    danh_gia: float = Field(alias="5", default=0.0)
    sang_tao: float = Field(alias="6", default=0.0)


class CLOClassifyResult(BaseModel):
    text: str = Field(description="Câu CLO đầu vào")
    label: int = Field(ge=0, le=6, description="Mức Bloom (0-6)")
    label_name: str = Field(description="Tên mức Bloom")
    confidence: float = Field(ge=0.0, le=1.0, description="Độ tin cậy")
    probabilities: dict[str, float] = Field(description="Xác suất từng lớp")
    model_version: str = Field(default="bloom-v1")


class CLOClassifyResponse(BaseModel):
    results: list[CLOClassifyResult]
    model_version: str = Field(default="bloom-v1")


# ---------------------------------------------------------------------------
# /analyze-syllabus
# ---------------------------------------------------------------------------

class CLOItem(BaseModel):
    clo_id: str
    text: str
    bloom_level: Optional[int] = None
    bloom_name: Optional[str] = None
    bloom_confidence: Optional[float] = None
    level_raw: Optional[Any] = None


class SyllabusAnalysisResponse(BaseModel):
    course_code: str
    course_name: str
    credits: int
    prerequisites: list[str] = Field(default_factory=list)
    clos: list[CLOItem] = Field(default_factory=list)
    sections: dict[str, str] = Field(default_factory=dict)
    missing_sections: list[str] = Field(default_factory=list)
    model_version: str = Field(default="v1.0")
    processing_time_s: float = Field(default=0.0)


# ---------------------------------------------------------------------------
# /ask
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(description="Câu hỏi tiếng Việt về đề cương")
    course_filter: Optional[str] = Field(None, description="Lọc theo mã môn (tuỳ chọn)")

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v):
        if not v.strip():
            raise ValueError("question không được để trống")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"question": "Môn Công nghệ phần mềm có những CLO nào?"},
                {"question": "Hình thức đánh giá của môn 841047 là gì?", "course_filter": "841047"},
            ]
        }
    }


class Citation(BaseModel):
    ref: str = Field(description="Số trích dẫn, ví dụ [1]")
    chunk_id: str
    course_code: str
    course_name: str
    section: str
    text_snippet: str


class RetrievedChunk(BaseModel):
    rank: int
    chunk_id: str
    course_code: str
    course_name: str
    section: str
    text: str
    score: float


class AskResponse(BaseModel):
    answer: str = Field(description="Câu trả lời có trích dẫn [n]")
    citations: list[Citation] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    provider_used: str = Field(description="gemini / groq / mock / cache")
    latency_ms: int = Field(default=0)


# ---------------------------------------------------------------------------
# /learning-path
# ---------------------------------------------------------------------------

class LearningPathRequest(BaseModel):
    target_course: str = Field(description="Mã môn đích")
    completed_courses: list[str] = Field(default_factory=list, description="Danh sách môn đã học")

    @field_validator("target_course")
    @classmethod
    def target_not_empty(cls, v):
        if not v.strip():
            raise ValueError("target_course không được để trống")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"target_course": "841470", "completed_courses": ["841020", "841401"]}
            ]
        }
    }


class CourseBrief(BaseModel):
    code: str
    name: str
    credits: int


class TermPlan(BaseModel):
    term: int
    courses: list[CourseBrief]
    total_credits: int


class LearningPathResponse(BaseModel):
    target_course: str
    plan: list[TermPlan]
    warnings: list[str] = Field(default_factory=list)
    soft_suggestions: list[str] = Field(default_factory=list)
    total_courses: int = 0
    total_credits: int = 0


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    retrieved: Optional[list[RetrievedChunk]] = None  # Dùng cho 503 khi LLM lỗi
