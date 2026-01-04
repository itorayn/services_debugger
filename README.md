# services_debugger

## Install requirements
### Install uv
`pip install --break-system-packages uv`


### Install python requirements
`uv sync --no-dev`

## Install development requirements
### Install docker
1. https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository
2. `sudo adduser $USER docker`

### Install all python requirements (with development tools)
`uv sync`

## Start
Запуск: `uv run uvicorn app.main:app`
Swagger: http://127.0.0.1:8000/docs