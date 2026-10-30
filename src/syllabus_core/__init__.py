"""syllabus_core — Thư viện lõi của hệ thống Syllabus RAG (SGU).

Modules:
    data        : Thu thập, làm sạch, tách đoạn và kiểm tra dữ liệu đề cương.
    features    : Xây đặc trưng cho các mô hình học máy.
    models      : Huấn luyện và dự đoán (M1-section, M2-Bloom, M3-reranker).
    retrieval   : Index BM25/Dense, kết hợp RRF, pipeline RAG.
    pathway     : Đồ thị tiên quyết và lên lộ trình học (M4).
    evaluation  : Các chỉ số đánh giá chuẩn hoá.
    visualization: Vẽ biểu đồ kết quả thí nghiệm.
"""

__version__ = "1.0.0"
__author__ = "Nhóm syllabus-rag — ĐH Sài Gòn"
