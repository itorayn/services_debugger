import sqlite3

import pytest
from fastapi.testclient import TestClient
from httpx import Response


@pytest.fixture
def first_host() -> dict:
    """
    Фикстура возвращающая словарь с тестовыми значениями первого хоста.

    Returns:
        dict: Словарь с тестовыми значениями первого хоста
    """

    return {
        'name': 'first_service',
        'description': 'Core service (Node 1)',
        'ssh_address': '127.0.0.1',
        'ssh_port': 9022,
        'username': 'test_user_1',
        'password': 'test_password_1',
    }


@pytest.fixture
def add_first_host_in_db(db_connection: sqlite3.Connection, first_host: dict) -> None:
    """
    Фикстура для добавления первой тестовой записи хоста в базу данных.

    Args:
        db_connection (sqlite3.Connection): Подключение к базе данных
        first_host (dict): Словарь с тестовыми значениями первого хоста
    """

    cursor = db_connection.cursor()
    insert_req = (
        f'INSERT INTO hosts ({", ".join(first_host.keys())}) VALUES ({", ".join(map(repr, first_host.values()))})'
    )
    cursor.execute(insert_req)
    db_connection.commit()


@pytest.fixture
def second_host() -> dict:
    """
    Фикстура возвращающая словарь с тестовыми значениями второго хоста.

    Returns:
        dict: Словарь с тестовыми значениями второго хоста
    """

    return {
        'name': 'second_service',
        'description': 'Core service (Node 2)',
        'ssh_address': '127.0.0.2',
        'ssh_port': 10022,
        'username': 'test_user_1',
        'password': 'test_password_2',
    }


@pytest.fixture
def add_second_host_in_db(db_connection: sqlite3.Connection, second_host: dict) -> None:
    """
    Фикстура для добавления второй тестовой записи хоста в базу данных.

    Args:
        db_connection (sqlite3.Connection): Подключение к базе данных
        second_host (dict): Словарь с тестовыми значениями второго хоста
    """

    cursor = db_connection.cursor()
    insert_req = (
        f'INSERT INTO hosts ({", ".join(second_host.keys())}) VALUES ({", ".join(map(repr, second_host.values()))})'
    )
    cursor.execute(insert_req)
    db_connection.commit()


def check_record_in_db(db_connection: sqlite3.Connection, record: dict) -> None:
    """
    Проверка записи хоста в базу данных.

    Args:
        db_connection (sqlite3.Connection): Подключение к базе данных
        record (dict): Словарь с тестовыми значениями хоста которые ожидаются в базе данных
    """

    cursor = db_connection.cursor()
    select_req = 'SELECT * FROM hosts WHERE ' + ' AND '.join((f'{key}={value!r}' for key, value in record.items()))
    result = cursor.execute(select_req)
    assert result.fetchone() is not None


def check_no_record_in_db(db_connection: sqlite3.Connection, record: dict) -> None:
    """
    Проверка отсутствия записи хоста в базу данных.

    Args:
        db_connection (sqlite3.Connection): Подключение к базе данных
        record (dict): Словарь с тестовыми значениями хоста которые должны отсутствовать в базе данных
    """

    cursor = db_connection.cursor()
    select_req = 'SELECT * FROM hosts WHERE ' + ' AND '.join((f'{key}={value!r}' for key, value in record.items()))
    result = cursor.execute(select_req)
    assert result.fetchone() is None


def check_response(response: Response, expected_answer: int = 200) -> None:
    """
    Проверка ответа приложения на запрос.

    Args:
        response (Response): Ответ полученный от приложения
        expected_answer (int, optional): Ожидаемый код ответа. Defaults to 200.
    """

    assert response.status_code == expected_answer
    assert response.headers['content-type'] == 'application/json'
    assert int(response.headers['content-length']) > 0


@pytest.mark.usefixtures('drop_all_data_in_db')
def test_post_host(test_client: TestClient, first_host: dict, db_connection: sqlite3.Connection) -> None:
    """
    Проверка добавления нового хоста.

    Args:
        test_client (TestClient): Тестовый клиент API
        first_host (dict): Словарь с тестовыми значениями первого хоста
        db_connection (sqlite3.Connection): Подключение к базе данных
    """

    response = test_client.post('/api/v1/hosts', json=first_host)
    check_response(response)
    check_record_in_db(db_connection, first_host)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['id'] == 1


@pytest.mark.usefixtures('add_first_host_in_db', 'drop_all_data_in_db')
def test_get_host(test_client: TestClient, first_host: dict) -> None:
    """
    Проверка получения информации о хосте по его идентификатору.

    Args:
        test_client (TestClient): Тестовый клиент API
        first_host (dict): Словарь с тестовыми значениями первого хоста
    """

    response = test_client.get('/api/v1/hosts/1')
    check_response(response)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['host_id'] == 1
    for key, expected_value in first_host.items():
        assert response_data[key] == expected_value


@pytest.mark.usefixtures('add_first_host_in_db', 'drop_all_data_in_db')
def test_get_nonexisting_host(test_client: TestClient) -> None:
    """
    Проверка получения ответа 404 при попытке получить инфо о несуществующем хосте.

    Args:
        test_client (TestClient): Тестовый клиент API
    """

    response = test_client.get('/api/v1/hosts/12')
    check_response(response, expected_answer=404)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Host not found'


@pytest.mark.usefixtures('add_first_host_in_db', 'add_second_host_in_db', 'drop_all_data_in_db')
def test_get_all_hosts(test_client: TestClient, first_host: dict, second_host: dict) -> None:
    """
    Проверка получения информации о всех добавленных хостах.

    Args:
        test_client (TestClient): Тестовый клиент API
        first_host (dict): Словарь с тестовыми значениями первого хоста
        second_host (dict): Словарь с тестовыми значениями второго хоста
    """

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
def test_delete_host(test_client: TestClient, first_host: dict, db_connection: sqlite3.Connection) -> None:
    """
    Проверка удаления информации о хосте по его идентификатору.

    Args:
        test_client (TestClient): Тестовый клиент API
        first_host (dict): Словарь с тестовыми значениями первого хоста
        db_connection (sqlite3.Connection): Подключение к базе данных
    """

    response = test_client.delete('/api/v1/hosts/1')
    check_response(response)
    check_no_record_in_db(db_connection, first_host)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Deleted'


def test_delete_nonexisting_host(test_client: TestClient) -> None:
    """
    Проверка получения ответа 404 при попытке удалить несуществующий хост.

    Args:
        test_client (TestClient): Тестовый клиент API
    """

    response = test_client.delete('/api/v1/hosts/12')
    check_response(response, expected_answer=404)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Host not found'


@pytest.mark.usefixtures('add_first_host_in_db', 'drop_all_data_in_db')
def test_update_host(
    test_client: TestClient, first_host: dict, second_host: dict, db_connection: sqlite3.Connection
) -> None:
    """
    Проверка обновления информации о хосте.

    Args:
        test_client (TestClient): Тестовый клиент API
        first_host (dict): Словарь с тестовыми значениями первого хоста
        second_host (dict): Словарь с тестовыми значениями второго хоста
        db_connection (sqlite3.Connection): Подключение к базе данных
    """

    response = test_client.put('/api/v1/hosts/1', json=second_host)
    check_response(response)
    check_record_in_db(db_connection, second_host)
    check_no_record_in_db(db_connection, first_host)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Updated'


def test_update_nonexisting_host(test_client: TestClient, second_host: dict) -> None:
    """
    Проверка обновления информации о несуществующем хосте.

    Args:
        test_client (TestClient): Тестовый клиент API
        second_host (dict): Словарь с тестовыми значениями второго хоста
    """

    response = test_client.put('/api/v1/hosts/12', json=second_host)
    check_response(response, expected_answer=404)
    response_data = response.json()
    assert isinstance(response_data, dict)
    assert response_data['detail'] == 'Host not found'
