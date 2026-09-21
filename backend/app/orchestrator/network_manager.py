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
        for container in containers:
            try:
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
