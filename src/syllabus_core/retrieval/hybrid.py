"""
hybrid.py
Kết hợp BM25 + Dense bằng Reciprocal Rank Fusion (RRF) — M3.

Dùng:
    from syllabus_core.retrieval.hybrid import HybridRetriever
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

from syllabus_core.retrieval.index import BM25Index, Chunk, DenseIndex

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RRF
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[Chunk, float]]],
    k: int = 60,
) -> list[tuple[Chunk, float]]:
    """
    Reciprocal Rank Fusion (Cormack 2009).

    Parameters
    ----------
    ranked_lists : danh sách các ranked list, mỗi phần tử là (Chunk, score)
    k : hằng số RRF (mặc định 60)

    Returns
    -------
    list[(Chunk, rrf_score)] đã sort giảm dần
    """
    rrf_scores: dict[str, float] = defaultdict(float)
    chunk_map: dict[str, Chunk] = {}

    for ranked in ranked_lists:
        for rank, (chunk, _) in enumerate(ranked, start=1):
            rrf_scores[chunk.chunk_id] += 1.0 / (k + rank)
            chunk_map[chunk.chunk_id] = chunk

    merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [(chunk_map[cid], score) for cid, score in merged]


# ---------------------------------------------------------------------------
# Course mention detection
# ---------------------------------------------------------------------------

def detect_course_mention(
    query: str,
    course_index: dict[str, str],  # {course_code: course_name}
) -> Optional[tuple[str, str]]:
    """
    Nhận diện tên môn học được nhắc đến trong câu hỏi.

    Parameters
    ----------
    query : câu hỏi người dùng
    course_index : {course_code: course_name}

    Returns
    -------
    (course_code, course_name) hoặc None
    """
    q_lower = query.lower()
    # Tìm theo mã môn (6 chữ số)
    m = re.search(r"\b(84\d{4})\b", query)
    if m and m.group(1) in course_index:
        code = m.group(1)
        return code, course_index[code]

    # Tìm theo tên môn (fuzzy substring)
    best_code, best_name, best_len = None, None, 0
    for code, name in course_index.items():
        name_lower = name.lower()
        # Thử các từ viết tắt phổ biến
        abbr = "".join(w[0] for w in name.split() if w)
        if (name_lower in q_lower or abbr.lower() in q_lower) and len(name) > best_len:
            best_code, best_name, best_len = code, name, len(name)

    return (best_code, best_name) if best_code else None


# ---------------------------------------------------------------------------
# HybridRetriever
# ---------------------------------------------------------------------------

class HybridRetriever:
    """
    Retriever kết hợp BM25 + Dense với RRF và reranker tuỳ chọn.

    Parameters
    ----------
    bm25_index : BM25Index đã được build
    dense_index : DenseIndex đã encode corpus
    params : dict cấu hình (từ params.yaml)
    """

    def __init__(
        self,
        bm25_index: BM25Index,
        dense_index: DenseIndex,
        params: Optional[dict] = None,
    ):
        self.bm25 = bm25_index
        self.dense = dense_index
        self.params = params or {}
        self.bm25_top_k = self.params.get("bm25_top_k", 30)
        self.dense_top_k = self.params.get("dense_top_k", 30)
        self.rrf_k = self.params.get("rrf_k", 60)
        self.rerank_in = self.params.get("rerank_in", 20)
        self.context_k = self.params.get("context_k", 5)

        # Index tên môn để detect mention
        self._course_index: dict[str, str] = {}
        for chunk in bm25_index.chunks:
            self._course_index[chunk.course_code] = chunk.course_name

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_course: Optional[str] = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Truy xuất lai: BM25 top-K + Dense top-K → RRF → top rerank_in.

        Parameters
        ----------
        query : câu hỏi người dùng
        top_k : số kết quả trả về (mặc định = rerank_in)
        filter_course : nếu có, chỉ giữ chunks của môn này

        Returns
        -------
        list[(Chunk, rrf_score)]
        """
        top_k = top_k or self.rerank_in

        # Tự động nhận diện môn nếu không chỉ định
        if filter_course is None:
            mention = detect_course_mention(query, self._course_index)
            if mention:
                filter_course = mention[0]
                logger.debug("Nhận diện môn: %s (%s)", filter_course, mention[1])

        bm25_results = self.bm25.search(query, top_k=self.bm25_top_k)
        dense_results = self.dense.search(query, top_k=self.dense_top_k)

        # Filter theo môn nếu cần
        if filter_course:
            bm25_results = [(c, s) for c, s in bm25_results if c.course_code == filter_course]
            dense_results = [(c, s) for c, s in dense_results if c.course_code == filter_course]

        fused = reciprocal_rank_fusion([bm25_results, dense_results], k=self.rrf_k)
        return fused[:top_k]

    def retrieve_with_reranker(
        self,
        query: str,
        reranker_model,
        top_k: Optional[int] = None,
        filter_course: Optional[str] = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Truy xuất + rerank: RRF top-20 → LightGBM reranker → top context_k.

        Parameters
        ----------
        reranker_model : model đã load (từ train_reranker.py)
        top_k : số kết quả cuối (mặc định = context_k)
        """
        top_k = top_k or self.context_k
        candidates = self.retrieve(query, top_k=self.rerank_in, filter_course=filter_course)

        if not candidates or reranker_model is None:
            return candidates[:top_k]

        # Build reranker features
        from syllabus_core.models.train_reranker import build_reranker_features
        bm25_results = self.bm25.search(query, top_k=self.bm25_top_k)
        dense_results = self.dense.search(query, top_k=self.dense_top_k)
        bm25_rank_map = {c.chunk_id: r + 1 for r, (c, _) in enumerate(bm25_results)}
        dense_rank_map = {c.chunk_id: r + 1 for r, (c, _) in enumerate(dense_results)}
        bm25_score_map = {c.chunk_id: s for c, s in bm25_results}
        dense_score_map = {c.chunk_id: s for c, s in dense_results}

        mention = detect_course_mention(query, self._course_index)
        detected_course = mention[0] if mention else None

        import numpy as np
        X_feat = []
        for chunk, rrf_score in candidates:
            feat = build_reranker_features(
                query=query,
                chunk=chunk,
                bm25_score=bm25_score_map.get(chunk.chunk_id, 0.0),
                cosine_score=dense_score_map.get(chunk.chunk_id, 0.0),
                bm25_rank=bm25_rank_map.get(chunk.chunk_id, 999),
                dense_rank=dense_rank_map.get(chunk.chunk_id, 999),
                chunk_section=chunk.section,
                detected_course=detected_course,
            )
            X_feat.append(list(feat.values()))

        try:
            scores = reranker_model.predict(np.array(X_feat))
            ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
            return [(c, float(s)) for (c, _), s in ranked[:top_k]]
        except Exception as e:
            logger.warning("Reranker lỗi: %s. Dùng RRF order.", e)
            return candidates[:top_k]
