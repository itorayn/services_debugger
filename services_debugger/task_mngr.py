import os
import logging
import string
import multiprocessing
import threading
from dataclasses import dataclass, field
from logging.handlers import QueueHandler
from typing import Union, Tuple, List, Dict
from queue import Empty
from random import choices

from .dumpers import PCAPDump, LogDump
from .ssh_conn_mngr import SSHConnectionManager


@dataclass
class TaskManagerCommand:
    """
    Класс вызова метода выполняемого в дочернем процессе.
    """

    name: str
    args: tuple = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)


@dataclass
class TaskManagerResult:
    """
    Класс результата выполненной команды.
    """

    data: ...


class TaskManager:
    """
    Менеджер задач. Работает в субпроцессе и выполняет следующие функции:
        - инициализацию менеджера SSH подключений;
        - создание PCAPDump, LogDump и объектов;
        - завершение работы PCAPDump и LogDump объектов;
        - контроль созданных задач.
    """

    def __init__(self, name: str, timeout: Union[int, float] = 5):
        self.name = name
        self.timeout = timeout
        self._logger = logging.getLogger(self.name)
        self._process = None
        self._log_thread = None
        self._need_stop = None
        self._log_queue = None
        self._cmd_queue = None
        self._res_queue = None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name={repr(self.name)}, timeout={repr(self.timeout)})'

    def start(self):
        """Запуск субпроцесса."""

        if self._process is None:
            context = multiprocessing.get_context('spawn')
            self._need_stop = context.Event()
            self._log_queue = context.Queue()
            self._cmd_queue = context.Queue()
            self._res_queue = context.Queue()
            self._process = context.Process(target=self._process_loop, daemon=True)
            self._process.start()
            self._log_thread = threading.Thread(target=self._thread_loop, daemon=True)
            self._log_thread.start()

    def _thread_loop(self):
        while not self._need_stop.is_set():
            try:
                message = self._log_queue.get(timeout=1)
            except Empty:
                continue
            self._logger.handle(message)

    def _process_loop(self):
        logger_name = f'proc_{os.getpid()}'
        logger = logging.getLogger(logger_name)
        logger.addHandler(QueueHandler(self._log_queue))
        logger.setLevel(logging.DEBUG)

        SSHConnectionManager(f'{logger_name}.ssh_mngr')
        tasks = {}

        def get_random_task_id():
            identifier = ''.join(choices(string.ascii_uppercase + string.digits, k=8))
            if identifier in tasks:
                return get_random_task_id()
            return identifier

        while not self._need_stop.is_set():
            try:
                cmd = self._cmd_queue.get(timeout=1)
            except Empty:
                continue

            logger.info(f'Trying to execute command "{cmd.name}" with {cmd.args = } {cmd.kwargs = }')
            try:
                if cmd.name in ('start_pcap_dump', 'start_log_dump'):
                    task_id = get_random_task_id()
                    if cmd.name == 'start_pcap_dump':
                        dumper = PCAPDump(f'{logger_name}.pcap_{task_id}', *cmd.args, **cmd.kwargs)
                    elif cmd.name == 'start_log_dump':
                        dumper = LogDump(f'{logger_name}.log_{task_id}', *cmd.args, **cmd.kwargs)
                    dumper.start()
                    tasks[task_id] = dumper
                    returned_value = ('Successfully started', task_id)
                elif cmd.name == 'get_task_info':
                    task_id = cmd.args[0]
                    task = tasks.get(task_id, None)
                    if task is None:
                        returned_value = Exception(f'Task with id="{task_id}" not found in task list.')
                    else:
                        returned_value = {'name': task.name, 'task_id': task_id, 'is_alive': task.is_alive()}
                elif cmd.name == 'get_all_tasks':
                    returned_value = []
                    for task_id, task in tasks.items():
                        returned_value.append({'name': task.name, 'task_id': task_id, 'is_alive': task.is_alive()})
                elif cmd.name == 'stop_task':
                    task_id = cmd.args[0]
                    task = tasks.pop(task_id, None)
                    if task is None:
                        returned_value = Exception(f'Task with id="{task_id}" not found in task list.')
                    else:
                        task.stop()
                        returned_value = ('Successfully stopped', task_id)
                else:
                    returned_value = Exception(f'Unknown command: "{cmd.name}"')
            # pylint: disable-next=broad-exception-caught
            except Exception as error:
                returned_value = error
            self._res_queue.put(TaskManagerResult(returned_value))

        for task_id, task in tasks.items():
            logger.info(f'Stopping task "{task_id}"')
            task.stop()

    def _send_rpc_command(self, rpc_command: TaskManagerCommand) -> TaskManagerResult:
        self._cmd_queue.put(rpc_command)

        try:
            result = self._res_queue.get(timeout=self.timeout)
        except Empty as error:
            raise TimeoutError(f'No answer was received within {self.timeout}s') from error

        if isinstance(result.data, Exception):
            raise result.data

        return result

    def start_pcap_dump(self, address: str, port: Union[str, int],
                        username: str, password: str, output_file: str) -> Tuple[str, str]:
        """
        Запуск удаленного сниффера траффика.

        Args:
            address (str): Адрес хоста на котором необходимо запустить tcpdump
            port (Union[str, int]): Порт для подключения по SSH
            username (str): Имя пользователя подключения по SSH
            password (str): Пароль пользователя подключения по SSH
            output_file (str): Путь к локальному файлу в который необходимо записать захваченный траффик

        Returns:
            Tuple[str, str]: Кортеж состоящий из сообщения и идентификатора задачи
        """

        command = TaskManagerCommand(name='start_pcap_dump',
                                     args=(address, port, username, password, output_file))
        result = self._send_rpc_command(command)
        return result.data

    def start_log_dump(self, address: str, port: Union[str, int],
                       username: str, password: str, output_file: str, dumped_file: str) -> Tuple[str, str]:
        """
        Запуск удаленного сниффера логов.

        Args:
            address (str): Адрес хоста на котором необходимо запустить захват логов
            port (Union[str, int]): Порт для подключения по SSH
            username (str): Имя пользователя подключения по SSH
            password (str): Пароль пользователя подключения по SSH
            output_file (str): Путь к локальному файлу в который необходимо записать захваченные логи
            dumped_file (str): Путь у удаленному файлу логов

        Returns:
            Tuple[str, str]: Кортеж состоящий из сообщения и идентификатора задачи
        """

        command = TaskManagerCommand(name='start_log_dump',
                                     args=(address, port, username, password, output_file, dumped_file))
        result = self._send_rpc_command(command)
        return result.data

    def get_task_info(self, task_id: str) -> Dict[str, Union[bool, str]]:
        """
        Получить информацию о состоянии задачи.

        Args:
            task_id (str): Идентификатор задачи

        Returns:
            Dict[str, Union[bool, str]]: Словарь с информацией о состоянии задачи
        """

        command = TaskManagerCommand(name='get_task_info', args=(task_id,))
        result = self._send_rpc_command(command)
        return result.data

    def get_all_tasks(self) -> List[Dict[str, Union[bool, str]]]:
        """
        Получить информацию о всех запущенных задачах.

        Returns:
            List[Dict[str, Union[bool, str]]]: Список текущих задач
        """

        command = TaskManagerCommand(name='get_all_tasks')
        result = self._send_rpc_command(command)
        return result.data

    def stop_task(self, task_id: str) -> Tuple[str, str]:
        """
        Остановить выполнение задачи.

        Args:
            task_id (str): Идентификатор завершаемой задачи

        Returns:
            Tuple[str, str]: Кортеж состоящий из сообщения и идентификатора задачи
        """

        command = TaskManagerCommand(name='stop_task', args=(task_id,))
        result = self._send_rpc_command(command)
        return result.data

    def stop(self):
        """Остановка субпроцесса."""

        self._need_stop.set()
        if self._process is not None:
            self._process.join()
        if self._log_thread is not None:
            self._log_thread.join()
        self._process = None
        self._log_thread = None
        self._need_stop = None
        self._log_queue = None
        self._cmd_queue = None
        self._res_queue = None
