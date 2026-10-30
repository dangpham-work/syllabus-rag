"""
train_reranker.py
Huấn luyện LightGBM LambdaMART reranker cho M3.

Dùng:
    python -m syllabus_core.models.train_reranker \\
        --qa-train data/processed/qa_train.jsonl \\
        --out models/reranker.txt
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def build_reranker_features(
    query: str,
    chunk,
    bm25_score: float,
    cosine_score: float,
    bm25_rank: int,
    dense_rank: int,
    chunk_section: str,
    detected_course: Optional[str] = None,
) -> dict[str, float]:
    """
    Xây 8 đặc trưng cho một cặp (câu hỏi, chunk).

    Features:
        bm25_score, cosine_score, bm25_rank, dense_rank,
        course_match, section_match, chunk_length, keyword_overlap_ratio
    """
    # Keyword overlap
    def tokens(text: str) -> set[str]:
        return set(re.findall(r"[\w\u1E00-\u1EFF]+", text.lower()))

    q_tokens = tokens(query)
    c_tokens = tokens(chunk.text)
    overlap = len(q_tokens & c_tokens) / len(q_tokens | c_tokens) if (q_tokens | c_tokens) else 0.0

    # Section match: câu hỏi về đánh giá → section assessment
    SECTION_KEYWORDS = {
        "assessment": ["thi", "đánh giá", "kiểm tra", "điểm", "trọng số", "hình thức"],
        "course_learning_outcomes": ["clo", "chuẩn đầu ra", "mục tiêu", "năng lực"],
        "prerequisites": ["tiên quyết", "học trước", "điều kiện"],
        "general_info": ["tín chỉ", "mã môn", "số tín"],
    }
    section_match = 0.0
    q_lower = query.lower()
    for section, kws in SECTION_KEYWORDS.items():
        if chunk_section == section and any(kw in q_lower for kw in kws):
            section_match = 1.0
            break

    return {
        "bm25_score": float(bm25_score),
        "cosine_score": float(cosine_score),
        "bm25_rank_inv": 1.0 / (bm25_rank + 1),
        "dense_rank_inv": 1.0 / (dense_rank + 1),
        "course_match": float(detected_course is not None and chunk.course_code == detected_course),
        "section_match": section_match,
        "chunk_length_norm": min(len(chunk.text) / 500.0, 1.0),
        "keyword_overlap": overlap,
    }


# ---------------------------------------------------------------------------
# Synthetic training data
# ---------------------------------------------------------------------------

def _make_synthetic_qa_data(n_queries: int = 120) -> list[dict]:
    """Tạo dữ liệu QA tổng hợp để test pipeline."""
    from syllabus_core.retrieval.index import _make_synthetic_corpus
    chunks = _make_synthetic_corpus()
    chunk_ids = [c.chunk_id for c in chunks]

    questions = [
        "Môn Cơ sở lập trình có những chuẩn đầu ra nào?",
        "Hình thức đánh giá của môn Công nghệ phần mềm là gì?",
        "Môn nào tiên quyết của Kiểm thử phần mềm?",
        "CLO2 của môn 841047 yêu cầu sinh viên làm gì?",
        "Số tín chỉ của môn Cơ sở lập trình là bao nhiêu?",
    ]

    data = []
    rng = np.random.default_rng(42)
    for i in range(n_queries):
        q = questions[i % len(questions)]
        # Gold chunk: chọn ngẫu nhiên 1-3 chunks liên quan
        gold_ids = list(rng.choice(chunk_ids, size=min(2, len(chunk_ids)), replace=False))
        # Candidates: gold + negative samples
        neg_ids = [cid for cid in chunk_ids if cid not in gold_ids]
        neg_sample = list(rng.choice(neg_ids, size=min(5, len(neg_ids)), replace=False))
        candidates = [
            {"chunk_id": cid, "relevance": 1} for cid in gold_ids
        ] + [
            {"chunk_id": cid, "relevance": 0} for cid in neg_sample
        ]
        rng.shuffle(candidates)
        data.append({
            "qid": f"Q{i:04d}",
            "question": q,
            "relevant_chunk_ids": gold_ids,
            "candidates": candidates,
        })
    return data


# ---------------------------------------------------------------------------
# Load QA data
# ---------------------------------------------------------------------------

def load_qa_data(path: str | Path) -> list[dict]:
    """Load QA jsonl. Fallback synthetic nếu không có file."""
    path = Path(path)
    if not path.exists():
        logger.warning("Không tìm thấy %s, dùng synthetic QA data.", path)
        return _make_synthetic_qa_data(120)
    data = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    return data


# ---------------------------------------------------------------------------
# Train LambdaMART
# ---------------------------------------------------------------------------

def train_lambdamart(
    train_data: list[dict],
    chunks_map: dict,
    params: Optional[dict] = None,
) -> Any:
    """
    Huấn luyện LightGBM LambdaMART reranker.

    Parameters
    ----------
    train_data : list of QA items với candidates
    chunks_map : {chunk_id: Chunk}
    params : hyperparams (từ config/params.yaml)

    Returns
    -------
    lightgbm.Booster
    """
    try:
        import lightgbm as lgb
    except ImportError:
        logger.error("lightgbm không khả dụng. Cài đặt: pip install lightgbm")
        raise

    p = params or {}
    lgb_params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "eval_at": [5, 10],
        "learning_rate": p.get("learning_rate", 0.05),
        "n_estimators": p.get("n_estimators", 300),
        "num_leaves": 31,
        "min_child_samples": 5,
        "verbosity": -1,
        "random_state": 42,
    }

    X_list, y_list, groups = [], [], []
    for item in train_data:
        q = item["question"]
        cands = item.get("candidates", [])
        feat_rows, rel_rows = [], []
        for cand in cands:
            cid = cand["chunk_id"]
            if cid not in chunks_map:
                continue
            chunk = chunks_map[cid]
            feat = build_reranker_features(
                query=q, chunk=chunk,
                bm25_score=cand.get("bm25_score", 0.0),
                cosine_score=cand.get("cosine_score", 0.0),
                bm25_rank=cand.get("bm25_rank", 99),
                dense_rank=cand.get("dense_rank", 99),
                chunk_section=chunk.section,
                detected_course=None,
            )
            feat_rows.append(list(feat.values()))
            rel_rows.append(int(cand.get("relevance", 0)))
        if feat_rows:
            X_list.extend(feat_rows)
            y_list.extend(rel_rows)
            groups.append(len(feat_rows))

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    group = np.array(groups, dtype=np.int32)

    feature_names = list(build_reranker_features(
        "q", type("C", (), {"text": "", "course_code": "", "section": ""})(),
        0, 0, 99, 99, "", None,
    ).keys())

    train_set = lgb.Dataset(X, label=y, group=group, feature_name=feature_names)
    model = lgb.train(
        lgb_params,
        train_set,
        num_boost_round=lgb_params.pop("n_estimators", 300),
        valid_sets=[train_set],
        callbacks=[lgb.log_evaluation(50)],
    )
    logger.info("Đã train LambdaMART: %d trees", model.num_trees())
    return model


# ---------------------------------------------------------------------------
# Train LogReg reranker (baseline)
# ---------------------------------------------------------------------------

def train_logreg_ranker(train_data: list[dict], chunks_map: dict) -> Any:
    """Baseline: LogisticRegression reranker trên cùng features."""
    from sklearn.linear_model import LogisticRegression

    X_list, y_list = [], []
    for item in train_data:
        for cand in item.get("candidates", []):
            cid = cand["chunk_id"]
            if cid not in chunks_map:
                continue
            chunk = chunks_map[cid]
            feat = build_reranker_features(
                query=item["question"], chunk=chunk,
                bm25_score=cand.get("bm25_score", 0.0),
                cosine_score=cand.get("cosine_score", 0.0),
                bm25_rank=cand.get("bm25_rank", 99),
                dense_rank=cand.get("dense_rank", 99),
                chunk_section=chunk.section,
            )
            X_list.append(list(feat.values()))
            y_list.append(int(cand.get("relevance", 0)))

    clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=500, random_state=42)
    clf.fit(np.array(X_list), y_list)
    return clf


# ---------------------------------------------------------------------------
# Evaluate reranker
# ---------------------------------------------------------------------------

def evaluate_reranker(
    model: Any,
    test_data: list[dict],
    chunks_map: dict,
    k: int = 5,
) -> dict:
    """
    Đánh giá reranker trên tập test.

    Returns
    -------
    dict: recall@k, mrr@10, ndcg@10
    """
    from syllabus_core.evaluation.metrics import mrr_at_k, ndcg_at_k, recall_at_k

    recalls, mrrs, ndcgs = [], [], []
    for item in test_data:
        relevant = set(item.get("relevant_chunk_ids", []))
        cands = item.get("candidates", [])
        if not cands:
            continue

        # Build features
        feat_rows, cand_ids = [], []
        for cand in cands:
            cid = cand["chunk_id"]
            if cid not in chunks_map:
                continue
            chunk = chunks_map[cid]
            feat = build_reranker_features(
                query=item["question"], chunk=chunk,
                bm25_score=cand.get("bm25_score", 0.0),
                cosine_score=cand.get("cosine_score", 0.0),
                bm25_rank=cand.get("bm25_rank", 99),
                dense_rank=cand.get("dense_rank", 99),
                chunk_section=chunk.section,
            )
            feat_rows.append(list(feat.values()))
            cand_ids.append(cid)

        if not feat_rows:
            continue

        scores = model.predict(np.array(feat_rows))
        ranked = [cid for cid, _ in sorted(zip(cand_ids, scores), key=lambda x: x[1], reverse=True)]

        recalls.append(recall_at_k(relevant, ranked, k))
        mrrs.append(mrr_at_k(relevant, ranked, 10))
        ndcgs.append(ndcg_at_k(relevant, ranked, 10))

    return {
        f"recall@{k}": float(np.mean(recalls)) if recalls else 0.0,
        "mrr@10": float(np.mean(mrrs)) if mrrs else 0.0,
        "ndcg@10": float(np.mean(ndcgs)) if ndcgs else 0.0,
    }


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

def save_reranker(model: Any, path: str | Path) -> None:
    """Lưu model: LightGBM → .txt, sklearn → .pkl."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        model.save_model(str(path))
        logger.info("Đã lưu LightGBM model → %s", path)
    except AttributeError:
        import pickle
        pkl_path = path.with_suffix(".pkl")
        with pkl_path.open("wb") as f:
            pickle.dump(model, f)
        logger.info("Đã lưu sklearn model → %s", pkl_path)


def load_reranker(path: str | Path) -> Any:
    """Load reranker từ file."""
    path = Path(path)
    if path.with_suffix(".txt").exists():
        import lightgbm as lgb
        return lgb.Booster(model_file=str(path.with_suffix(".txt")))
    pkl = path.with_suffix(".pkl")
    if pkl.exists():
        import pickle
        with pkl.open("rb") as f:
            return pickle.load(f)
    raise FileNotFoundError(f"Không tìm thấy reranker tại {path}")
