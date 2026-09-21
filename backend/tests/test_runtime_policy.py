import socket
import struct
from unittest.mock import MagicMock
from docker.errors import APIError
import pytest
from app.orchestrator.docker_runtime import DockerConsole, DockerRuntime
from app.orchestrator.models import ContainerSpec, ImageInUse


def test_docker_network_has_no_external_gateway_or_control_plane_attachment():
    client = MagicMock()
    runtime = DockerRuntime(client)
    runtime.create_network("safe-uuid")
    options = client.networks.create.call_args.kwargs
    assert options["internal"] is True and options["driver"] == "bridge"
    assert options["options"]["com.docker.network.bridge.gateway_mode_ipv4"] == "isolated"


@pytest.mark.parametrize("kind", ["KALI", "TARGET"])
def test_container_policy_cannot_be_overridden_by_image(kind):
    client = MagicMock()
    runtime = DockerRuntime(client)
    runtime.create_container(ContainerSpec("safe-name", "sha256:fixed", "isolated-net", kind, "session-uuid", 1.25, 512))
    options = client.containers.create.call_args.kwargs
    assert options["image"] == "sha256:fixed"
    assert options["network"] == "isolated-net" and options["privileged"] is False
    assert options["nano_cpus"] == 1_250_000_000 and options["mem_limit"] == "512m"
    assert options["pids_limit"] == 256 and options["cap_drop"] == ["ALL"]
    assert options["security_opt"] == ["no-new-privileges:true"]
    assert not any(key in options for key in ("volumes", "mounts", "ports", "devices", "network_mode"))


def test_image_removal_never_uses_force():
    client = MagicMock()
    client.containers.list.return_value = []
    DockerRuntime(client).remove_image("sha256:target")
    assert client.images.remove.call_args.kwargs["force"] is False


def test_docker_delete_conflict_maps_to_image_in_use():
    client = MagicMock()
    client.containers.list.return_value = []
    response = MagicMock(status_code=409)
    client.images.remove.side_effect = APIError("conflict", response=response)
    with pytest.raises(ImageInUse):
        DockerRuntime(client).remove_image("sha256:target")


def test_console_demultiplexes_binary_stdout_without_stderr():
    left, right = socket.socketpair()
    channel = DockerConsole(left)
    try:
        stderr = b"do not expose this"
        vnc = b"RFB 003.008\n\x00\xff"
        right.sendall(bytes([2, 0, 0, 0]) + struct.pack(">I", len(stderr)) + stderr)
        right.sendall(bytes([1, 0, 0, 0]) + struct.pack(">I", len(vnc)) + vnc)
        assert channel.read() == vnc
        channel.write(b"\x00\x01\xff")
        assert right.recv(3) == b"\x00\x01\xff"
    finally:
        channel.close(); right.close()
