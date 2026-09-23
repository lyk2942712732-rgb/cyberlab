from datetime import timedelta
from unittest.mock import Mock
import pytest
from app.core.db import utcnow
from app.models import LabSession
from app.orchestrator.metrics import ResourceMonitor, summarize
from app.orchestrator.docker_runtime import DockerRuntime
from app.orchestrator.models import RuntimeFailure


def sample(total=100, system=1000, rx=200):
    return {"cpu_stats": {"cpu_usage": {"total_usage": total}, "system_cpu_usage": system, "online_cpus": 4},
            "memory_stats": {"usage": 512, "stats": {"inactive_file": 128}},
            "networks": {"eth0": {"rx_bytes": rx, "tx_bytes": 100}}, "pids_stats": {"current": 12}}


ATTRS = {"State": {"Running": True, "Status": "running", "Health": {"Status": "healthy"}},
         "HostConfig": {"NanoCpus": 2_000_000_000, "Memory": 1024, "PidsLimit": 512},
         "Config": {"Env": ["LAB_FLAG=secret"]}}


def test_delta_and_limits():
    first, prior = summarize(ATTRS, sample(), now=10)
    assert first["cpu_percent"] is None
    result, _ = summarize(ATTRS, sample(300, 2000, 500), prior, now=15)
    assert result["cpu_percent"] == 80
    assert result["cpu_limit_percent"] == 40
    assert result["memory_bytes"] == 384
    assert result["memory_percent"] == 37.5
    assert result["network_rx_bytes_per_second"] == 60
    assert "secret" not in str(result)


def test_missing_and_reset_counters():
    _, prior = summarize(ATTRS, sample(), now=10)
    result, _ = summarize({"State": {"Running": True}, "HostConfig": {}}, sample(1, 2, 3), prior, now=15)
    assert result["cpu_percent"] is None
    assert result["network_rx_bytes_per_second"] is None
    assert result["health"] == "not_configured"
    stopped, _ = summarize({"State": {"Running": False, "OOMKilled": True}}, {}, now=20)
    assert stopped["health"] == "stopped" and stopped["oom_killed"]
    assert stopped["memory_bytes"] is None


def test_cache_invalidation_and_failures():
    runtime = Mock()
    runtime.resource_snapshot.return_value = ATTRS, sample()
    monitor = ResourceMonitor(runtime)
    items = [("KALI", "one", False)]
    assert monitor.collect("session", 0, items) == monitor.collect("session", 0, items)
    assert runtime.resource_snapshot.call_count == 1
    monitor.collect("session", 1, items)
    assert runtime.resource_snapshot.call_count == 2
    removed = monitor.collect("session", 1, [("KALI", "one", True)])
    assert removed["instances"][0]["status"] == "removed"
    runtime.resource_snapshot.side_effect = RuntimeError("sensitive Docker details")
    failed = monitor.collect("session", 2, items)
    assert failed["instances"][0]["available"] is False
    assert "sensitive" not in str(failed)


def test_container_ownership_is_checked_before_stats():
    container = Mock(labels={"cyberlab.managed": "true", "cyberlab.session": "other"})
    client = Mock()
    client.containers.get.return_value = container
    with pytest.raises(RuntimeFailure):
        DockerRuntime(client).resource_snapshot("container", "session")
    container.stats.assert_not_called()


def test_metrics_endpoint_ownership(client, db, users, headers, lab, monkeypatch):
    session = LabSession(user_id=users["student01"].id, lab_template_id=lab.id, expires_at=utcnow() + timedelta(hours=1))
    db.add(session); db.commit()
    fetch = Mock(return_value={"instances": []})
    monkeypatch.setattr("app.api.sessions.OrchestratorClient.session_metrics", fetch)
    path = f"/api/lab-sessions/{session.id}/metrics"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers["student02"]).status_code == 404
    fetch.assert_not_called()
    assert client.get(path, headers=headers["student01"]).status_code == 200
    assert client.get(path, headers=headers["admin"]).status_code == 200
