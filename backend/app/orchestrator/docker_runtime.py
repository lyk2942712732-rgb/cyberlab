import logging
import socket
import struct
from pathlib import Path
import docker
from docker.errors import APIError, ImageNotFound, NotFound
from app.orchestrator.models import ContainerInfo, ContainerSpec, ImageInfo, ImageInUse, RuntimeFailure

log = logging.getLogger(__name__)
MANAGED = {"cyberlab.managed": "true"}
SESSION_LABEL = "cyberlab.session"

# This fixed program only forwards stdin/stdout to the loopback VNC socket inside Kali.
# It accepts no user commands, hostnames, paths or ports.
VNC_RELAY = """
import os, select, socket, sys
s = socket.create_connection(('127.0.0.1', 5901), timeout=10)
s.settimeout(None)
while True:
    ready, _, _ = select.select([s, sys.stdin.buffer], [], [])
    if s in ready:
        data = s.recv(65536)
        if not data: break
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    if sys.stdin.buffer in ready:
        data = os.read(0, 65536)
        if not data: break
        s.sendall(data)
s.close()
"""


class DockerConsole:
    """Decode Docker's non-TTY multiplexing without altering binary VNC data."""

    def __init__(self, connection):
        self.connection = connection
        self.socket = getattr(connection, "_sock", connection)
        self.socket.settimeout(None)

    def _exact(self, length: int) -> bytes:
        result = bytearray()
        while len(result) < length:
            chunk = self.socket.recv(length - len(result))
            if not chunk:
                return b""
            result.extend(chunk)
        return bytes(result)

    def read(self) -> bytes:
        while header := self._exact(8):
            stream, length = header[0], struct.unpack(">I", header[4:])[0]
            if length > 16 * 1024 * 1024:
                raise RuntimeFailure("桌面数据帧过大")
            data = self._exact(length)
            if stream == 1 and data:
                return data
            if not data and length:
                return b""
            # stderr is never mixed into the VNC protocol or returned to browsers.
        return b""

    def write(self, data: bytes) -> None:
        self.socket.sendall(data)

    def close(self) -> None:
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.connection.close()


class DockerRuntime:
    def __init__(self, client=None, timeout=120):
        self.client = client or docker.from_env(timeout=timeout)

    def resource_snapshot(self, container_id: str, session_id: str) -> tuple[dict, dict]:
        obj = self._container(container_id)
        if obj.labels.get(SESSION_LABEL) != session_id:
            raise RuntimeFailure("实例不属于当前实验")
        attrs = obj.attrs
        stats = obj.stats(stream=False, one_shot=True) if attrs["State"].get("Running") else {}
        return attrs, stats

    def _container(self, identifier: str):
        obj = self.client.containers.get(identifier)
        if obj.labels.get("cyberlab.managed") != "true":
            raise RuntimeFailure("拒绝操作非 CyberLab 容器")
        return obj

    def create_network(self, session_id: str) -> str:
        network = self.client.networks.create(
            name=f"lab-net-{session_id}", driver="bridge", internal=True,
            labels={**MANAGED, SESSION_LABEL: session_id},
            options={"com.docker.network.bridge.gateway_mode_ipv4": "isolated", "com.docker.network.bridge.enable_icc": "true"},
        )
        return network.id

    def delete_network(self, network_id: str) -> None:
        try:
            network = self.client.networks.get(network_id)
            if network.attrs.get("Labels", {}).get("cyberlab.managed") != "true":
                raise RuntimeFailure("拒绝操作非 CyberLab 网络")
            network.remove()
        except NotFound:
            pass

    def create_container(self, spec: ContainerSpec) -> str:
        if not self.image_exists(spec.image):
            raise RuntimeFailure("实验所需镜像不存在，请联系教学管理员")
        container = self.client.containers.create(
            image=spec.image, name=spec.name, network=spec.network_id,
            labels={**MANAGED, SESSION_LABEL: spec.session_id, "cyberlab.type": spec.instance_type},
            environment=spec.environment, detach=True, init=True,
            nano_cpus=int(spec.cpu * 1_000_000_000), mem_limit=f"{spec.memory_mb}m",
            # Firefox uses many threads, all counted by the pids cgroup.
            # Keep a bounded desktop allowance separate from small targets.
            memswap_limit=f"{spec.memory_mb}m", pids_limit=512 if spec.instance_type == "KALI" else 256,
            cap_drop=["ALL"], cap_add=["NET_RAW"] if spec.instance_type == "KALI" else [],
            security_opt=["no-new-privileges:true"], privileged=False,
            dns=["127.0.0.1"], shm_size="256m", restart_policy={"Name": "no"},
            log_config=docker.types.LogConfig(type="json-file", config={"max-size": "10m", "max-file": "2"}),
            # Deliberately no host mounts, devices, published ports or extra networks.
        )
        return container.id

    def start_container(self, container_id: str) -> None:
        self._container(container_id).start()

    def stop_container(self, container_id: str) -> None:
        try:
            self._container(container_id).stop(timeout=5)
        except NotFound:
            pass

    def delete_container(self, container_id: str) -> None:
        try:
            self._container(container_id).remove(force=True, v=True)
        except NotFound:
            pass

    def inspect_container(self, container_id: str) -> ContainerInfo:
        obj = self._container(container_id)
        state = obj.attrs["State"]
        networks = obj.attrs["NetworkSettings"]["Networks"]
        ip = next((v.get("IPAddress", "") for v in networks.values()), "")
        health = state.get("Health", {}).get("Status")
        # Imported targets without HEALTHCHECK are ready when their main process runs.
        healthy = state.get("Running", False) and health in (None, "healthy")
        return ContainerInfo(obj.id, obj.name, ip, obj.status, healthy)

    def image_exists(self, image: str) -> bool:
        try:
            self.client.images.get(image)
            return True
        except ImageNotFound:
            return False

    def probe_target(self, kali_id: str, target_ip: str, target_port: int) -> bool:
        script = "import socket,sys; s=socket.create_connection((sys.argv[1],int(sys.argv[2])),2); s.close()"
        result = self._container(kali_id).exec_run(["python3", "-c", script, target_ip, str(target_port)])
        return result.exit_code == 0

    def load_image(self, path: str) -> ImageInfo:
        # Docker SDK forwards this file object without buffering a whole tar in RAM.
        # load restores CMD/ENTRYPOINT/ENV/layers/tags; rootfs import is never used.
        with Path(path).open("rb") as stream:
            loaded = self.client.images.load(stream)
        unique = {item.id: item for item in loaded}
        if len(unique) != 1:
            raise RuntimeFailure("每个 tar 必须只包含一个靶机镜像")
        obj = next(iter(unique.values()))
        obj.reload()
        tag = sorted(obj.tags)[0] if obj.tags else ""
        repository, _, version = tag.rpartition(":")
        digest = next(iter(obj.attrs.get("RepoDigests") or []), None)
        return ImageInfo(obj.id, repository, version, int(obj.attrs["Size"]), digest)

    def image_in_use(self, image_id: str) -> bool:
        return bool(self.client.containers.list(all=True, filters={"ancestor": image_id}))

    def remove_image(self, image_id: str) -> None:
        if self.image_in_use(image_id):
            raise ImageInUse("镜像仍被容器使用，请先停止并删除相关实例")
        try:
            self.client.images.remove(image=image_id, force=False, noprune=True)
        except ImageNotFound:
            pass
        except APIError as exc:
            if exc.status_code == 409:
                raise ImageInUse("镜像仍有关联容器、子镜像或其他标签，Docker 拒绝删除") from None
            raise

    def session_resources(self, session_id: str) -> tuple[list[str], list[str]]:
        filters = {"label": ["cyberlab.managed=true", f"{SESSION_LABEL}={session_id}"]}
        return ([c.id for c in self.client.containers.list(all=True, filters=filters)], [n.id for n in self.client.networks.list(filters=filters)])

    def managed_session_ids(self) -> set[str]:
        objects = self.client.containers.list(all=True, filters={"label": "cyberlab.managed=true"})
        networks = self.client.networks.list(filters={"label": "cyberlab.managed=true"})
        return {x for x in [*(c.labels.get(SESSION_LABEL) for c in objects), *(n.attrs.get("Labels", {}).get(SESSION_LABEL) for n in networks)] if x}

    def open_console(self, container_id: str) -> DockerConsole:
        obj = self._container(container_id)
        if obj.labels.get("cyberlab.type") != "KALI":
            raise RuntimeFailure("此实例不支持桌面连接")
        executable = self.client.api.exec_create(obj.id, ["python3", "-u", "-c", VNC_RELAY], stdin=True, stdout=True, stderr=True, tty=False)
        connection = self.client.api.exec_start(executable["Id"], socket=True, tty=False)
        return DockerConsole(connection)
