import asyncio
import contextlib
import json
import logging
from fastapi import APIRouter, WebSocket
from websockets.asyncio.client import connect
from app.core.config import settings
from app.core.desktop import validate_claims, validate_desktop
from app.core.limits import cache

router = APIRouter(tags=["Desktop"])
log = logging.getLogger(__name__)


@router.websocket("/lab-sessions/{identifier}/desktop")
async def desktop(websocket: WebSocket, identifier: str):
    # The bearer ticket is sent as the first message, never put in URLs/access logs.
    if websocket.headers.get("origin") != settings().public_origin:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    tasks = []
    lease_key = None
    lease_owner = ""
    try:
        payload = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        if len(payload) > 4096:
            raise ValueError("ticket too large")
        ticket = json.loads(payload)["ticket"]
        claims, _ = await asyncio.to_thread(validate_desktop, identifier, ticket)
        consumed = await asyncio.to_thread(cache().set, f"desktop-used:{claims['jti']}", "1", nx=True, ex=150)
        if not consumed:
            raise ValueError("ticket already used")
        lease_owner = claims["jti"]
        # At most an embedded desktop and one pop-out window per Session.
        for slot in range(2):
            candidate = f"desktop-connection:{identifier}:{slot}"
            if await asyncio.to_thread(cache().set, candidate, lease_owner, nx=True, ex=30):
                lease_key = candidate
                break
        if lease_key is None:
            raise ValueError("too many desktop connections")
        async with connect(
            f"{settings().orchestrator_url}/internal/sessions/{identifier}/desktop",
            additional_headers={"Authorization": f"Bearer {settings().orchestrator_secret}", "X-Desktop-Ticket": ticket},
            max_size=16 * 1024 * 1024, open_timeout=15, ping_interval=20,
        ) as upstream:
            await websocket.send_json({"ready": True})

            async def outbound():
                while True:
                    await upstream.send(await websocket.receive_bytes())

            async def inbound():
                async for data in upstream:
                    if isinstance(data, bytes):
                        await websocket.send_bytes(data)

            async def guard():
                while True:
                    await asyncio.sleep(2)
                    await asyncio.to_thread(validate_claims, identifier, claims)
                    renewed = await asyncio.to_thread(cache().eval, "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('EXPIRE',KEYS[1],30) end; return 0", 1, lease_key, lease_owner)
                    if not renewed:
                        raise ValueError("desktop connection lease expired")

            tasks = [asyncio.create_task(f()) for f in (outbound, inbound, guard)]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
    except Exception:
        # Avoid logging credentials, frame contents, submitted flags or backend URLs.
        log.info("Desktop connection closed session=%s", identifier)
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if lease_key:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(cache().eval, "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) end; return 0", 1, lease_key, lease_owner)
        with contextlib.suppress(Exception):
            await websocket.close(code=1000)
