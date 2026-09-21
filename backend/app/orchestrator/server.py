import asyncio
import contextlib
import hmac
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, WebSocket
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.desktop import validate_claims, validate_desktop
from app.orchestrator.docker_runtime import DockerRuntime
from app.orchestrator.lab_orchestrator import LabOrchestrator
from app.orchestrator.image_manager import ImageManager
from app.orchestrator.worker import Worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = await asyncio.to_thread(DockerRuntime)
    app.state.runtime = runtime
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


@app.websocket("/internal/sessions/{identifier}/desktop")
async def desktop(websocket: WebSocket, identifier: str):
    expected = f"Bearer {settings().orchestrator_secret}"
    if not hmac.compare_digest(websocket.headers.get("authorization", ""), expected):
        await websocket.close(code=1008)
        return
    channel = None
    tasks = []
    try:
        claims, container = await asyncio.to_thread(validate_desktop, identifier, websocket.headers.get("x-desktop-ticket", ""))
        channel = await asyncio.to_thread(app.state.runtime.open_console, container)
        await websocket.accept()

        async def read():
            while data := await asyncio.to_thread(channel.read):
                await websocket.send_bytes(data)

        async def write():
            while True:
                await asyncio.to_thread(channel.write, await websocket.receive_bytes())

        async def guard():
            while True:
                await asyncio.sleep(2)
                await asyncio.to_thread(validate_claims, identifier, claims)

        tasks = [asyncio.create_task(f()) for f in (read, write, guard)]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except Exception:
        log.info("Private desktop closed session=%s", identifier)
    finally:
        if channel:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(channel.close)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        with contextlib.suppress(Exception):
            await websocket.close()
