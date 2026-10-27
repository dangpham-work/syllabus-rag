"""Huấn luyện mô hình phân loại 11 mục đề cương học phần (Module M1).

Dùng: python src/syllabus_core/models/train_section.py
        [--data data/processed/sections_labeled.csv]
        [--split data/processed/m1_split.csv]
        [--out models/section_clf.pkl]
        [--c 5.0] [--seed 42]

Phương pháp:
  - TF-IDF từ (1-2 gram) + ký tự (2-4 gram).
  - Đặc trưng vị trí: số trang, trang tương đối, chỉ số đoạn, đoạn tương đối, độ dài ký tự, số dòng.
  - Nhãn của đoạn liền trước (prev_section, one-hot encoded).
  - Logistic Regression với trọng số lớp cân bằng (class_weight='balanced').
  - Cơ chế giải mã tự hồi quy (autoregressive decoding) và ràng buộc thứ tự mục không giảm.
"""
from __future__ import annotations

import argparse
import pickle
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")

SECTIONS = [
    "START",
    "other",
    "general_info",
    "course_description",
    "course_objectives",
    "course_learning_outcomes",
    "course_content",
    "learning_resources",
    "teaching_schedule",
    "course_policies",
    "assessment",
    "responsible_unit",
]

SECTION_ORDER = {
    "START": 0,
    "other": 0,
    "general_info": 1,
    "course_description": 2,
    "course_objectives": 3,
    "course_learning_outcomes": 4,
    "course_content": 5,
    "learning_resources": 6,
    "teaching_schedule": 7,
    "course_policies": 8,
    "assessment": 9,
    "responsible_unit": 10,
}

NUM_COLS = ["page", "page_rel", "para_idx", "para_rel", "char_len", "line_cnt"]


class SectionClassifierBundle:
    """Đóng gói toàn bộ pipeline phân loại mục (M1) phục vụ inference tự hồi quy."""

    def __init__(
        self,
        clf: LogisticRegression,
        word_vec: TfidfVectorizer,
        char_vec: TfidfVectorizer,
        scaler: StandardScaler,
        ohe: OneHotEncoder,
        classes: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.clf = clf
        self.word_vec = word_vec
        self.char_vec = char_vec
        self.scaler = scaler
        self.ohe = ohe
        self.classes = list(classes)
        self.metadata = metadata or {}

    def predict_course_paragraphs(
        self,
        paragraphs: List[Dict[str, Any]],
        monotonic: bool = True,
    ) -> List[str]:
        """Dự đoán nhãn mục cho danh sách các đoạn trong một đề cương theo thứ tự xuất hiện.

        Mỗi phần tử trong paragraphs là một dict gồm tối thiểu:
          {'page': int, 'text': str} (có thể có 'para_idx', 'para_id').
        """
        if not paragraphs:
            return []

        tot_paras = max(len(paragraphs), 1)
        max_page = max(max(p.get("page", 1) for p in paragraphs), 1)

        preds: List[str] = []
        cur_prev = "START"
        highest_sec_idx = 0

        for idx, para in enumerate(paragraphs):
            p_text = str(para.get("text", "") or "")
            page = int(para.get("page", 1))
            page_rel = page / max_page
            para_idx = idx
            para_rel = para_idx / tot_paras
            char_len = float(np.log1p(len(p_text)))
            line_cnt = float(p_text.count("\n") + 1)

            # Biến đổi đặc trưng
            w = self.word_vec.transform([p_text])
            ch = self.char_vec.transform([p_text])
            num_df = pd.DataFrame([[page, page_rel, para_idx, para_rel, char_len, line_cnt]], columns=NUM_COLS)
            num_scaled = csr_matrix(self.scaler.transform(num_df))
            prev_df = pd.DataFrame([[cur_prev]], columns=["prev_section"])
            prev_encoded = self.ohe.transform(prev_df)

            feat = hstack([w, ch, num_scaled, prev_encoded])
            probs = self.clf.predict_proba(feat)[0].copy()

            if monotonic:
                # Không đi lùi về mục trước, ngoại trừ nhãn 'other'
                for i, c_name in enumerate(self.classes):
                    c_idx = SECTION_ORDER.get(c_name, 0)
                    if c_name != "other" and c_idx < highest_sec_idx:
                        probs[i] = 0.0

                if probs.sum() > 0:
                    best_cls = self.classes[int(np.argmax(probs))]
                else:
                    best_cls = cur_prev
            else:
                best_cls = self.classes[int(np.argmax(probs))]

            preds.append(best_cls)
            cur_prev = best_cls
            highest_sec_idx = max(highest_sec_idx, SECTION_ORDER.get(best_cls, 0))

        return preds


def prepare_features(df_sub: pd.DataFrame) -> pd.DataFrame:
    """Tạo các đặc trưng số học về vị trí và nhãn đoạn trước theo từng môn."""
    dfs = []
    for _, group in df_sub.groupby("course_code", sort=False):
        g = group.copy().reset_index(drop=True)
        max_p = max(g["page"].max(), 1)
        tot_para = max(len(g), 1)
        g["page_rel"] = g["page"] / max_p
        g["para_idx"] = np.arange(len(g))
        g["para_rel"] = g["para_idx"] / tot_para
        g["char_len"] = np.log1p(g["text"].fillna("").str.len())
        g["line_cnt"] = g["text"].fillna("").str.count("\n") + 1
        g["prev_section"] = ["START"] + list(g["section_gold"].iloc[:-1])
        dfs.append(g)
    return pd.concat(dfs, ignore_index=True)


def train_and_evaluate(
    data_path: str = "data/processed/sections_labeled.csv",
    split_path: str = "data/processed/m1_split.csv",
    out_path: str = "models/section_clf.pkl",
    c_val: float = 5.0,
    seed: int = 42,
) -> SectionClassifierBundle:
    """Quy trình huấn luyện và đánh giá mô hình M1 hoàn chỉnh."""
    print(f"--- Đọc dữ liệu từ {data_path} và bảng chia tập {split_path} ---")
    df = pd.read_csv(data_path)
    split_df = pd.read_csv(split_path)

    split_map = dict(zip(split_df["course_code"].astype(str), split_df["split"]))
    df["split"] = df["course_code"].astype(str).map(split_map)

    train_df = prepare_features(df[df["split"] == "train"])
    val_df = prepare_features(df[df["split"] == "val"])
    test_df = prepare_features(df[df["split"] == "test"])

    print(
        f"Kích thước tập: Train={len(train_df)} đoạn ({train_df['course_code'].nunique()} môn) | "
        f"Val={len(val_df)} đoạn ({val_df['course_code'].nunique()} môn) | "
        f"Test={len(test_df)} đoạn ({test_df['course_code'].nunique()} môn)"
    )

    # 1. Fit Text Transformers
    word_vec = TfidfVectorizer(ngram_range=(1, 2), max_features=10000, sublinear_tf=True)
    char_vec = TfidfVectorizer(ngram_range=(2, 4), analyzer="char", max_features=10000, sublinear_tf=True)

    X_train_word = word_vec.fit_transform(train_df["text"].fillna(""))
    X_train_char = char_vec.fit_transform(train_df["text"].fillna(""))

    # 2. Fit Numeric Scaler
    scaler = StandardScaler()
    X_train_num = csr_matrix(scaler.fit_transform(train_df[NUM_COLS]))

    # 3. Fit OneHotEncoder
    ohe = OneHotEncoder(categories=[SECTIONS], handle_unknown="ignore")
    X_train_prev = ohe.fit_transform(train_df[["prev_section"]])

    # Kết hợp toàn bộ đặc trưng cho tập huấn luyện
    X_train = hstack([X_train_word, X_train_char, X_train_num, X_train_prev])
    y_train = train_df["section_gold"]

    print(f"Huấn luyện Logistic Regression (C={c_val}, class_weight='balanced', seed={seed})...")
    clf = LogisticRegression(C=c_val, max_iter=1000, class_weight="balanced", random_state=seed)
    clf.fit(X_train, y_train)

    bundle = SectionClassifierBundle(
        clf=clf,
        word_vec=word_vec,
        char_vec=char_vec,
        scaler=scaler,
        ohe=ohe,
        classes=list(clf.classes_),
        metadata={
            "model_type": "TF-IDF + LogisticRegression (Autoregressive)",
            "C": c_val,
            "seed": seed,
            "classes": list(clf.classes_),
            "train_courses": int(train_df["course_code"].nunique()),
            "val_courses": int(val_df["course_code"].nunique()),
            "test_courses": int(test_df["course_code"].nunique()),
        },
    )

    # Đánh giá tự hồi quy trên tập Validation
    val_preds = []
    for _, group in val_df.groupby("course_code", sort=False):
        paras = group[["page", "text"]].to_dict(orient="records")
        val_preds.extend(bundle.predict_course_paragraphs(paras, monotonic=True))

    val_acc = accuracy_score(val_df["section_gold"], val_preds)
    val_f1 = f1_score(val_df["section_gold"], val_preds, average="macro")
    print(f"\n[Validation Set - Autoregressive]: Accuracy = {val_acc:.4f} | Macro-F1 = {val_f1:.4f}")

    # Đánh giá tự hồi quy trên tập Test
    test_preds = []
    for _, group in test_df.groupby("course_code", sort=False):
        paras = group[["page", "text"]].to_dict(orient="records")
        test_preds.extend(bundle.predict_course_paragraphs(paras, monotonic=True))

    test_acc = accuracy_score(test_df["section_gold"], test_preds)
    test_f1 = f1_score(test_df["section_gold"], test_preds, average="macro")
    print(f"[Test Set - Autoregressive]:       Accuracy = {test_acc:.4f} | Macro-F1 = {test_f1:.4f}")

    bundle.metadata["val_accuracy"] = float(val_acc)
    bundle.metadata["val_macro_f1"] = float(val_f1)
    bundle.metadata["test_accuracy"] = float(test_acc)
    bundle.metadata["test_macro_f1"] = float(test_f1)

    # Lưu mô hình dưới dạng dictionary để tránh lỗi phụ thuộc module __main__ khi nạp ở nơi khác
    save_dict = {
        "clf": clf,
        "word_vec": word_vec,
        "char_vec": char_vec,
        "scaler": scaler,
        "ohe": ohe,
        "classes": list(clf.classes_),
        "metadata": bundle.metadata,
    }

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "wb") as f:
        pickle.dump(save_dict, f)
    print(f"\nĐã lưu mô hình M1 thành công vào {out_file}")

    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", default="data/processed/sections_labeled.csv", help="Đường dẫn CSV nhãn mục")
    parser.add_argument("--split", default="data/processed/m1_split.csv", help="Đường dẫn CSV phân chia tập")
    parser.add_argument("--out", default="models/section_clf.pkl", help="Đường dẫn lưu mô hình")
    parser.add_argument("--c", type=float, default=5.0, help="Hệ số điều hòa C cho Logistic Regression")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    train_and_evaluate(
        data_path=args.data,
        split_path=args.split,
        out_path=args.out,
        c_val=args.c,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
