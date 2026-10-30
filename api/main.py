"""
main.py
FastAPI application cho hệ thống Syllabus RAG.

Chạy:
    uvicorn api.main:app --reload --port 8000
Docs:
    http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Thêm src vào sys.path để import syllabus_core
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.schemas import (
    AskRequest,
    AskResponse,
    CLOClassifyRequest,
    CLOClassifyResponse,
    CLOClassifyResult,
    CourseBrief,
    ErrorResponse,
    HealthResponse,
    LearningPathRequest,
    LearningPathResponse,
    SyllabusAnalysisResponse,
    TermPlan,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/api.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("api")

# ---------------------------------------------------------------------------
# Global state (load khi startup)
# ---------------------------------------------------------------------------

_state: dict = {
    "models": {},
    "retriever": None,
    "rag_pipeline": None,
    "planner": None,
    "graph": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models khi startup, giải phóng khi shutdown."""
    logger.info("Đang khởi động API và load models...")
    try:
        from syllabus_core.models.predict import load_models
        _state["models"] = load_models("models/")

        # Build retrieval index
        try:
            from syllabus_core.retrieval.index import BM25Index, DenseIndex, build_corpus
            from syllabus_core.retrieval.hybrid import HybridRetriever
            from syllabus_core.retrieval.rag import RAGPipeline
            import yaml

            params = {}
            if Path("config/params.yaml").exists():
                with open("config/params.yaml", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    params = cfg.get("m3_retrieval", {})
                    params["embedding_model"] = cfg.get("m3_embedding", {}).get("model", "intfloat/multilingual-e5-small")

            chunks = build_corpus("data/processed/syllabi")
            if not chunks:
                from syllabus_core.retrieval.index import _make_synthetic_corpus
                chunks = _make_synthetic_corpus()

            bm25 = BM25Index(chunks)
            dense = DenseIndex(chunks, model_name=params.get("embedding_model", "intfloat/multilingual-e5-small"), vectors_path="models/vectors.npy")
            retriever = HybridRetriever(bm25, dense, params=params)
            _state["retriever"] = retriever
            _state["rag_pipeline"] = RAGPipeline(
                retriever=retriever,
                reranker_model=_state["models"].get("reranker"),
                cache_path="logs/rag_cache.json",
            )
            logger.info("Retrieval index đã build: %d chunks", len(chunks))
        except Exception as e:
            logger.warning("Không build được retrieval index: %s", e)

        # Pathway graph + planner
        try:
            from syllabus_core.pathway.graph import PrerequisiteGraph
            from syllabus_core.pathway.planner import LearningPlanner
            graph = PrerequisiteGraph()
            graph.load_from_syllabi("data/processed/syllabi")
            if Path("data/external/DanhMuc_KyThuatPhanMem.xlsx").exists():
                graph.load_from_xlsx("data/external/DanhMuc_KyThuatPhanMem.xlsx")
            _state["graph"] = graph
            _state["planner"] = LearningPlanner(graph)
            logger.info("Graph: %d môn", len(graph.nodes))
        except Exception as e:
            logger.warning("Không build được graph: %s", e)

    except Exception as e:
        logger.error("Lỗi khi load models: %s", e)

    logger.info(
        "API sẵn sàng. Models: %s",
        list(_state["models"].keys()),
    )
    yield
    logger.info("API đang tắt.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Syllabus RAG API",
    description="Hệ thống phân tích đề cương môn học kết hợp RAG — ĐH Sài Gòn",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Kiểm tra trạng thái API."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        models_loaded=list(_state["models"].keys()),
    )


@app.post("/classify-clo", response_model=CLOClassifyResponse, tags=["M2 Bloom"])
async def classify_clo(req: CLOClassifyRequest):
    """
    Phân loại mức Bloom cho CLO.

    Nhận một câu (`text`) hoặc nhiều câu (`texts`).
    Trả về label (0-6), tên mức, độ tin cậy và phân bố xác suất.
    """
    texts_to_classify = []
    if req.text:
        texts_to_classify = [req.text]
    elif req.texts:
        texts_to_classify = req.texts
    else:
        raise HTTPException(status_code=400, detail="Cần cung cấp 'text' hoặc 'texts'")

    bloom_model = _state["models"].get("bloom_model")
    version = "bloom-v1"

    try:
        from syllabus_core.models.predict import predict_bloom
        results = []
        for text in texts_to_classify:
            pred = predict_bloom(text, bloom_model)
            results.append(CLOClassifyResult(
                text=text,
                label=pred["label"],
                label_name=pred["label_name"],
                confidence=pred["confidence"],
                probabilities=pred["probabilities"],
                model_version=version,
            ))
        return CLOClassifyResponse(results=results, model_version=version)
    except Exception as e:
        logger.error("Lỗi classify_clo: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-syllabus", response_model=SyllabusAnalysisResponse, tags=["M1 Extraction"])
async def analyze_syllabus(file: UploadFile = File(...)):
    """
    Phân tích đề cương PDF: trích xuất 10 mục, gán mức Bloom cho CLO.

    Upload file PDF; trả về JSON đề cương đầy đủ.
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="Không có file được upload")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf",):
        raise HTTPException(status_code=422, detail=f"Chỉ hỗ trợ PDF, nhận được: {ext}")

    # Lưu tạm
    tmp_path = Path("logs") / f"tmp_{int(time.time())}_{file.filename}"
    try:
        content = await file.read()
        tmp_path.write_bytes(content)

        from syllabus_core.models.predict import analyze_pdf
        result = analyze_pdf(tmp_path, models=_state["models"])
        return SyllabusAnalysisResponse(**{k: v for k, v in result.items() if k not in ("model_version", "processing_time_s")},
                                        model_version=result.get("model_version", "v1.0"),
                                        processing_time_s=result.get("processing_time_s", 0.0))
    except Exception as e:
        logger.error("Lỗi analyze_syllabus: %s", e)
        raise HTTPException(status_code=422, detail=f"Không đọc được PDF: {e}")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.post("/ask", tags=["M3 RAG"])
async def ask(req: AskRequest):
    """
    Hỏi đáp RAG về đề cương.

    Câu hỏi tiếng Việt; trả về câu trả lời có trích dẫn nguồn [n].
    Khi LLM không khả dụng: trả HTTP 503 kèm các đoạn đã truy xuất.
    """
    if not _state.get("rag_pipeline"):
        raise HTTPException(status_code=503, detail="Pipeline RAG chưa sẵn sàng")

    try:
        pipeline = _state["rag_pipeline"]
        result = pipeline.answer(req.question, filter_course=req.course_filter)

        if result.get("provider_used") == "error":
            return JSONResponse(
                status_code=503,
                content={
                    "error": "LLM không khả dụng",
                    "retrieved": result.get("retrieved_chunks", []),
                },
            )

        return AskResponse(**result)
    except Exception as e:
        logger.error("Lỗi ask: %s", e)
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/learning-path", response_model=LearningPathResponse, tags=["M4 Pathway"])
async def learning_path(req: LearningPathRequest):
    """
    Gợi ý lộ trình học.

    Nhận môn đích và danh sách môn đã học; trả về kế hoạch theo học kỳ.
    """
    if not _state.get("planner"):
        raise HTTPException(status_code=503, detail="Planner chưa sẵn sàng")

    graph = _state["graph"]
    if req.target_course not in graph.nodes:
        raise HTTPException(
            status_code=400,
            detail=f"Môn {req.target_course} không có trong hệ thống",
        )

    try:
        planner = _state["planner"]
        result = planner.plan(req.target_course, completed_courses=req.completed_courses)

        terms = [
            TermPlan(
                term=t["term"],
                courses=[CourseBrief(**c) for c in t["courses"]],
                total_credits=t["total_credits"],
            )
            for t in result["plan"]
        ]

        total_courses = sum(len(t.courses) for t in terms)
        total_credits = sum(t.total_credits for t in terms)

        return LearningPathResponse(
            target_course=req.target_course,
            plan=terms,
            warnings=result["warnings"],
            soft_suggestions=result["soft_suggestions"],
            total_courses=total_courses,
            total_credits=total_credits,
        )
    except Exception as e:
        logger.error("Lỗi learning_path: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
