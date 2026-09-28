import asyncio
import logging
from urllib.parse import quote
from fastapi import APIRouter, Header, HTTPException, Request, Response
from sqlalchemy import select
from app.core.db import SessionLocal
from app.core.desktop import validate_desktop
from app.core.limits import cache
from app.models import LabInstance

router = APIRouter(tags=["Desktop"])
log = logging.getLogger(__name__)


@router.get("/desktop/verify")
async def verify(request: Request, ticket: str = Header(default="", alias="X-Desktop-Ticket")):
    """One-shot ticket gate for nginx auth_request; never proxies pixel data.

    The desktop stream itself now goes browser -> nginx -> websockify inside the
    Kali container, so this endpoint only re-validates the signed ticket and
    marks it consumed. It returns 204 with the container's DNS name for nginx
    to proxy to, or 4xx which auth_request turns into a rejected upgrade.
    """
    identifier = request.query_params.get("identifier", "")
    if not identifier or not ticket or len(ticket) > 4096:
        raise HTTPException(401, "桌面访问凭证无效")
    try:
        claims, runtime_id = await asyncio.to_thread(validate_desktop, identifier, ticket)
        consumed = cache().set(f"desktop-used:{claims['jti']}", "1", nx=True, ex=300)
        if not consumed:
            raise HTTPException(401, "桌面访问凭证已被使用")
    except HTTPException:
        # auth_request only looks at the status code; keep logs credential-free.
        log.info("Desktop ticket rejected session=%s", identifier[:8])
        raise
    with SessionLocal() as db:
        instance = db.scalar(select(LabInstance).where(LabInstance.runtime_id == runtime_id))
        if not instance or not instance.container_name:
            raise HTTPException(409, "桌面实例不可用")
        name = instance.container_name
    return Response(status_code=204, headers={"X-Desktop-Container": quote(name, safe="")})


