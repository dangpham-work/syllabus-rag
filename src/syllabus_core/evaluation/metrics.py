"""
metrics.py
Các chỉ số đánh giá chuẩn hoá cho M1, M2, M3, M4.

Dùng:
    from syllabus_core.evaluation.metrics import evaluate_bloom, recall_at_k, save_metrics
"""

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# M2 — Bloom classification metrics
# ---------------------------------------------------------------------------

BLOOM_LABEL_NAMES = {
    0: "Ngoài miền", 1: "Nhớ", 2: "Hiểu",
    3: "Áp dụng", 4: "Phân tích", 5: "Đánh giá", 6: "Sáng tạo",
}


def _confusion(y_true, y_pred, labels):
    idx = {l: i for i, l in enumerate(labels)}
    n = len(labels)
    cm = np.zeros((n, n), dtype=int)
    for t, p in zip(y_true, y_pred):
        if t in idx and p in idx:
            cm[idx[t]][idx[p]] += 1
    return cm


def per_class_f1(y_true, y_pred, labels=None):
    """F1 từng lớp → dict {label: f1}."""
    if labels is None:
        labels = sorted(set(y_true) | set(y_pred))
    cm = _confusion(y_true, y_pred, labels)
    result = {}
    for i, lbl in enumerate(labels):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec  = tp / (tp + fn) if (tp + fn) else 0.0
        result[lbl] = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return result


def macro_f1(y_true, y_pred, labels=None):
    """Macro-F1 trên tất cả lớp."""
    pf1 = per_class_f1(y_true, y_pred, labels)
    return float(np.mean(list(pf1.values()))) if pf1 else 0.0


def accuracy_pm1(y_true, y_pred):
    """Accuracy cho phép sai ±1 mức Bloom."""
    correct = sum(abs(t - p) <= 1 for t, p in zip(y_true, y_pred))
    return correct / len(y_true) if y_true else 0.0


def evaluate_bloom(y_true, y_pred, label_names=None):
    """
    Đánh giá đầy đủ mô hình Bloom.

    Returns
    -------
    dict với các key: macro_f1, per_class, accuracy, accuracy_pm1, grouped
    """
    labels = sorted(set(y_true) | set(y_pred))
    pf1 = per_class_f1(y_true, y_pred, labels)
    acc = sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true) if y_true else 0.0

    # Gộp 3 nhóm: thấp={1,2}, trung={3,4}, cao={5,6}
    def group(lvl):
        if lvl == 0: return "ngoai_mien"
        if lvl in {1, 2}: return "thap"
        if lvl in {3, 4}: return "trung"
        return "cao"

    g_true = [group(t) for t in y_true]
    g_pred = [group(p) for p in y_pred]
    g_labels = ["ngoai_mien", "thap", "trung", "cao"]
    grouped_f1 = per_class_f1(g_true, g_pred, g_labels)

    return {
        "macro_f1": macro_f1(y_true, y_pred, labels),
        "accuracy": acc,
        "accuracy_pm1": accuracy_pm1(y_true, y_pred),
        "per_class_f1": {(label_names or BLOOM_LABEL_NAMES).get(l, str(l)): v for l, v in pf1.items()},
        "grouped_f1": grouped_f1,
    }


def cohen_kappa(labels_a, labels_b):
    """Cohen's Kappa cho inter-annotator agreement."""
    assert len(labels_a) == len(labels_b), "Danh sách nhãn phải cùng độ dài"
    cats = sorted(set(labels_a) | set(labels_b))
    n = len(labels_a)
    if n == 0:
        return 0.0
    po = sum(a == b for a, b in zip(labels_a, labels_b)) / n
    count_a = defaultdict(int)
    count_b = defaultdict(int)
    for a, b in zip(labels_a, labels_b):
        count_a[a] += 1
        count_b[b] += 1
    pe = sum(count_a[c] / n * count_b[c] / n for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


# ---------------------------------------------------------------------------
# M3 — Retrieval metrics
# ---------------------------------------------------------------------------

def recall_at_k(relevant: set, retrieved: list, k: int) -> float:
    """Recall@k: tỷ lệ tài liệu liên quan được truy xuất trong top-k."""
    if not relevant:
        return 0.0
    retrieved_k = set(retrieved[:k])
    return len(relevant & retrieved_k) / len(relevant)


def mrr_at_k(relevant: set, retrieved: list, k: int) -> float:
    """MRR@k: Mean Reciprocal Rank."""
    for i, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(relevant: set, retrieved: list, k: int) -> float:
    """nDCG@k: Normalized Discounted Cumulative Gain (binary relevance)."""
    dcg = sum(1.0 / math.log2(i + 2) for i, item in enumerate(retrieved[:k]) if item in relevant)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_retrieval(qa_data: list[dict], retriever_fn, k_values=(1, 3, 5, 10)) -> dict:
    """
    Đánh giá retrieval trên tập QA.

    Parameters
    ----------
    qa_data : list of dict với keys: question, relevant_chunk_ids (list)
    retriever_fn : callable(question) → list of chunk_ids (sorted by score)
    k_values : các mức k cần tính

    Returns
    -------
    dict: {f"recall@{k}": float, f"mrr@{k}": float, f"ndcg@{k}": float}
    """
    results = defaultdict(list)
    for item in qa_data:
        relevant = set(item["relevant_chunk_ids"])
        retrieved = retriever_fn(item["question"])
        for k in k_values:
            results[f"recall@{k}"].append(recall_at_k(relevant, retrieved, k))
            results[f"mrr@{k}"].append(mrr_at_k(relevant, retrieved, k))
            results[f"ndcg@{k}"].append(ndcg_at_k(relevant, retrieved, k))

    return {key: float(np.mean(vals)) for key, vals in results.items()}


# ---------------------------------------------------------------------------
# Lưu metrics
# ---------------------------------------------------------------------------

def save_metrics(metrics_dict: dict[str, Any], path: str | Path, key: str) -> None:
    """
    Merge metrics vào file JSON (thường là results/metrics.json).

    Parameters
    ----------
    metrics_dict : dict kết quả cần lưu
    path : đường dẫn đến file JSON
    key : tên module, ví dụ "m2_bloom"
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists() and path.stat().st_size > 0:
        try:
            with path.open(encoding="utf-8") as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            pass
    existing[key] = metrics_dict
    with path.open("w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"✓ Đã ghi metrics['{key}'] → {path}")
