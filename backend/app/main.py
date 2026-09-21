import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from app.api import admin, auth, catalog, desktop, sessions
from app.core.db import SessionLocal
from app.core.limits import cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="CyberLab API", version="0.1.0")
app.include_router(auth.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(desktop.router, prefix="/api")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    error = exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail}
    return JSONResponse({"error": error}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse({"error": {"message": "请求参数不合法", "fields": [{"loc": e["loc"], "message": e["msg"]} for e in exc.errors()]}}, status_code=422)


@app.exception_handler(IntegrityError)
async def conflict(request: Request, exc: IntegrityError):
    return JSONResponse({"error": {"message": "记录重复或仍被其他数据引用"}}, status_code=409)


@app.exception_handler(OperationalError)
async def database_busy(request: Request, exc: OperationalError):
    return JSONResponse({"error": {"message": "服务繁忙，请稍后重试"}}, status_code=503)


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled API error")
    return JSONResponse({"error": {"message": "服务暂时异常，请稍后重试"}}, status_code=500)


@app.get("/api/health")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    cache().ping()
    return {"data": {"status": "ok"}}
