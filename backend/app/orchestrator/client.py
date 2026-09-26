import httpx
from fastapi import HTTPException
from app.core.config import settings


class OrchestratorClient:
    """Platform-side transport: the backend never imports or calls Docker SDK."""

    def session_metrics(self, identifier: str) -> dict:
        base = settings().orchestrator_url.replace("ws://", "http://").replace("wss://", "https://")
        try:
            response = httpx.get(f"{base}/internal/sessions/{identifier}/metrics",
                                 headers={"Authorization": f"Bearer {settings().orchestrator_secret}"}, timeout=15)
            response.raise_for_status()
            return response.json()["data"]
        except (httpx.HTTPError, ValueError, KeyError):
            raise HTTPException(503, "资源监控暂时不可用，实验可以继续") from None

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

    def session_activity(self, identifier: str, generation: int | None, after: int) -> dict:
        base = settings().orchestrator_url.replace("ws://", "http://").replace("wss://", "https://")
        params = {"after": after}
        if generation is not None:
            params["generation"] = generation
        try:
            response = httpx.get(f"{base}/internal/sessions/{identifier}/activity", params=params,
                                 headers={"Authorization": f"Bearer {settings().orchestrator_secret}"}, timeout=10)
            response.raise_for_status()
            return response.json()["data"]
        except (httpx.HTTPError, ValueError, KeyError):
            raise HTTPException(503, "操作记录暂时无法读取") from None
