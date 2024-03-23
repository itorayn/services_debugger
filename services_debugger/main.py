from fastapi import FastAPI, HTTPException

from .host_model import Host
from .database import host_repo


app = FastAPI()


@app.post('/api/v1/hosts')
def add_host(host: Host):
   new_host_id = host_repo.add_host(host)
   return {'id': new_host_id}


@app.get('/api/v1/hosts')
def get_all_hosts():
   hosts = host_repo.get_all_hosts()
   return hosts


@app.get('/api/v1/hosts/{host_id}')
def get_host(host_id: int):
   try:
      host = host_repo.get_host(host_id)
   except LookupError:
      raise HTTPException(status_code=404, detail='Host not found')

   return host


@app.delete('/api/v1/hosts/{host_id}')
def delete_host(host_id: int):
   try:
      host_repo.delete_host(host_id)
   except LookupError:
      raise HTTPException(status_code=404, detail='Host not found')
   return {'detail': 'Deleted'}


@app.put('/api/v1/hosts/{host_id}')
def update_host(host: Host, host_id: int):
   try:
      host_repo.update_host(host, host_id)
   except LookupError:
      raise HTTPException(status_code=404, detail='Host not found')
   return {'detail': 'Updated'}
