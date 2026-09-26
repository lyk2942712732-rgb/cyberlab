"""On-demand Docker counters. No exec probes, host process lists or environment data."""
import threading
import time
from app.orchestrator.activity import state as activity_state
from datetime import datetime, timezone


def summarize(attrs, stats, previous=None, now=None):
    now = time.monotonic() if now is None else now
    state, limits = attrs.get("State", {}), attrs.get("HostConfig", {})
    cpu = stats.get("cpu_stats", {})
    total = cpu.get("cpu_usage", {}).get("total_usage", 0)
    system = cpu.get("system_cpu_usage", 0)
    cores = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage", [])) or 1
    network = stats.get("networks", {})
    rx = sum(n.get("rx_bytes", 0) for n in network.values()) if network else None
    tx = sum(n.get("tx_bytes", 0) for n in network.values()) if network else None
    current = {"time": now, "cpu": total, "system": system, "rx": rx, "tx": tx}
    cpu_percent = rx_rate = tx_rate = None
    if previous and now > previous["time"]:
        delta_cpu, delta_system = total - previous["cpu"], system - previous["system"]
        if delta_system > 0 and delta_cpu >= 0:
            cpu_percent = round(delta_cpu / delta_system * cores * 100, 2)
        elapsed = now - previous["time"]
        if rx is not None and previous["rx"] is not None and rx >= previous["rx"]:
            rx_rate = round((rx - previous["rx"]) / elapsed)
        if tx is not None and previous["tx"] is not None and tx >= previous["tx"]:
            tx_rate = round((tx - previous["tx"]) / elapsed)
    memory = stats.get("memory_stats", {})
    cache = memory.get("stats", {}).get("inactive_file", memory.get("stats", {}).get("total_inactive_file", 0))
    used = max(0, memory["usage"] - cache) if "usage" in memory else None
    memory_limit = limits.get("Memory") or memory.get("limit") or None
    cpu_limit = limits.get("NanoCpus", 0) / 1e9 or None
    if cpu_limit is None and limits.get("CpuQuota", 0) > 0:
        cpu_limit = limits["CpuQuota"] / (limits.get("CpuPeriod") or 100000)
    uptime = None
    try:
        if state.get("Running"):
            started = datetime.fromisoformat(state["StartedAt"].replace("Z", "+00:00"))
            uptime = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    except (KeyError, ValueError):
        pass
    health = state.get("Health", {}).get("Status", "not_configured") if state.get("Running") else "stopped"
    result = {
        "status": state.get("Status", "unknown"), "health": health,
        "oom_killed": bool(state.get("OOMKilled")), "uptime_seconds": uptime,
        "cpu_percent": cpu_percent, "cpu_limit": cpu_limit,
        "cpu_limit_percent": round(cpu_percent / cpu_limit, 2) if cpu_percent is not None and cpu_limit else None,
        "memory_bytes": used, "memory_limit_bytes": memory_limit,
        "memory_percent": round(used / memory_limit * 100, 2) if used is not None and memory_limit else None,
        "pids": stats.get("pids_stats", {}).get("current"), "pids_limit": limits.get("PidsLimit"),
        "network_rx_bytes": rx, "network_tx_bytes": tx,
        "network_rx_bytes_per_second": rx_rate, "network_tx_bytes_per_second": tx_rate,
    }
    return result, current


class ResourceMonitor:
    def __init__(self, runtime):
        self.runtime = runtime
        self._lock = threading.Lock()
        self._sessions = {}
        self._previous = {}

    def collect(self, identifier, generation, instances):
        with self._lock:
            now = time.monotonic()
            # Bound memory even if many completed sessions have been viewed.
            self._sessions = {k: v for k, v in self._sessions.items() if now - v[0] < 60}
            self._previous = {k: v for k, v in self._previous.items() if now - v["time"] < 60}
            key = (identifier, generation, tuple(instances))
            cached = self._sessions.get(key)
            if cached and now - cached[0] < 5:
                return cached[1]
            rows = []
            for kind, runtime_id, removed in instances:
                row = {"instance_type": kind, "available": False}
                if removed:
                    row.update(status="removed", health="stopped")
                else:
                    try:
                        attrs, stats = self.runtime.resource_snapshot(runtime_id, identifier)
                        values, current = summarize(attrs, stats, self._previous.get(runtime_id))
                        self._previous[runtime_id] = current
                        row.update(values, available=True)
                    except Exception:
                        row.update(status="unknown", health="unknown", error="暂时无法读取实例指标")
                rows.append(row)
            try:
                activity = activity_state(identifier)
            except ValueError:
                activity = {"status": "unavailable"}
            result = {"sampled_at": datetime.now(timezone.utc).isoformat(), "interval_seconds": 5, "instances": rows, "activity": activity}
            self._sessions[key] = (time.monotonic(), result)
            return result
