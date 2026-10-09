"""TV4 integration: real HTTP to mock backend + Streamlit user interactions."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest
import requests
from streamlit.testing.v1 import AppTest

from app.api_client import APIClient, Result

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def api_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if requests.get(url + "/health", timeout=0.3).ok:
                    break
            except requests.RequestException:
                pass
            if process.poll() is not None:
                pytest.fail("Test API exited before startup")
            time.sleep(0.1)
        else:
            pytest.fail("Test API did not start")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_forms_call_live_mock_and_clear_stale_answer(api_url, monkeypatch):
    monkeypatch.setenv("API_URL", api_url)
    at = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=20).run()
    assert not at.exception
    assert [tab.label for tab in at.tabs] == ["Hỏi đáp", "Lộ trình", "Phân tích đề cương"]
    at.text_area(key="question").set_value("Mon hoc co tien quyet khong?")
    at.button(key="ask_submit").click().run()
    assert not at.exception and not at.error
    assert at.session_state["ask_result"][1].data["retrieved_chunks"]
    at.text_area(key="question").set_value("[simulate_external_failure]")
    at.button(key="ask_submit").click().run()
    assert "503" in at.error[0].value
    assert "answer" not in at.session_state["ask_result"][1].data
    at.multiselect(key="targets").set_value(["841108"])
    at.multiselect(key="completed").set_value(["841020"])
    at.button(key="path_submit").click().run()
    assert not at.exception
    assert at.session_state["path_result"][1].data["plan"]


def test_pdf_upload_over_http_and_render(api_url, monkeypatch):
    # API at this milestone checks the header and selects a fixture by filename.
    result = APIClient(api_url).analyze("841020.pdf", b"%PDF-1.4 TV4 transport fixture")
    assert not result.error and result.data["course_code"] == "841020"
    monkeypatch.setenv("API_URL", api_url)
    at = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=20)
    at.session_state["analysis_result"] = ("841020.pdf", result)
    at.run()
    assert not at.exception
    assert len(at.dataframe) == 1
    assert any("10. Phụ trách" in e.label for e in at.expander)


def test_invalid_form_does_not_call_api(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid input should not reach API")
    monkeypatch.setattr(requests, "request", unexpected)
    at = AppTest.from_file(str(ROOT / "app/app.py")).run()
    at.button(key="ask_submit").click().run()
    assert at.error
    at.button(key="path_submit").click().run()
    assert at.error
    at.button(key="analyze_submit").click().run()
    assert at.error and not at.exception


@pytest.mark.parametrize("exception", [requests.Timeout, requests.ConnectionError])
def test_network_failure_keeps_input(monkeypatch, exception):
    def fail(*args, **kwargs):
        raise exception()
    monkeypatch.setattr(requests, "request", fail)
    at = AppTest.from_file(str(ROOT / "app/app.py")).run()
    at.text_area(key="question").set_value("Cau hoi can giu lai")
    at.button(key="ask_submit").click().run()
    assert at.error and not at.exception
    assert at.text_area(key="question").value == "Cau hoi can giu lai"


def test_503_preserves_retrieved_chunks(monkeypatch):
    response = requests.Response()
    response.status_code = 503
    response._content = b'{"detail":{"message":"Unavailable"},"retrieved":[{"text":"Evidence"}]}'
    monkeypatch.setattr(requests, "request", lambda *a, **kw: response)
    result = APIClient("http://localhost:8000").ask("Question", None)
    assert "503" in result.error
    assert result.data["retrieved"][0]["text"] == "Evidence"
