import logging
import multiprocessing
import os
import string
import threading
from dataclasses import dataclass, field
from logging.handlers import QueueHandler
from queue import Empty
from random import choices
from typing import Any

from app.core.dumpers import Dumper, LogDump, PCAPDump
from app.core.ssh_conn_mngr import SSHConnectionManager
from app.models.host import Host
from app.models.task import Task


@dataclass
class TaskManagerCommand:
    """
    Класс вызова метода выполняемого в дочернем процессе.
    """

    name: str
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskManagerResult:
    """
    Класс результата выполненной команды.
    """

    data: Any


context = multiprocessing.get_context('spawn')


class ProcessTaskManager(context.Process):  # type: ignore[name-defined]
    """
    Бековая часть менеджер задач. Работает в субпроцессе и выполняет следующие функции:
        - инициализацию менеджера SSH подключений;
        - создание PCAPDump, LogDump и объектов;
        - завершение работы PCAPDump и LogDump объектов;
        - контроль созданных задач.
    """

    def __init__(
        self,
        name: str,
        log_queue: 'multiprocessing.Queue[logging.LogRecord]',
        cmd_queue: 'multiprocessing.Queue[TaskManagerCommand]',
        res_queue: 'multiprocessing.Queue[TaskManagerResult]',
    ) -> None:
        super().__init__(daemon=True)
        self.name = name
        self.need_stop = context.Event()
        self._logger = logging.getLogger(self.name)
        self._log_queue = log_queue
        self._cmd_queue = cmd_queue
        self._res_queue = res_queue
        self._tasks: dict[str, Dumper] = {}

    def run(self) -> None:
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
                returned_value = Exception(f'Unknown command: "{cmd.name}"') if method is None else method(cmd)
            except Exception as error:  # noqa: BLE001
                returned_value = error
            self._res_queue.put(TaskManagerResult(returned_value))

        for task_id, task in self._tasks.items():
            logger.info(f'Stopping task "{task_id}"')
            task.stop()

    def _get_random_task_id(self) -> str:
        identifier = ''.join(choices(string.ascii_uppercase + string.digits, k=8))
        if identifier in self._tasks:
            return self._get_random_task_id()
        return identifier

    def _start_pcap_dump(self, cmd: TaskManagerCommand) -> Task:
        task_id = self._get_random_task_id()
        dumper = PCAPDump(f'proc_{os.getpid()}.pcap_{task_id}', *cmd.args, **cmd.kwargs)
        dumper.start()
        self._tasks[task_id] = dumper
        return Task(task_id=task_id, name=dumper.name, task_type=dumper.task_type, is_alive=dumper.is_alive())

    def _start_log_dump(self, cmd: TaskManagerCommand) -> Task:
        task_id = self._get_random_task_id()
        dumper = LogDump(f'proc_{os.getpid()}.log_{task_id}', *cmd.args, **cmd.kwargs)
        dumper.start()
        self._tasks[task_id] = dumper
        return Task(task_id=task_id, name=dumper.name, task_type=dumper.task_type, is_alive=dumper.is_alive())

    def _get_task_info(self, cmd: TaskManagerCommand) -> Task | Exception:
        task_id = cmd.args[0]
        dumper = self._tasks.get(task_id, None)
        if dumper is None:
            return LookupError(f'Task with id="{task_id}" not found in task list.')
        return Task(task_id=task_id, name=dumper.name, task_type=dumper.task_type, is_alive=dumper.is_alive())

    def _stop_task(self, cmd: TaskManagerCommand) -> Task | Exception:
        task_id = cmd.args[0]
        dumper = self._tasks.pop(task_id, None)
        if dumper is None:
            return LookupError(f'Task with id="{task_id}" not found in task list.')
        dumper.stop()
        return Task(task_id=task_id, name=dumper.name, task_type=dumper.task_type, is_alive=dumper.is_alive())

    def _get_all_tasks(self, _cmd: TaskManagerCommand) -> list[Task]:
        returned_value: list[Task] = []
        for task_id, task in self._tasks.items():
            returned_value.append(
                Task(task_id=task_id, name=task.name, task_type=task.task_type, is_alive=task.is_alive())
            )
        return returned_value


class LogProxyThread(threading.Thread):
    """Прокси для лог записей, получает записи из очереди и передает их логгеру."""

    def __init__(
        self, name: str, log_queue: 'multiprocessing.Queue[logging.LogRecord]', logger: logging.Logger
    ) -> None:
        super().__init__(name=name, daemon=True)
        self.need_stop = threading.Event()
        self._log_queue = log_queue
        self._logger = logger

    def run(self) -> None:
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

    def __init__(self, name: str, timeout: int | float = 5) -> None:
        self.name = name
        self.timeout = timeout
        self._logger = logging.getLogger(self.name)
        self._process: ProcessTaskManager | None = None
        self._log_thread: LogProxyThread | None = None
        self._log_queue: multiprocessing.Queue[logging.LogRecord] = context.Queue()
        self._cmd_queue: multiprocessing.Queue[TaskManagerCommand] = context.Queue()
        self._res_queue: multiprocessing.Queue[TaskManagerResult] = context.Queue()

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name={self.name!r}, timeout={self.timeout!r})'

    def start(self) -> None:
        """Запуск "бековой" субпроцессной части."""

        if self._process is None:
            self._process = ProcessTaskManager(
                name=self.name, log_queue=self._log_queue, cmd_queue=self._cmd_queue, res_queue=self._res_queue
            )
            self._process.start()
            self._log_thread = LogProxyThread(name=self.name, log_queue=self._log_queue, logger=self._logger)
            self._log_thread.start()

    def _send_rpc_command(self, rpc_command: TaskManagerCommand) -> TaskManagerResult:
        if self._process is None:
            raise RuntimeError('TaskManager not started!')

        self._cmd_queue.put(rpc_command)

        try:
            result = self._res_queue.get(timeout=self.timeout)
        except Empty as error:
            raise TimeoutError(f'No answer was received within {self.timeout}s') from error

        if isinstance(result.data, Exception):
            raise result.data

        return result

    def start_pcap_dump(self, host: Host, output_file: str) -> Task:
        """
        Запуск удаленного сниффера траффика.

        Args:
            host (Host): Data-object хоста на котором необходимо запустить tcpdump
            output_file (str): Путь к локальному файлу в который необходимо записать захваченный траффик

        Returns:
            Task: Объект задачи
        """

        command = TaskManagerCommand(name='start_pcap_dump', args=[host, output_file])
        result = self._send_rpc_command(command)
        assert isinstance(result.data, Task)
        return result.data

    def start_log_dump(self, host: Host, output_file: str, dumped_file: str) -> Task:
        """
        Запуск удаленного сниффера логов.

        Args:
            host (Host): Data-object хоста на котором необходимо запустить tcpdump
            output_file (str): Путь к локальному файлу в который необходимо записать захваченные логи
            dumped_file (str): Путь у удаленному файлу логов

        Returns:
            Task: Объект задачи
        """

        command = TaskManagerCommand(name='start_log_dump', args=[host, output_file, dumped_file])
        result = self._send_rpc_command(command)
        assert isinstance(result.data, Task)
        return result.data

    def get_task_info(self, task_id: str) -> Task:
        """
        Получить информацию о состоянии задачи.

        Args:
            task_id (str): Идентификатор задачи

        Returns:
            Task: Объект задачи
        """

        command = TaskManagerCommand(name='get_task_info', args=[task_id])
        result = self._send_rpc_command(command)
        assert isinstance(result.data, Task)
        return result.data

    def get_all_tasks(self) -> list[Task]:
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

        command = TaskManagerCommand(name='stop_task', args=[task_id])
        result = self._send_rpc_command(command)
        assert isinstance(result.data, Task)
        return result.data

    def stop(self) -> None:
        """Остановка субпроцесса."""

        if self._process is not None:
            self._process.need_stop.set()
            self._process.join()
            self._process = None

        if self._log_thread is not None:
            self._log_thread.need_stop.set()
            self._log_thread.join()
            self._log_thread = None
