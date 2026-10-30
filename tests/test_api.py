"""
tests/test_api.py
=================
Kiểm thử tự động cho REST API Syllabus RAG.
Dùng FastAPI TestClient để giả lập HTTP mà không cần chạy server thật.
Mọi model được mock trong lifespan để không cần file pkl thật.
"""

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Mock toàn bộ model trước khi import app để tránh lỗi file không tồn tại
# ---------------------------------------------------------------------------

_MOCK_SECTION_CLF = MagicMock()
_MOCK_SECTION_CLF.predict.return_value = ["course_learning_outcomes"]

_MOCK_BLOOM_MODEL = MagicMock()
_MOCK_BLOOM_MODEL.predict.return_value = [3]
_MOCK_BLOOM_MODEL.predict_proba.return_value = [[0.1] * 7]

_MOCK_RERANKER = MagicMock()
_MOCK_RERANKER.predict.return_value = [0.9, 0.8, 0.7, 0.6, 0.5]

_MOCK_INDEX = MagicMock()
_MOCK_INDEX.search_bm25.return_value = [
    {"chunk_id": "c1", "text": "Môn Cơ sở lập trình trang bị kiến thức...", "score": 1.5},
    {"chunk_id": "c2", "text": "Yêu cầu: sinh viên cần có nền tảng toán...", "score": 1.2},
]
_MOCK_INDEX.search_dense.return_value = [
    {"chunk_id": "c1", "text": "Môn Cơ sở lập trình trang bị kiến thức...", "score": 0.92},
]

_MOCK_GRAPH = MagicMock()
_MOCK_GRAPH.get_learning_path.return_value = {
    "target_course": "841470",
    "path": [["841020"], ["841303"], ["841470"]],
    "total_credits": 9,
    "warnings": [],
}
_MOCK_GRAPH.courses = {
    "841020": {"course_name": "Cơ sở lập trình", "credits": 3},
    "841303": {"course_name": "Cấu trúc dữ liệu", "credits": 3},
    "841470": {"course_name": "Trí tuệ nhân tạo", "credits": 3},
}


def _make_dummy_pdf() -> bytes:
    """Tạo bytes giả mô phỏng file PDF nhỏ."""
    return b"%PDF-1.4 1 0 obj<</Type/Catalog>>endobj\n%%EOF"


# ---------------------------------------------------------------------------
# Fixture: TestClient với mock models
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Khởi tạo TestClient với app đã mock models."""
    with (
        patch("api.main.load_models") as mock_load,
        patch("api.main.section_clf", _MOCK_SECTION_CLF, create=True),
        patch("api.main.bloom_model", _MOCK_BLOOM_MODEL, create=True),
        patch("api.main.reranker", _MOCK_RERANKER, create=True),
        patch("api.main.retrieval_index", _MOCK_INDEX, create=True),
        patch("api.main.course_graph", _MOCK_GRAPH, create=True),
    ):
        mock_load.return_value = None
        from api.main import app
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        """GET /health → 200 với status ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    def test_health_has_version(self, client):
        """GET /health phải trả về trường version."""
        resp = client.get("/health")
        assert "version" in resp.json()


# ---------------------------------------------------------------------------
# 2. POST /classify-clo
# ---------------------------------------------------------------------------

class TestClassifyClo:
    ENDPOINT = "/classify-clo"

    def test_classify_clo_valid(self, client):
        """CLO hợp lệ → 200, label trong 0-6."""
        payload = {"text": "Áp dụng UML để thiết kế hệ thống phần mềm cỡ vừa"}
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "label" in data
        assert 0 <= data["label"] <= 6

    def test_classify_clo_empty_string(self, client):
        """CLO rỗng → 422 hoặc 400."""
        payload = {"text": ""}
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code in (400, 422)

    def test_classify_clo_missing_field(self, client):
        """Thiếu trường text → 422."""
        resp = client.post(self.ENDPOINT, json={})
        assert resp.status_code == 422

    def test_classify_clo_returns_bloom_name(self, client):
        """Kết quả phải có bloom_name."""
        payload = {"text": "Phân tích ưu nhược điểm của các thuật toán sắp xếp"}
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200
        assert "bloom_name" in resp.json()

    def test_classify_clo_batch(self, client):
        """POST /classify-clo/batch với danh sách CLO → 200, list kết quả."""
        texts = [
            "Nhớ định nghĩa biến trong Python",
            "Hiểu vòng lặp for",
            "Áp dụng đệ quy giải bài toán tháp Hà Nội",
        ]
        resp = client.post("/classify-clo/batch", json={"texts": texts})
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list) or "results" in results


# ---------------------------------------------------------------------------
# 3. POST /ask
# ---------------------------------------------------------------------------

class TestAsk:
    ENDPOINT = "/ask"

    def test_ask_valid(self, client):
        """Câu hỏi hợp lệ → 200 với answer và sources."""
        payload = {
            "question": "Môn Cơ sở lập trình có bao nhiêu tín chỉ?",
            "top_k": 3,
        }
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data or "retrieved_chunks" in data

    def test_ask_empty_question(self, client):
        """Câu hỏi rỗng → 400 hoặc 422."""
        resp = client.post(self.ENDPOINT, json={"question": ""})
        assert resp.status_code in (400, 422)

    def test_ask_missing_question(self, client):
        """Thiếu trường question → 422."""
        resp = client.post(self.ENDPOINT, json={})
        assert resp.status_code == 422

    def test_ask_llm_unavailable_returns_chunks(self, client):
        """Khi LLM lỗi, API vẫn phải trả retrieved_chunks (503 hoặc 200 degraded)."""
        with patch("api.main.generate_answer", side_effect=RuntimeError("LLM timeout")):
            payload = {"question": "Phương pháp giảng dạy của môn Giải tích là gì?"}
            resp = client.post(self.ENDPOINT, json=payload)
            # 503 với chunks HOẶC 200 degraded mode đều chấp nhận
            assert resp.status_code in (200, 503)
            if resp.status_code == 503:
                assert "retrieved_chunks" in resp.json()


# ---------------------------------------------------------------------------
# 4. POST /analyze-syllabus
# ---------------------------------------------------------------------------

class TestAnalyzeSyllabus:
    ENDPOINT = "/analyze-syllabus"

    def test_analyze_no_file(self, client):
        """Không gửi file → 422."""
        resp = client.post(self.ENDPOINT)
        assert resp.status_code == 422

    def test_analyze_with_pdf(self, client):
        """Gửi file PDF giả → 200 với schema đầy đủ."""
        dummy_pdf = _make_dummy_pdf()
        with patch("api.main.analyze_pdf") as mock_analyze:
            mock_analyze.return_value = {
                "course_code": "841020",
                "course_name": "Cơ sở lập trình",
                "credits": 3,
                "prerequisites": [],
                "clos": [{"clo_id": "CLO1", "text": "...", "bloom_level": 2}],
                "sections": {},
                "missing_sections": [],
                "model_version": "v0.1-mock",
                "processing_time_s": 0.14,
            }
            resp = client.post(
                self.ENDPOINT,
                files={"file": ("test.pdf", io.BytesIO(dummy_pdf), "application/pdf")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "course_code" in data
        assert "clos" in data

    def test_analyze_wrong_mime_type(self, client):
        """Gửi file không phải PDF → 400 hoặc 422."""
        resp = client.post(
            self.ENDPOINT,
            files={"file": ("test.txt", io.BytesIO(b"plain text"), "text/plain")},
        )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 5. POST /learning-path
# ---------------------------------------------------------------------------

class TestLearningPath:
    ENDPOINT = "/learning-path"

    def test_learning_path_valid(self, client):
        """target + completed hợp lệ → 200 với path."""
        payload = {"target_course": "841470", "completed_courses": ["841020"]}
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data or "learning_path" in data

    def test_learning_path_empty_completed(self, client):
        """completed rỗng → vẫn 200."""
        payload = {"target_course": "841470", "completed_courses": []}
        resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code == 200

    def test_learning_path_invalid_course(self, client):
        """Mã môn không tồn tại → 400 hoặc 404."""
        with patch("api.main.course_graph") as mock_graph:
            mock_graph.get_learning_path.side_effect = ValueError("Course not found")
            mock_graph.courses = {}
            payload = {"target_course": "999999", "completed_courses": []}
            resp = client.post(self.ENDPOINT, json=payload)
        assert resp.status_code in (400, 404)

    def test_learning_path_missing_target(self, client):
        """Thiếu target_course → 422."""
        resp = client.post(self.ENDPOINT, json={"completed_courses": ["841020"]})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. GET /courses
# ---------------------------------------------------------------------------

class TestCourses:
    def test_list_courses(self, client):
        """GET /courses → 200 với danh sách môn."""
        resp = client.get("/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) or "courses" in data

    def test_get_course_detail(self, client):
        """GET /courses/{code} → 200 hoặc 404."""
        resp = client.get("/courses/841020")
        assert resp.status_code in (200, 404)
