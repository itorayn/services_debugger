import logging
import string
from collections.abc import Generator
from contextlib import contextmanager
from random import choices
from threading import Lock

import paramiko

from .singleton import SingletonMeta


class SSHConnectionManager(metaclass=SingletonMeta):
    """
    Менеджер SSH подключений. Выполняет следующие функции:
        - создание и выдача SSH подключений;
        - освобождение SSH подключений;
        - контроль выданных SSH подключений.
    В классе SSHConnectionManager используется паттерн "одиночка",
    может быть создан только один менеджер SSH подключений.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._logger = logging.getLogger(self.name)
        self._logger.info('Start init new SSHConnectionManager')
        self._ssh_lock = Lock()
        self._connections: dict[tuple[str, int], paramiko.SSHClient] = {}
        self._leases: dict[str, tuple[str, int]] = {}

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name={self.name!r})'

    def get_random_lease_id(self) -> str:
        """
        Создание случайного и уникального идентификатора аренды.

        Returns:
            str: Идентификатор аренды
        """

        lease_id = ''.join(choices(string.ascii_uppercase + string.digits, k=8))
        if lease_id in self._leases:
            return self.get_random_lease_id()
        return lease_id

    def get_connection(
        self, address: str, port: str | int, username: str, password: str
    ) -> tuple[str, paramiko.SSHClient]:
        """
        Создание нового SSH подключения,
        если подключение по указанному адресу и порту уже было ранее создано,
        то будет использоваться существующее подключение.

        Args:
            address (str): Адрес удаленной стороны к которой необходимо создать SSH подключение
            port (Union[str, int]): SSH порт удаленной стороны
            username (str): Имя пользователя
            password (str): Пароль пользователя

        Returns:
            Tuple[str, paramiko.SSHClient]: Кортеж из идентификатора аренды подключения
                                            и непосредственно само SSH подключение
        """

        self._logger.info(f'Request new SSH connection: {username}:{password}@{address}:{port}')
        with self._ssh_lock:
            self._logger.debug(f'Open connections: {self._connections}')
            self._logger.debug(f'Active leases: {self._leases}')
            lease_id = self.get_random_lease_id()
            if (address, int(port)) in self._connections:
                # Get existing connection
                conn = self._connections[(address, int(port))]
            else:
                # Create new connection
                conn = self._create_ssh_connection(address, port, username, password)
                self._connections[(address, int(port))] = conn
            self._logger.info(f'Create new lease connection: {lease_id}, connection: {(address, int(port))}')
            self._leases[lease_id] = (address, int(port))

        return lease_id, conn

    def _create_ssh_connection(self, address: str, port: str | int, username: str, password: str) -> paramiko.SSHClient:
        self._logger.info(f'Create new SSH connection: {username}:{password}@{address}:{port}')
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=address, username=username, password=password, port=int(port))
        return ssh_client

    def release_connection(self, lease_id: str) -> None:
        """
        Освобождение SSH подключения по идентификатору аренды,
        если подключение используется несколькими элементами,
        т.е. для данного имеется как минимум еще одна аренда то подключение не закрывается.

        Args:
            lease_id (str): Идентификатор аренды

        Raises:
            LookupError: Возникает в случае если передан аннулированный
                         или неправильный идентификатор аренды
        """

        self._logger.info(f'Release connection with lease_id: {lease_id}')
        self._logger.debug(f'Open connections: {self._connections}')
        self._logger.debug(f'Active leases: {self._leases}')

        if lease_id not in self._leases:
            raise LookupError(f'Failed to find the lease ID {lease_id} in lease list')

        released_connection = self._leases.pop(lease_id)

        for leased_connection in self._leases.values():
            if leased_connection == released_connection:
                break
        else:
            self._destroy_connection(*released_connection)

    def _destroy_connection(self, address: str, port: str | int) -> None:
        destroyed_connection = (address, int(port))
        self._logger.info(f'Close connection: {destroyed_connection}')

        if destroyed_connection not in self._connections:
            raise LookupError(f'Failed to find the connection {destroyed_connection} in connection list')
        conn = self._connections.pop(destroyed_connection)
        conn.close()

    def destroy_all_connections(self) -> None:
        """Закрытие всех SSH подключений и аннулирование всех аренд."""

        self._logger.info('Destroy all connections')
        self._logger.debug(f'Open connections: {self._connections}')
        self._logger.debug(f'Active leases: {self._leases}')

        for conn in self._connections.values():
            conn.close()

        self._connections.clear()
        self._leases.clear()

    @contextmanager
    def connection(
        self, address: str, port: str | int, username: str, password: str
    ) -> Generator[paramiko.SSHClient, None, None]:
        """
        Контекстный менеджер подключения. При входе в контекст создает SSH подключение,
        а при выходе из контекста освобождает аренду подключения.

        Args:
            address (str): Адрес удаленной стороны к которой необходимо создать SSH подключение
            port (Union[str, int]): SSH порт удаленной стороны
            username (str): Имя пользователя
            password (str): Пароль пользователя

        Yields:
            paramiko.SSHClient: SSH подключение
        """

        lease_id, conn = self.get_connection(address, port, username, password)
        yield conn
        self.release_connection(lease_id)

    def __del__(self) -> None:
        self.destroy_all_connections()
