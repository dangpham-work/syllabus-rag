"""
src/syllabus_core/visualization/visualize.py
=============================================
Bộ hàm vẽ đồ thị cho dự án Syllabus RAG.
Bao gồm: phân bố Bloom, ma trận nhầm lẫn, so sánh retrieval, learning curve.

Tất cả hàm đều nhận tham số `save_path` tuỳ chọn:
  - None  → hiển thị trực tiếp (plt.show())
  - str   → lưu file PNG và đóng figure (không hiển thị)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# Dùng Agg backend khi không có màn hình (server/notebook headless)
matplotlib.use("Agg")

# ---------------------------------------------------------------------------
# Hằng số chung
# ---------------------------------------------------------------------------

BLOOM_LABELS = [
    "0: Ngoài miền",
    "1: Nhớ",
    "2: Hiểu",
    "3: Áp dụng",
    "4: Phân tích",
    "5: Đánh giá",
    "6: Sáng tạo",
]

BLOOM_COLORS = [
    "#9E9E9E",  # 0 – xám
    "#2196F3",  # 1 – xanh dương
    "#4CAF50",  # 2 – xanh lá
    "#FFC107",  # 3 – vàng
    "#FF9800",  # 4 – cam
    "#F44336",  # 5 – đỏ
    "#9C27B0",  # 6 – tím
]

RETRIEVAL_COLORS = ["#1565C0", "#2E7D32", "#F57F17", "#6A1B9A", "#AD1457", "#00695C"]

DPI = 150
FIGSIZE_DEFAULT = (10, 6)


def _save_or_show(fig: plt.Figure, save_path: Optional[str]) -> None:
    """Lưu hoặc hiển thị figure; luôn đóng sau khi xong."""
    if save_path is not None:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=DPI, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()
        plt.close(fig)


# ---------------------------------------------------------------------------
# 1. Phân bố Bloom
# ---------------------------------------------------------------------------

def plot_bloom_distribution(
    clos_df: Any,
    save_path: Optional[str] = None,
    title: str = "Phân bố mức Bloom của CLO đề cương SGU",
) -> None:
    """
    Vẽ biểu đồ thanh phân bố 7 lớp Bloom trong tập CLO.

    Parameters
    ----------
    clos_df : pandas.DataFrame
        DataFrame có cột ``bloom_level`` (int 0-6).
    save_path : str | None
        Đường dẫn lưu PNG. None → plt.show().
    title : str
        Tiêu đề đồ thị.

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({"bloom_level": [1, 2, 3, 3, 3, 4, 5]})
    >>> plot_bloom_distribution(df, save_path="reports/figures/bloom_dist.png")
    """
    try:
        import pandas as pd  # type: ignore
    except ImportError:
        raise ImportError("Cần cài đặt pandas: pip install pandas")

    df = clos_df.copy()
    counts = df["bloom_level"].value_counts().sort_index()
    # Đảm bảo đủ 7 lớp (0-6)
    counts = counts.reindex(range(7), fill_value=0)

    fig, ax = plt.subplots(figsize=FIGSIZE_DEFAULT)
    bars = ax.bar(
        counts.index,
        counts.values,
        color=[BLOOM_COLORS[i] for i in range(7)],
        edgecolor="white",
        linewidth=0.8,
    )

    # Nhãn giá trị trên đầu mỗi thanh
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.5,
                f"{int(height)}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

    ax.set_xticks(range(7))
    ax.set_xticklabels(BLOOM_LABELS, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Số lượng CLO", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.grid(axis="y", alpha=0.4, linestyle="--")
    ax.set_axisbelow(True)

    total = counts.sum()
    ax.set_xlabel(f"Lớp Bloom (tổng: {total} CLO)", fontsize=11)

    fig.tight_layout()
    _save_or_show(fig, save_path)


# ---------------------------------------------------------------------------
# 2. Ma trận nhầm lẫn
# ---------------------------------------------------------------------------

def plot_confusion_matrix(
    y_true: Any,
    y_pred: Any,
    labels: Optional[list[str]] = None,
    title: str = "Ma trận nhầm lẫn",
    save_path: Optional[str] = None,
    normalize: bool = True,
    cmap: str = "Blues",
) -> None:
    """
    Vẽ ma trận nhầm lẫn với annotation giá trị.

    Parameters
    ----------
    y_true : array-like
        Nhãn thực tế.
    y_pred : array-like
        Nhãn dự đoán.
    labels : list[str] | None
        Tên các lớp. None → dùng tên lớp mặc định hoặc số.
    title : str
        Tiêu đề đồ thị.
    save_path : str | None
        Đường dẫn lưu PNG. None → plt.show().
    normalize : bool
        True → chia theo hàng (tỷ lệ %). False → giá trị tuyệt đối.
    cmap : str
        Colormap matplotlib.

    Examples
    --------
    >>> y_true = [1, 2, 3, 1, 2]
    >>> y_pred = [1, 2, 2, 1, 3]
    >>> plot_confusion_matrix(y_true, y_pred, save_path="reports/figures/cm.png")
    """
    try:
        from sklearn.metrics import confusion_matrix  # type: ignore
    except ImportError:
        raise ImportError("Cần cài đặt scikit-learn: pip install scikit-learn")

    import numpy as np

    cm = confusion_matrix(y_true, y_pred)
    n_classes = cm.shape[0]

    if labels is None:
        # Lấy tên lớp từ giá trị duy nhất hoặc dùng số
        unique = sorted(set(list(y_true) + list(y_pred)))
        labels = [str(u) for u in unique]

    if normalize:
        row_sums = cm.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1  # tránh chia 0
        cm_display = cm.astype(float) / row_sums
        fmt = ".2f"
        cbar_label = "Tỷ lệ (theo hàng)"
    else:
        cm_display = cm
        fmt = "d"
        cbar_label = "Số lượng"

    fig_size = max(8, n_classes * 1.2)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size * 0.85))

    im = ax.imshow(cm_display, interpolation="nearest", cmap=cmap, vmin=0, vmax=1 if normalize else None)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(cbar_label, fontsize=10)

    # Annotations
    thresh = cm_display.max() / 2.0
    for i in range(n_classes):
        for j in range(n_classes):
            val = cm_display[i, j]
            text = f"{val:{fmt}}" if normalize else f"{val}"
            ax.text(
                j, i, text,
                ha="center", va="center",
                color="white" if val > thresh else "black",
                fontsize=max(7, 12 - n_classes // 2),
            )

    ax.set_xticks(range(n_classes))
    ax.set_yticks(range(n_classes))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_ylabel("Nhãn thực tế", fontsize=11)
    ax.set_xlabel("Nhãn dự đoán", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)

    fig.tight_layout()
    _save_or_show(fig, save_path)


# ---------------------------------------------------------------------------
# 3. So sánh retrieval
# ---------------------------------------------------------------------------

def plot_retrieval_comparison(
    results_dict: dict[str, dict[str, float]],
    metric: str = "recall@5",
    save_path: Optional[str] = None,
    title: Optional[str] = None,
) -> None:
    """
    Vẽ biểu đồ thanh ngang so sánh các cấu hình retrieval.

    Parameters
    ----------
    results_dict : dict
        Dict dạng ``{"config_name": {"recall@5": 0.87, "mrr@10": 0.75, ...}, ...}``.
        Ví dụ::

            {
                "BM25": {"recall@5": 0.65, "mrr@10": 0.58},
                "Dense": {"recall@5": 0.72, "mrr@10": 0.65},
                "RRF+LambdaMART": {"recall@5": 0.87, "mrr@10": 0.82},
            }
    metric : str
        Tên metric muốn vẽ (key trong dict).
    save_path : str | None
        Đường dẫn lưu PNG.
    title : str | None
        Tiêu đề. None → tự sinh từ tên metric.

    Examples
    --------
    >>> results = {"BM25": {"recall@5": 0.65}, "Dense": {"recall@5": 0.72}}
    >>> plot_retrieval_comparison(results, metric="recall@5")
    """
    configs = list(results_dict.keys())
    values = [results_dict[c].get(metric, 0.0) for c in configs]

    # Sắp xếp theo giá trị tăng dần (biểu đồ ngang dễ đọc hơn)
    sorted_pairs = sorted(zip(values, configs), key=lambda x: x[0])
    values_sorted, configs_sorted = zip(*sorted_pairs) if sorted_pairs else ([], [])

    colors = [RETRIEVAL_COLORS[i % len(RETRIEVAL_COLORS)] for i in range(len(configs_sorted))]

    fig, ax = plt.subplots(figsize=(10, max(4, len(configs) * 0.8)))
    bars = ax.barh(configs_sorted, values_sorted, color=colors, edgecolor="white", height=0.6)

    # Giá trị cuối thanh
    for bar, val in zip(bars, values_sorted):
        ax.text(
            bar.get_width() + 0.005,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}",
            va="center",
            fontsize=10,
            fontweight="bold",
        )

    if title is None:
        title = f"So sánh cấu hình Retrieval – {metric}"

    ax.set_xlabel(metric, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlim(0, max(values_sorted) * 1.15 if values_sorted else 1.0)
    ax.grid(axis="x", alpha=0.4, linestyle="--")
    ax.set_axisbelow(True)

    # Vẽ đường target nếu metric là recall@5
    if "recall" in metric.lower() and "5" in metric:
        ax.axvline(0.85, color="red", linestyle="--", linewidth=1.2, label="Target (0.85)")
        ax.legend(fontsize=9)

    fig.tight_layout()
    _save_or_show(fig, save_path)


def plot_retrieval_multi_metrics(
    results_dict: dict[str, dict[str, float]],
    metrics: Optional[list[str]] = None,
    save_path: Optional[str] = None,
    title: str = "So sánh Retrieval – Nhiều chỉ số",
) -> None:
    """
    Vẽ biểu đồ nhóm so sánh nhiều metric cùng lúc cho các cấu hình.

    Parameters
    ----------
    results_dict : dict
        Dict dạng ``{"config_name": {"recall@1": ..., "recall@5": ..., "mrr@10": ...}}``.
    metrics : list[str] | None
        Danh sách metric muốn vẽ. None → dùng ["recall@1", "recall@5", "mrr@10"].
    save_path : str | None
        Đường dẫn lưu PNG.
    title : str
        Tiêu đề đồ thị.
    """
    if metrics is None:
        metrics = ["recall@1", "recall@5", "mrr@10"]

    configs = list(results_dict.keys())
    n_configs = len(configs)
    n_metrics = len(metrics)

    x = np.arange(n_configs)
    width = 0.8 / n_metrics

    fig, ax = plt.subplots(figsize=(max(10, n_configs * 1.5), 6))

    for i, metric in enumerate(metrics):
        vals = [results_dict[c].get(metric, 0.0) for c in configs]
        offset = (i - n_metrics / 2 + 0.5) * width
        bars = ax.bar(x + offset, vals, width=width * 0.9, label=metric,
                      color=RETRIEVAL_COLORS[i % len(RETRIEVAL_COLORS)], edgecolor="white")
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.005,
                    f"{val:.2f}",
                    ha="center", va="bottom", fontsize=7,
                )

    ax.set_xticks(x)
    ax.set_xticklabels(configs, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Giá trị metric", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=9)
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.4, linestyle="--")
    ax.set_axisbelow(True)

    fig.tight_layout()
    _save_or_show(fig, save_path)


# ---------------------------------------------------------------------------
# 4. Learning curve
# ---------------------------------------------------------------------------

def plot_learning_curve(
    train_sizes: Any,
    train_scores: Any,
    val_scores: Any,
    title: str = "Learning Curve",
    save_path: Optional[str] = None,
    metric_name: str = "Macro-F1",
) -> None:
    """
    Vẽ learning curve (train & validation score theo kích thước training set).

    Parameters
    ----------
    train_sizes : array-like, shape (n_points,)
        Số lượng mẫu train tại mỗi điểm.
    train_scores : array-like, shape (n_points,) hoặc (n_points, n_folds)
        Điểm train. Nếu 2D sẽ tính mean ± std.
    val_scores : array-like, shape (n_points,) hoặc (n_points, n_folds)
        Điểm validation. Nếu 2D sẽ tính mean ± std.
    title : str
        Tiêu đề đồ thị.
    save_path : str | None
        Đường dẫn lưu PNG.
    metric_name : str
        Tên metric dùng cho nhãn trục Y.

    Examples
    --------
    >>> import numpy as np
    >>> sizes = np.array([100, 200, 400, 800])
    >>> t_scores = np.array([0.95, 0.93, 0.91, 0.90])
    >>> v_scores = np.array([0.72, 0.76, 0.79, 0.81])
    >>> plot_learning_curve(sizes, t_scores, v_scores)
    """
    train_sizes = np.array(train_sizes)
    train_scores = np.array(train_scores)
    val_scores = np.array(val_scores)

    # Tính mean và std nếu là 2D
    if train_scores.ndim == 2:
        train_mean = train_scores.mean(axis=1)
        train_std = train_scores.std(axis=1)
    else:
        train_mean = train_scores
        train_std = np.zeros_like(train_scores)

    if val_scores.ndim == 2:
        val_mean = val_scores.mean(axis=1)
        val_std = val_scores.std(axis=1)
    else:
        val_mean = val_scores
        val_std = np.zeros_like(val_scores)

    fig, ax = plt.subplots(figsize=FIGSIZE_DEFAULT)

    # Train
    ax.plot(train_sizes, train_mean, "o-", color="#1565C0", label="Train", linewidth=2)
    if train_std.any():
        ax.fill_between(
            train_sizes,
            train_mean - train_std,
            train_mean + train_std,
            alpha=0.15, color="#1565C0",
        )

    # Validation
    ax.plot(train_sizes, val_mean, "s--", color="#C62828", label="Validation", linewidth=2)
    if val_std.any():
        ax.fill_between(
            train_sizes,
            val_mean - val_std,
            val_mean + val_std,
            alpha=0.15, color="#C62828",
        )

    ax.set_xlabel("Số mẫu huấn luyện", fontsize=11)
    ax.set_ylabel(metric_name, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.4, linestyle="--")
    ax.set_axisbelow(True)

    # Đường target M2
    if "F1" in metric_name or "f1" in metric_name:
        ax.axhline(0.75, color="green", linestyle=":", linewidth=1.2, label="Target M2 (0.75)")
        ax.legend(fontsize=10)

    fig.tight_layout()
    _save_or_show(fig, save_path)


# ---------------------------------------------------------------------------
# 5. Hàm tiện ích bổ sung
# ---------------------------------------------------------------------------

def plot_clo_length_distribution(
    lengths: Any,
    save_path: Optional[str] = None,
    title: str = "Phân bố độ dài CLO (số từ)",
    bins: int = 30,
) -> None:
    """
    Vẽ histogram phân bố độ dài CLO.

    Parameters
    ----------
    lengths : array-like
        Danh sách số từ/token của từng CLO.
    save_path : str | None
        Đường dẫn lưu PNG.
    title : str
        Tiêu đề đồ thị.
    bins : int
        Số bin histogram.
    """
    lengths = np.array(lengths)

    fig, ax = plt.subplots(figsize=FIGSIZE_DEFAULT)
    ax.hist(lengths, bins=bins, color="#1565C0", edgecolor="white", alpha=0.85)

    mean_len = lengths.mean()
    median_len = np.median(lengths)

    ax.axvline(mean_len, color="#C62828", linestyle="--", linewidth=1.5,
               label=f"Trung bình ({mean_len:.1f})")
    ax.axvline(median_len, color="#2E7D32", linestyle=":", linewidth=1.5,
               label=f"Trung vị ({median_len:.1f})")

    ax.set_xlabel("Số từ", fontsize=11)
    ax.set_ylabel("Số lượng CLO", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.4, linestyle="--")
    ax.set_axisbelow(True)

    fig.tight_layout()
    _save_or_show(fig, save_path)


def plot_missing_sections(
    missing_counts: dict[str, int],
    save_path: Optional[str] = None,
    title: str = "Số đề cương thiếu từng mục",
) -> None:
    """
    Vẽ biểu đồ thanh số đề cương thiếu từng mục tiêu chuẩn.

    Parameters
    ----------
    missing_counts : dict
        Dict dạng ``{"tên_mục": số_đề_cương_thiếu}``.
    save_path : str | None
        Đường dẫn lưu PNG.
    title : str
        Tiêu đề đồ thị.
    """
    sections = list(missing_counts.keys())
    counts = [missing_counts[s] for s in sections]

    fig, ax = plt.subplots(figsize=(10, max(5, len(sections) * 0.6)))
    bars = ax.barh(sections, counts, color="#F57F17", edgecolor="white", height=0.6)

    for bar, val in zip(bars, counts):
        ax.text(
            bar.get_width() + 0.1,
            bar.get_y() + bar.get_height() / 2,
            str(int(val)),
            va="center", fontsize=9, fontweight="bold",
        )

    ax.set_xlabel("Số đề cương thiếu mục này", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.grid(axis="x", alpha=0.4, linestyle="--")
    ax.set_axisbelow(True)

    fig.tight_layout()
    _save_or_show(fig, save_path)
