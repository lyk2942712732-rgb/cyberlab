from app.orchestrator.base import RuntimeProvider


class NetworkManager:
    def __init__(self, runtime: RuntimeProvider):
        self.runtime = runtime

    def create(self, session_id: str) -> str:
        return self.runtime.create_network(session_id)

    def cleanup(self, session_id: str) -> None:
        # Labels also recover resources created just before a process crash/DB rollback.
        containers, networks = self.runtime.session_resources(session_id)
        errors = []
        # A claimed warm desktop keeps its parking-slot session label, so the
        # label scan cannot see it; the stop path passes its runtime id here.
        for container in containers:
            if not self.runtime.owns_container(container, session_id):
                continue
            try:
                self.runtime.disconnect_desktop(container)
                self.runtime.delete_container(container)
            except Exception as exc:
                errors.append(exc)
        for network in networks:
            try:
                self.runtime.delete_network(network)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[0]
