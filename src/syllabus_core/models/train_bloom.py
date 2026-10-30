"""
train_bloom.py
Huấn luyện mô hình phân loại Bloom M2: B0 luật, B1 TF-IDF+LogReg, B2 Embedding+LogReg.

Dùng:
    python -m syllabus_core.models.train_bloom \\
        --clos data/processed/clos_labeled.csv \\
        --out models/bloom_model.pkl
"""

from __future__ import annotations

import json
import logging
import pickle
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hằng số Bloom
# ---------------------------------------------------------------------------

BLOOM_LABELS: dict[int, str] = {
    0: "Ngoài miền nhận thức",
    1: "Nhớ (Remember)",
    2: "Hiểu (Understand)",
    3: "Áp dụng (Apply)",
    4: "Phân tích (Analyze)",
    5: "Đánh giá (Evaluate)",
    6: "Sáng tạo (Create)",
}

# Từ điển động từ Bloom tiếng Việt
BLOOM_VERBS: dict[int, list[str]] = {
    0: [  # Ngoài miền nhận thức (thái độ, kỹ năng mềm)
        "thể hiện", "rèn luyện", "hình thành", "duy trì", "phát triển",
        "tuân thủ", "tôn trọng", "có ý thức", "chủ động", "tích cực",
        "hợp tác", "giao tiếp", "làm việc nhóm", "kỷ luật",
    ],
    1: [  # Nhớ (Remember)
        "liệt kê", "nhận biết", "nhớ lại", "xác định", "gọi tên",
        "trình bày", "mô tả", "nêu", "phát biểu", "định nghĩa",
        "nhận dạng", "tái hiện", "thuộc", "ghi nhớ", "kể",
    ],
    2: [  # Hiểu (Understand)
        "giải thích", "diễn giải", "phân biệt", "tóm tắt", "phân loại",
        "so sánh", "hiểu", "minh hoạ", "biểu diễn", "dịch",
        "suy luận", "ước tính", "dự đoán", "nhận xét", "mô tả sự khác biệt",
    ],
    3: [  # Áp dụng (Apply)
        "áp dụng", "thực hiện", "sử dụng", "cài đặt", "vận dụng",
        "giải quyết", "tính toán", "xây dựng", "lập trình", "triển khai",
        "thực hành", "viết", "lập", "thao tác", "thi hành",
    ],
    4: [  # Phân tích (Analyze)
        "phân tích", "so sánh", "phân biệt", "chia nhỏ", "kiểm tra",
        "cấu trúc hoá", "suy luận", "phân rã", "tổ chức", "đánh giá quan hệ",
        "điều tra", "tìm hiểu nguyên nhân", "lập luận", "chứng minh",
    ],
    5: [  # Đánh giá (Evaluate)
        "đánh giá", "phán xét", "lựa chọn", "biện hộ", "phê bình",
        "kiểm tra tính hợp lệ", "nhận xét", "phê phán", "kết luận",
        "đề xuất cải tiến", "đo lường", "kiểm định", "xác nhận",
    ],
    6: [  # Sáng tạo (Create)
        "thiết kế", "xây dựng", "sáng tạo", "tổng hợp", "lập kế hoạch",
        "đề xuất", "phát triển", "tạo ra", "viết", "lắp ráp",
        "kết hợp", "hình thành giải pháp", "đổi mới", "khởi tạo",
    ],
}

# Compile regex một lần
_VERB_PATTERNS: dict[int, re.Pattern] = {
    lvl: re.compile("|".join(re.escape(v) for v in verbs), re.IGNORECASE)
    for lvl, verbs in BLOOM_VERBS.items()
}


# ---------------------------------------------------------------------------
# B0 — Luật động từ
# ---------------------------------------------------------------------------

def predict_bloom_rule(text: str) -> int:
    """B0: Gán nhãn dựa trên động từ đầu câu (mức cao nhất tìm được)."""
    best_level = -1
    for lvl in sorted(BLOOM_VERBS.keys(), reverse=True):
        if _VERB_PATTERNS[lvl].search(text):
            if lvl > best_level:
                best_level = lvl
    return best_level if best_level >= 0 else 1  # default: Nhớ


def train_baseline_rule(texts: list[str], labels: list[int]) -> dict:
    """Dự đoán B0 và tính metrics."""
    from syllabus_core.evaluation.metrics import evaluate_bloom
    preds = [predict_bloom_rule(t) for t in texts]
    metrics = evaluate_bloom(labels, preds)
    metrics["predictions"] = preds
    logger.info("B0 Rule Macro-F1 = %.4f", metrics["macro_f1"])
    return metrics


# ---------------------------------------------------------------------------
# B1 — TF-IDF + LogisticRegression
# ---------------------------------------------------------------------------

def train_tfidf_logreg(X_train, y_train, C: float = 1.0, seed: int = 42):
    """
    B1: Huấn luyện TF-IDF + LogisticRegression.

    Parameters
    ----------
    X_train : sparse matrix (từ build_tfidf_features)
    y_train : list/array nhãn Bloom

    Returns
    -------
    sklearn LogisticRegression đã fit
    """
    from sklearn.linear_model import LogisticRegression
    clf = LogisticRegression(
        C=C, class_weight="balanced", max_iter=1000,
        random_state=seed, solver="lbfgs", multi_class="multinomial",
    )
    clf.fit(X_train, y_train)
    return clf


# ---------------------------------------------------------------------------
# B2 — Embedding + LogisticRegression
# ---------------------------------------------------------------------------

def train_embedding_logreg(X_train, y_train, seed: int = 42):
    """B2: LogisticRegression trên embedding dense."""
    from sklearn.linear_model import LogisticRegression
    clf = LogisticRegression(
        C=1.0, class_weight="balanced", max_iter=1000,
        random_state=seed, solver="lbfgs",
    )
    clf.fit(X_train, y_train)
    return clf


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

def cross_validate_bloom(
    df: pd.DataFrame,
    feature_type: str = "tfidf",
    n_folds: int = 5,
    seed: int = 42,
    C: float = 1.0,
) -> dict:
    """
    Cross-validation Bloom classification theo fold.

    Parameters
    ----------
    df : DataFrame với columns: text, bloom_level, fold (từ make_folds)
    feature_type : 'tfidf' | 'embedding'
    n_folds : số fold
    seed : random seed

    Returns
    -------
    dict với mean/std macro_f1, per_fold_f1
    """
    from syllabus_core.evaluation.metrics import macro_f1 as calc_macro_f1
    from syllabus_core.features.build_features import (
        build_embedding_features,
        build_tfidf_features,
        make_folds,
    )

    if "fold" not in df.columns:
        df = make_folds(df, n_folds=n_folds, seed=seed)

    fold_f1s = []
    best_model = None
    best_f1 = -1.0

    for fold_idx in range(n_folds):
        train_df = df[df["fold"] != fold_idx]
        val_df   = df[df["fold"] == fold_idx]

        train_texts = train_df["text"].tolist()
        val_texts   = val_df["text"].tolist()
        y_train = train_df["bloom_level"].tolist()
        y_val   = val_df["bloom_level"].tolist()

        if feature_type == "tfidf":
            X_train, vect = build_tfidf_features(train_texts)
            X_val, _ = build_tfidf_features(val_texts, vectorizer=vect)
            clf = train_tfidf_logreg(X_train, y_train, C=C, seed=seed)
        else:
            X_train = build_embedding_features(train_texts)
            X_val = build_embedding_features(val_texts)
            clf = train_embedding_logreg(X_train, y_train, seed=seed)

        preds = clf.predict(X_val)
        f1 = calc_macro_f1(y_val, preds.tolist())
        fold_f1s.append(f1)
        logger.info("Fold %d: Macro-F1 = %.4f", fold_idx, f1)

        if f1 > best_f1:
            best_f1 = f1
            best_model = clf

    result = {
        "feature_type": feature_type,
        "n_folds": n_folds,
        "per_fold_macro_f1": fold_f1s,
        "mean_macro_f1": float(np.mean(fold_f1s)),
        "std_macro_f1": float(np.std(fold_f1s)),
        "best_fold_f1": float(best_f1),
        "_best_model": best_model,
    }
    logger.info(
        "CV %s: Macro-F1 = %.4f ± %.4f", feature_type,
        result["mean_macro_f1"], result["std_macro_f1"],
    )
    return result


# ---------------------------------------------------------------------------
# Save / load model
# ---------------------------------------------------------------------------

def save_model(model: Any, path: str | Path) -> None:
    """Lưu model bằng pickle."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(model, f)
    logger.info("Đã lưu model → %s", path)


def load_model(path: str | Path) -> Any:
    """Load model từ pickle."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy model tại {path}")
    with path.open("rb") as f:
        return pickle.load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    from syllabus_core.evaluation.metrics import save_metrics
    from syllabus_core.features.build_features import (
        build_tfidf_features,
        load_clos,
        make_folds,
    )

    ap = argparse.ArgumentParser(description="Huấn luyện Bloom classifier M2")
    ap.add_argument("--clos", default="data/processed/clos_labeled.csv")
    ap.add_argument("--out", default="models/bloom_model.pkl")
    ap.add_argument("--feature", choices=["tfidf", "embedding"], default="tfidf")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    df = load_clos(a.clos)
    df = make_folds(df, seed=a.seed)

    print(f"Dữ liệu: {len(df)} CLO, {df['bloom_level'].nunique()} lớp Bloom")

    # B0
    b0 = train_baseline_rule(df["text"].tolist(), df["bloom_level"].tolist())
    print(f"B0 Rule Macro-F1 = {b0['macro_f1']:.4f}")

    # B1/B2 CV
    cv = cross_validate_bloom(df, feature_type=a.feature, seed=a.seed)
    print(f"CV {a.feature} Macro-F1 = {cv['mean_macro_f1']:.4f} ± {cv['std_macro_f1']:.4f}")

    # Train trên toàn bộ dữ liệu
    texts = df["text"].tolist()
    labels = df["bloom_level"].tolist()
    if a.feature == "tfidf":
        X, vect = build_tfidf_features(texts)
        final_model = train_tfidf_logreg(X, labels, seed=a.seed)
        save_model({"clf": final_model, "vectorizer": vect, "feature_type": "tfidf"}, a.out)
    else:
        from syllabus_core.features.build_features import build_embedding_features
        X = build_embedding_features(texts)
        final_model = train_embedding_logreg(X, labels, seed=a.seed)
        save_model({"clf": final_model, "feature_type": "embedding"}, a.out)

    metrics = {
        "b0_rule_macro_f1": round(b0["macro_f1"], 4),
        f"{a.feature}_cv_mean_macro_f1": round(cv["mean_macro_f1"], 4),
        f"{a.feature}_cv_std_macro_f1": round(cv["std_macro_f1"], 4),
        "target_macro_f1": 0.75,
        "n_samples": len(df),
        "n_folds": 5,
    }
    save_metrics(metrics, "results/metrics.json", "m2_bloom")
    print("Hoàn thành!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
