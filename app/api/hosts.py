from fastapi import APIRouter, HTTPException

from app.models.host import Host
from app.db.hosts import host_repo


hosts_api = APIRouter()


@hosts_api.post('/api/v1/hosts')
def add_host(host: Host):

    new_host_id = host_repo.add_host(host)
    return {'id': new_host_id}


@hosts_api.get('/api/v1/hosts')
def get_all_hosts():
    hosts = host_repo.get_all_hosts()
    return hosts


@hosts_api.get('/api/v1/hosts/{host_id}')
def get_host(host_id: int):
    try:
        host = host_repo.get_host(host_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail='Host not found') from err

    return host


@hosts_api.delete('/api/v1/hosts/{host_id}')
def delete_host(host_id: int):
    try:
        host_repo.delete_host(host_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail='Host not found') from err
    return {'detail': 'Deleted'}


@hosts_api.put('/api/v1/hosts/{host_id}')
def update_host(host: Host, host_id: int):
    try:
        host_repo.update_host(host, host_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail='Host not found') from err
    return {'detail': 'Updated'}
