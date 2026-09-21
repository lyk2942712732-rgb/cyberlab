import httpx
from fastapi import HTTPException
from app.core.config import settings


class OrchestratorClient:
    """Platform-side transport: the backend never imports or calls Docker SDK."""

    def delete_image(self, identifier: str) -> dict:
        base = settings().orchestrator_url.replace("ws://", "http://").replace("wss://", "https://")
        try:
            response = httpx.delete(f"{base}/internal/images/{identifier}", headers={"Authorization": f"Bearer {settings().orchestrator_secret}"}, timeout=30)
        except httpx.HTTPError:
            raise HTTPException(503, "实验编排服务不可用，请稍后重试") from None
        if not response.is_success:
            try:
                detail = response.json().get("detail", "镜像删除失败")
            except ValueError:
                detail = "镜像删除失败"
            raise HTTPException(response.status_code, detail)
        return response.json()["data"]
