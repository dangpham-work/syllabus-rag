"""
main.py
FastAPI application cho hệ thống Syllabus RAG.

Chạy:
    uvicorn api.main:app --reload --port 8000
Docs:
    http://localhost:8000/docs
"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

_ROOT_DIR = Path(__file__).parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
if str(_ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR / "src"))

from api.schemas import (
    AskRequest,
    AskResponse,
    CLOClassifyBatchRequest,
    CLOClassifyRequest,
    CLOClassifyResponse,
    CLOClassifyResult,
    CLOItem,
    CourseBrief,
    CourseDetailResponse,
    CourseListResponse,
    CourseSummary,
    HealthResponse,
    LearningPathRequest,
    LearningPathResponse,
    SyllabusAnalysisResponse,
    TermPlan,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

Path("logs").mkdir(parents=True, exist_ok=True)
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
        from src.syllabus_core.models.predict import load_models
        _state["models"] = load_models("models/")

        # Build retrieval index
        try:
            import yaml
            from src.syllabus_core.retrieval.hybrid import HybridRetriever
            from src.syllabus_core.retrieval.index import (
                BM25Index,
                DenseIndex,
                _make_synthetic_corpus,
                build_corpus,
            )
            from src.syllabus_core.retrieval.rag import RAGPipeline

            params: dict = {}
            llm_cfg: dict = {}
            if Path("config/params.yaml").exists():
                with open("config/params.yaml", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    params = dict(cfg.get("m3_retrieval", {}))
                    params["embedding_model"] = cfg.get("m3_embedding", {}).get(
                        "model", "intfloat/multilingual-e5-small"
                    )
                    llm_cfg = cfg.get("m3_llm", {}) or {}

            chunks = build_corpus("data/processed/syllabi")
            if not chunks:
                chunks = _make_synthetic_corpus()

            bm25 = BM25Index(chunks)
            vectors_file = Path("models/vectors.npy")
            dense = DenseIndex(
                chunks,
                model_name=params.get("embedding_model", "intfloat/multilingual-e5-small"),
                vectors_path=vectors_file if vectors_file.exists() else None,
            )
            retriever = HybridRetriever(bm25, dense, params=params)
            _state["retriever"] = retriever
            _state["rag_pipeline"] = RAGPipeline(
                retriever=retriever,
                llm_provider=llm_cfg.get("provider", "gemini"),
                fallback_provider=llm_cfg.get("fallback_provider", "groq"),
                temperature=float(llm_cfg.get("temperature", 0.2)),
                max_tokens=int(llm_cfg.get("max_tokens", 512)),
                reranker_model=_state["models"].get("reranker"),
                cache_path="logs/rag_cache.json",
            )
            logger.info("Retrieval index đã build: %d chunks", len(chunks))
        except Exception as e:
            logger.warning("Không build được retrieval index: %s", e)

        # Pathway graph + planner
        try:
            from src.syllabus_core.pathway.graph import PrerequisiteGraph
            from src.syllabus_core.pathway.planner import LearningPlanner

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

    logger.info("API sẵn sàng. Models: %s", list(_state["models"].keys()))
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
# Helpers
# ---------------------------------------------------------------------------

def _classify_clo_texts(texts: list[str]) -> CLOClassifyResponse:
    """Chạy M2 Bloom classifier (hoặc rule fallback) và đọc model_version động."""
    from src.syllabus_core.models.predict import get_model_version, predict_bloom

    models = _state.get("models") or {}
    bloom_model = models.get("bloom_model")
    version = get_model_version(models, "m2_bloom_classifier", default="m2-rule-v1")

    results = []
    for text in texts:
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


def _find_course_json(course_code: str) -> dict | None:
    """Đọc file JSON chi tiết của môn học nếu có."""
    for folder in (Path("data/processed/syllabi"), Path("samples/syllabi")):
        cand = folder / f"{course_code}.json"
        if cand.exists():
            try:
                with cand.open(encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("Lỗi đọc %s: %s", cand, exc)
    return None


def _to_clo_items(raw_clos: list[dict]) -> list[CLOItem]:
    """Chuyển list dict CLO sang list[CLOItem] chuẩn schema."""
    items: list[CLOItem] = []
    for idx, c in enumerate(raw_clos, start=1):
        conf = c.get("bloom_confidence")
        if conf is None:
            conf = c.get("confidence")
        lvl_raw = c.get("level_raw")
        if lvl_raw is None:
            lvl_raw = c.get("level")
        items.append(CLOItem(
            clo_id=str(c.get("clo_id") or f"CLO{idx}"),
            text=str(c.get("text") or ""),
            bloom_level=c.get("bloom_level"),
            bloom_name=c.get("bloom_name"),
            bloom_confidence=conf,
            level_raw=lvl_raw,
        ))
    return items


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
    if req.text is not None:
        texts_to_classify = [req.text]
    elif req.texts is not None:
        texts_to_classify = req.texts
    else:
        raise HTTPException(status_code=422, detail="Cần cung cấp 'text' hoặc 'texts'")

    try:
        return _classify_clo_texts(texts_to_classify)
    except Exception as e:
        logger.error("Lỗi classify_clo: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classify-clo/batch", response_model=CLOClassifyResponse, tags=["M2 Bloom"])
async def classify_clo_batch(req: CLOClassifyBatchRequest):
    """Phân loại mức Bloom cho danh sách nhiều CLO."""
    try:
        return _classify_clo_texts(req.texts)
    except Exception as e:
        logger.error("Lỗi classify_clo_batch: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-syllabus", response_model=SyllabusAnalysisResponse, tags=["M1 Extraction"])
async def analyze_syllabus(file: UploadFile = File(...)):
    """
    Phân tích đề cương PDF: trích xuất 10 mục, gán mức Bloom cho CLO.

    Upload file PDF; trả về JSON đề cương đầy đủ.
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="Không có file được upload")

    safe_filename = Path(file.filename).name
    if not safe_filename:
        raise HTTPException(status_code=422, detail="Tên file không hợp lệ")

    ext = Path(safe_filename).suffix.lower()
    if ext not in (".pdf",):
        raise HTTPException(status_code=422, detail=f"Chỉ hỗ trợ PDF, nhận được: {ext}")

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = logs_dir / f"tmp_{time.time_ns()}_{safe_filename}"

    try:
        content = await file.read()
        tmp_path.write_bytes(content)

        from src.syllabus_core.models.predict import analyze_pdf, get_model_version

        models = _state.get("models") or {}
        result = analyze_pdf(tmp_path, models=models)
        default_ver = get_model_version(models, "m1_section_classifier", default="m1-v1.0")

        return SyllabusAnalysisResponse(
            course_code=str(result.get("course_code") or "unknown"),
            course_name=str(result.get("course_name") or "unknown"),
            credits=int(result.get("credits") or 3),
            prerequisites=list(result.get("prerequisites") or []),
            clos=_to_clo_items(result.get("clos") or []),
            sections=dict(result.get("sections") or {}),
            missing_sections=list(result.get("missing_sections") or []),
            model_version=str(result.get("model_version") or default_ver),
            processing_time_s=float(result.get("processing_time_s") or 0.0),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Lỗi analyze_syllabus: %s", e)
        raise HTTPException(status_code=422, detail=f"Không đọc được PDF: {e}")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.post("/ask", response_model=AskResponse, tags=["M3 RAG"])
async def ask(req: AskRequest):
    """
    Hỏi đáp RAG về đề cương.

    Câu hỏi tiếng Việt; trả về câu trả lời có trích dẫn nguồn [n].
    Khi LLM không khả dụng: trả HTTP 503 kèm các đoạn đã truy xuất.
    """
    if not _state.get("rag_pipeline"):
        return JSONResponse(
            status_code=503,
            content={
                "error": "Pipeline RAG chưa sẵn sàng",
                "retrieved_chunks": [],
                "retrieved": [],
            },
        )

    try:
        pipeline = _state["rag_pipeline"]
        result = pipeline.answer(req.question, filter_course=req.course_filter)

        if result.get("provider_used") == "error":
            chunks = result.get("retrieved_chunks", [])
            return JSONResponse(
                status_code=503,
                content={
                    "error": "LLM không khả dụng",
                    "retrieved_chunks": chunks,
                    "retrieved": chunks,
                },
            )

        return AskResponse(**result)
    except Exception as e:
        logger.error("Lỗi ask: %s", e)
        return JSONResponse(
            status_code=503,
            content={
                "error": str(e),
                "retrieved_chunks": [],
                "retrieved": [],
            },
        )


@app.post("/learning-path", response_model=LearningPathResponse, tags=["M4 Pathway"])
async def learning_path(req: LearningPathRequest):
    """
    Gợi ý lộ trình học.

    Nhận môn đích và danh sách môn đã học; trả về kế hoạch theo học kỳ.
    """
    if not _state.get("planner") or not _state.get("graph"):
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


@app.get("/courses", response_model=CourseListResponse, tags=["Courses"])
async def list_courses():
    """Liệt kê tất cả môn học trong đồ thị tiên quyết."""
    graph = _state.get("graph")
    if graph is None:
        raise HTTPException(status_code=503, detail="Đồ thị môn học chưa sẵn sàng")

    summaries = [
        CourseSummary(
            code=code,
            name=node.name,
            credits=node.credits,
            prerequisites=sorted(graph._reverse.get(code, set())),
            avg_bloom_level=node.avg_bloom_level,
            recommended_semester=node.recommended_semester,
        )
        for code, node in sorted(graph.nodes.items())
    ]
    return CourseListResponse(courses=summaries, total=len(summaries))


@app.get("/courses/{course_code}", response_model=CourseDetailResponse, tags=["Courses"])
async def get_course_detail(course_code: str):
    """Lấy thông tin chi tiết một môn học theo mã môn."""
    graph = _state.get("graph")
    if graph is None:
        raise HTTPException(status_code=503, detail="Đồ thị môn học chưa sẵn sàng")

    node = graph.nodes.get(course_code)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy môn học {course_code}")

    syl = _find_course_json(course_code) or {}
    clos = _to_clo_items(syl.get("clos") or [])
    sections = dict(syl.get("sections") or {})

    return CourseDetailResponse(
        code=node.code,
        name=node.name,
        credits=node.credits,
        prerequisites=sorted(graph._reverse.get(course_code, set())),
        dependents=sorted(graph.edges.get(course_code, set())),
        avg_bloom_level=node.avg_bloom_level,
        recommended_semester=node.recommended_semester,
        clos=clos,
        sections=sections,
    )
