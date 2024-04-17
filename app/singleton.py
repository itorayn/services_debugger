from threading import Lock


class Singleton:
    """Потокобезопасная реализация класса Singleton (Одиночка)."""

    _instance = None
    _lock: Lock = Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not isinstance(cls._instance, cls):
                cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance
