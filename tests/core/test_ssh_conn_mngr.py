import os
from collections.abc import Generator
from subprocess import PIPE, Popen

import paramiko
import pytest

from app.core.ssh_conn_mngr import SSHConnectionManager


@pytest.fixture
def ssh_connection_manager() -> Generator[SSHConnectionManager, None, None]:
    """
    Фикстура для создания менеджера SSH подключений.

    Yields:
        Iterator[SSHConnectionManager]: Менеджер SSH подключений
    """

    manager = SSHConnectionManager('ssh_conn_manager')
    yield manager
    manager.destroy_all_connections()


def get_all_connections() -> list[str]:
    """
    Получить все активные SSH-соединения по портам 10022 и 10023.

    Returns:
        list: Список содержащий всем активные SSH-соединения
    """
    with Popen(['lsof', '-a', '-iTCP', '-p', str(os.getpid()), '-n'], stdout=PIPE, encoding='utf8') as proc:
        return [
            line
            for line in proc.stdout  # type: ignore[union-attr]
            if '->127.0.0.1:10022 (ESTABLISHED)' in line or '->127.0.0.1:10023 (ESTABLISHED)' in line
        ]


def check_has_connections() -> None:
    """Проверка что существуют активное подключение по SSH к тестовому серверу."""

    if len(get_all_connections()) == 0:
        raise AssertionError('SSH connection not found')


def check_has_not_connections() -> None:
    """Проверка что отсутствует активное подключение по SSH к тестовому серверу."""

    if len(get_all_connections()) != 0:
        raise AssertionError('SSH connection found')


def test_constructor() -> None:
    """Проверка того что создается только один менеджер SSH подключений."""

    manager1 = SSHConnectionManager('test_ssh_conn_manager_1')
    manager2 = SSHConnectionManager('test_ssh_conn_manager_2')
    assert manager1 is manager2


@pytest.mark.usefixtures('test_ssh_server')
def test_get_new_connection(ssh_connection_manager: SSHConnectionManager) -> None:
    """
    Проверка создания нового подключения по SSH к тестовому серверу.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    lease_id, connection = ssh_connection_manager.get_connection('127.0.0.1', 10022, 'test_user', 'test_password')
    assert isinstance(connection, paramiko.SSHClient)
    assert isinstance(lease_id, str)
    assert len(lease_id) == 8
    check_has_connections()


@pytest.mark.usefixtures('test_ssh_server')
def test_get_existing_connection(ssh_connection_manager: SSHConnectionManager) -> None:
    """
    Проверка того при запросе нового подключения вернется уже существующее подключения вместо создания нового.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    first_lease_id, first_connection = ssh_connection_manager.get_connection(
        '127.0.0.1', 10022, 'test_user', 'test_password'
    )
    assert isinstance(first_connection, paramiko.SSHClient)
    assert isinstance(first_lease_id, str)
    assert len(first_lease_id) == 8

    second_lease_id, second_connection = ssh_connection_manager.get_connection(
        '127.0.0.1', 10022, 'test_user', 'test_password'
    )
    assert isinstance(second_connection, paramiko.SSHClient)
    assert isinstance(second_lease_id, str)
    assert len(second_lease_id) == 8

    assert second_connection is first_connection
    assert first_lease_id != second_lease_id
    assert len(get_all_connections()) == 1


@pytest.mark.usefixtures('test_ssh_server')
def test_get_existing_connection_from_second_manager(ssh_connection_manager: SSHConnectionManager) -> None:
    """
    Проверка того при запросе нового подключения у "второго" менеджера,
    вернется уже существующее подключения вместо создания нового.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    first_lease_id, first_connection = ssh_connection_manager.get_connection(
        '127.0.0.1', 10022, 'test_user', 'test_password'
    )
    assert isinstance(first_connection, paramiko.SSHClient)
    assert isinstance(first_lease_id, str)
    assert len(first_lease_id) == 8
    check_has_connections()

    second_connection_manager = SSHConnectionManager('test_ssh_conn_manager_2')
    assert second_connection_manager is ssh_connection_manager

    second_lease_id, second_connection = second_connection_manager.get_connection(
        '127.0.0.1', 10022, 'test_user', 'test_password'
    )
    assert isinstance(second_connection, paramiko.SSHClient)
    assert isinstance(second_lease_id, str)
    assert len(second_lease_id) == 8
    assert second_connection is first_connection
    assert first_lease_id != second_lease_id
    assert len(get_all_connections()) == 1


def test_failed_get_new_connection(ssh_connection_manager: SSHConnectionManager) -> None:
    """
    Проверка создания нового подключения по SSH к недоступному серверу.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    with pytest.raises(paramiko.ssh_exception.NoValidConnectionsError):
        ssh_connection_manager.get_connection('127.0.0.1', 20022, 'test_user', 'test_password')


@pytest.mark.usefixtures('test_ssh_server')
def test_release_connection(ssh_connection_manager: SSHConnectionManager) -> None:
    """
    Проверка освобождения аренды подключения.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10022, 'test_user', 'test_password')
    ssh_connection_manager.release_connection(lease_id)
    check_has_not_connections()


@pytest.mark.usefixtures('test_ssh_server')
def test_release_two_leases(ssh_connection_manager: SSHConnectionManager) -> None:
    """
    Проверка что при освобождения аренды подключения, SSH подключение не закрывается до тех пор,
    пока не будет освобождены все аренды.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    first_lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10022, 'test_user', 'test_password')
    second_lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10022, 'test_user', 'test_password')

    ssh_connection_manager.release_connection(first_lease_id)
    check_has_connections()

    ssh_connection_manager.release_connection(second_lease_id)
    check_has_not_connections()


def test_release_non_existing_connection(ssh_connection_manager: SSHConnectionManager) -> None:
    """
    Проверка освобождения несуществующей аренды подключения.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    with pytest.raises(LookupError):
        ssh_connection_manager.release_connection('non_existing_lease_id')


@pytest.mark.usefixtures('test_ssh_server')
def test_destroy_all_connections(ssh_connection_manager: SSHConnectionManager) -> None:
    """
    Проверка закрытия всех подключений.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    first_lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10022, 'test_user', 'test_password')
    second_lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10023, 'test_user', 'test_password')
    assert len(get_all_connections()) == 2

    ssh_connection_manager.destroy_all_connections()
    check_has_not_connections()
    with pytest.raises(LookupError):
        ssh_connection_manager.release_connection(first_lease_id)
    with pytest.raises(LookupError):
        ssh_connection_manager.release_connection(second_lease_id)
