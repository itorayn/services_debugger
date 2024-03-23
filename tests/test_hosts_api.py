import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def first_host() -> dict:
    return {
        'name': 'core',
        'description': 'Core service',
        'ssh_address': '127.0.0.1',
        'ssh_port': 9022,
        'username': 'test_user',
        'password': 'test_password'
    }


def check_record_in_db(db: sqlite3.Connection, record: dict):
    cursor = db.cursor()
    select_req = 'SELECT * FROM hosts WHERE ' + ' AND '.join((f'{key}={repr(value)}' for key, value in record.items()))
    result = cursor.execute(select_req)
    assert result.fetchone() is not None


def check_response(response, expected_answer: int = 200):
    assert response.status_code == expected_answer
    assert response.headers['content-type'] == 'application/json'
    assert int(response.headers['content-length']) > 0


@pytest.mark.usefixtures('drop_all_data_in_db')
def test_post_service(test_client: TestClient, first_host: dict, db_connection: sqlite3.Connection):
    response = test_client.post('/api/v1/hosts', json=first_host)
    check_response(response)
    check_record_in_db(db_connection, first_host)
