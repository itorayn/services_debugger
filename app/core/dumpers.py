import logging
import select
from abc import ABC, abstractmethod
from threading import Thread

from app.core.ssh_conn_mngr import SSHConnectionManager
from app.models.host import Host
from app.models.task import TaskType


class DumperError(Exception):
    """Исключение возникающее при ошибке в работе сниффера."""


class Dumper(Thread, ABC):
    """Базовый класс сниффера."""

    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        """Тип сниффера."""

    @property
    @abstractmethod
    def executed_command(self) -> str:
        """Выполняемая команда на удаленном хосте."""

    def __init__(self, name: str, host: Host, output_file: str) -> None:
        Thread.__init__(self, name=name, daemon=True)
        self._logger = logging.getLogger(self.name)
        self._host: Host = host
        self._need_stop = False
        self._output_file = output_file

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name={self.name!r}, host={self._host!r}, output_file={self._output_file!r})'

    def run(self) -> None:
        self._logger.info('Starting ...')
        ssh_manager = SSHConnectionManager(f'{self.name}.ssh_mngr')
        with (
            ssh_manager.connection(
                address=self._host.ssh_address,
                port=self._host.ssh_port,
                username=self._host.username,
                password=self._host.password,
            ) as ssh,
            open(self._output_file, 'wb') as output_file,
        ):
            self._logger.info(f'Execute command: {self.executed_command}')
            _, stdout, stderr = ssh.exec_command(self.executed_command)
            channel = stdout.channel

            if channel.exit_status_ready():
                exitcode = channel.recv_exit_status()
                raise DumperError(f'The process terminated early with exit code: {exitcode}')

            file_descriptor = channel.fileno()
            epoll = select.epoll()
            epoll.register(file_descriptor, select.EPOLLIN | select.EPOLLHUP)

            while self._need_stop is False:
                for fileno, event in epoll.poll(1):
                    if fileno != file_descriptor:
                        self._logger.error(f'Recived epoll data with unknown file descriptor {fileno}')
                        continue
                    if event & select.EPOLLIN:
                        while channel.recv_ready():
                            data = stdout.read(len(channel.in_buffer))
                            output_file.write(data)
                        while channel.recv_stderr_ready():
                            data = stderr.read(len(channel.in_stderr_buffer))
                            self._logger.error(f'Recived new err data: {data.decode(encoding="utf8")}')
                    elif event & select.EPOLLHUP:
                        self._logger.info('Recive End-Of-Steam, terminate buffer reader')
                        self._need_stop = True
                        continue
                    else:
                        self._logger.error(f'Recived epoll data with unknown event {event}')
                        continue

            epoll.unregister(file_descriptor)
            epoll.close()

            stdout.channel.close()

    def stop(self) -> None:
        """
        Остановка сниффера.
        """

        if self.is_alive():
            self._logger.info('Stoping ...')
            self._need_stop = True
            self.join()


class LogDump(Dumper):
    """
    Класс удаленного сниффера логов. Выполняет подключение к удаленному хосту по SSH,
    запуск команды tail -f <dumped_file> с выводом захваченных логов в SSH канал, прием захваченных логов из
    SSH канала и запись их в файл.
    """

    task_type = TaskType.LOG

    def __init__(self, name: str, host: Host, output_file: str, dumped_file: str) -> None:
        super().__init__(name, host, output_file)
        self._dumped_file = dumped_file

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}(name={self.name!r}, host={self._host!r}, '
            f'output_file={self._output_file!r}, dumped_file={self._dumped_file!r})'
        )

    @property
    def executed_command(self) -> str:
        return f'tail --follow=name --retry --lines=1 {self._dumped_file}'


class PCAPDump(Dumper):
    """
    Класс удаленного сниффера траффика. Выполняет подключение к удаленному хосту по SSH,
    запуск команды tcpdump с выводом захваченного трафика в SSH канал, прием захваченного трафика из
    SSH канала и запись его в файл.
    """

    task_type = TaskType.PCAP

    def __init__(
        self,
        name: str,
        host: Host,
        output_file: str,
        dumped_interface: str = 'any',
    ) -> None:
        super().__init__(name, host, output_file)
        self._dumped_interface = dumped_interface

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}(name={self.name!r}, host={self._host!r}, '
            f'output_file={self._output_file!r}, dumped_interface={self._dumped_interface!r})'
        )

    @property
    def executed_command(self) -> str:
        return f'tcpdump -i {self._dumped_interface} -U -w - -f not tcp port 22'
