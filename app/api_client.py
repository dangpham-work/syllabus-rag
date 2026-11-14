"""HTTP boundary for the Syllabus RAG API. No model or backend imports here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass
class Result:
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def error_message(detail: Any) -> str:
    """Format FastAPI error detail/error payload into a readable string."""
    if isinstance(detail, list):
        return "; ".join(
            f"{'.'.join(map(str, item.get('loc', [])))}: {item.get('msg', 'Dữ liệu không hợp lệ')}"
            if isinstance(item, dict)
            else str(item)
            for item in detail
        )
    if isinstance(detail, dict):
        return str(
            detail.get("message")
            or detail.get("detail")
            or detail.get("error")
            or "Dữ liệu không hợp lệ."
        )
    return str(detail or "API chưa xử lý được yêu cầu.")


class APIClient:
    """HTTP client matching the FastAPI endpoints in api/main.py & api/schemas.py."""

    def __init__(self, base_url: str, timeout: tuple[float, float] | float = (5, 60)):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, path: str, *, method: str = "POST", **kwargs: Any) -> Result:
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = requests.request(method, self.base_url + path, **kwargs)
        except requests.Timeout:
            return Result(error="API phản hồi quá lâu. Dữ liệu nhập vẫn được giữ; hãy thử lại.")
        except requests.RequestException:
            return Result(error="Không kết nối được API. Kiểm tra backend và API_URL rồi thử lại.")

        try:
            data = response.json()
        except ValueError:
            return Result(error=f"API trả dữ liệu không phải JSON (HTTP {response.status_code}).")

        if not response.ok:
            body = data if isinstance(data, dict) else {}
            raw_err = body.get("detail")
            if raw_err is None:
                raw_err = body.get("error")
            return Result(
                data=body,
                error=f"HTTP {response.status_code}: {error_message(raw_err)}",
            )

        if isinstance(data, list):
            return Result(data={"courses": data})
        if not isinstance(data, dict):
            return Result(error="Phản hồi API không đúng cấu trúc object dự kiến.")
        return Result(data=data)

    def health(self) -> Result:
        return self.request("/health", method="GET")

    def ask(self, question: str, course_filter: str | None = None) -> Result:
        payload: dict[str, Any] = {"question": question}
        if course_filter and course_filter.strip():
            payload["course_filter"] = course_filter.strip()
        return self.request("/ask", method="POST", json=payload)

    def classify_clo(
        self,
        text: str | None = None,
        texts: list[str] | None = None,
    ) -> Result:
        payload: dict[str, Any] = {}
        if texts is not None:
            payload["texts"] = texts
        elif text is not None:
            payload["text"] = text
        return self.request("/classify-clo", method="POST", json=payload)

    def classify_clo_batch(self, texts: list[str]) -> Result:
        return self.request("/classify-clo/batch", method="POST", json={"texts": texts})

    def analyze_syllabus(self, filename: str, content: bytes) -> Result:
        return self.request(
            "/analyze-syllabus",
            method="POST",
            files={"file": (filename, content, "application/pdf")},
        )

    def learning_path(
        self,
        target_course: str,
        completed_courses: list[str] | None = None,
    ) -> Result:
        return self.request(
            "/learning-path",
            method="POST",
            json={
                "target_course": target_course,
                "completed_courses": completed_courses or [],
            },
        )

    def list_courses(self) -> Result:
        return self.request("/courses", method="GET")

    def get_course(self, course_code: str) -> Result:
        return self.request(f"/courses/{course_code}", method="GET")
