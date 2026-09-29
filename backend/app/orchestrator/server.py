import asyncio
import hmac
import logging
import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Query
from app.core.config import settings
from app.core.db import SessionLocal
from app.orchestrator.docker_runtime import DockerRuntime
from app.orchestrator.lab_orchestrator import LabOrchestrator
from app.orchestrator.image_manager import ImageManager
from app.orchestrator.worker import Worker
from app.orchestrator.metrics import ResourceMonitor
from app.models import LabInstance, LabSession
from sqlalchemy import select
from app.orchestrator.activity import events as activity_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = await asyncio.to_thread(DockerRuntime)
    app.state.runtime = runtime
    app.state.metrics = ResourceMonitor(await asyncio.to_thread(DockerRuntime, timeout=3))
    worker = Worker(LabOrchestrator(runtime))

    async def loop(operation):
        while True:
            try:
                await asyncio.to_thread(operation)
            except Exception:
                log.exception("Worker iteration failed; durable commands will retry")
            await asyncio.sleep(settings().worker_interval)

    tasks = [asyncio.create_task(loop(operation)) for operation in (worker.tick, worker.import_tick)]
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    worker.close()
    # In-flight synchronous Docker calls finish or are recovered from DB/labels on restart.


app = FastAPI(title="CyberLab private orchestrator", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.delete("/internal/images/{identifier}")
def delete_image(identifier: str, authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, f"Bearer {settings().orchestrator_secret}"):
        raise HTTPException(403, "拒绝访问")
    with SessionLocal() as db:
        return {"data": ImageManager(app.state.runtime).delete(db, identifier)}


@app.get("/internal/sessions/{identifier}/metrics")
def metrics(identifier: str, authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, f"Bearer {settings().orchestrator_secret}"):
        raise HTTPException(403, "拒绝访问")
    with SessionLocal() as db:
        session = db.get(LabSession, identifier)
        if not session:
            raise HTTPException(404, "实验实例不存在")
        instances = [(i.instance_type, i.runtime_id, i.status == "removed") for i in
                     db.scalars(select(LabInstance).where(LabInstance.session_id == identifier))]
        return {"data": app.state.metrics.collect(identifier, session.generation, instances)}


@app.get("/internal/sessions/{identifier}/activity")
def activity(identifier: str, generation: int | None = Query(default=None, ge=0), after: int = Query(default=0, ge=0), authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, f"Bearer {settings().orchestrator_secret}"):
        raise HTTPException(403, "拒绝访问")
    with SessionLocal() as db:
        if not db.get(LabSession, identifier):
            raise HTTPException(404, "实验实例不存在")
    try:
        return {"data": activity_events(identifier, generation, after)}
    except (ValueError, OSError, sqlite3.Error):
        raise HTTPException(503, "操作记录暂时无法读取") from None


