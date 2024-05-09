import os
import time
import re

import pytest
from scapy.all import rdpcap, ICMP  # pylint: disable=no-name-in-module

from app.task_mngr import TaskManager


@pytest.fixture(scope='session')
def task_manager() -> TaskManager:
    """
    Фикстура для создания тестового менеджера задач.

    Yields:
        Iterator[TaskManager]: Менеджер задач
    """

    manager = TaskManager('task_mngr')
    manager.start()

    yield manager

    manager.stop()


@pytest.mark.usefixtures('test_ssh_server')
def test_start_pcap_dump(task_manager: TaskManager):
    """
    Проверка запуска удаленного сниффера траффика.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    message, task_id = task_manager.start_pcap_dump(address='127.0.0.1', port=10022,
                                                    username='test_user', password='test_password',
                                                    output_file='test_dump.pcap')
    assert message == 'Successfully started'
    assert isinstance(task_id, str) and len(task_id) == 8
    time.sleep(5)
    task_manager.stop_task(task_id)

    assert os.path.isfile('test_dump.pcap')
    assert os.path.getsize('test_dump.pcap') > 0

    pcap = rdpcap('test_dump.pcap')
    assert len(pcap) > 0
    ping_requests = [pkt for pkt in pcap if ICMP in pkt and pkt.payload['ICMP'].type == 8]
    assert len(ping_requests) >= 4

    os.remove('test_dump.pcap')


@pytest.mark.usefixtures('test_ssh_server')
def test_get_task_info(task_manager: TaskManager):
    """
    Проверка получения информации о запущенной задаче.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    _, task_id = task_manager.start_pcap_dump(address='127.0.0.1', port=10022,
                                              username='test_user', password='test_password',
                                              output_file='test_dump.pcap')
    assert isinstance(task_id, str) and len(task_id) == 8

    time.sleep(1)

    task_info = task_manager.get_task_info(task_id)
    assert isinstance(task_info['name'], str) and task_info['name'].endswith(f'pcap_{task_id}')
    assert task_info['task_id'] == task_id
    assert task_info['is_alive'] is True

    task_manager.stop_task(task_id)
    os.remove('test_dump.pcap')

    with pytest.raises(Exception) as e_info:
        task_manager.get_task_info(task_id)
    assert str(e_info.value) == f'Task with id="{task_id}" not found in task list.'


def test_get_task_info_non_existing_task(task_manager: TaskManager):
    """
    Проверка получения информации о несуществующей задаче.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    with pytest.raises(Exception) as e_info:
        task_manager.get_task_info('yhsf76ha')
    assert str(e_info.value) == 'Task with id="yhsf76ha" not found in task list.'


@pytest.mark.usefixtures('test_ssh_server')
def test_start_log_dump(task_manager: TaskManager):
    """
    Проверка запуска удаленного сниффера логов.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    message, task_id = task_manager.start_log_dump(address='127.0.0.1', port=10022,
                                                   username='test_user', password='test_password',
                                                   output_file='ping.log', dumped_file='/tmp/ping.log')
    assert message == 'Successfully started'
    assert isinstance(task_id, str) and len(task_id) == 8
    time.sleep(5)
    task_manager.stop_task(task_id)

    assert os.path.isfile('ping.log')
    assert os.path.getsize('ping.log') > 0

    count_ping = 0
    with open('ping.log', 'rt', encoding='utf8') as log_file:
        for line in log_file:
            if re.match(r'64 bytes from 127\.0\.0\.1: seq=\d+ ttl=64 time=\d+\.\d{3} ms', line):
                count_ping += 1
            else:
                assert False, f'Unmatched line: {line}'
    assert count_ping >= 4
    os.remove('ping.log')


def test_stop_non_existing_task(task_manager: TaskManager):
    """
    Проверка завершения выполнения несуществующий задачи.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    with pytest.raises(Exception) as e_info:
        task_manager.stop_task('yhsf76ha')
    assert str(e_info.value) == 'Task with id="yhsf76ha" not found in task list.'


@pytest.mark.usefixtures('test_ssh_server')
def test_start_two_task(task_manager: TaskManager):
    """
    Проверка работы двух задач одновременно.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    message, log_dump_task_id = task_manager.start_log_dump(address='127.0.0.1', port=10022,
                                                            username='test_user', password='test_password',
                                                            output_file='ping.log', dumped_file='/tmp/ping.log')
    assert message == 'Successfully started'
    assert isinstance(log_dump_task_id, str) and len(log_dump_task_id) == 8

    message, pcap_dump_task_id = task_manager.start_pcap_dump(address='127.0.0.1', port=10022,
                                                              username='test_user', password='test_password',
                                                              output_file='test_dump.pcap')
    assert message == 'Successfully started'
    assert isinstance(pcap_dump_task_id, str) and len(pcap_dump_task_id) == 8

    time.sleep(5)

    task_manager.stop_task(log_dump_task_id)
    task_manager.stop_task(pcap_dump_task_id)

    # Check captured log file
    assert os.path.isfile('ping.log')
    assert os.path.getsize('ping.log') > 0
    count_ping = 0
    with open('ping.log', 'rt', encoding='utf8') as log_file:
        for line in log_file:
            if re.match(r'64 bytes from 127\.0\.0\.1: seq=\d+ ttl=64 time=\d+\.\d{3} ms', line):
                count_ping += 1
            else:
                assert False, f'Unmatched line: {line}'
    assert count_ping >= 4
    os.remove('ping.log')

    # Check captured pcap file
    assert os.path.isfile('test_dump.pcap')
    assert os.path.getsize('test_dump.pcap') > 0
    pcap = rdpcap('test_dump.pcap')
    assert len(pcap) > 0
    ping_requests = [pkt for pkt in pcap if ICMP in pkt and pkt.payload['ICMP'].type == 8]
    assert len(ping_requests) >= 4
    os.remove('test_dump.pcap')


@pytest.mark.usefixtures('test_ssh_server')
def test_get_all_tasks(task_manager: TaskManager):
    """
    Проверка получения информации о всех запущенных задачах.

    Args:
        task_manager (TaskManager): Менеджер задач
    """

    _, log_dump_task_id = task_manager.start_log_dump(address='127.0.0.1', port=10022,
                                                      username='test_user', password='test_password',
                                                      output_file='ping.log', dumped_file='/tmp/ping.log')
    tasks = task_manager.get_all_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    log_dump_task_info = tasks[0]
    assert isinstance(log_dump_task_info, dict)
    assert isinstance(log_dump_task_info['name'], str)
    assert log_dump_task_info['name'].endswith(f'log_{log_dump_task_id}')
    assert log_dump_task_info['task_id'] == log_dump_task_id
    assert log_dump_task_info['is_alive'] is True

    time.sleep(1)

    _, pcap_dump_task_id = task_manager.start_pcap_dump(address='127.0.0.1', port=10022,
                                                        username='test_user', password='test_password',
                                                        output_file='test_dump.pcap')
    tasks = task_manager.get_all_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 2
    log_dump_task_info = tasks[0]
    assert isinstance(log_dump_task_info, dict)
    assert isinstance(log_dump_task_info['name'], str)
    assert log_dump_task_info['name'].endswith(f'log_{log_dump_task_id}')
    assert log_dump_task_info['task_id'] == log_dump_task_id
    assert log_dump_task_info['is_alive'] is True
    pcap_dump_task_info = tasks[1]
    assert isinstance(pcap_dump_task_info, dict)
    assert isinstance(pcap_dump_task_info['name'], str)
    assert pcap_dump_task_info['name'].endswith(f'pcap_{pcap_dump_task_id}')
    assert pcap_dump_task_info['task_id'] == pcap_dump_task_id
    assert pcap_dump_task_info['is_alive'] is True

    time.sleep(1)

    task_manager.stop_task(log_dump_task_id)
    tasks = task_manager.get_all_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    pcap_dump_task_info = tasks[0]
    assert isinstance(pcap_dump_task_info, dict)
    assert isinstance(pcap_dump_task_info['name'], str)
    assert pcap_dump_task_info['name'].endswith(f'pcap_{pcap_dump_task_id}')
    assert pcap_dump_task_info['task_id'] == pcap_dump_task_id
    assert pcap_dump_task_info['is_alive'] is True

    task_manager.stop_task(pcap_dump_task_id)
    tasks = task_manager.get_all_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 0

    os.remove('ping.log')
    os.remove('test_dump.pcap')
