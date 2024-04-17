from fastapi import FastAPI

from app.api.hosts import hosts_api


app = FastAPI()
app.include_router(hosts_api)
