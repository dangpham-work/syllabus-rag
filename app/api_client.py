"""HTTP boundary for the TV3 v1 API. No model or backend imports here."""
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass
class Result:
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def error_message(detail: Any) -> str:
    if isinstance(detail, list):
        return "; ".join(
            f"{'.'.join(map(str, item.get('loc', [])))}: {item.get('msg', 'Dữ liệu không hợp lệ')}"
            if isinstance(item, dict) else str(item) for item in detail
        )
    if isinstance(detail, dict):
        return str(detail.get("message", "Dữ liệu không hợp lệ."))
    return str(detail or "API chưa xử lý được yêu cầu.")


class APIClient:
    def __init__(self, base_url: str):
        # API_URL is the server root; business endpoints include /api/v1.
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, *, method: str = "POST", **kwargs: Any) -> Result:
        try:
            response = requests.request(
                method, self.base_url + path, timeout=(5, 60), **kwargs
            )
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
            return Result(data=body, error=f"HTTP {response.status_code}: {error_message(body.get('detail'))}")
        if not isinstance(data, dict):
            return Result(error="Phản hồi API không đúng cấu trúc object dự kiến.")
        return Result(data=data)

    def ask(self, question: str, course_code: str | None) -> Result:
        return self.request("/api/v1/ask", json={"question": question, "course_code": course_code, "top_k": 5})

    def learning_path(self, targets: list[str], completed: list[str], credits: int) -> Result:
        return self.request("/api/v1/learning-path", json={
            "target_courses": targets, "passed_courses": completed,
            "max_credits_per_semester": credits,
        })

    def analyze(self, filename: str, content: bytes) -> Result:
        return self.request("/api/v1/analyze-syllabus", files={"file": (filename, content, "application/pdf")})
