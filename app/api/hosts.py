from fastapi import APIRouter, HTTPException

from app.db.hosts import host_repo
from app.models.host import Host

hosts_api = APIRouter()


@hosts_api.post('/api/v1/hosts')
def add_host(host: Host) -> dict[str, int]:
    """Добавление новой записи хоста."""

    new_host_id = host_repo.add_host(host)
    return {'id': new_host_id}


@hosts_api.get('/api/v1/hosts')
def get_all_hosts() -> list[Host]:
    """Извлечение всех записей хостов."""

    return host_repo.get_all_hosts()


@hosts_api.get('/api/v1/hosts/{host_id}')
def get_host(host_id: int) -> Host:
    """Извлечение записи хоста по его идентификатору."""

    try:
        host = host_repo.get_host(host_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail='Host not found') from err

    return host


@hosts_api.delete('/api/v1/hosts/{host_id}')
def delete_host(host_id: int) -> dict[str, str]:
    """Удаление записи хоста с указанными идентификатором."""

    try:
        host_repo.delete_host(host_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail='Host not found') from err
    return {'detail': 'Deleted'}


@hosts_api.put('/api/v1/hosts/{host_id}')
def update_host(host: Host, host_id: int) -> dict[str, str]:
    """Обновление записи хосте."""

    try:
        host_repo.update_host(host, host_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail='Host not found') from err
    return {'detail': 'Updated'}
