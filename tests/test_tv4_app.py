"""TV4 integration & unit tests: APIClient + Streamlit AppTest against unified API contract."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from app.api_client import APIClient

ROOT = Path(__file__).resolve().parents[1]


def _json_response(status_code: int, payload: dict | list) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    resp.headers["Content-Type"] = "application/json"
    return resp


# ---------------------------------------------------------------------------
# Unit tests for APIClient
# ---------------------------------------------------------------------------

def test_api_client_endpoints_and_payloads(monkeypatch):
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/courses"):
            return _json_response(200, {"courses": [{"code": "841020"}], "total": 1})
        return _json_response(200, {"status": "ok"})

    monkeypatch.setattr(requests, "request", fake_request)
    client = APIClient("http://localhost:8000/")

    assert not client.health().error
    assert not client.ask("Môn 841020 có mấy tín chỉ?", "841020").error
    assert not client.classify_clo(text="Áp dụng UML").error
    assert not client.classify_clo_batch(["Nhớ khái niệm", "Thiết kế kiến trúc"]).error
    assert not client.analyze_syllabus("841020.pdf", b"%PDF-1.4\n%%EOF").error
    assert not client.learning_path("841470", ["841020"]).error
    assert not client.list_courses().error
    assert not client.get_course("841020").error

    recorded = [(m, u.replace("http://localhost:8000", ""), kw) for m, u, kw in calls]
    assert [r[:2] for r in recorded] == [
        ("GET", "/health"),
        ("POST", "/ask"),
        ("POST", "/classify-clo"),
        ("POST", "/classify-clo/batch"),
        ("POST", "/analyze-syllabus"),
        ("POST", "/learning-path"),
        ("GET", "/courses"),
        ("GET", "/courses/841020"),
    ]
    assert all("/api/v1/" not in r[1] for r in recorded)
    assert recorded[1][2]["json"] == {"question": "Môn 841020 có mấy tín chỉ?", "course_filter": "841020"}
    assert recorded[2][2]["json"] == {"text": "Áp dụng UML"}
    assert recorded[3][2]["json"] == {"texts": ["Nhớ khái niệm", "Thiết kế kiến trúc"]}
    assert recorded[5][2]["json"] == {"target_course": "841470", "completed_courses": ["841020"]}


def test_503_preserves_retrieved_chunks(monkeypatch):
    payload = {
        "error": "LLM không khả dụng",
        "retrieved_chunks": [
            {
                "rank": 1,
                "chunk_id": "841020_c1",
                "course_code": "841020",
                "course_name": "Cơ sở lập trình",
                "section": "general_info",
                "text": "Số tín chỉ: 3",
                "score": 0.95,
            }
        ],
        "retrieved": [{"text": "Số tín chỉ: 3"}],
    }
    monkeypatch.setattr(requests, "request", lambda *a, **kw: _json_response(503, payload))
    result = APIClient("http://localhost:8000").ask("Question", None)
    assert "503" in result.error
    assert "LLM không khả dụng" in result.error
    assert result.data["retrieved_chunks"][0]["text"] == "Số tín chỉ: 3"
    assert result.data["retrieved"][0]["text"] == "Số tín chỉ: 3"


# ---------------------------------------------------------------------------
# Offline AppTest UI tests (mocked HTTP)
# ---------------------------------------------------------------------------

def test_app_renders_tabs_and_no_external_logo(monkeypatch):
    def fake_request(method, url, **kwargs):
        if method == "GET" and url.endswith("/health"):
            return _json_response(200, {"status": "ok", "version": "1.0.0", "models_loaded": ["section_clf"]})
        raise AssertionError(f"Unexpected HTTP call: {method} {url}")

    monkeypatch.setattr(requests, "request", fake_request)
    at = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=20).run()
    assert not at.exception
    assert len(at.image) == 0
    assert [tab.label for tab in at.tabs] == ["💬 Hỏi đáp", "🗺️ Lộ trình học", "📄 Phân tích đề cương"]
    assert any("API sẵn sàng" in s.value for s in at.sidebar.success)


def test_invalid_form_does_not_call_api(monkeypatch):
    def fake_request(method, url, **kwargs):
        if method == "GET" and url.endswith("/health"):
            return _json_response(200, {"status": "ok", "version": "1.0.0", "models_loaded": []})
        pytest.fail(f"Invalid input should not reach API: {method} {url}")

    monkeypatch.setattr(requests, "request", fake_request)
    at = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=20).run()
    at.button(key="ask_submit").click().run()
    assert any("câu hỏi" in w.value.lower() for w in at.warning)
    at.button(key="path_submit").click().run()
    assert any("môn đích" in w.value.lower() for w in at.warning)
    assert not at.exception


@pytest.mark.parametrize("exception", [requests.Timeout, requests.ConnectionError])
def test_network_failure_keeps_input(monkeypatch, exception):
    def fail(method, url, **kwargs):
        if method == "GET" and url.endswith("/health"):
            return _json_response(200, {"status": "ok", "version": "1.0.0", "models_loaded": []})
        raise exception()

    monkeypatch.setattr(requests, "request", fail)
    at = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=20).run()
    at.text_area(key="question").set_value("Cau hoi can giu lai")
    at.button(key="ask_submit").click().run()
    assert at.error and not at.exception
    assert at.text_area(key="question").value == "Cau hoi can giu lai"


def test_ask_503_degraded_displays_chunks(monkeypatch):
    def fake_request(method, url, **kwargs):
        if method == "GET" and url.endswith("/health"):
            return _json_response(200, {"status": "ok", "version": "1.0.0", "models_loaded": []})
        if method == "POST" and url.endswith("/ask"):
            return _json_response(
                503,
                {
                    "error": "LLM không khả dụng",
                    "retrieved_chunks": [
                        {
                            "rank": 1,
                            "chunk_id": "841020_clo",
                            "course_code": "841020",
                            "course_name": "Cơ sở lập trình",
                            "section": "course_learning_outcomes",
                            "text": "CLO1: Trình bày được cú pháp ngôn ngữ C",
                            "score": 0.91,
                        }
                    ],
                    "retrieved": [{"text": "CLO1: Trình bày được cú pháp ngôn ngữ C"}],
                },
            )
        raise AssertionError(f"Unexpected HTTP call: {method} {url}")

    monkeypatch.setattr(requests, "request", fake_request)
    at = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=20).run()
    at.text_area(key="question").set_value("CLO của môn 841020 là gì?")
    at.button(key="ask_submit").click().run()
    assert not at.exception
    assert not at.error
    assert any("503" in w.value for w in at.warning)
    assert any("CLO1: Trình bày được cú pháp ngôn ngữ C" in t.value for t in at.text)


def test_analyze_tab_upload_and_render(monkeypatch):
    analysis_payload = {
        "course_code": "841020",
        "course_name": "Cơ sở lập trình",
        "credits": 3,
        "prerequisites": [],
        "clos": [
            {
                "clo_id": "CLO1",
                "text": "Áp dụng vòng lặp và hàm trong C",
                "bloom_level": 3,
                "bloom_name": "Áp dụng",
                "bloom_confidence": 0.92,
            }
        ],
        "sections": {"general_info": "Mã học phần: 841020", "course_description": "Nhập môn lập trình"},
        "missing_sections": [],
        "model_version": "v1.0",
        "processing_time_s": 0.12,
    }

    def fake_request(method, url, **kwargs):
        if method == "GET" and url.endswith("/health"):
            return _json_response(200, {"status": "ok", "version": "1.0.0", "models_loaded": ["section_clf"]})
        if method == "POST" and url.endswith("/analyze-syllabus"):
            return _json_response(200, analysis_payload)
        raise AssertionError(f"Unexpected HTTP call: {method} {url}")

    monkeypatch.setattr(requests, "request", fake_request)
    at = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=20).run()
    at.file_uploader(key="pdf_uploader").upload("841020.pdf", b"%PDF-1.4\n%%EOF", "application/pdf").run()
    at.button(key="analyze_submit").click().run()
    assert not at.exception
    assert not at.error
    assert any("841020" in s.value for s in at.main.success)
    assert len(at.dataframe) == 1


# ---------------------------------------------------------------------------
# Live integration tests against real FastAPI server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(150):
            try:
                if requests.get(url + "/health", timeout=0.5).ok:
                    break
            except requests.RequestException:
                pass
            if process.poll() is not None:
                pytest.fail("Test API exited before startup")
            time.sleep(0.2)
        else:
            pytest.fail("Test API did not start")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_live_client_and_app_flows(api_url, monkeypatch):
    client = APIClient(api_url)
    health_res = client.health()
    assert not health_res.error
    assert health_res.data["status"] == "ok"

    courses_res = client.list_courses()
    assert not courses_res.error
    assert courses_res.data["total"] >= 1

    detail_res = client.get_course("841020")
    assert not detail_res.error
    assert detail_res.data["code"] == "841020"

    clo_res = client.classify_clo(text="Áp dụng UML để mô hình hoá hệ thống")
    assert not clo_res.error
    assert len(clo_res.data["results"]) == 1

    batch_res = client.classify_clo_batch(["Liệt kê biến", "Thiết kế kiến trúc MVC"])
    assert not batch_res.error
    assert len(batch_res.data["results"]) == 2

    analyze_res = client.analyze_syllabus("841020.pdf", b"%PDF-1.4\n%%EOF")
    assert not analyze_res.error
    assert analyze_res.data["course_code"] == "841020"

    monkeypatch.setenv("API_URL", api_url)
    at = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=20).run()
    assert not at.exception
    assert any("API sẵn sàng" in s.value for s in at.sidebar.success)

    # Tab 1: Ask
    at.text_area(key="question").set_value("Môn Cơ sở lập trình có bao nhiêu tín chỉ?")
    at.button(key="ask_submit").click().run()
    assert not at.exception
    assert not at.error

    # Tab 2: Learning path (841108 exists in bundled processed syllabi)
    at.text_input(key="target_course").set_value("841108")
    at.text_area(key="completed_courses").set_value("841020")
    at.button(key="path_submit").click().run()
    assert not at.exception
    assert not at.error
    assert any("Kế hoạch" in s.value for s in at.main.success)
