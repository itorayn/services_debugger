import logging
from typing import List

from sqlalchemy import create_engine, MetaData, Table, String, Integer, Column

from app.singleton import Singleton
from app.models.host import Host


metadata = MetaData()
engine = create_engine('sqlite:///test.db')

hosts = Table('hosts', metadata,
              Column('host_id', Integer(), primary_key=True),
              Column('name', String(32), nullable=False),
              Column('description', String(256), nullable=True),
              Column('ssh_address', String(256), nullable=False),
              Column('ssh_port', Integer(), default=22, nullable=False),
              Column('username', String(256), nullable=False),
              Column('password', String(256), nullable=False))

metadata.create_all(engine)


class HostRepository(Singleton):
    """
    Класс для выполнения CRUD операций с хостами в базе данных.
    В классе HostRepository используется паттерн "одиночка",
    может быть создан только один экземпляр.
    """

    def __init__(self):
        self._logger = logging.getLogger('host_repo')

    def add_host(self, host: Host) -> int:
        """
        Добавление нового хоста в базу данных.

        Args:
            host (Host): Хост который необходимо добавить в базу данных

        Returns:
            int: Идентификатор в базе данных добавленого хоста
        """

        self._logger.info(f'Creating a host in the database: {host}')
        insert_request = hosts.insert().values(
            **host.model_dump(exclude_unset=True)
        )
        with engine.connect() as conn:
            response = conn.execute(insert_request)
            host_id = response.inserted_primary_key[0]
            conn.commit()
        self._logger.info(f'Created a host in the database: {host_id}')
        return host_id

    def get_all_hosts(self) -> List[Host]:
        """
        Получить все записи хостов из базы данных.

        Returns:
            List[Host]: Список всех хостов из базы данных
        """

        self._logger.info('Retrieving all hosts from the database')
        with engine.connect() as conn:
            select_request = hosts.select()
            response = conn.execute(select_request)
        return [Host.from_orm(data) for data in response.fetchall()]

    def get_host(self, host_id: int) -> Host:
        """
        Получить запись хоста по его идентификатору.

        Args:
            host_id (int): Идентификатор хоста

        Raises:
            LookupError: Возникает в случае если хост с указанным идентификатор не удалось найти

        Returns:
            Host: Запись хоста из базы данных.
        """

        self._logger.info(f'Retrieving host by id {host_id}')
        with engine.connect() as conn:
            select_request = hosts.select().where(
                hosts.c.host_id == host_id
            )
            response = conn.execute(select_request)
        data = response.first()
        if data is None:
            raise LookupError
        return Host.from_orm(data)

    def delete_host(self, host_id: int):
        """
        Удалить запись хоста из базы данных.

        Args:
            host_id (int): Идентификатор хоста

        Raises:
            LookupError: Возникает в случае если хост с указанным идентификатор не удалось найти
        """

        self._logger.info(f'Deleting host with id {host_id}')
        with engine.connect() as conn:
            delete_request = hosts.delete().where(
                hosts.c.host_id == host_id
            )
            response = conn.execute(delete_request)
            conn.commit()
        if response.rowcount == 0:
            raise LookupError

    def update_host(self, host: Host, host_id: int):
        """
        Обновить запись хоста в базе данных.

        Args:
            host (Host):  Новые данные хоста
            host_id (int): Идентификатор хоста

        Raises:
            LookupError: Возникает в случае если хост с указанным идентификатор не удалось найти
        """

        self._logger.info(f'Updating host with id {host_id}, {host}')
        with engine.connect() as conn:
            update_request = hosts.update().where(
                hosts.c.host_id == host_id
            ).values(
                **host.model_dump(exclude_unset=True)
            )
            response = conn.execute(update_request)
            conn.commit()
        if response.rowcount == 0:
            raise LookupError


host_repo = HostRepository()
