from fastapi import Request

from vin15.config.container import Container


def container(request: Request) -> Container:
    return request.app.state.container
