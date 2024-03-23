import sqlite3

import pytest
import docker
from fastapi.testclient import TestClient

from services_debugger.main import app


@pytest.fixture(scope='session')
def test_client() -> TestClient:
    client = TestClient(app)
    return client


@pytest.fixture()
def db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect('test.db')

    yield connection

    connection.commit()
    connection.close()


@pytest.fixture()
def drop_all_data_in_db(db_connection: sqlite3.Connection):

    yield

    cursor = db_connection.cursor()
    cursor.execute('DELETE FROM hosts')


@pytest.fixture(scope='session')
def test_ssh_server():
    client = docker.from_env()
    try:
        _ = client.images.get('test_ssh_server')
    except docker.errors.ImageNotFound:
        _ = client.images.build(path='docker',
                                tag='test_ssh_server',
                                network_mode='host')
    container = client.containers.run(image='test_ssh_server',
                                      ports={'10022/tcp': [10022, 10023]},
                                      cap_add=['NET_ADMIN', 'CAP_NET_RAW'],
                                      detach=True)

    yield

    container.stop()
