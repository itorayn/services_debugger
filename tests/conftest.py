import sqlite3
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

import docker
from app.main import app


@pytest.fixture(scope='session')
def test_client() -> TestClient:
    """
    Фикстура для создания тестового клиента API.

    Returns:
        TestClient: Тестовый клиент API
    """

    return TestClient(app)


@pytest.fixture
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Фикстура для создания подключения к базе данных.
    В SETUP происходит подключение к базе, в тест передается объект для взаимодействия с базой,
    а в TEARDOWN происходит закрытие подключения.

    Yields:
        Iterator[sqlite3.Connection]: Объект для взаимодействия с базой
    """

    connection = sqlite3.connect('test.db')

    yield connection

    connection.close()


@pytest.fixture
def drop_all_data_in_db(db_connection: sqlite3.Connection) -> Generator[None, None, None]:
    """
    Фикстура для удаления всех данных из базы по окончанию теста.
    Все  действия по удалению происходят в TEARDOWN теста.

    Args:
        db_connection (sqlite3.Connection): Объект для взаимодействия с базой
    """

    yield

    cursor = db_connection.cursor()
    cursor.execute('DELETE FROM hosts')

    db_connection.commit()


@pytest.fixture(scope='session')
def test_ssh_server() -> Generator[None, None, None]:
    """
    Фикстура для запуска Docker контейнера выполняющего роль тестового сервера,
    к которому происходит подключение по SSH протоколу в тестах.
    В запускаемом контейнере будет запущен "ping" c выводом отчета в файл следующей командой:
    "ping localhost > /tmp/ping.log"
    """

    client = docker.from_env()
    try:
        _ = client.images.get('test_ssh_server')
    except docker.errors.ImageNotFound:
        _ = client.images.build(path='docker', tag='test_ssh_server', network_mode='host')
    container = client.containers.run(
        image='test_ssh_server', ports={'10022/tcp': [10022, 10023]}, cap_add=['NET_ADMIN', 'CAP_NET_RAW'], detach=True
    )

    yield

    container.stop()
