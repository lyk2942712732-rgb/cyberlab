from dataclasses import dataclass, field


@dataclass
class ContainerSpec:
    name: str
    image: str
    network_id: str
    instance_type: str
    session_id: str
    cpu: float
    memory_mb: int
    environment: dict[str, str] = field(default_factory=dict)
    # Warm pool desktops park on a private network and journal directory until
    # a session claims them; labels are immutable, so ownership moves via DB.
    parked: bool = False
    slot: str | None = None


@dataclass
class ContainerInfo:
    id: str
    name: str
    ip_address: str
    status: str
    healthy: bool


@dataclass
class ImageInfo:
    id: str
    repository: str
    tag: str
    size: int
    repo_digest: str | None = None


class RuntimeFailure(Exception):
    """A runtime error safe for display, without daemon credentials/host paths."""


class ProvisionCancelled(RuntimeFailure):
    """A stop request or expiry interrupted provisioning."""


class ImageInUse(RuntimeFailure):
    """An image cannot be removed while containers still reference it."""
