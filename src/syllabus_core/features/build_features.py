"""
build_features.py
Xây đặc trưng TF-IDF và embedding cho M2 (phân loại Bloom CLO).

Dùng:
    python -m syllabus_core.features.build_features \\
        --clos data/processed/clos_labeled.csv \\
        --out data/processed/features/
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthetic fallback data
# ---------------------------------------------------------------------------

_SYNTHETIC_CLOS = [
    ("841020", "CLO1", "Liệt kê được các kiểu dữ liệu cơ bản trong C.", 1),
    ("841020", "CLO2", "Trình bày được khái niệm thuật toán và lưu đồ.", 1),
    ("841020", "CLO3", "Giải thích được cấu trúc rẽ nhánh và vòng lặp.", 2),
    ("841020", "CLO4", "Phân biệt được hàm và thủ tục trong lập trình.", 2),
    ("841020", "CLO5", "Áp dụng mảng để giải bài toán sắp xếp.", 3),
    ("841020", "CLO6", "Cài đặt được chương trình quản lý sinh viên bằng C.", 3),
    ("841047", "CLO1", "Trình bày các khái niệm về công nghệ phần mềm.", 1),
    ("841047", "CLO2", "Phân tích yêu cầu phần mềm từ bài toán thực tế.", 4),
    ("841047", "CLO3", "Áp dụng UML để mô hình hoá hệ thống phần mềm.", 3),
    ("841047", "CLO4", "Thiết kế kiến trúc phần mềm theo mô hình MVC.", 6),
    ("841047", "CLO5", "Đánh giá chất lượng phần mềm theo tiêu chuẩn ISO.", 5),
    ("841408", "CLO1", "Mô tả quy trình kiểm thử phần mềm.", 1),
    ("841408", "CLO2", "Phân tích và thiết kế ca kiểm thử từ đặc tả.", 4),
    ("841408", "CLO3", "Thực hiện kiểm thử hộp đen và hộp trắng.", 3),
    ("841408", "CLO4", "Đánh giá rủi ro và lập kế hoạch kiểm thử.", 5),
    ("841108", "CLO1", "Nhận biết các cấu trúc dữ liệu cơ bản.", 1),
    ("841108", "CLO2", "Hiểu nguyên lý hoạt động của danh sách liên kết.", 2),
    ("841108", "CLO3", "Áp dụng cây nhị phân tìm kiếm trong bài toán.", 3),
    ("841108", "CLO4", "So sánh độ phức tạp các thuật toán sắp xếp.", 4),
    ("841108", "CLO5", "Thể hiện tính kỷ luật trong làm việc nhóm.", 0),
    ("841303", "CLO1", "Giải thích các khái niệm mạng máy tính.", 2),
    ("841303", "CLO2", "Phân tích mô hình OSI và TCP/IP.", 4),
    ("841303", "CLO3", "Cấu hình được mạng LAN cơ bản.", 3),
    ("841303", "CLO4", "Đánh giá bảo mật mạng theo tiêu chuẩn.", 5),
    ("841058", "CLO1", "Trình bày nguyên lý hệ điều hành mã nguồn mở.", 1),
    ("841058", "CLO2", "Sử dụng lệnh Linux để quản lý hệ thống.", 3),
    ("841058", "CLO3", "Xây dựng script shell tự động hoá tác vụ.", 6),
    ("841058", "CLO4", "Phân tích hiệu năng hệ thống Linux.", 4),
]


def make_synthetic_clos() -> pd.DataFrame:
    """Tạo DataFrame CLO tổng hợp khi không có dữ liệu thực."""
    rows = []
    for course_code, clo_id, text, bloom_level in _SYNTHETIC_CLOS:
        rows.append({
            "course_code": course_code,
            "clo_id": clo_id,
            "text": text,
            "bloom_level": bloom_level,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_clos(path: str | Path) -> pd.DataFrame:
    """
    Load CLO đã gán nhãn từ CSV.

    Columns cần có: course_code, clo_id, text, bloom_level
    Nếu file không tồn tại → dùng synthetic data.
    """
    path = Path(path)
    if not path.exists():
        logger.warning("Không tìm thấy %s, dùng synthetic data.", path)
        return make_synthetic_clos()
    df = pd.read_csv(path, encoding="utf-8")
    required = {"course_code", "clo_id", "text", "bloom_level"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV thiếu cột: {missing}")
    df["bloom_level"] = df["bloom_level"].astype(int)
    df = df.dropna(subset=["text", "bloom_level"])
    logger.info("Đã load %d CLO từ %s", len(df), path)
    return df


# ---------------------------------------------------------------------------
# TF-IDF features
# ---------------------------------------------------------------------------

def build_tfidf_features(
    texts: list[str],
    vectorizer=None,
    word_ngram=(1, 2),
    char_ngram=(2, 4),
    max_features: int = 20_000,
):
    """
    Xây đặc trưng TF-IDF kết hợp word n-gram và char n-gram.

    Parameters
    ----------
    texts : danh sách văn bản CLO
    vectorizer : nếu None → fit mới; nếu có → chỉ transform
    word_ngram, char_ngram : khoảng n-gram
    max_features : tổng số đặc trưng tối đa

    Returns
    -------
    (X_sparse, vectorizer) : scipy sparse matrix và sklearn vectorizer
    """
    from scipy.sparse import hstack
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion

    if vectorizer is None:
        word_vect = TfidfVectorizer(
            ngram_range=word_ngram,
            analyzer="word",
            max_features=max_features // 2,
            sublinear_tf=True,
        )
        char_vect = TfidfVectorizer(
            ngram_range=char_ngram,
            analyzer="char_wb",
            max_features=max_features // 2,
            sublinear_tf=True,
        )
        X_word = word_vect.fit_transform(texts)
        X_char = char_vect.fit_transform(texts)
        X = hstack([X_word, X_char])
        vectorizer = (word_vect, char_vect)
    else:
        word_vect, char_vect = vectorizer
        X_word = word_vect.transform(texts)
        X_char = char_vect.transform(texts)
        X = hstack([X_word, X_char])

    return X, vectorizer


# ---------------------------------------------------------------------------
# Embedding features
# ---------------------------------------------------------------------------

def build_embedding_features(
    texts: list[str],
    model_name: str = "intfloat/multilingual-e5-small",
    batch_size: int = 32,
) -> np.ndarray:
    """
    Encode văn bản thành dense embedding bằng sentence-transformers.
    Fallback: TF-IDF SVD 128 dims nếu không có thư viện/GPU.

    Returns
    -------
    np.ndarray shape (n_samples, embedding_dim)
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        prefix = "query: "
        prefixed = [prefix + t for t in texts]
        embeddings = model.encode(prefixed, batch_size=batch_size, show_progress_bar=True, normalize_embeddings=True)
        logger.info("Embedding: %s, shape=%s", model_name, embeddings.shape)
        return embeddings
    except (ImportError, Exception) as e:
        logger.warning("Không dùng được sentence-transformers (%s). Fallback TF-IDF SVD.", e)
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        vect = TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True)
        X = vect.fit_transform(texts)
        svd = TruncatedSVD(n_components=min(128, X.shape[1] - 1), random_state=42)
        return svd.fit_transform(X).astype(np.float32)


# ---------------------------------------------------------------------------
# Fold generation
# ---------------------------------------------------------------------------

def make_folds(
    df: pd.DataFrame,
    n_folds: int = 5,
    group_col: str = "course_code",
    label_col: str = "bloom_level",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Tạo cột 'fold' (0..n_folds-1) bằng StratifiedGroupKFold theo môn.

    Returns
    -------
    df với cột 'fold' bổ sung
    """
    from sklearn.model_selection import StratifiedGroupKFold
    skf = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    df = df.copy().reset_index(drop=True)
    df["fold"] = -1
    X_dummy = np.zeros(len(df))
    y = df[label_col].values
    groups = df[group_col].values
    for fold_idx, (_, val_idx) in enumerate(skf.split(X_dummy, y, groups)):
        df.loc[val_idx, "fold"] = fold_idx
    logger.info("Đã tạo %d folds. Phân bố: %s", n_folds, df["fold"].value_counts().to_dict())
    return df


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

def save_features(X, path: str | Path) -> None:
    """Lưu ma trận đặc trưng: numpy → .npy, scipy sparse → .npz."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from scipy.sparse import issparse
        if issparse(X):
            from scipy.sparse import save_npz
            save_npz(str(path.with_suffix(".npz")), X)
            logger.info("Đã lưu sparse features → %s.npz", path.stem)
            return
    except ImportError:
        pass
    np.save(str(path.with_suffix(".npy")), X)
    logger.info("Đã lưu dense features → %s.npy", path.stem)


def load_features(path: str | Path):
    """Load đặc trưng từ .npz (sparse) hoặc .npy (dense)."""
    path = Path(path)
    npz = path.with_suffix(".npz")
    npy = path.with_suffix(".npy")
    if npz.exists():
        from scipy.sparse import load_npz
        return load_npz(str(npz))
    if npy.exists():
        return np.load(str(npy))
    raise FileNotFoundError(f"Không tìm thấy features tại {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Xây đặc trưng Bloom CLO")
    ap.add_argument("--clos", default="data/processed/clos_labeled.csv")
    ap.add_argument("--out", default="data/processed/features")
    ap.add_argument("--type", choices=["tfidf", "embedding", "both"], default="tfidf")
    a = ap.parse_args()

    df = load_clos(a.clos)
    texts = df["text"].tolist()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    if a.type in ("tfidf", "both"):
        X, vect = build_tfidf_features(texts)
        save_features(X, out / "tfidf")
        with open(out / "tfidf_vectorizer.pkl", "wb") as f:
            pickle.dump(vect, f)
        print(f"TF-IDF shape: {X.shape}")

    if a.type in ("embedding", "both"):
        E = build_embedding_features(texts)
        save_features(E, out / "embedding")
        print(f"Embedding shape: {E.shape}")

    df_folds = make_folds(df)
    df_folds.to_csv(out / "clos_with_folds.csv", index=False, encoding="utf-8")
    print("Xong!")


if __name__ == "__main__":
    main()
