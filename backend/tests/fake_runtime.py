import uuid
from app.core.config import settings
from app.orchestrator.models import ContainerInfo, ContainerSpec, ImageInfo, ImageInUse, RuntimeFailure


class FakeRuntime:
    """Deterministic test double, never used as a production runtime."""
    def __init__(self):
        self.images = {"sha256:target", settings().kali_image}
        self.networks: dict[str, str] = {}
        self.containers: dict[str, ContainerSpec] = {}
        self.states: dict[str, str] = {}
        self.fail_on_type: str | None = None
        self.fail_cleanup = False
        self.loaded: list[str] = []
        self.removed_images: list[str] = []

    def create_network(self, session_id: str) -> str:
        identifier = str(uuid.uuid4())
        self.networks[identifier] = session_id
        return identifier

    def delete_network(self, identifier: str) -> None:
        if self.fail_cleanup:
            raise RuntimeFailure("engine unavailable")
        self.networks.pop(identifier, None)

    def create_container(self, spec: ContainerSpec) -> str:
        if spec.instance_type == self.fail_on_type:
            raise RuntimeFailure("injected creation failure")
        identifier = str(uuid.uuid4())
        self.containers[identifier], self.states[identifier] = spec, "created"
        return identifier

    def start_container(self, identifier: str) -> None:
        self.states[identifier] = "running"

    def stop_container(self, identifier: str) -> None:
        self.states[identifier] = "exited"

    def delete_container(self, identifier: str) -> None:
        if self.fail_cleanup:
            raise RuntimeFailure("engine unavailable")
        self.containers.pop(identifier, None)
        self.states.pop(identifier, None)

    def inspect_container(self, identifier: str) -> ContainerInfo:
        spec = self.containers[identifier]
        state = self.states[identifier]
        return ContainerInfo(identifier, spec.name, "10.20.0.10" if spec.instance_type == "KALI" else "10.20.0.20", state, state == "running")

    def probe_target(self, kali_id: str, target_ip: str, target_port: int) -> bool:
        return self.states.get(kali_id) == "running" and target_port == 8000

    def image_exists(self, image: str) -> bool:
        return image in self.images

    def load_image(self, path: str) -> ImageInfo:
        self.loaded.append(path)
        self.images.add("sha256:uploaded")
        return ImageInfo("sha256:uploaded", "teaching/target", "v1", 123456, None)

    def image_in_use(self, image_id: str) -> bool:
        return any(c.image == image_id for c in self.containers.values())

    def remove_image(self, image_id: str) -> None:
        if self.image_in_use(image_id):
            raise ImageInUse("still used")
        self.images.discard(image_id)
        self.removed_images.append(image_id)

    def session_resources(self, session_id: str) -> tuple[list[str], list[str]]:
        return ([k for k, v in self.containers.items() if v.session_id == session_id], [k for k, v in self.networks.items() if v == session_id])

    def managed_session_ids(self) -> set[str]:
        return set(self.networks.values()) | {c.session_id for c in self.containers.values()}

    def open_console(self, container_id: str):
        raise NotImplementedError("desktop wire protocol is covered by the Docker integration checklist")
