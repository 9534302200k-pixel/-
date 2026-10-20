import asyncio
import hmac
import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .config import ROOT, settings, MODELS
from .db import init_db, rows, db, now, company
from .seed import seed
from .ingest import import_csv, import_pdf, add_event, TOPIC_NAMES
from .retrieval import feed, profile, ROLE_NAMES
from .sources import refresh_sources, import_url, OFFICIAL_HOSTS, FEEDS
from .agent import analyze, AgentError, budget_day

logger = logging.getLogger("business-pulse")
refresh_lock = asyncio.Lock()
import_lock = asyncio.Lock()
analyze_slots = asyncio.Semaphore(2)
requests_by_ip = defaultdict(deque)


async def poller():
    while True:
        await asyncio.sleep(max(5, settings.news_poll_minutes) * 60)
        async with refresh_lock:
            await refresh_sources()


@asynccontextmanager
async def lifespan(app):
    init_db()
    if settings.demo_mode:
        seed()
    task = asyncio.create_task(poller())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Бизнес Пульс · Альфа Хак", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def security(request: Request, call_next):
    if int(request.headers.get("content-length", "0") or 0) > 260_000_000:
        return JSONResponse({"detail": "Слишком большой запрос"}, status_code=413)
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        auth = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if settings.app_access_token and not hmac.compare_digest(
            auth, settings.app_access_token
        ):
            return JSONResponse(
                {"detail": "Требуется код доступа к демонстрации"}, status_code=401
            )
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse(
                    {"detail": "Запрос с другого сайта отклонён"}, status_code=403
                )
            client = request.client.host if request.client else "unknown"
            queue = requests_by_ip[client]
            t = time.monotonic()
            while queue and queue[0] < t - 60:
                queue.popleft()
            if len(queue) >= 30:
                return JSONResponse(
                    {"detail": "Слишком много запросов. Повторите через минуту."},
                    status_code=429,
                )
            queue.append(t)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'"
    )
    return response


@app.exception_handler(AgentError)
async def agent_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(KeyError)
async def missing_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.get("/api/health")
def health():
    with db() as c:
        c.execute("SELECT 1").fetchone()
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/status")
def status():
    counts = {
        t: rows(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"]
        for t in ["companies", "events", "documents", "payments", "runs"]
    }
    real = {
        t: rows(f"SELECT COUNT(*) AS n FROM {t} WHERE synthetic=0")[0]["n"]
        for t in ["companies", "events", "documents"]
    }
    usage = rows(
        """SELECT COUNT(*) AS calls,COALESCE(SUM(input_tokens),0) AS input_tokens,COALESCE(SUM(output_tokens),0) AS output_tokens,
      COALESCE(SUM(CASE WHEN status='done' THEN actual ELSE reserved END),0) AS charged_or_reserved_rub FROM usage WHERE day=?""",
        (budget_day(),),
    )[0]
    return {
        "counts": counts,
        "real_counts": real,
        "model_ready": settings.model_ready,
        "model_family": settings.llm_model_family if settings.model_ready else None,
        "allowed_models": MODELS,
        "usage": usage,
        "daily_budget_rub": min(500, settings.daily_budget_rub),
        "sources": rows("SELECT * FROM source_status"),
        "demo_mode": settings.demo_mode,
        "access_protected": bool(settings.app_access_token),
        "revenue_unit_confirmed": settings.revenue_unit_confirmed,
        "roles": ROLE_NAMES,
        "topics": TOPIC_NAMES,
        "official_hosts": sorted(OFFICIAL_HOSTS),
    }


@app.get("/api/companies")
def companies(q: str = "", limit: int = 50, large_only: bool = False):
    limit = max(1, min(200, limit))
    query = "SELECT id,name,sector,region,revenue,credit,fts,synthetic,conflicts FROM companies WHERE (casefold(name) LIKE casefold(?) OR casefold(id) LIKE casefold(?) OR casefold(sector) LIKE casefold(?))"
    args = ["%" + q[:120] + "%"] * 3
    if large_only:
        if not settings.revenue_unit_confirmed:
            query += " AND synthetic=1 AND revenue>15000000000"
        else:
            query += " AND revenue>15000000000"
    query += " ORDER BY synthetic ASC,revenue DESC LIMIT ?"
    return rows(query, (*args, limit))


@app.get("/api/companies/{company_id}")
def get_profile(company_id: str):
    return profile(company_id)


@app.get("/api/feed")
def get_feed(
    company_id: str,
    role: Literal["cfo", "ceo", "treasurer"] = "cfo",
    topic: str = "",
    bookmarked: bool = False,
):
    return feed(company_id, role, topic, bookmarked)


class AnalysisRequest(BaseModel):
    company_id: str = Field(max_length=160)
    event_id: str = Field(max_length=100)
    role: Literal["cfo", "ceo", "treasurer"] = "cfo"
    question: str = Field(default="", max_length=1500)
    force: bool = False
    parent_id: str | None = None


@app.post("/api/analyze")
async def do_analyze(body: AnalysisRequest):
    async with analyze_slots:
        try:
            return await analyze(**body.model_dump())
        except AgentError as exc:
            with db() as c:
                c.execute(
                    "INSERT INTO failures(company_id,event_id,role,created,message) VALUES(?,?,?,?,?)",
                    (body.company_id, body.event_id, body.role, now(), str(exc)),
                )
            raise


class FeedbackRequest(BaseModel):
    run_id: str
    rating: Literal[-1, 1]
    reason: str = Field(default="", max_length=1000)


@app.post("/api/feedback")
def feedback(body: FeedbackRequest):
    if not rows("SELECT id FROM runs WHERE id=?", (body.run_id,)):
        raise HTTPException(404, "Анализ не найден")
    with db() as c:
        c.execute(
            "INSERT INTO feedback(run_id,rating,reason,created) VALUES(?,?,?,?)",
            (body.run_id, body.rating, body.reason, now()),
        )
    return {"saved": True}


class Bookmark(BaseModel):
    company_id: str
    event_id: str
    enabled: bool


@app.post("/api/bookmarks")
def bookmark(body: Bookmark):
    company(body.company_id)
    if not rows("SELECT id FROM events WHERE id=?", (body.event_id,)):
        raise HTTPException(404, "Событие не найдено")
    with db() as c:
        if body.enabled:
            c.execute(
                "INSERT OR IGNORE INTO bookmarks VALUES(?,?)",
                (body.company_id, body.event_id),
            )
        else:
            c.execute(
                "DELETE FROM bookmarks WHERE company_id=? AND event_id=?",
                (body.company_id, body.event_id),
            )
    return {"saved": True}


@app.post("/api/sources/refresh")
async def refresh():
    if refresh_lock.locked():
        raise HTTPException(409, "Обновление уже выполняется")
    async with refresh_lock:
        return await refresh_sources()


class URLImport(BaseModel):
    url: str = Field(max_length=2000)
    published: str | None = None


@app.post("/api/events/url")
async def event_url(body: URLImport):
    try:
        return await import_url(body.url, body.published)
    except (ValueError, AgentError):
        raise
    except Exception:
        raise HTTPException(
            502, "Официальный источник недоступен. Проверьте сетевую политику и адрес."
        )


class TextImport(BaseModel):
    title: str = Field(min_length=10, max_length=300)
    body: str = Field(min_length=80, max_length=30000)
    published: str


@app.post("/api/events/test")
def event_test(body: TextImport):
    # Pasted texts are always marked synthetic/unverified; cannot impersonate a bank/source.
    return {
        "id": add_event(
            body.title,
            body.body,
            "",
            "Тестовый материал пользователя",
            body.published,
            True,
        )
    }


@app.get("/api/documents")
def documents():
    return rows(
        "SELECT d.*,COUNT(c.id) AS chunks,MAX(c.page) AS pages,SUM(c.ocr) AS ocr_chunks FROM documents d LEFT JOIN chunks c ON c.document_id=d.id GROUP BY d.id ORDER BY synthetic,published DESC"
    )


class DocumentMetadata(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    published: str


@app.post("/api/documents/{document_id}/metadata")
def document_metadata(document_id: str, body: DocumentMetadata):
    published = date.fromisoformat(body.published).isoformat()
    if published > date.today().isoformat():
        raise ValueError("Дата материала находится в будущем")
    with db() as c:
        if not c.execute(
            "SELECT id FROM documents WHERE id=?", (document_id,)
        ).fetchone():
            raise HTTPException(404, "Документ не найден")
        c.execute(
            "UPDATE documents SET title=?,published=? WHERE id=?",
            (body.title, published, document_id),
        )
    return {"saved": True}


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: str):
    found = rows("SELECT filename FROM documents WHERE id=?", (document_id,))
    if not found or not found[0]["filename"]:
        raise HTTPException(404, "PDF отсутствует: это учебный текст")
    path = settings.data_dir / "documents" / Path(found[0]["filename"]).name
    if not path.is_file():
        raise HTTPException(404, "PDF не найден")
    return FileResponse(path, media_type="application/pdf")


@app.post("/api/import")
async def upload(
    kind: Literal["companies", "payments", "links", "bank"] = Form(...),
    file: UploadFile = File(...),
    title: str = Form(""),
    published: str = Form(""),
    url: str = Form(""),
):
    if import_lock.locked():
        raise HTTPException(409, "Другой импорт уже выполняется")
    async with import_lock:
        with TemporaryDirectory() as temp:
            path = Path(temp) / (
                "upload.pdf"
                if kind == "bank"
                else Path(file.filename or "upload.csv").name
            )
            total = 0
            with path.open("wb") as dest:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > 250_000_000:
                        raise HTTPException(413, "Максимальный размер — 250 МБ")
                    dest.write(chunk)
            if kind == "bank":
                result = await asyncio.to_thread(
                    import_pdf, path, title or file.filename, published or None, url
                )
            else:
                result = await asyncio.to_thread(import_csv, path, kind)
    return result


class Scenario(BaseModel):
    principal: float = Field(gt=0, le=1e15)
    delta_pp: float = Field(ge=-100, le=100)
    months: float = Field(gt=0, le=120)


@app.post("/api/scenario")
def scenario(body: Scenario):
    return {
        "annual_delta": round(body.principal * body.delta_pp / 100, 2),
        "period_delta": round(
            body.principal * body.delta_pp / 100 * body.months / 12, 2
        ),
        "assumptions": [
            "Параметры введены пользователем, а не извлечены из клиентской базы.",
            "Неизменный основной долг; новая ставка действует весь выбранный период.",
            "Комиссии, погашение, налоги и сложные проценты не учитываются.",
        ],
        "currency": "Валюта введённой суммы",
    }


@app.get("/api/metrics")
def metrics():
    runs = rows(
        "SELECT id,company_id,event_id,role,created,elapsed_ms,mode,result FROM runs ORDER BY created DESC LIMIT 200"
    )
    times = sorted(r["elapsed_ms"] for r in runs)
    modes = {m: sum(r["mode"] == m for r in runs) for m in ["llm", "rules"]}
    feedback = rows("SELECT rating,COUNT(*) AS count FROM feedback GROUP BY rating")
    for r in runs:
        result = json.loads(r.pop("result"))
        r["synthetic"] = result["synthetic"]
        r["trace"] = result["trace"]
    return {
        "runs": runs,
        "latency": {
            "median_ms": times[len(times) // 2] if times else None,
            "p95_ms": times[min(len(times) - 1, int(len(times) * 0.95))]
            if times
            else None,
        },
        "modes": modes,
        "feedback": feedback,
        "failures": rows("SELECT * FROM failures ORDER BY created DESC LIMIT 100"),
        "quality_note": "Релевантность и смысловая точность требуют экспертной разметки. Автоматическая проверка ссылок не доказывает истинность вывода.",
    }


dist = ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
