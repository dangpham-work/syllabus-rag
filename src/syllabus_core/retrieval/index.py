"""
index.py
Xây dựng và tìm kiếm index BM25 + Dense (M3).

Dùng:
    from syllabus_core.retrieval.index import build_corpus, BM25Index, DenseIndex
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------

SECTION_NAMES_VI = {
    "general_info": "Thông tin chung",
    "course_description": "Mô tả học phần",
    "course_objectives": "Mục tiêu học phần",
    "course_learning_outcomes": "Chuẩn đầu ra",
    "course_content": "Nội dung chi tiết",
    "teaching_methods": "Phương pháp dạy",
    "assessment": "Đánh giá học phần",
    "learning_resources": "Giáo trình",
    "teaching_schedule": "Kế hoạch giảng dạy",
    "course_policies": "Yêu cầu học phần",
}


@dataclass
class Chunk:
    """Đơn vị văn bản có nghĩa được trích từ JSON đề cương."""
    chunk_id: str          # "<course_code>__<section>__<idx>"
    course_code: str
    course_name: str
    section: str           # tên mục (general_info, clos, ...)
    text: str              # nội dung chunk
    context_prefix: str    # tiền tố ngữ cảnh cho embedding
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Văn bản đầy đủ = tiền tố + nội dung."""
        return f"{self.context_prefix}\n{self.text}"


def _make_prefix(course_code: str, course_name: str, section: str) -> str:
    section_vi = SECTION_NAMES_VI.get(section, section)
    return f"[{course_code} {course_name} | {section_vi}]"


# ---------------------------------------------------------------------------
# Build chunks
# ---------------------------------------------------------------------------

def build_chunks_from_json(syllabus: dict) -> list[Chunk]:
    """
    Tạo chunks từ dict đề cương JSON.

    Mỗi CLO → 1 chunk; mỗi section → 1 chunk; schedule → nhiều chunks nhỏ.
    """
    chunks: list[Chunk] = []
    code = syllabus.get("course_code", "unknown")
    name = syllabus.get("course_name", "")

    def add(section: str, text: str, idx: int = 0, meta: dict | None = None):
        if not text or not text.strip():
            return
        chunk_id = f"{code}__{section}__{idx:03d}"
        prefix = _make_prefix(code, name, section)
        chunks.append(Chunk(
            chunk_id=chunk_id,
            course_code=code,
            course_name=name,
            section=section,
            text=text.strip(),
            context_prefix=prefix,
            metadata=meta or {},
        ))

    # CLO chunks
    for i, clo in enumerate(syllabus.get("clos", [])):
        text = clo.get("text", "")
        bloom = clo.get("bloom_level", "")
        bloom_name = clo.get("bloom_name", "")
        clo_id = clo.get("clo_id", f"CLO{i+1}")
        add(
            "clos", f"{clo_id}: {text}",
            idx=i,
            meta={"clo_id": clo_id, "bloom_level": bloom, "bloom_name": bloom_name},
        )

    # Section chunks
    for section, text in (syllabus.get("sections") or {}).items():
        if not text:
            continue
        # Nếu text dài, chia theo dòng tối đa 300 ký tự
        lines = text.split("\n")
        buffer, buf_idx = [], 0
        for line in lines:
            buffer.append(line)
            if sum(len(l) for l in buffer) >= 300:
                add(section, " ".join(buffer), idx=buf_idx)
                buf_idx += 1
                buffer = []
        if buffer:
            add(section, " ".join(buffer), idx=buf_idx)

    # Prerequisites
    prereqs = syllabus.get("prerequisites", [])
    if prereqs:
        prereq_text = "Tiên quyết: " + ", ".join(str(p) for p in prereqs)
        add("prerequisites", prereq_text)

    logger.debug("Đề cương %s → %d chunks", code, len(chunks))
    return chunks


def build_corpus(syllabi_dir: str | Path) -> list[Chunk]:
    """Load tất cả JSON đề cương và build toàn bộ chunks."""
    syllabi_dir = Path(syllabi_dir)
    all_chunks: list[Chunk] = []

    json_files = sorted(syllabi_dir.glob("*.json"))
    if not json_files:
        logger.warning("Không có JSON trong %s — dùng synthetic corpus.", syllabi_dir)
        return _make_synthetic_corpus()

    for jf in json_files:
        try:
            with jf.open(encoding="utf-8") as f:
                syl = json.load(f)
            all_chunks.extend(build_chunks_from_json(syl))
        except Exception as e:
            logger.error("Lỗi đọc %s: %s", jf.name, e)

    logger.info("Corpus: %d chunks từ %d đề cương", len(all_chunks), len(json_files))
    return all_chunks


def _make_synthetic_corpus() -> list[Chunk]:
    """Tạo corpus tổng hợp cho testing khi không có dữ liệu thực."""
    syllabi = [
        {
            "course_code": "841020", "course_name": "Cơ sở lập trình", "credits": 3,
            "prerequisites": [],
            "clos": [
                {"clo_id": "CLO1", "text": "Trình bày được các khái niệm cơ bản về thuật toán.", "bloom_level": 1},
                {"clo_id": "CLO2", "text": "Áp dụng cấu trúc điều khiển để giải bài toán.", "bloom_level": 3},
            ],
            "sections": {
                "general_info": "1. Thông tin chung: Mã: 841020, Tín chỉ: 3, Tiên quyết: Không.",
                "course_description": "2. Mô tả: Cung cấp tư duy thuật toán và kỹ thuật lập trình C/C++.",
                "assessment": "7. Đánh giá: Quá trình 20%, Thực hành 30%, Cuối kỳ 50%.",
            },
        },
        {
            "course_code": "841047", "course_name": "Công nghệ phần mềm", "credits": 4,
            "prerequisites": ["841020"],
            "clos": [
                {"clo_id": "CLO1", "text": "Phân tích yêu cầu phần mềm từ bài toán thực tế.", "bloom_level": 4},
                {"clo_id": "CLO2", "text": "Thiết kế kiến trúc phần mềm theo mô hình MVC.", "bloom_level": 6},
                {"clo_id": "CLO3", "text": "Đánh giá chất lượng phần mềm theo tiêu chuẩn ISO.", "bloom_level": 5},
            ],
            "sections": {
                "general_info": "1. Thông tin chung: Mã: 841047, Tín chỉ: 4, Tiên quyết: 841020.",
                "course_description": "2. Mô tả: Kiến thức nâng cao về quy trình phát triển phần mềm.",
                "assessment": "7. Đánh giá: Đồ án 40%, Cuối kỳ 50%, Chuyên cần 10%.",
            },
        },
        {
            "course_code": "841408", "course_name": "Kiểm thử phần mềm", "credits": 3,
            "prerequisites": ["841047"],
            "clos": [
                {"clo_id": "CLO1", "text": "Mô tả quy trình kiểm thử phần mềm.", "bloom_level": 1},
                {"clo_id": "CLO2", "text": "Thiết kế ca kiểm thử hộp đen và hộp trắng.", "bloom_level": 6},
            ],
            "sections": {
                "general_info": "1. Thông tin chung: Mã: 841408, Tín chỉ: 3, Tiên quyết: 841047.",
                "assessment": "7. Đánh giá: Kiểm tra giữa kỳ 30%, Cuối kỳ 70%.",
            },
        },
    ]
    chunks = []
    for s in syllabi:
        chunks.extend(build_chunks_from_json(s))
    logger.info("Synthetic corpus: %d chunks", len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Save / load chunks
# ---------------------------------------------------------------------------

def save_chunks(chunks: list[Chunk], path: str | Path) -> None:
    """Lưu chunks ra JSONL."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    logger.info("Đã lưu %d chunks → %s", len(chunks), path)


def load_chunks(path: str | Path) -> list[Chunk]:
    """Load chunks từ JSONL."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    chunks = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            chunks.append(Chunk(**d))
    return chunks


# ---------------------------------------------------------------------------
# BM25 Index
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Tokenize đơn giản: lowercase, tách khoảng trắng."""
    return re.findall(r"[\w\u00C0-\u024F\u1E00-\u1EFF]+", text.lower())


class BM25Index:
    """BM25 retrieval index (Robertson 2009)."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self._build()

    def _build(self):
        """Xây dựng index."""
        try:
            from rank_bm25 import BM25Okapi
            corpus = [_tokenize(c.full_text) for c in self.chunks]
            self._bm25 = BM25Okapi(corpus, k1=self.k1, b=self.b)
            self._use_lib = True
        except ImportError:
            logger.warning("rank_bm25 không khả dụng, dùng BM25 tự implement.")
            self._use_lib = False
            self._build_custom()

    def _build_custom(self):
        """BM25 tự implement khi không có thư viện."""
        self._corpus_tokens = [_tokenize(c.full_text) for c in self.chunks]
        N = len(self._corpus_tokens)
        self._avgdl = sum(len(doc) for doc in self._corpus_tokens) / N if N else 1

        # DF
        df = Counter()
        for doc in self._corpus_tokens:
            for term in set(doc):
                df[term] += 1
        self._idf = {
            term: math.log((N - n + 0.5) / (n + 0.5) + 1)
            for term, n in df.items()
        }

    def _score_custom(self, query_tokens: list[str]) -> np.ndarray:
        scores = np.zeros(len(self.chunks))
        for term in query_tokens:
            idf = self._idf.get(term, 0)
            for i, doc in enumerate(self._corpus_tokens):
                tf = doc.count(term)
                dl = len(doc)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                scores[i] += idf * (tf * (self.k1 + 1)) / denom if denom else 0
        return scores

    def search(self, query: str, top_k: int = 30) -> list[tuple[Chunk, float]]:
        """Tìm kiếm BM25, trả về [(Chunk, score)] đã sort."""
        query_tokens = _tokenize(query)
        if self._use_lib:
            scores = self._bm25.get_scores(query_tokens)
        else:
            scores = self._score_custom(query_tokens)

        top_idx = np.argsort(scores)[::-1][:top_k]
        return [(self.chunks[i], float(scores[i])) for i in top_idx if scores[i] > 0]


# ---------------------------------------------------------------------------
# Dense Index
# ---------------------------------------------------------------------------

class DenseIndex:
    """Dense retrieval bằng sentence-transformers (hoặc TF-IDF SVD fallback)."""

    def __init__(
        self,
        chunks: list[Chunk],
        model_name: str = "intfloat/multilingual-e5-small",
        vectors_path: str | Path | None = None,
    ):
        self.chunks = chunks
        self.model_name = model_name
        self.vectors_path = Path(vectors_path) if vectors_path else None
        self._vectors: Optional[np.ndarray] = None
        self._encoder = None
        self._is_tfidf_fallback = False

        # Load vectors nếu đã có
        if self.vectors_path and self.vectors_path.exists():
            self._vectors = np.load(str(self.vectors_path))
            logger.info("Đã load vectors từ %s, shape=%s", self.vectors_path, self._vectors.shape)

    def _get_encoder(self):
        if self._encoder is not None:
            return self._encoder
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.model_name)
            self._is_tfidf_fallback = False
            logger.info("Dùng SentenceTransformer: %s", self.model_name)
        except (ImportError, Exception):
            from sklearn.decomposition import TruncatedSVD
            from sklearn.feature_extraction.text import TfidfVectorizer
            logger.warning("Fallback TF-IDF SVD encoder.")
            texts = [c.full_text for c in self.chunks]
            vect = TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True)
            X = vect.fit_transform(texts)
            svd = TruncatedSVD(n_components=min(128, X.shape[1] - 1), random_state=42)
            svd.fit(X)
            self._encoder = (vect, svd)
            self._is_tfidf_fallback = True
        return self._encoder

    def _encode_texts(self, texts: list[str]) -> np.ndarray:
        enc = self._get_encoder()
        if self._is_tfidf_fallback:
            vect, svd = enc
            X = vect.transform(texts)
            return svd.transform(X).astype(np.float32)
        else:
            prefix = "query: "
            return enc.encode(
                [prefix + t for t in texts],
                batch_size=32, show_progress_bar=False, normalize_embeddings=True,
            )

    def encode_corpus(self, save_path: str | Path | None = None) -> np.ndarray:
        """Encode toàn bộ corpus và lưu vectors.npy nếu có path."""
        texts = [c.full_text for c in self.chunks]
        enc = self._get_encoder()
        if not self._is_tfidf_fallback:
            prefix = "passage: "
            self._vectors = enc.encode(
                [prefix + t for t in texts],
                batch_size=32, show_progress_bar=True, normalize_embeddings=True,
            )
        else:
            self._vectors = self._encode_texts(texts)

        save_path = save_path or self.vectors_path
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            np.save(str(save_path), self._vectors)
            logger.info("Đã lưu vectors → %s, shape=%s", save_path, self._vectors.shape)
        return self._vectors

    def search(self, query: str, top_k: int = 30) -> list[tuple[Chunk, float]]:
        """Tìm kiếm dense, trả về [(Chunk, cosine_score)]."""
        if self._vectors is None:
            self.encode_corpus()

        q_vec = self._encode_texts([query])  # (1, dim)
        if q_vec.ndim == 1:
            q_vec = q_vec.reshape(1, -1)

        # Cosine similarity (vectors đã normalize)
        scores = (self._vectors @ q_vec.T).squeeze()
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [(self.chunks[i], float(scores[i])) for i in top_idx]
