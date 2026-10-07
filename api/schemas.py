"""api/schemas.py
Pydantic v2 Schemas for Syllabus Analysis and RAG System (Project 1 - SGU).

Hợp đồng dữ liệu (API Contract) chuẩn RESTful cho các endpoint:
1. GET  /health: Kiểm tra tình trạng hoạt động dịch vụ.
2. POST /api/v1/analyze-syllabus: Trích xuất 10 mục đề cương học phần scan.
3. POST /api/v1/classify-clo: Phân loại mức Bloom (0-6) cho chuẩn đầu ra (CLO).
4. POST /api/v1/ask: Hỏi đáp có trích dẫn nguồn trên dữ liệu đề cương (RAG).
5. POST /api/v1/learning-path: Gợi ý lộ trình học tập tối ưu theo tiên quyết & tín chỉ.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# HẰNG SỐ & BẢNG TRA CỨU THANG ĐO BLOOM (REVISED BLOOM'S TAXONOMY)
# ==============================================================================
BLOOM_LEVEL_NAMES: Dict[int, str] = {
    0: "Chưa phân loại / Khác",
    1: "Nhớ (Remember)",
    2: "Hiểu (Understand)",
    3: "Áp dụng (Apply)",
    4: "Phân tích (Analyze)",
    5: "Đánh giá (Evaluate)",
    6: "Sáng tạo (Create)",
}


# ==============================================================================
# 1. SCHEMAS CHO ENDPOINT HEALTH CHECK (GET /health)
# ==============================================================================
class HealthResponse(BaseModel):
    """Schema phản hồi trạng thái hoạt động của hệ thống API."""

    status: str = Field(
        default="ok",
        description="Trạng thái hiện tại của dịch vụ (ok, degraded, maintenance)",
    )
    service: str = Field(
        default="syllabus-rag-api",
        description="Tên định danh dịch vụ API",
    )
    version: str = Field(
        default="v0.1-mock",
        description="Phiên bản API hiện tại",
    )
    timestamp: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Thời gian phản hồi tính theo giờ UTC",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "syllabus-rag-api",
                "version": "v0.1-mock",
                "timestamp": "2026-10-07T05:00:00Z",
            }
        }
    )


# ==============================================================================
# 2. SCHEMAS CHO ENDPOINT PHÂN TÍCH ĐỀ CƯƠNG (POST /api/v1/analyze-syllabus)
# ==============================================================================
class CLOItem(BaseModel):
    """Thông tin một Chuẩn đầu ra học phần (Course Learning Outcome - CLO)."""

    clo_id: str = Field(
        ...,
        description="Mã định danh của chuẩn đầu ra (VD: CLO1, CLO2, CĐR1.1)",
        examples=["CLO1"],
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Nội dung chi tiết của câu chuẩn đầu ra",
        examples=["Trình bày được các khái niệm cơ bản về thuật toán và kiểu dữ liệu."],
    )
    bloom_level: int = Field(
        default=0,
        ge=0,
        le=6,
        description="Mức độ tư duy theo thang đo Bloom (0: Chưa phân loại, 1: Nhớ ... 6: Sáng tạo)",
        examples=[2],
    )
    bloom_name: Optional[str] = Field(
        default=None,
        description="Tên mô tả mức Bloom tương ứng (VD: Hiểu (Understand))",
        examples=["Hiểu (Understand)"],
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy của kết quả dự đoán (0.0 đến 1.0)",
        examples=[0.92],
    )

    @model_validator(mode="after")
    def populate_bloom_name(self) -> CLOItem:
        """Tự động điền tên mức Bloom nếu chưa có."""
        if not self.bloom_name and self.bloom_level in BLOOM_LEVEL_NAMES:
            self.bloom_name = BLOOM_LEVEL_NAMES[self.bloom_level]
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clo_id": "CLO1",
                "text": "Trình bày được các khái niệm cơ bản về thuật toán và kiểu dữ liệu.",
                "bloom_level": 2,
                "bloom_name": "Hiểu (Understand)",
                "confidence": 0.92,
            }
        }
    )


class SyllabusSections(BaseModel):
    """Trích xuất chi tiết nội dung 10 mục chuẩn của đề cương chi tiết học phần."""

    general_info: Optional[str] = Field(
        default=None,
        description="Mục 1: Thông tin chung học phần (Tên môn, mã môn, số tín chỉ, môn tiên quyết/học trước, khoa/bộ môn phụ trách)",
    )
    course_description: Optional[str] = Field(
        default=None,
        description="Mục 2: Mô tả tóm tắt học phần (Vị trí, vai trò, nội dung tổng quan môn học trong CTĐT)",
    )
    course_objectives: Optional[str] = Field(
        default=None,
        description="Mục 3: Mục tiêu học phần (Course Objectives - COs)",
    )
    course_learning_outcomes: Optional[str] = Field(
        default=None,
        description="Mục 4: Chuẩn đầu ra học phần (Course Learning Outcomes - CLOs)",
    )
    course_content: Optional[str] = Field(
        default=None,
        description="Mục 5: Nội dung chi tiết học phần (Đề cương chi tiết theo chương/bài)",
    )
    teaching_methods: Optional[str] = Field(
        default=None,
        description="Mục 6: Phương pháp dạy và học (Thuyết giảng, thảo luận, thực hành, bài tập lớn)",
    )
    assessment: Optional[str] = Field(
        default=None,
        description="Mục 7: Phương pháp và tiêu chí đánh giá học phần (Quá trình, chuyên cần, thi kết thúc)",
    )
    learning_resources: Optional[str] = Field(
        default=None,
        description="Mục 8: Giáo trình và tài liệu tham khảo (Sách bắt buộc, sách tham khảo, tài liệu trực tuyến)",
    )
    teaching_schedule: Optional[str] = Field(
        default=None,
        description="Mục 9: Kế hoạch giảng dạy chi tiết (Phân bổ nội dung theo tuần/buổi học)",
    )
    course_policies: Optional[str] = Field(
        default=None,
        description="Mục 10: Yêu cầu và quy định đối với học phần (Chuyên cần, đạo đức học thuật, điều kiện dự thi)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "general_info": "Môn học: Cơ sở lập trình. Mã môn: 841020. Tín chỉ: 3 (2 LT + 1 TH). Tiên quyết: Không.",
                "course_description": "Trang bị các kiến thức cơ bản về lập trình cấu trúc, biến, mảng, hàm và con trỏ.",
                "course_objectives": "Hiểu cấu trúc chương trình máy tính và viết mã nguồn giải quyết bài toán cơ bản.",
                "course_learning_outcomes": "CLO1: Hiểu cú pháp cơ bản; CLO2: Áp dụng cấu trúc rẽ nhánh và vòng lặp.",
                "course_content": "Chương 1: Giới thiệu; Chương 2: Cú pháp cơ bản; Chương 3: Rẽ nhánh & lặp; Chương 4: Mảng; Chương 5: Hàm.",
                "teaching_methods": "Thuyết giảng lý thuyết tại giảng đường kết hợp thực hành lập trình tại phòng máy.",
                "assessment": "Đánh giá quá trình: 30%, Đánh giá thực hành: 20%, Thi cuối kỳ trắc nghiệm/tự luận: 50%.",
                "learning_resources": "Giáo trình Kỹ thuật lập trình C - ĐH Sài Gòn; C How to Program (Paul Deitel).",
                "teaching_schedule": "Tuần 1-4: Cơ bản; Tuần 5-9: Cấu trúc điều khiển & mảng; Tuần 10-15: Hàm và cấu trúc dữ liệu con trỏ.",
                "course_policies": "Tham dự lớp học tối thiểu 80% thời lượng. Hoàn thành 100% bài tập thực hành theo yêu cầu.",
            }
        }
    )


class AnalyzeSyllabusRequest(BaseModel):
    """Schema yêu cầu phân tích đề cương qua đường dẫn file nội bộ (JSON body).
    
    Lưu ý: Endpoint còn hỗ trợ upload file PDF trực tiếp thông qua form-data (multipart/form-data).
    """

    file_path: Optional[str] = Field(
        default=None,
        description="Đường dẫn file PDF đề cương scan trên server (nếu không upload trực tiếp)",
        examples=["data/raw/841020 - Co so lap trinh.pdf"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "data/raw/841020 - Co so lap trinh.pdf"
            }
        }
    )


class AnalyzeSyllabusResponse(BaseModel):
    """Schema kết quả phân tích và trích xuất cấu trúc đề cương học phần."""

    course_code: str = Field(
        ...,
        description="Mã học phần (VD: 841020, 841108)",
        examples=["841020"],
    )
    course_name: str = Field(
        ...,
        description="Tên học phần (VD: Cơ sở lập trình)",
        examples=["Cơ sở lập trình"],
    )
    credits: int = Field(
        ...,
        ge=1,
        le=12,
        description="Số tín chỉ tích lũy của học phần",
        examples=[3],
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Danh sách mã các học phần tiên quyết hoặc học trước",
        examples=[["841401"]],
    )
    clos: List[CLOItem] = Field(
        default_factory=list,
        description="Danh sách các Chuẩn đầu ra (CLO) kèm mức Bloom dự đoán",
    )
    sections: SyllabusSections = Field(
        ...,
        description="Nội dung trích xuất chi tiết theo 10 mục chuẩn của đề cương",
    )
    missing_sections: List[str] = Field(
        default_factory=list,
        description="Danh sách tên các mục bị thiếu hoặc không nhận diện được trong đề cương scan",
        examples=[[]],
    )
    model_version: str = Field(
        default="v0.1-mock",
        description="Phiên bản pipeline OCR & phân đoạn đề cương",
        examples=["v0.1-mock"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "course_code": "841020",
                "course_name": "Cơ sở lập trình",
                "credits": 3,
                "prerequisites": [],
                "clos": [
                    {
                        "clo_id": "CLO1",
                        "text": "Trình bày được các khái niệm cơ bản về thuật toán và kiểu dữ liệu.",
                        "bloom_level": 2,
                        "bloom_name": "Hiểu (Understand)",
                        "confidence": 0.92,
                    },
                    {
                        "clo_id": "CLO2",
                        "text": "Áp dụng cấu trúc rẽ nhánh và vòng lặp để giải quyết bài toán cơ bản.",
                        "bloom_level": 3,
                        "bloom_name": "Áp dụng (Apply)",
                        "confidence": 0.89,
                    },
                ],
                "sections": {
                    "general_info": "Môn học: Cơ sở lập trình. Mã môn: 841020. Tín chỉ: 3 (2 LT + 1 TH). Tiên quyết: Không.",
                    "course_description": "Trang bị các kiến thức cơ bản về lập trình cấu trúc, biến, mảng, hàm.",
                    "course_objectives": "Hiểu cấu trúc chương trình máy tính và viết mã nguồn giải quyết bài toán cơ bản.",
                    "course_learning_outcomes": "CLO1: Hiểu cú pháp cơ bản; CLO2: Áp dụng cấu trúc rẽ nhánh và vòng lặp.",
                    "course_content": "Chương 1: Giới thiệu; Chương 2: Cú pháp; Chương 3: Rẽ nhánh & lặp; Chương 4: Mảng; Chương 5: Hàm.",
                    "teaching_methods": "Thuyết giảng lý thuyết kết hợp thực hành phòng máy.",
                    "assessment": "Đánh giá quá trình: 30%, Thực hành: 20%, Thi cuối kỳ: 50%.",
                    "learning_resources": "Giáo trình Kỹ thuật lập trình C - ĐH Sài Gòn.",
                    "teaching_schedule": "Tuần 1-15: Giảng dạy theo đề cương chi tiết.",
                    "course_policies": "Tham dự lớp tối thiểu 80%. Hoàn thành đầy đủ bài tập.",
                },
                "missing_sections": [],
                "model_version": "v0.1-mock",
            }
        }
    )


# ==============================================================================
# 3. SCHEMAS CHO ENDPOINT PHÂN LOẠI BLOOM CLO (POST /api/v1/classify-clo)
# ==============================================================================
class ClassifyCLORequest(BaseModel):
    """Schema yêu cầu phân loại mức độ tư duy Bloom cho một hoặc nhiều câu CLO.
    
    Hỗ trợ linh hoạt:
    - Truyền 1 câu CLO qua trường `text` (str) hoặc `texts` ([str]).
    - Truyền danh sách nhiều câu CLO qua `texts` (list[str]) hoặc `text` (list[str]).
    """

    text: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Một câu CLO (str) hoặc danh sách các câu CLO (list[str])",
        examples=["Áp dụng cấu trúc rẽ nhánh và vòng lặp để giải quyết bài toán tính toán cơ bản."],
    )
    texts: Optional[List[str]] = Field(
        default=None,
        description="Danh sách các câu CLO cần phân loại",
        examples=[
            [
                "Hiểu và trình bày được nguyên lý hoạt động của cấu trúc dữ liệu cây.",
                "Cài đặt và áp dụng thuật toán tìm kiếm nhị phân vào bài toán thực tế.",
            ]
        ],
    )

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize_inputs(cls, data: Any) -> Any:
        """Kiểm tra tính hợp lệ và chuẩn hóa dữ liệu đầu vào.
        
        Đảm bảo có ít nhất một câu CLO hợp lệ (không rỗng, không toàn khoảng trắng).
        """
        if not isinstance(data, dict):
            return data

        raw_texts: List[str] = []

        # Hỗ trợ nhận diện trường `text`
        val_text = data.get("text")
        if isinstance(val_text, str) and val_text.strip():
            raw_texts.append(val_text.strip())
        elif isinstance(val_text, list):
            raw_texts.extend([t.strip() for t in val_text if isinstance(t, str) and t.strip()])

        # Hỗ trợ nhận diện trường `texts`
        val_texts = data.get("texts")
        if isinstance(val_texts, list):
            raw_texts.extend([t.strip() for t in val_texts if isinstance(t, str) and t.strip()])
        elif isinstance(val_texts, str) and val_texts.strip():
            raw_texts.append(val_texts.strip())

        # Hỗ trợ thêm alias `clo` hoặc `clos` nếu client gửi
        for alias in ("clo", "clos"):
            val_alias = data.get(alias)
            if isinstance(val_alias, str) and val_alias.strip():
                raw_texts.append(val_alias.strip())
            elif isinstance(val_alias, list):
                raw_texts.extend([t.strip() for t in val_alias if isinstance(t, str) and t.strip()])

        if not raw_texts:
            raise ValueError(
                "Yêu cầu phải chứa ít nhất một câu CLO hợp lệ trong trường 'text' hoặc 'texts'."
            )

        # Lưu lại danh sách đã chuẩn hóa vào `texts`
        data["texts"] = raw_texts
        return data

    def get_clo_texts(self) -> List[str]:
        """Phương thức helper trích xuất danh sách câu CLO đã làm sạch."""
        if self.texts:
            return self.texts
        if isinstance(self.text, list):
            return self.text
        if isinstance(self.text, str):
            return [self.text]
        return []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "texts": [
                    "Hiểu và trình bày được nguyên lý hoạt động của cấu trúc dữ liệu mảng và danh sách liên kết.",
                    "Cài đặt và áp dụng thuật toán tìm kiếm nhị phân để tối ưu hóa thời gian tìm kiếm dữ liệu.",
                ]
            }
        }
    )


class CLOClassificationItem(BaseModel):
    """Kết quả phân loại mức Bloom cho một câu CLO cụ thể."""

    clo_id: str = Field(
        ...,
        description="Định danh CLO (VD: CLO1, CLO2...)",
        examples=["CLO1"],
    )
    text: str = Field(
        ...,
        description="Nội dung câu chuẩn đầu ra được đánh giá",
        examples=["Cài đặt và áp dụng thuật toán tìm kiếm nhị phân vào bài toán thực tế."],
    )
    bloom_level: int = Field(
        ...,
        ge=0,
        le=6,
        description="Mức độ Bloom phân loại được (từ 0 đến 6)",
        examples=[3],
    )
    bloom_name: Optional[str] = Field(
        default=None,
        description="Tên mô tả mức Bloom tương ứng (VD: Áp dụng (Apply))",
        examples=["Áp dụng (Apply)"],
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy của mức dự đoán cao nhất (0.0 - 1.0)",
        examples=[0.89],
    )
    probabilities: Dict[int, float] = Field(
        ...,
        description="Phân phối xác suất dự đoán cho từng mức Bloom từ 0 đến 6",
        examples=[
            {
                0: 0.01,
                1: 0.02,
                2: 0.05,
                3: 0.89,
                4: 0.02,
                5: 0.01,
                6: 0.00,
            }
        ],
    )
    model_version: str = Field(
        default="v0.1-mock",
        description="Phiên bản mô hình phân loại Bloom",
        examples=["v0.1-mock"],
    )

    @model_validator(mode="after")
    def populate_bloom_name(self) -> CLOClassificationItem:
        """Tự động điền tên mức Bloom nếu chưa có."""
        if not self.bloom_name and self.bloom_level in BLOOM_LEVEL_NAMES:
            self.bloom_name = BLOOM_LEVEL_NAMES[self.bloom_level]
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clo_id": "CLO1",
                "text": "Cài đặt và áp dụng thuật toán tìm kiếm nhị phân vào bài toán thực tế.",
                "bloom_level": 3,
                "bloom_name": "Áp dụng (Apply)",
                "confidence": 0.89,
                "probabilities": {
                    0: 0.01,
                    1: 0.02,
                    2: 0.05,
                    3: 0.89,
                    4: 0.02,
                    5: 0.01,
                    6: 0.00,
                },
                "model_version": "v0.1-mock",
            }
        }
    )


class ClassifyCLOResponse(BaseModel):
    """Schema bọc danh sách kết quả phân loại CLO (dành cho client cần metadata bọc ngoài)."""

    results: List[CLOClassificationItem] = Field(
        ...,
        description="Danh sách kết quả phân loại cho từng câu CLO",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Tổng số câu CLO được phân loại",
        examples=[1],
    )
    model_version: str = Field(
        default="v0.1-mock",
        description="Phiên bản mô hình",
        examples=["v0.1-mock"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "clo_id": "CLO1",
                        "text": "Cài đặt và áp dụng thuật toán tìm kiếm nhị phân vào bài toán thực tế.",
                        "bloom_level": 3,
                        "bloom_name": "Áp dụng (Apply)",
                        "confidence": 0.89,
                        "probabilities": {
                            0: 0.01,
                            1: 0.02,
                            2: 0.05,
                            3: 0.89,
                            4: 0.02,
                            5: 0.01,
                            6: 0.00,
                        },
                        "model_version": "v0.1-mock",
                    }
                ],
                "total": 1,
                "model_version": "v0.1-mock",
            }
        }
    )


# ==============================================================================
# 4. SCHEMAS CHO ENDPOINT HỎI ĐÁP RAG (POST /api/v1/ask)
# ==============================================================================
class AskRequest(BaseModel):
    """Schema yêu cầu hỏi đáp RAG trên dữ liệu đề cương."""

    question: str = Field(
        ...,
        min_length=2,
        description="Nội dung câu hỏi của người dùng về môn học hoặc đề cương",
        examples=["Môn Cơ sở lập trình có môn học nào bắt buộc làm tiên quyết không?"],
    )
    course_code: Optional[str] = Field(
        default=None,
        description="Mã môn học để giới hạn không gian tìm kiếm (VD: 841020). Nếu null, tìm trên toàn bộ đề cương.",
        examples=["841020"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Số lượng đoạn tài liệu có độ liên quan cao nhất cần truy xuất",
        examples=[5],
    )

    @field_validator("question")
    @classmethod
    def validate_question_non_blank(cls, v: str) -> str:
        """Đảm bảo câu hỏi không phải toàn khoảng trắng rỗng."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Câu hỏi không được để trống hoặc chỉ chứa khoảng trắng.")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "Môn Cơ sở lập trình có môn học nào bắt buộc làm tiên quyết không?",
                "course_code": "841020",
                "top_k": 5,
            }
        }
    )


class CitationItem(BaseModel):
    """Thông tin bằng chứng trích dẫn phục vụ câu trả lời RAG."""

    course_code: str = Field(
        ...,
        description="Mã môn học chứa nội dung trích dẫn",
        examples=["841020"],
    )
    section: str = Field(
        ...,
        description="Tên mục trong đề cương (VD: general_info, assessment)",
        examples=["general_info"],
    )
    chunk_id: str = Field(
        ...,
        description="Mã định danh đoạn trích xuất (Chunk ID)",
        examples=["841020_sec1_chunk0"],
    )
    quote: str = Field(
        ...,
        description="Đoạn trích dẫn nguyên văn dùng làm căn cứ trả lời",
        examples=["Học phần tiên quyết: Không. Học phần học trước: Không."],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "course_code": "841020",
                "section": "general_info",
                "chunk_id": "841020_sec1_chunk0",
                "quote": "Học phần tiên quyết: Không. Học phần học trước: Không.",
            }
        }
    )


class RetrievedChunkItem(BaseModel):
    """Chi tiết một đoạn văn bản (chunk) được truy xuất từ cơ sở tri thức đề cương."""

    chunk_id: str = Field(
        ...,
        description="Định danh duy nhất của chunk văn bản",
        examples=["841020_sec1_chunk0"],
    )
    course_code: str = Field(
        ...,
        description="Mã môn học của chunk",
        examples=["841020"],
    )
    section: str = Field(
        ...,
        description="Mục đề cương mà đoạn văn bản trực thuộc",
        examples=["general_info"],
    )
    content: str = Field(
        ...,
        description="Nội dung văn bản đầy đủ của chunk",
        examples=["1. Thông tin chung học phần: Mã môn học 841020, Tên học phần: Cơ sở lập trình, Số tín chỉ: 3."],
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Điểm số độ liên quan tương đồng (hybrid ranking score)",
        examples=[0.895],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chunk_id": "841020_sec1_chunk0",
                "course_code": "841020",
                "section": "general_info",
                "content": "1. Thông tin chung học phần: Mã môn học 841020, Tên học phần: Cơ sở lập trình, Số tín chỉ: 3.",
                "score": 0.895,
            }
        }
    )


class AskResponse(BaseModel):
    """Schema phản hồi kết quả hỏi đáp từ hệ thống RAG."""

    answer: str = Field(
        ...,
        description="Câu trả lời tổng hợp được sinh ra từ các bằng chứng trích dẫn",
        examples=[
            "Theo đề cương môn Cơ sở lập trình (mã môn 841020), học phần này không yêu cầu môn tiên quyết bắt buộc."
        ],
    )
    citations: List[CitationItem] = Field(
        default_factory=list,
        description="Danh sách các trích dẫn làm bằng chứng kiểm chứng cho câu trả lời",
    )
    retrieved_chunks: List[RetrievedChunkItem] = Field(
        default_factory=list,
        description="Danh sách các đoạn văn bản được truy xuất từ mô hình tìm kiếm lai (BM25 + Dense)",
    )
    llm_provider: str = Field(
        default="mock",
        description="Nhà cung cấp mô hình ngôn ngữ lớn (mock, gemini, groq)",
        examples=["mock"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "Theo đề cương môn Cơ sở lập trình (mã môn 841020), học phần này không yêu cầu môn tiên quyết bắt buộc.",
                "citations": [
                    {
                        "course_code": "841020",
                        "section": "general_info",
                        "chunk_id": "841020_sec1_chunk0",
                        "quote": "Học phần tiên quyết: Không. Học phần học trước: Không.",
                    }
                ],
                "retrieved_chunks": [
                    {
                        "chunk_id": "841020_sec1_chunk0",
                        "course_code": "841020",
                        "section": "general_info",
                        "content": "1. Thông tin chung học phần: Mã môn học 841020, Tên học phần: Cơ sở lập trình, Số tín chỉ: 3.",
                        "score": 0.895,
                    }
                ],
                "llm_provider": "mock",
            }
        }
    )


# ==============================================================================
# 5. SCHEMAS CHO ENDPOINT LỘ TRÌNH HỌC TẬP (POST /api/v1/learning-path)
# ==============================================================================
class LearningPathRequest(BaseModel):
    """Schema yêu cầu đề xuất lộ trình học tập."""

    target_courses: List[str] = Field(
        ...,
        min_length=1,
        description="Danh sách mã các môn học mục tiêu cần hoàn thành",
        examples=[["841108", "841109"]],
    )
    passed_courses: List[str] = Field(
        default_factory=list,
        description="Danh sách mã các môn học sinh viên đã hoàn thành/tích lũy",
        examples=[["841020", "841401"]],
    )
    max_credits_per_semester: int = Field(
        default=20,
        ge=1,
        le=30,
        description="Số lượng tín chỉ tối đa được phép đăng ký trong một học kỳ",
        examples=[20],
    )

    @field_validator("target_courses")
    @classmethod
    def validate_target_courses_not_empty(cls, v: List[str]) -> List[str]:
        """Đảm bảo danh sách môn mục tiêu chứa ít nhất 1 mã môn hợp lệ."""
        cleaned = [c.strip() for c in v if isinstance(c, str) and c.strip()]
        if not cleaned:
            raise ValueError("Danh sách target_courses phải chứa ít nhất một mã môn học hợp lệ.")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_courses": ["841108", "841109"],
                "passed_courses": ["841020", "841401"],
                "max_credits_per_semester": 20,
            }
        }
    )


class SemesterPlanItem(BaseModel):
    """Kế hoạch đăng ký môn học cho một học kỳ cụ thể."""

    semester: int = Field(
        ...,
        ge=1,
        description="Thứ tự học kỳ (1, 2, 3...)",
        examples=[1],
    )
    courses: List[str] = Field(
        ...,
        description="Danh sách mã các môn học được xếp vào học kỳ này",
        examples=[["841303", "841403"]],
    )
    total_credits: int = Field(
        ...,
        ge=0,
        description="Tổng số tín chỉ dự kiến của học kỳ này",
        examples=[7],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "semester": 1,
                "courses": ["841303", "841403"],
                "total_credits": 7,
            }
        }
    )


class LearningPathResponse(BaseModel):
    """Schema phản hồi kết quả gợi ý lộ trình học tập."""

    plan: List[SemesterPlanItem] = Field(
        ...,
        description="Lộ trình học tập sắp xếp theo từng học kỳ tối ưu",
    )
    soft_suggestions: List[str] = Field(
        default_factory=list,
        description="Các lời khuyên mềm về phân bổ tải học tập và môn tự chọn",
        examples=[
            [
                "Nên hoàn thành môn Kỹ thuật lập trình (841303) trước khi học Cấu trúc dữ liệu và giải thuật (841108).",
                "Phân bổ đều các môn toán và lập trình để tránh quá tải bài tập lớn.",
            ]
        ],
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Các cảnh báo về môn tiên quyết hoặc ràng buộc chương trình đào tạo",
        examples=[
            [
                "Môn 841108 yêu cầu tiên quyết là 841303, cần đảm bảo không bị rớt môn ở kỳ trước.",
            ]
        ],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan": [
                    {
                        "semester": 1,
                        "courses": ["841303", "841403"],
                        "total_credits": 7,
                    },
                    {
                        "semester": 2,
                        "courses": ["841108", "841109"],
                        "total_credits": 7,
                    },
                ],
                "soft_suggestions": [
                    "Nên hoàn thành môn Kỹ thuật lập trình (841303) trước khi học Cấu trúc dữ liệu và giải thuật (841108).",
                    "Phân bổ đều các môn toán và lập trình để tránh quá tải bài tập lớn.",
                ],
                "warnings": [
                    "Môn 841108 yêu cầu tiên quyết là 841303, cần đảm bảo không bị rớt môn ở kỳ trước.",
                ],
            }
        }
    )
