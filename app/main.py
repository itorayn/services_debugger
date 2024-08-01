from fastapi import FastAPI

from app.api.hosts import hosts_api

APP_DESCRIPTION = """
API сервиса для дебага других микросервисов.
"""

app = FastAPI(description=APP_DESCRIPTION)
app.include_router(hosts_api)
