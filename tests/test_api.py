"""
tests/test_api.py
=================
Kiểm thử tự động cho REST API Syllabus RAG.
Dùng FastAPI TestClient với lifespan thật (_state) để kiểm tra đầy đủ contract theo api/schemas.py.
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import _state, app
from api.schemas import (
    AskResponse,
    CLOClassifyResponse,
    CourseDetailResponse,
    CourseListResponse,
    HealthResponse,
    LearningPathResponse,
    SyllabusAnalysisResponse,
)


def _make_dummy_pdf() -> bytes:
    """Tạo bytes giả mô phỏng file PDF nhỏ."""
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"


@pytest.fixture(scope="module")
def client():
    """Khởi tạo TestClient với FastAPI lifespan thật."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        parsed = HealthResponse(**resp.json())
        assert parsed.status == "ok"
        assert parsed.version == "1.0.0"
        assert isinstance(parsed.models_loaded, list)
        assert "section_clf" in parsed.models_loaded


# ---------------------------------------------------------------------------
# 2. POST /classify-clo & POST /classify-clo/batch
# ---------------------------------------------------------------------------

class TestClassifyClo:
    ENDPOINT = "/classify-clo"
    BATCH_ENDPOINT = "/classify-clo/batch"

    def test_classify_clo_single_valid(self, client):
        payload = {"text": "Áp dụng UML để thiết kế hệ thống phần mềm cỡ vừa"}
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200
        parsed = CLOClassifyResponse(**resp.json())
        assert len(parsed.results) == 1
        item = parsed.results[0]
        assert item.text == payload["text"]
        assert 0 <= item.label <= 6
        assert item.label_name
        assert 0.0 <= item.confidence <= 1.0
        assert len(item.probabilities) == 7
        assert parsed.model_version and parsed.model_version != "bloom-v1"

    def test_classify_clo_texts_valid(self, client):
        texts = [
            "Nhớ định nghĩa biến trong Python",
            "Thiết kế kiến trúc phần mềm theo mô hình MVC",
        ]
        resp = client.post(self.ENDPOINT, json={"texts": texts})
        assert resp.status_code == 200
        parsed = CLOClassifyResponse(**resp.json())
        assert len(parsed.results) == 2
        assert [r.text for r in parsed.results] == texts

    def test_classify_clo_empty_string(self, client):
        resp = client.post(self.ENDPOINT, json={"text": "   "})
        assert resp.status_code == 422

    def test_classify_clo_missing_field(self, client):
        resp = client.post(self.ENDPOINT, json={})
        assert resp.status_code == 422

    def test_classify_clo_batch_valid(self, client):
        texts = [
            "Nhớ định nghĩa biến trong Python",
            "Hiểu vòng lặp for",
            "Áp dụng đệ quy giải bài toán tháp Hà Nội",
        ]
        resp = client.post(self.BATCH_ENDPOINT, json={"texts": texts})
        assert resp.status_code == 200
        parsed = CLOClassifyResponse(**resp.json())
        assert len(parsed.results) == 3
        for r in parsed.results:
            assert 0 <= r.label <= 6
            assert r.label_name

    def test_classify_clo_batch_empty_list(self, client):
        resp = client.post(self.BATCH_ENDPOINT, json={"texts": []})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. POST /ask
# ---------------------------------------------------------------------------

class TestAsk:
    ENDPOINT = "/ask"

    def test_ask_valid(self, client):
        payload = {
            "question": "Môn Cơ sở lập trình có bao nhiêu tín chỉ?",
            "course_filter": "841020",
        }
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200
        parsed = AskResponse(**resp.json())
        assert parsed.answer
        assert len(parsed.retrieved_chunks) > 0
        assert parsed.provider_used in ("gemini", "groq", "mock", "cache")
        assert parsed.latency_ms >= 0

    def test_ask_empty_question(self, client):
        resp = client.post(self.ENDPOINT, json={"question": ""})
        assert resp.status_code == 422

    def test_ask_missing_question(self, client):
        resp = client.post(self.ENDPOINT, json={})
        assert resp.status_code == 422

    def test_ask_llm_unavailable_returns_503_with_chunks(self, client):
        pipeline = _state["rag_pipeline"]
        assert pipeline is not None
        prev_allow_mock = pipeline.allow_mock_fallback
        prev_cache = pipeline.cache
        from src.syllabus_core.retrieval.rag import SimpleCache

        pipeline.allow_mock_fallback = False
        pipeline.cache = SimpleCache(None)
        try:
            with (
                patch("src.syllabus_core.retrieval.rag.call_gemini", side_effect=RuntimeError("Gemini down")),
                patch("src.syllabus_core.retrieval.rag.call_groq", side_effect=RuntimeError("Groq down")),
            ):
                resp = client.post(
                    self.ENDPOINT,
                    json={"question": "Chuẩn đầu ra CLO của môn 841020 gồm những gì?"},
                )
        finally:
            pipeline.allow_mock_fallback = prev_allow_mock
            pipeline.cache = prev_cache

        assert resp.status_code == 503
        data = resp.json()
        assert data.get("error")
        assert isinstance(data.get("retrieved_chunks"), list)
        assert len(data["retrieved_chunks"]) > 0
        assert data.get("retrieved") == data["retrieved_chunks"]


# ---------------------------------------------------------------------------
# 4. POST /analyze-syllabus
# ---------------------------------------------------------------------------

class TestAnalyzeSyllabus:
    ENDPOINT = "/analyze-syllabus"

    def test_analyze_no_file(self, client):
        resp = client.post(self.ENDPOINT)
        assert resp.status_code == 422

    def test_analyze_with_pdf(self, client):
        resp = client.post(
            self.ENDPOINT,
            files={"file": ("841020.pdf", io.BytesIO(_make_dummy_pdf()), "application/pdf")},
        )
        assert resp.status_code == 200
        parsed = SyllabusAnalysisResponse(**resp.json())
        assert parsed.course_code == "841020"
        assert parsed.credits == 3
        assert len(parsed.clos) > 0
        assert len(parsed.sections) > 0
        assert parsed.model_version
        assert parsed.processing_time_s >= 0.0

    def test_analyze_wrong_file_extension(self, client):
        resp = client.post(
            self.ENDPOINT,
            files={"file": ("test.txt", io.BytesIO(b"plain text"), "text/plain")},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. POST /learning-path
# ---------------------------------------------------------------------------

class TestLearningPath:
    ENDPOINT = "/learning-path"

    def test_learning_path_valid(self, client):
        payload = {"target_course": "841108", "completed_courses": ["841020"]}
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200
        parsed = LearningPathResponse(**resp.json())
        assert parsed.target_course == "841108"
        assert len(parsed.plan) >= 1
        assert parsed.total_courses >= 1
        assert parsed.total_credits >= 1

    def test_learning_path_empty_completed(self, client):
        payload = {"target_course": "841108", "completed_courses": []}
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200
        parsed = LearningPathResponse(**resp.json())
        codes = [c.code for term in parsed.plan for c in term.courses]
        assert "841108" in codes

    def test_learning_path_invalid_course(self, client):
        resp = client.post(self.ENDPOINT, json={"target_course": "999999", "completed_courses": []})
        assert resp.status_code == 400

    def test_learning_path_missing_target(self, client):
        resp = client.post(self.ENDPOINT, json={"completed_courses": ["841020"]})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. GET /courses & GET /courses/{course_code}
# ---------------------------------------------------------------------------

class TestCourses:
    def test_list_courses(self, client):
        resp = client.get("/courses")
        assert resp.status_code == 200
        parsed = CourseListResponse(**resp.json())
        assert parsed.total == len(parsed.courses)
        assert parsed.total >= 3
        assert "841020" in {c.code for c in parsed.courses}

    def test_get_course_detail_found(self, client):
        resp = client.get("/courses/841020")
        assert resp.status_code == 200
        parsed = CourseDetailResponse(**resp.json())
        assert parsed.code == "841020"
        assert parsed.credits == 3
        assert len(parsed.clos) > 0
        assert len(parsed.sections) > 0

    def test_get_course_detail_not_found(self, client):
        resp = client.get("/courses/999999")
        assert resp.status_code == 404
