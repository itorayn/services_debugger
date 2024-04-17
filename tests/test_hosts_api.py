import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def first_host() -> dict:
    return {
        'name': 'first_service',
        'description': 'Core service (Node 1)',
        'ssh_address': '127.0.0.1',
        'ssh_port': 9022,
        'username': 'test_user_1',
        'password': 'test_password_1'
    }


@pytest.fixture()
def add_first_host_in_db(db_connection: sqlite3.Connection, first_host: dict):
    cursor = db_connection.cursor()
    insert_req = ('INSERT INTO hosts '
                  f'({", ".join(first_host.keys())}) VALUES '
                  f'({", ".join(map(lambda value: repr(value), first_host.values()))})')
    cursor.execute(insert_req)
    db_connection.commit()


@pytest.fixture()
def second_host() -> dict:
    return {
        'name': 'second_service',
        'description': 'Core service (Node 2)',
        'ssh_address': '127.0.0.2',
        'ssh_port': 10022,
        'username': 'test_user_1',
        'password': 'test_password_2'
    }


@pytest.fixture()
def add_second_host_in_db(db_connection: sqlite3.Connection, second_host: dict):
    cursor = db_connection.cursor()
    insert_req = ('INSERT INTO hosts '
                  f'({", ".join(second_host.keys())}) VALUES '
                  f'({", ".join(map(lambda value: repr(value), second_host.values()))})')
    cursor.execute(insert_req)
    db_connection.commit()


def check_record_in_db(db: sqlite3.Connection, record: dict):
    cursor = db.cursor()
    select_req = 'SELECT * FROM hosts WHERE ' + ' AND '.join((f'{key}={repr(value)}' for key, value in record.items()))
    result = cursor.execute(select_req)
    assert result.fetchone() is not None


def check_no_record_in_db(db: sqlite3.Connection, record: dict):
    cursor = db.cursor()
    select_req = 'SELECT * FROM hosts WHERE ' + ' AND '.join((f'{key}={repr(value)}' for key, value in record.items()))
    result = cursor.execute(select_req)
    assert result.fetchone() is None


def check_response(response, expected_answer: int = 200):
    assert response.status_code == expected_answer
    assert response.headers['content-type'] == 'application/json'
    assert int(response.headers['content-length']) > 0


@pytest.mark.usefixtures('drop_all_data_in_db')
def test_post_host(test_client: TestClient, first_host: dict, db_connection: sqlite3.Connection):
    response = test_client.post('/api/v1/hosts', json=first_host)
    check_response(response)
    check_record_in_db(db_connection, first_host)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['id'] == 1


@pytest.mark.usefixtures('add_first_host_in_db', 'drop_all_data_in_db')
def test_get_host(test_client: TestClient, first_host: dict):
    response = test_client.get('/api/v1/hosts/1')
    check_response(response)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['host_id'] == 1
    for key, expected_value in first_host.items():
        assert response_data[key] == expected_value


@pytest.mark.usefixtures('add_first_host_in_db', 'drop_all_data_in_db')
def test_get_nonexisting_host(test_client: TestClient):
    response = test_client.get('/api/v1/hosts/12')
    check_response(response, expected_answer=404)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Host not found'


@pytest.mark.usefixtures('add_first_host_in_db', 'add_second_host_in_db', 'drop_all_data_in_db')
def test_get_all_hosts(test_client: TestClient, first_host: dict, second_host: dict):
    response = test_client.get('/api/v1/hosts')
    check_response(response)
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 2

    for index, expected_host_data in enumerate((first_host, second_host)):
        assert isinstance(response_data[index], dict)
        assert response_data[index]['host_id'] == index + 1
        for key, expected_value in expected_host_data.items():
            assert response_data[index][key] == expected_value


@pytest.mark.usefixtures('add_first_host_in_db', 'drop_all_data_in_db')
def test_delete_host(test_client: TestClient, first_host: dict, db_connection: sqlite3.Connection):
    response = test_client.delete('/api/v1/hosts/1')
    check_response(response)
    check_no_record_in_db(db_connection, first_host)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Deleted'


def test_delete_nonexisting_host(test_client: TestClient):
    response = test_client.delete('/api/v1/hosts/12')
    check_response(response, expected_answer=404)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Host not found'


@pytest.mark.usefixtures('add_first_host_in_db', 'drop_all_data_in_db')
def test_update_host(test_client: TestClient, first_host: dict, second_host: dict, db_connection: sqlite3.Connection):
    response = test_client.put('/api/v1/hosts/1', json=second_host)
    check_response(response)
    check_record_in_db(db_connection, second_host)
    check_no_record_in_db(db_connection, first_host)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Updated'


def test_update_nonexisting_host(test_client: TestClient, second_host: dict):
    response = test_client.put('/api/v1/hosts/12', json=second_host)
    check_response(response, expected_answer=404)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Host not found'
