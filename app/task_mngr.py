import os
import logging
import string
import multiprocessing
import threading
from dataclasses import dataclass, field
from logging.handlers import QueueHandler
from typing import Union, List, Dict, Any
from queue import Empty
from random import choices

from .dumpers import Dumper, PCAPDump, LogDump
from .ssh_conn_mngr import SSHConnectionManager
from .models.task import Task


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

    data: Any


context = multiprocessing.get_context('spawn')


class ProcessTaskManager(context.Process):
    """
    Бековая часть менеджер задач. Работает в субпроцессе и выполняет следующие функции:
        - инициализацию менеджера SSH подключений;
        - создание PCAPDump, LogDump и объектов;
        - завершение работы PCAPDump и LogDump объектов;
        - контроль созданных задач.
    """

    def __init__(self, name: str, log_queue: context.Queue, cmd_queue: context.Queue, res_queue: context.Queue):
        super().__init__(daemon=True)
        self.name = name
        self.need_stop = context.Event()
        self._logger = logging.getLogger(self.name)
        self._log_queue = log_queue
        self._cmd_queue = cmd_queue
        self._res_queue = res_queue
        self._tasks: Dict[str, Dumper] = {}

    def run(self):
        """Главный цикл субпроцесса."""

        logger_name = f'proc_{os.getpid()}'
        logger = logging.getLogger(logger_name)
        logger.addHandler(QueueHandler(self._log_queue))
        logger.setLevel(logging.DEBUG)

        SSHConnectionManager(f'{logger_name}.ssh_mngr')

        while not self.need_stop.is_set():
            try:
                cmd = self._cmd_queue.get(timeout=1)
            except Empty:
                continue

            logger.info(f'Trying to execute command "{cmd.name}" with {cmd.args = } {cmd.kwargs = }')
            try:
                method = getattr(self, f'_{cmd.name}', None)
                if method is None:
                    returned_value = Exception(f'Unknown command: "{cmd.name}"')
                else:
                    returned_value = method(cmd)
            # pylint: disable-next=broad-exception-caught
            except Exception as error:
                returned_value = error
            self._res_queue.put(TaskManagerResult(returned_value))

        for task_id, task in self._tasks.items():
            logger.info(f'Stopping task "{task_id}"')
            task.stop()

    def _get_random_task_id(self):
        identifier = ''.join(choices(string.ascii_uppercase + string.digits, k=8))
        if identifier in self._tasks:
            return self._get_random_task_id()
        return identifier

    def _start_pcap_dump(self, cmd: TaskManagerCommand) -> Task:
        task_id = self._get_random_task_id()
        dumper = PCAPDump(f'proc_{os.getpid()}.pcap_{task_id}', *cmd.args, **cmd.kwargs)
        dumper.start()
        self._tasks[task_id] = dumper
        return Task(task_id=task_id, name=dumper.name,
                    task_type=dumper.task_type, is_alive=dumper.is_alive())

    def _start_log_dump(self, cmd: TaskManagerCommand) -> Task:
        task_id = self._get_random_task_id()
        dumper = LogDump(f'proc_{os.getpid()}.log_{task_id}', *cmd.args, **cmd.kwargs)
        dumper.start()
        self._tasks[task_id] = dumper
        return Task(task_id=task_id, name=dumper.name,
                    task_type=dumper.task_type, is_alive=dumper.is_alive())

    def _get_task_info(self, cmd: TaskManagerCommand) -> Union[Task, Exception]:
        task_id = cmd.args[0]
        dumper = self._tasks.get(task_id, None)
        if dumper is None:
            return LookupError(f'Task with id="{task_id}" not found in task list.')
        return Task(task_id=task_id, name=dumper.name,
                    task_type=dumper.task_type, is_alive=dumper.is_alive())

    def _stop_task(self, cmd: TaskManagerCommand) -> Union[Task, Exception]:
        task_id = cmd.args[0]
        dumper = self._tasks.pop(task_id, None)
        if dumper is None:
            return LookupError(f'Task with id="{task_id}" not found in task list.')
        dumper.stop()
        return Task(task_id=task_id, name=dumper.name,
                    task_type=dumper.task_type, is_alive=dumper.is_alive())

    def _get_all_tasks(self, _cmd: TaskManagerCommand) -> List[Task]:
        returned_value = []
        for task_id, task in self._tasks.items():
            returned_value.append(Task(task_id=task_id, name=task.name,
                                       task_type=task.task_type, is_alive=task.is_alive()))
        return returned_value


class LogProxyThread(threading.Thread):
    """Прокси для лог записей, получает записи из очереди и передает их логгеру."""

    def __init__(self, name: str, log_queue: context.Queue, logger: logging.Logger):
        super().__init__(name=name, daemon=True)
        self.need_stop = threading.Event()
        self._log_queue = log_queue
        self._logger = logger

    def run(self):
        while not self.need_stop.is_set():
            try:
                message = self._log_queue.get(timeout=1)
            except Empty:
                continue
            self._logger.handle(message)


class TaskManager:
    """
    Фронтовая часть менеджер задач. Работает в том-же процессе в котором был создан.
    Реализирует интерфейс взаимодействия с бековой частью работающей в субпроцессе.
    Совокупность фронтовой и бековой частей выполняют следующие функции:
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
        """Запуск "бековой" субпроцессной части."""

        if self._process is None:
            self._log_queue = context.Queue()
            self._cmd_queue = context.Queue()
            self._res_queue = context.Queue()
            self._process = ProcessTaskManager(name=self.name, log_queue=self._log_queue,
                                               cmd_queue=self._cmd_queue, res_queue=self._res_queue)
            self._process.start()
            self._log_thread = LogProxyThread(name=self.name, log_queue=self._log_queue, logger=self._logger)
            self._log_thread.start()

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
                        username: str, password: str, output_file: str) -> Task:
        """
        Запуск удаленного сниффера траффика.

        Args:
            address (str): Адрес хоста на котором необходимо запустить tcpdump
            port (Union[str, int]): Порт для подключения по SSH
            username (str): Имя пользователя подключения по SSH
            password (str): Пароль пользователя подключения по SSH
            output_file (str): Путь к локальному файлу в который необходимо записать захваченный траффик

        Returns:
            Task: Объект задачи
        """

        command = TaskManagerCommand(name='start_pcap_dump',
                                     args=(address, port, username, password, output_file))
        result = self._send_rpc_command(command)
        return result.data

    def start_log_dump(self, address: str, port: Union[str, int],
                       username: str, password: str, output_file: str, dumped_file: str) -> Task:
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
            Task: Объект задачи
        """

        command = TaskManagerCommand(name='start_log_dump',
                                     args=(address, port, username, password, output_file, dumped_file))
        result = self._send_rpc_command(command)
        return result.data

    def get_task_info(self, task_id: str) -> Task:
        """
        Получить информацию о состоянии задачи.

        Args:
            task_id (str): Идентификатор задачи

        Returns:
            Task: Объект задачи
        """

        command = TaskManagerCommand(name='get_task_info', args=(task_id,))
        result = self._send_rpc_command(command)
        return result.data

    def get_all_tasks(self) -> List[Task]:
        """
        Получить информацию о всех запущенных задачах.

        Returns:
            List[Task]: Список текущих задач
        """

        command = TaskManagerCommand(name='get_all_tasks')
        result = self._send_rpc_command(command)
        return result.data

    def stop_task(self, task_id: str) -> Task:
        """
        Остановить выполнение задачи.

        Args:
            task_id (str): Идентификатор завершаемой задачи

        Returns:
            Task: Объект задачи
        """

        command = TaskManagerCommand(name='stop_task', args=(task_id,))
        result = self._send_rpc_command(command)
        return result.data

    def stop(self):
        """Остановка субпроцесса."""

        self._process.need_stop.set()
        if self._process is not None:
            self._process.join()
        self._log_thread.need_stop.set()
        if self._log_thread is not None:
            self._log_thread.join()

        self._process = None
        self._log_thread = None
        self._log_queue = None
        self._cmd_queue = None
        self._res_queue = None
