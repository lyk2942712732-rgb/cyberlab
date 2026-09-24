"""Forward native receipts through the authentication wrapper in the pinned snapshot."""
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
old = '''@dataclass
class _GatedInputReservation:
    """A native input reservation that holds the privacy boundary open."""

    reservation: EventReservation | WindowActionReservation
    retention: Any


@dataclass(frozen=True)
class _SuppressedInputReservation:
    """Marker returned when a protected interval drops native input."""
'''
new = '''@dataclass
class _GatedInputReservation:
    """A native input reservation that holds the privacy boundary open."""

    reservation: EventReservation | WindowActionReservation
    retention: Any
    _released: bool = False

    @property
    def finished(self) -> bool:
        return self.reservation.finished

    def release(self) -> None:
        if not self._released:
            self._released = True
            self.retention.release()

    def fail(self, error: BaseException) -> None:
        try:
            self.reservation.fail(error)
        finally:
            self.release()


@dataclass(frozen=True)
class _SuppressedInputReservation:
    """Marker returned when a protected interval drops native input."""

    @property
    def finished(self) -> bool:
        return True

    def fail(self, error: BaseException) -> None:
        pass
'''
old_release = "                reservation.retention.release()"
if source.count(old) != 1 or source.count(old_release) != 1:
    raise SystemExit("Pinned input receipt source differs; patch refused")
path.write_text(source.replace(old, new).replace(old_release, "                reservation.release()"))
print("Applied native-receipt-forwarding-v1")
