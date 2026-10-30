"""
rag.py
Pipeline RAG: truy xuất → prompt → LLM → ánh xạ trích dẫn (M3).

Dùng:
    from syllabus_core.retrieval.rag import RAGPipeline
    pipeline = RAGPipeline(retriever)
    result = pipeline.answer("Môn CNPM có những CLO nào?")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from syllabus_core.retrieval.index import Chunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Bạn là trợ lý tra cứu đề cương môn học của Trường Đại học Sài Gòn (SGU).
Bạn CHỈ được dùng thông tin trong các đoạn ngữ cảnh được cung cấp.
Quy tắc bắt buộc:
1. Ghi số nguồn [1], [2]... sau mỗi ý lấy từ ngữ cảnh.
2. Nếu câu hỏi không có thông tin trong ngữ cảnh, trả lời đúng một câu: "Đề cương không đề cập thông tin này."
3. Không bịa, không suy luận ngoài ngữ cảnh.
4. Trả lời bằng tiếng Việt, ngắn gọn và rõ ràng."""


def format_chunk_for_prompt(chunk: Chunk, idx: int) -> str:
    """Format một chunk thành chuỗi prompt có đánh số."""
    return f"[{idx}] {chunk.context_prefix}\n{chunk.text}"


def build_prompt(question: str, chunks: list[Chunk]) -> str:
    """
    Xây dựng prompt RAG với 3 yêu cầu bắt buộc.

    Parameters
    ----------
    question : câu hỏi người dùng
    chunks : danh sách chunks đã được rerank (top-5)

    Returns
    -------
    str : prompt đầy đủ gửi đến LLM
    """
    context_parts = [format_chunk_for_prompt(c, i + 1) for i, c in enumerate(chunks)]
    context = "\n\n".join(context_parts)

    return f"""{SYSTEM_PROMPT}

---
NGỮ CẢNH ({len(chunks)} đoạn):

{context}

---
CÂU HỎI: {question}

TRẢ LỜI:"""


# ---------------------------------------------------------------------------
# LLM caller
# ---------------------------------------------------------------------------

def call_gemini(prompt: str, temperature: float = 0.2, max_tokens: int = 512) -> str:
    """Gọi Gemini API."""
    try:
        import google.generativeai as genai  # type: ignore
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY chưa được đặt")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini lỗi: {e}") from e


def call_groq(prompt: str, temperature: float = 0.2, max_tokens: int = 512) -> str:
    """Gọi Groq API (fallback)."""
    try:
        from groq import Groq  # type: ignore
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY chưa được đặt")
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"Groq lỗi: {e}") from e


def call_llm_mock(prompt: str, chunks: list[Chunk]) -> str:
    """Mock LLM — trả câu trả lời đơn giản từ chunk đầu tiên (dùng khi test/demo)."""
    if not chunks:
        return "Đề cương không đề cập thông tin này."
    first = chunks[0]
    return (
        f"Theo đề cương môn {first.course_name} ({first.course_code}), "
        f"{first.text[:200]}... [1]"
    )


# ---------------------------------------------------------------------------
# Citation mapping
# ---------------------------------------------------------------------------

def map_citations(answer: str, chunks: list[Chunk]) -> list[dict]:
    """
    Ánh xạ [n] trong câu trả lời → {course_code, course_name, section, chunk_id}.

    Returns
    -------
    list of citation dicts
    """
    import re
    citations = []
    mentioned = set(re.findall(r"\[(\d+)\]", answer))
    for n_str in sorted(mentioned, key=int):
        n = int(n_str)
        if 1 <= n <= len(chunks):
            c = chunks[n - 1]
            citations.append({
                "ref": f"[{n}]",
                "chunk_id": c.chunk_id,
                "course_code": c.course_code,
                "course_name": c.course_name,
                "section": c.section,
                "text_snippet": c.text[:120] + ("..." if len(c.text) > 120 else ""),
            })
    return citations


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class SimpleCache:
    """Cache câu trả lời LLM theo key = hash(question + chunk_ids)."""

    def __init__(self, cache_path: str | Path | None = None):
        self._data: dict[str, str] = {}
        self.cache_path = Path(cache_path) if cache_path else None
        if self.cache_path and self.cache_path.exists():
            try:
                with self.cache_path.open(encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info("Cache đã load: %d entries từ %s", len(self._data), self.cache_path)
            except Exception:
                self._data = {}

    def _key(self, question: str, chunk_ids: list[str]) -> str:
        raw = question + "|" + ",".join(sorted(chunk_ids))
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, question: str, chunk_ids: list[str]) -> Optional[str]:
        return self._data.get(self._key(question, chunk_ids))

    def set(self, question: str, chunk_ids: list[str], answer: str) -> None:
        self._data[self._key(question, chunk_ids)] = answer
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# RAGPipeline
# ---------------------------------------------------------------------------

class RAGPipeline:
    """
    Pipeline RAG đầy đủ: retrieve → prompt → LLM → map citations.

    Parameters
    ----------
    retriever : HybridRetriever
    llm_provider : 'gemini' | 'groq' | 'mock'
    fallback_provider : 'groq' | 'mock'
    cache_path : đường dẫn file cache JSON (None = không cache)
    temperature : nhiệt độ LLM
    max_tokens : độ dài tối đa câu trả lời
    """

    def __init__(
        self,
        retriever,
        llm_provider: str = "gemini",
        fallback_provider: str = "groq",
        cache_path: Optional[str | Path] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        reranker_model=None,
    ):
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.fallback_provider = fallback_provider
        self.cache = SimpleCache(cache_path)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reranker = reranker_model

    def _call_llm(self, prompt: str, chunks: list[Chunk]) -> tuple[str, str]:
        """Gọi LLM với fallback. Returns (answer, provider_used)."""
        providers = [self.llm_provider, self.fallback_provider, "mock"]
        for provider in providers:
            try:
                if provider == "gemini":
                    return call_gemini(prompt, self.temperature, self.max_tokens), "gemini"
                elif provider == "groq":
                    return call_groq(prompt, self.temperature, self.max_tokens), "groq"
                else:
                    return call_llm_mock(prompt, chunks), "mock"
            except Exception as e:
                logger.warning("Provider %s lỗi: %s. Thử provider tiếp theo.", provider, e)
        return call_llm_mock(prompt, chunks), "mock"

    def answer(
        self,
        question: str,
        filter_course: Optional[str] = None,
    ) -> dict:
        """
        Trả lời câu hỏi với trích dẫn nguồn.

        Parameters
        ----------
        question : câu hỏi tiếng Việt
        filter_course : lọc theo mã môn (None = tìm trên toàn bộ corpus)

        Returns
        -------
        dict với keys: answer, citations, retrieved_chunks, provider_used, latency_ms
        """
        t0 = time.time()

        # Retrieve
        if self.reranker:
            candidates = self.retriever.retrieve_with_reranker(
                question, self.reranker, filter_course=filter_course,
            )
        else:
            candidates = self.retriever.retrieve(question, filter_course=filter_course)

        chunks = [c for c, _ in candidates]
        chunk_ids = [c.chunk_id for c in chunks]

        # Check cache
        cached = self.cache.get(question, chunk_ids)
        if cached:
            answer_text = cached
            provider_used = "cache"
        else:
            prompt = build_prompt(question, chunks)
            answer_text, provider_used = self._call_llm(prompt, chunks)
            self.cache.set(question, chunk_ids, answer_text)

        citations = map_citations(answer_text, chunks)
        latency_ms = int((time.time() - t0) * 1000)

        return {
            "answer": answer_text,
            "citations": citations,
            "retrieved_chunks": [
                {
                    "rank": i + 1,
                    "chunk_id": c.chunk_id,
                    "course_code": c.course_code,
                    "course_name": c.course_name,
                    "section": c.section,
                    "text": c.text[:200] + ("..." if len(c.text) > 200 else ""),
                    "score": float(s),
                }
                for i, (c, s) in enumerate(candidates)
            ],
            "provider_used": provider_used,
            "latency_ms": latency_ms,
        }
