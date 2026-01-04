import os
import re
import time
from collections.abc import Generator
from contextlib import suppress

import pytest
from scapy.all import ICMP, rdpcap

from app.models.task import Task
from app.task_mngr import TaskManager


@pytest.fixture(scope='session')
def task_manager() -> Generator[TaskManager, None, None]:
    """
    Фикстура для создания тестового менеджера задач.

    Yields:
        Iterator[TaskManager]: Менеджер задач
    """

    manager = TaskManager('task_mngr')
    manager.start()

    yield manager

    manager.stop()


@pytest.fixture(autouse=True)
def remove_artifacts() -> Generator[None, None, None]:
    """
    Фикстура для удаления артифактов теста.
    """

    yield

    for filename in ('test_dump.pcap', 'ping.log'):
        with suppress(FileNotFoundError):
            os.remove(filename)


def check_captured_pcap_file() -> None:
    """Проверка файла 'test_dump.pcap'."""

    assert os.path.isfile('test_dump.pcap')
    assert os.path.getsize('test_dump.pcap') > 0

    pcap = rdpcap('test_dump.pcap')
    assert len(pcap) > 0
    ping_requests = [pkt for pkt in pcap if ICMP in pkt and pkt.payload['ICMP'].type == 8]
    assert len(ping_requests) >= 4


def check_captured_log_file() -> None:
    """Проверка файла 'ping.log'."""

    assert os.path.isfile('ping.log')
    assert os.path.getsize('ping.log') > 0

    count_ping = 0
    with open('ping.log', encoding='utf8') as log_file:
        for line in log_file:
            if re.match(r'64 bytes from 127\.0\.0\.1: seq=\d+ ttl=64 time=\d+\.\d{3} ms', line):
                count_ping += 1
            else:
                raise AssertionError(f'Unmatched line: {line}')
    assert count_ping >= 4


@pytest.mark.usefixtures('test_ssh_server')
def test_start_pcap_dump(task_manager: TaskManager) -> None:
    """
    Проверка запуска удаленного сниффера траффика.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    task_info = task_manager.start_pcap_dump(
        address='127.0.0.1', port=10022, username='test_user', password='test_password', output_file='test_dump.pcap'
    )
    assert isinstance(task_info, Task)
    assert task_info.name.endswith(f'pcap_{task_info.task_id}')
    assert task_info.task_type == 'pcap_dump'
    assert task_info.is_alive is True

    time.sleep(5)

    task_manager.stop_task(task_info.task_id)
    check_captured_pcap_file()


@pytest.mark.usefixtures('test_ssh_server')
def test_get_task_info(task_manager: TaskManager) -> None:
    """
    Проверка получения информации о запущенной задаче.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    task_info = task_manager.start_pcap_dump(
        address='127.0.0.1', port=10022, username='test_user', password='test_password', output_file='test_dump.pcap'
    )
    assert isinstance(task_info, Task)
    assert task_info.name.endswith(f'pcap_{task_info.task_id}')
    assert task_info.task_type == 'pcap_dump'
    assert task_info.is_alive is True
    task_id = task_info.task_id

    time.sleep(1)

    task_info = task_manager.get_task_info(task_id)
    assert isinstance(task_info, Task)
    assert isinstance(task_info.name, str)
    assert task_info.name.endswith(f'pcap_{task_id}')
    assert task_info.task_id == task_id
    assert task_info.task_type == 'pcap_dump'
    assert task_info.is_alive is True

    task_manager.stop_task(task_id)

    with pytest.raises(LookupError) as e_info:
        task_manager.get_task_info(task_id)
    assert str(e_info.value) == f'Task with id="{task_id}" not found in task list.'


def test_get_task_info_non_existing_task(task_manager: TaskManager) -> None:
    """
    Проверка получения информации о несуществующей задаче.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    with pytest.raises(LookupError) as e_info:
        task_manager.get_task_info('yhsf76ha')
    assert str(e_info.value) == 'Task with id="yhsf76ha" not found in task list.'


@pytest.mark.usefixtures('test_ssh_server')
def test_start_log_dump(task_manager: TaskManager) -> None:
    """
    Проверка запуска удаленного сниффера логов.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    task_info = task_manager.start_log_dump(
        address='127.0.0.1',
        port=10022,
        username='test_user',
        password='test_password',
        output_file='ping.log',
        dumped_file='/tmp/ping.log',
    )
    assert isinstance(task_info, Task)
    assert task_info.name.endswith(f'log_{task_info.task_id}')
    assert task_info.task_type == 'log_dump'
    assert task_info.is_alive is True

    time.sleep(5)

    task_manager.stop_task(task_info.task_id)
    check_captured_log_file()


@pytest.mark.usefixtures('test_ssh_server')
def test_stop_task(task_manager: TaskManager) -> None:
    """
    Проверка завершения выполнения задачи.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    task_info = task_manager.start_log_dump(
        address='127.0.0.1',
        port=10022,
        username='test_user',
        password='test_password',
        output_file='ping.log',
        dumped_file='/tmp/ping.log',
    )

    time.sleep(5)

    task_info = task_manager.stop_task(task_info.task_id)
    assert isinstance(task_info, Task)
    assert task_info.name.endswith(f'log_{task_info.task_id}')
    assert task_info.task_type == 'log_dump'
    assert task_info.is_alive is False
    check_captured_log_file()


def test_stop_non_existing_task(task_manager: TaskManager) -> None:
    """
    Проверка завершения выполнения несуществующий задачи.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    with pytest.raises(LookupError) as e_info:
        task_manager.stop_task('yhsf76ha')
    assert str(e_info.value) == 'Task with id="yhsf76ha" not found in task list.'


@pytest.mark.usefixtures('test_ssh_server')
def test_start_two_task(task_manager: TaskManager) -> None:
    """
    Проверка работы двух задач одновременно.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    log_dump_task_info = task_manager.start_log_dump(
        address='127.0.0.1',
        port=10022,
        username='test_user',
        password='test_password',
        output_file='ping.log',
        dumped_file='/tmp/ping.log',
    )
    assert isinstance(log_dump_task_info, Task)
    assert log_dump_task_info.is_alive is True

    pcap_dump_task_info = task_manager.start_pcap_dump(
        address='127.0.0.1', port=10022, username='test_user', password='test_password', output_file='test_dump.pcap'
    )
    assert isinstance(pcap_dump_task_info, Task)
    assert pcap_dump_task_info.is_alive is True

    time.sleep(5)

    task_manager.stop_task(log_dump_task_info.task_id)
    task_manager.stop_task(pcap_dump_task_info.task_id)

    check_captured_log_file()
    check_captured_pcap_file()


@pytest.mark.usefixtures('test_ssh_server')
def test_get_all_tasks(task_manager: TaskManager) -> None:
    """
    Проверка получения информации о всех запущенных задачах.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    log_dump_task_id = task_manager.start_log_dump(
        address='127.0.0.1',
        port=10022,
        username='test_user',
        password='test_password',
        output_file='ping.log',
        dumped_file='/tmp/ping.log',
    ).task_id
    tasks = task_manager.get_all_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    log_dump_task_info = tasks[0]
    assert isinstance(log_dump_task_info, Task)
    assert isinstance(log_dump_task_info.name, str)
    assert log_dump_task_info.name.endswith(f'log_{log_dump_task_id}')
    assert log_dump_task_info.task_type == 'log_dump'
    assert log_dump_task_info.task_id == log_dump_task_id
    assert log_dump_task_info.is_alive is True

    time.sleep(1)

    pcap_dump_task_id = task_manager.start_pcap_dump(
        address='127.0.0.1', port=10022, username='test_user', password='test_password', output_file='test_dump.pcap'
    ).task_id
    tasks = task_manager.get_all_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 2
    log_dump_task_info = tasks[0]
    assert isinstance(log_dump_task_info, Task)
    assert isinstance(log_dump_task_info.name, str)
    assert log_dump_task_info.name.endswith(f'log_{log_dump_task_id}')
    assert log_dump_task_info.task_id == log_dump_task_id
    assert log_dump_task_info.task_type == 'log_dump'
    assert log_dump_task_info.is_alive is True
    pcap_dump_task_info = tasks[1]
    assert isinstance(pcap_dump_task_info, Task)
    assert isinstance(pcap_dump_task_info.name, str)
    assert pcap_dump_task_info.name.endswith(f'pcap_{pcap_dump_task_id}')
    assert pcap_dump_task_info.task_id == pcap_dump_task_id
    assert pcap_dump_task_info.task_type == 'pcap_dump'
    assert pcap_dump_task_info.is_alive is True

    time.sleep(1)

    task_manager.stop_task(log_dump_task_id)
    tasks = task_manager.get_all_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    pcap_dump_task_info = tasks[0]
    assert isinstance(pcap_dump_task_info, Task)
    assert isinstance(pcap_dump_task_info.name, str)
    assert pcap_dump_task_info.name.endswith(f'pcap_{pcap_dump_task_id}')
    assert pcap_dump_task_info.task_id == pcap_dump_task_id
    assert pcap_dump_task_info.task_type == 'pcap_dump'
    assert pcap_dump_task_info.is_alive is True

    task_manager.stop_task(pcap_dump_task_id)
    tasks = task_manager.get_all_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 0
