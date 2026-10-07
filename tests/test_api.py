"""tests/test_api.py
Bộ kiểm thử tự động (Unit / Integration Tests) cho Tầng API (Project 1 - TV3).
Đồ án: "Hệ thống phân tích đề cương môn học kết hợp RAG" (Trường ĐH Sài Gòn).

Sử dụng FastAPI TestClient và Pytest:
- Kiểm tra mã phản hồi HTTP 200 khi payload hợp lệ cho tất cả 5 endpoint.
- Kiểm tra mã phản hồi HTTP 422 Unprocessable Content khi payload thiếu trường hoặc sai kiểu dữ liệu.
- Kiểm tra cấu trúc dữ liệu JSON trả về tuân thủ đầy đủ Pydantic Schemas.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Generator

# Đảm bảo đường dẫn gốc của project luôn nằm trong sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.schemas import (
    HealthResponse,
    AnalyzeSyllabusResponse,
    CLOClassificationItem,
    AskResponse,
    LearningPathResponse,
)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Khởi tạo TestClient dùng chung cho toàn bộ module kiểm thử."""
    with TestClient(app) as test_client:
        yield test_client


# ==============================================================================
# 1. KIỂM THỬ ENDPOINT GET /health
# ==============================================================================
class TestHealthEndpoint:
    """Các kịch bản kiểm thử cho endpoint GET /health."""

    def test_health_check_returns_200(self, client: TestClient) -> None:
        """Endpoint /health phải trả về HTTP 200 và cấu trúc chuẩn."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "syllabus-rag-api"
        assert "version" in data

        # Kiểm tra tính tương thích với Pydantic schema
        validated = HealthResponse(**data)
        assert validated.status == "ok"


# ==============================================================================
# 2. KIỂM THỬ ENDPOINT POST /api/v1/analyze-syllabus
# ==============================================================================
class TestAnalyzeSyllabusEndpoint:
    """Các kịch bản kiểm thử cho endpoint POST /api/v1/analyze-syllabus."""

    def test_analyze_with_valid_json_file_path(self, client: TestClient) -> None:
        """Gửi đường dẫn file qua JSON body phải trả về HTTP 200 và trích xuất đủ 10 mục."""
        payload = {"file_path": "data/raw/841020 - Co so lap trinh.pdf"}
        response = client.post("/api/v1/analyze-syllabus", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["course_code"] == "841020"
        assert "course_name" in data
        assert data["credits"] > 0
        assert isinstance(data["clos"], list)
        assert len(data["clos"]) > 0

        # Kiểm tra sự hiện diện của 10 mục trong sections
        sections = data["sections"]
        expected_sections = [
            "general_info",
            "course_description",
            "course_objectives",
            "course_learning_outcomes",
            "course_content",
            "teaching_methods",
            "assessment",
            "learning_resources",
            "teaching_schedule",
            "course_policies",
        ]
        for sec_name in expected_sections:
            assert sec_name in sections
            assert sections[sec_name] is not None

        # Xác thực với Pydantic schema
        validated = AnalyzeSyllabusResponse(**data)
        assert validated.course_code == "841020"

    def test_analyze_with_file_upload(self, client: TestClient) -> None:
        """Tải lên file PDF trực tiếp qua multipart/form-data phải trả về HTTP 200."""
        dummy_pdf_content = b"%PDF-1.4 Mock binary content for SGU syllabus scan"
        files = {
            "file": ("841020_scan.pdf", io.BytesIO(dummy_pdf_content), "application/pdf")
        }
        response = client.post("/api/v1/analyze-syllabus", files=files)
        assert response.status_code == 200

        data = response.json()
        assert "course_code" in data
        assert "sections" in data

    def test_analyze_with_form_data_file_path(self, client: TestClient) -> None:
        """Gửi file_path qua form-data phải trả về HTTP 200."""
        form_data = {"file_path": "data/raw/841020 - Co so lap trinh.pdf"}
        response = client.post("/api/v1/analyze-syllabus", data=form_data)
        assert response.status_code == 200

    def test_analyze_missing_input_returns_422(self, client: TestClient) -> None:
        """Gửi request rỗng (không có file và không có file_path) phải trả về HTTP 422."""
        response = client.post("/api/v1/analyze-syllabus", json={})
        assert response.status_code == 422

    def test_analyze_blank_file_path_returns_422(self, client: TestClient) -> None:
        """Gửi file_path chỉ chứa khoảng trắng rỗng phải trả về HTTP 422."""
        response = client.post("/api/v1/analyze-syllabus", json={"file_path": "   "})
        assert response.status_code == 422


# ==============================================================================
# 3. KIỂM THỬ ENDPOINT POST /api/v1/classify-clo
# ==============================================================================
class TestClassifyCLOEndpoint:
    """Các kịch bản kiểm thử cho endpoint POST /api/v1/classify-clo."""

    def test_classify_single_clo_success(self, client: TestClient) -> None:
        """Gửi 1 câu CLO đơn lẻ qua trường 'text' phải trả về HTTP 200 và phân loại đúng."""
        payload = {"text": "Áp dụng cấu trúc rẽ nhánh và vòng lặp để giải quyết bài toán cơ bản."}
        response = client.post("/api/v1/classify-clo", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        item = data[0]
        assert item["clo_id"] == "CLO1"
        assert 0 <= item["bloom_level"] <= 6
        assert 0.0 <= item["confidence"] <= 1.0
        assert "probabilities" in item
        assert len(item["probabilities"]) == 7

        # Kiểm tra schema Pydantic
        validated = CLOClassificationItem(**item)
        assert validated.bloom_level == 3

    def test_classify_multiple_clos_success(self, client: TestClient) -> None:
        """Gửi danh sách nhiều câu CLO qua trường 'texts' phải trả về HTTP 200."""
        payload = {
            "texts": [
                "Trình bày các khái niệm cơ bản về thuật toán.",
                "Cài đặt thuật toán tìm kiếm nhị phân trên mảng đã sắp xếp.",
                "Phân tích độ phức tạp thời gian của giải thuật QuickSort.",
                "Thiết kế kiến trúc hệ thống phân tán chịu lỗi cao.",
            ]
        }
        response = client.post("/api/v1/classify-clo", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 4
        assert [d["clo_id"] for d in data] == ["CLO1", "CLO2", "CLO3", "CLO4"]

    def test_classify_empty_payload_returns_422(self, client: TestClient) -> None:
        """Gửi JSON rỗng không chứa trường text hay texts phải trả về HTTP 422."""
        response = client.post("/api/v1/classify-clo", json={})
        assert response.status_code == 422

    def test_classify_blank_string_returns_422(self, client: TestClient) -> None:
        """Gửi text rỗng hoặc chỉ có dấu cách phải trả về HTTP 422."""
        response = client.post("/api/v1/classify-clo", json={"text": "   "})
        assert response.status_code == 422

    def test_classify_empty_list_returns_422(self, client: TestClient) -> None:
        """Gửi danh sách texts rỗng phải trả về HTTP 422."""
        response = client.post("/api/v1/classify-clo", json={"texts": []})
        assert response.status_code == 422


# ==============================================================================
# 4. KIỂM THỬ ENDPOINT POST /api/v1/ask
# ==============================================================================
class TestAskEndpoint:
    """Các kịch bản kiểm thử cho endpoint POST /api/v1/ask."""

    def test_ask_valid_question_returns_200(self, client: TestClient) -> None:
        """Gửi câu hỏi hợp lệ kèm mã môn học phải trả về HTTP 200 kèm trích dẫn."""
        payload = {
            "question": "Môn Cơ sở lập trình có môn học nào bắt buộc làm tiên quyết không?",
            "course_code": "841020",
            "top_k": 5,
        }
        response = client.post("/api/v1/ask", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0
        assert isinstance(data["citations"], list)
        assert len(data["citations"]) > 0
        assert isinstance(data["retrieved_chunks"], list)
        assert data["llm_provider"] == "mock"

        # Kiểm tra chi tiết citation đầu tiên
        citation = data["citations"][0]
        assert citation["course_code"] == "841020"
        assert "section" in citation
        assert "quote" in citation

        # Xác thực với Pydantic schema
        validated = AskResponse(**data)
        assert validated.llm_provider == "mock"

    def test_ask_without_course_code_returns_200(self, client: TestClient) -> None:
        """Hỏi không chỉ định course_code (tìm kiếm toàn cục) phải trả về HTTP 200."""
        payload = {
            "question": "Quy định về việc vắng học quá 20% số tiết được xử lý thế nào?",
            "top_k": 3,
        }
        response = client.post("/api/v1/ask", json=payload)
        assert response.status_code == 200
        assert len(response.json()["answer"]) > 0

    def test_ask_missing_question_returns_422(self, client: TestClient) -> None:
        """Thiếu trường 'question' bắt buộc phải trả về HTTP 422."""
        response = client.post("/api/v1/ask", json={"course_code": "841020"})
        assert response.status_code == 422

    def test_ask_blank_question_returns_422(self, client: TestClient) -> None:
        """Câu hỏi rỗng chỉ có khoảng trắng phải trả về HTTP 422."""
        response = client.post("/api/v1/ask", json={"question": "   "})
        assert response.status_code == 422

    def test_ask_invalid_top_k_returns_422(self, client: TestClient) -> None:
        """top_k nhỏ hơn 1 hoặc vượt quá giới hạn phải trả về HTTP 422."""
        response = client.post(
            "/api/v1/ask",
            json={"question": "Môn học này có gì vui?", "top_k": 0},
        )
        assert response.status_code == 422


# ==============================================================================
# 5. KIỂM THỬ ENDPOINT POST /api/v1/learning-path
# ==============================================================================
class TestLearningPathEndpoint:
    """Các kịch bản kiểm thử cho endpoint POST /api/v1/learning-path."""

    def test_learning_path_valid_request_returns_200(self, client: TestClient) -> None:
        """Gửi danh sách môn mục tiêu và môn đã đạt phải trả về HTTP 200 kèm lộ trình."""
        payload = {
            "target_courses": ["841108", "841044"],
            "passed_courses": ["841020", "841401"],
            "max_credits_per_semester": 20,
        }
        response = client.post("/api/v1/learning-path", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data["plan"], list)
        assert len(data["plan"]) > 0
        assert isinstance(data["soft_suggestions"], list)
        assert isinstance(data["warnings"], list)

        # Kiểm tra chi tiết kế hoạch từng kỳ
        first_sem = data["plan"][0]
        assert first_sem["semester"] == 1
        assert isinstance(first_sem["courses"], list)
        assert first_sem["total_credits"] >= 0

        # Xác thực với Pydantic schema
        validated = LearningPathResponse(**data)
        assert len(validated.plan) > 0

    def test_learning_path_missing_target_courses_returns_422(self, client: TestClient) -> None:
        """Thiếu trường 'target_courses' bắt buộc phải trả về HTTP 422."""
        response = client.post(
            "/api/v1/learning-path",
            json={"passed_courses": ["841020"]},
        )
        assert response.status_code == 422

    def test_learning_path_empty_target_courses_returns_422(self, client: TestClient) -> None:
        """Danh sách 'target_courses' rỗng phải trả về HTTP 422."""
        response = client.post(
            "/api/v1/learning-path",
            json={"target_courses": []},
        )
        assert response.status_code == 422

    def test_learning_path_invalid_max_credits_returns_422(self, client: TestClient) -> None:
        """Số tín chỉ tối đa bằng 0 hoặc âm phải trả về HTTP 422."""
        response = client.post(
            "/api/v1/learning-path",
            json={
                "target_courses": ["841108"],
                "max_credits_per_semester": 0,
            },
        )
        assert response.status_code == 422


# ==============================================================================
# 6. KIỂM THỬ XỬ LÝ LỖI THỐNG NHẤT (MÃ LỖI 400, 422, 503) & NẠP DỮ LIỆU THẬT
# ==============================================================================
class TestMilestone2Enhancements:
    """Kiểm thử các tính năng nâng cấp theo Checklist Tuần 2 (Mốc 2):
    - Đọc JSON thật của nhiều môn học.
    - Xử lý mã lỗi 400 (Bad Request).
    - Xử lý mã lỗi 422 (PDF rỗng / không đọc được).
    - Xử lý mã lỗi 503 (Dịch vụ ngoài lỗi / LLM gián đoạn).
    - Ghi log vào logs/api.log.
    """

    def test_analyze_empty_file_upload_returns_422(self, client: TestClient) -> None:
        """Upload file PDF 0 bytes phải bị từ chối với HTTP 422."""
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        response = client.post("/api/v1/analyze-syllabus", files=files)
        assert response.status_code == 422
        assert "rỗng" in response.json()["detail"].lower()

    def test_analyze_invalid_pdf_content_returns_422(self, client: TestClient) -> None:
        """Upload file không đúng header PDF (%PDF-) phải trả về HTTP 422."""
        files = {"file": ("fake.pdf", io.BytesIO(b"NOT A REAL PDF FILE"), "application/pdf")}
        response = client.post("/api/v1/analyze-syllabus", files=files)
        assert response.status_code == 422
        assert "định dạng pdf" in response.json()["detail"].lower()

    def test_analyze_real_course_841401(self, client: TestClient) -> None:
        """Phân tích đề cương Giải tích 1 (841401) nạp đúng JSON môn thật."""
        payload = {"file_path": "data/raw/26 - 841401 - Giải tích 1.pdf"}
        response = client.post("/api/v1/analyze-syllabus", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["course_code"] == "841401"
        assert "Giải tích 1" in data["course_name"]
        assert len(data["clos"]) == 3

    def test_analyze_real_course_841108(self, client: TestClient) -> None:
        """Phân tích đề cương Cấu trúc dữ liệu & giải thuật (841108) nạp đúng JSON môn thật."""
        payload = {"file_path": "data/raw/34 - 841108 - Cấu trúc dữ liệu và giải thuật.pdf"}
        response = client.post("/api/v1/analyze-syllabus", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["course_code"] == "841108"
        assert "Cấu trúc dữ liệu" in data["course_name"]
        assert data["credits"] == 4
        assert "841303" in data["prerequisites"]

    def test_ask_invalid_course_code_returns_400(self, client: TestClient) -> None:
        """Hỏi với mã môn không đúng quy cách SGU (không phải 6 chữ số) trả về HTTP 400."""
        payload = {
            "question": "Học phần này mấy tín chỉ?",
            "course_code": "INVALID_CODE",
        }
        response = client.post("/api/v1/ask", json=payload)
        assert response.status_code == 400
        assert "không hợp lệ" in response.json()["detail"].lower()

    def test_ask_external_service_unavailable_returns_503(self, client: TestClient) -> None:
        """Khi dịch vụ AI/LLM bên ngoài lỗi hoặc gián đoạn, API trả về HTTP 503."""
        payload = {
            "question": "Kiểm tra lỗi kết nối mạng [simulate_external_failure]",
            "course_code": "841020",
        }
        response = client.post("/api/v1/ask", json=payload)
        assert response.status_code == 503
        assert "không khả dụng" in response.json()["detail"].lower()

    def test_learning_path_conflict_target_and_passed_returns_400(self, client: TestClient) -> None:
        """Môn trong target_courses đã có trong passed_courses gây xung đột nghiệp vụ, trả về HTTP 400."""
        payload = {
            "target_courses": ["841020", "841108"],
            "passed_courses": ["841020"],  # Trùng môn 841020
            "max_credits_per_semester": 20,
        }
        response = client.post("/api/v1/learning-path", json=payload)
        assert response.status_code == 400
        assert "đã nằm trong danh sách" in response.json()["detail"].lower()

    def test_logging_file_populated(self, client: TestClient) -> None:
        """Xác minh tệp logs/api.log tồn tại và được ghi nội dung nhật ký."""
        # Gọi thử health check để kích hoạt middleware log
        resp = client.get("/health")
        assert resp.status_code == 200

        log_path = Path(__file__).resolve().parent.parent / "logs" / "api.log"
        assert log_path.exists(), "Tệp logs/api.log phải tồn tại"
        assert log_path.stat().st_size > 0, "Tệp logs/api.log phải có dung lượng > 0"

