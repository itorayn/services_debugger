from threading import Lock
from typing import Any, ClassVar, TypeVar

T = TypeVar('T', bound=object)


class SingletonMeta[T](type):
    """Потокобезопасная реализация класса Singleton (Одиночка)."""

    _instances: ClassVar[dict[type[T], T]] = {}
    _lock: Lock = Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> T:  # noqa: ANN401
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)

        return cls._instances[cls]
