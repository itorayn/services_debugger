import os
from subprocess import Popen, PIPE

import pytest
import paramiko
# from gi.repository import Gio

from app.ssh_conn_mngr import SSHConnectionManager


@pytest.fixture()
def ssh_connection_manager() -> SSHConnectionManager:
    """
    Фикстура для создания менеджера SSH подключений.

    Yields:
        Iterator[SSHConnectionManager]: Менеджер SSH подключений
    """

    manager = SSHConnectionManager('ssh_conn_manager')
    yield manager
    manager.destroy_all_connections()


def get_all_connections() -> list:
    """
    Получить все активные SSH-соединения по портам 10022 и 10023.

    Returns:
        list: Список содержащий всем активные SSH-соединения
    """
    connections = []
    with Popen(['lsof', '-a', '-iTCP', '-p', str(os.getpid()), '-n'], stdout=PIPE, encoding='utf8') as proc:
        for line in proc.stdout:
            if '->127.0.0.1:10022 (ESTABLISHED)' in line:
                connections.append(line)
            elif '->127.0.0.1:10023 (ESTABLISHED)' in line:
                connections.append(line)
    return connections


def check_has_connections():
    """Проверка что существуют активное подключение по SSH к тестовому серверу."""

    if len(get_all_connections()) == 0:
        assert False, 'SSH connection not found'


def check_has_not_connections():
    """Проверка что отсутствует активное подключение по SSH к тестовому серверу."""

    if len(get_all_connections()) != 0:
        assert False, 'SSH connection found'


def test_constructor():
    """Проверка того что создается только один менеджер SSH подключений."""

    # pylint: disable-next=protected-access
    if SSHConnectionManager._instance is not None:
        # pylint: disable-next=protected-access
        SSHConnectionManager._instance = None

    manager1 = SSHConnectionManager('test_ssh_conn_manager_1')
    manager2 = SSHConnectionManager('test_ssh_conn_manager_2')
    assert manager1 is manager2
    assert manager2.name == 'test_ssh_conn_manager_1'


@pytest.mark.usefixtures('test_ssh_server')
def test_get_new_connection(ssh_connection_manager: SSHConnectionManager):
    """
    Проверка создания нового подключения по SSH к тестовому серверу.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    lease_id, connection = ssh_connection_manager.get_connection('127.0.0.1', 10022, 'test_user', 'test_password')
    assert isinstance(connection, paramiko.SSHClient)
    assert isinstance(lease_id, str) and len(lease_id) == 8
    check_has_connections()


@pytest.mark.usefixtures('test_ssh_server')
def test_get_existing_connection(ssh_connection_manager: SSHConnectionManager):
    """
    Проверка того при запросе нового подключения вернется уже существующее подключения вместо создания нового.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    first_lease_id, first_connection = ssh_connection_manager.get_connection('127.0.0.1', 10022,
                                                                             'test_user', 'test_password')
    assert isinstance(first_connection, paramiko.SSHClient)
    assert isinstance(first_lease_id, str) and len(first_lease_id) == 8

    second_lease_id, second_connection = ssh_connection_manager.get_connection('127.0.0.1', 10022,
                                                                               'test_user', 'test_password')
    assert isinstance(second_connection, paramiko.SSHClient)
    assert isinstance(second_lease_id, str) and len(second_lease_id) == 8

    assert second_connection is first_connection
    assert first_lease_id != second_lease_id
    assert len(get_all_connections()) == 1


@pytest.mark.usefixtures('test_ssh_server')
def test_get_existing_connection_from_second_manager(ssh_connection_manager: SSHConnectionManager):
    """
    Проверка того при запросе нового подключения у "второго" менеджера,
    вернется уже существующее подключения вместо создания нового.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    first_lease_id, first_connection = ssh_connection_manager.get_connection('127.0.0.1', 10022,
                                                                             'test_user', 'test_password')
    assert isinstance(first_connection, paramiko.SSHClient)
    assert isinstance(first_lease_id, str) and len(first_lease_id) == 8
    check_has_connections()

    second_connection_manager = SSHConnectionManager('test_ssh_conn_manager_2')
    assert second_connection_manager is ssh_connection_manager

    second_lease_id, second_connection = second_connection_manager.get_connection('127.0.0.1', 10022,
                                                                                  'test_user', 'test_password')
    assert isinstance(second_connection, paramiko.SSHClient)
    assert isinstance(second_lease_id, str) and len(second_lease_id) == 8
    assert second_connection is first_connection
    assert first_lease_id != second_lease_id
    assert len(get_all_connections()) == 1


def test_failed_get_new_connection(ssh_connection_manager: SSHConnectionManager):
    """
    Проверка создания нового подключения по SSH к недоступному серверу.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    with pytest.raises(Exception):
        ssh_connection_manager.get_connection('127.0.0.1', 20022, 'test_user', 'test_password')


@pytest.mark.usefixtures('test_ssh_server')
def test_release_connection(ssh_connection_manager: SSHConnectionManager):
    """
    Проверка освобождения аренды подключения.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10022, 'test_user', 'test_password')
    ssh_connection_manager.release_connection(lease_id)
    check_has_not_connections()


@pytest.mark.usefixtures('test_ssh_server')
def test_release_two_leases(ssh_connection_manager: SSHConnectionManager):
    """
    Проверка что при освобождения аренды подключения, SSH подключение не закрывается до тех пор,
    пока не будет освобождены все аренды.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    first_lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10022,
                                                              'test_user', 'test_password')
    second_lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10022,
                                                               'test_user', 'test_password')

    ssh_connection_manager.release_connection(first_lease_id)
    check_has_connections()

    ssh_connection_manager.release_connection(second_lease_id)
    check_has_not_connections()


def test_release_non_existing_connection(ssh_connection_manager: SSHConnectionManager):
    """
    Проверка освобождения несуществующей аренды подключения.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    with pytest.raises(LookupError):
        ssh_connection_manager.release_connection('non_existing_lease_id')


@pytest.mark.usefixtures('test_ssh_server')
def test_destroy_all_connections(ssh_connection_manager: SSHConnectionManager):
    """
    Проверка закрытия всех подключений.

    Args:
        ssh_connection_manager (SSHConnectionManager): Менеджер SSH подключений
    """

    first_lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10022,
                                                              'test_user', 'test_password')
    second_lease_id, _ = ssh_connection_manager.get_connection('127.0.0.1', 10023,
                                                               'test_user', 'test_password')
    assert len(get_all_connections()) == 2

    ssh_connection_manager.destroy_all_connections()
    check_has_not_connections()
    with pytest.raises(LookupError):
        ssh_connection_manager.release_connection(first_lease_id)
    with pytest.raises(LookupError):
        ssh_connection_manager.release_connection(second_lease_id)
