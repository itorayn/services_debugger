import logging
import select
from typing import Union
from threading import Thread
from abc import ABC, abstractmethod

from .ssh_conn_mngr import SSHConnectionManager


class DumperError(Exception):
    """Исключение возникающее при ошибке в работе сниффера."""


class BaseDumper(Thread, ABC):
    """Базовый класс сниффера."""

    @property
    @abstractmethod
    def task_type(self) -> str:
        """Тип сниффера в текстовом виде."""

    @property
    def executed_command(self) -> str:
        """Выполняемая команда на удаленном хосте."""

    def __init__(self, name: str, address: str, port: Union[str, int],
                 username: str, password: str, output_file: str):
        Thread.__init__(self, name=name, daemon=True)
        self._logger = logging.getLogger(self.name)
        self._connection_parameters = {
            "address": address,
            "port": port,
            "username": username,
            "password": password
        }
        self._ssh_manager = SSHConnectionManager(None)
        self._need_stop = False
        self._output_file = output_file

    def __repr__(self) -> str:
        repr_value = f'{self.__class__.__name__}(name={repr(self.name)}'
        for attr_name in ('address', 'port', 'username', 'password'):
            attr_value = repr(self._connection_parameters[attr_name])
            repr_value += f', {attr_name}={attr_value}'
        repr_value += f', output_file={repr(self._output_file)})'
        return repr_value

    def run(self):
        self._logger.info('Starting ...')

        with self._ssh_manager.connection(**self._connection_parameters) as ssh, \
             open(self._output_file, 'wb') as output_file:
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
                            # self._logger.error(f'Recived new data: {data.decode(encoding="utf8")}')
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

    def stop(self):
        """
        Остановка сниффера.
        """

        if self.is_alive():
            self._logger.info('Stoping ...')
            self._need_stop = True
            self.join()


class LogDump(BaseDumper):
    """
    Класс удаленного сниффера логов. Выполняет подключение к удаленному хосту по SSH,
    запуск команды tail -f <dumped_file> с выводом захваченных логов в SSH канал, прием захваченных логов из
    SSH канала и запись их в файл.
    """

    task_type = 'log_dump'

    def __init__(self, name: str, address: str, port: Union[str, int],
                 username: str, password: str, output_file: str, dumped_file: str):
        super().__init__(name, address, port, username, password, output_file)
        self._dumped_file = dumped_file

    def __repr__(self) -> str:
        repr_value = f'{self.__class__.__name__}(name={repr(self.name)}'
        for attr_name in ('address', 'port', 'username', 'password'):
            attr_value = repr(self._connection_parameters[attr_name])
            repr_value += f', {attr_name}={attr_value}'
        repr_value += f', output_file={repr(self._output_file)}, dumped_file={repr(self._dumped_file)})'
        return repr_value

    @property
    def executed_command(self) -> str:
        return f'tail --follow=name --retry --lines=1 {self._dumped_file}'


class PCAPDump(BaseDumper):
    """
    Класс удаленного сниффера траффика. Выполняет подключение к удаленному хосту по SSH,
    запуск команды tcpdump с выводом захваченного трафика в SSH канал, прием захваченного трафика из
    SSH канала и запись его в файл.
    """

    task_type = 'pcap_dump'

    def __init__(self, name: str, address: str, port: Union[str, int],
                 username: str, password: str, output_file: str, dumped_interface: str = 'any'):
        super().__init__(name, address, port, username, password, output_file)
        self._dumped_interface = dumped_interface

    def __repr__(self) -> str:
        repr_value = f'{self.__class__.__name__}(name={repr(self.name)}'
        for attr_name in ('address', 'port', 'username', 'password'):
            attr_value = repr(self._connection_parameters[attr_name])
            repr_value += f', {attr_name}={attr_value}'
        repr_value += f', output_file={repr(self._output_file)}, dumped_interface={repr(self._dumped_interface)})'
        return repr_value

    @property
    def executed_command(self) -> str:
        return f'tcpdump -i {self._dumped_interface} -U -w - -f not tcp port 22'
