"""Hạ tầng e2e: BE thật (uvicorn trong thread, schema Postgres riêng) + agent THẬT (tiến trình riêng) + máy chủ OpenAI giả.

Không thêm hook test vào code sản phẩm: agent chỉ được trỏ ``OPENAI_BASE_URL`` sang máy chủ giả. Chạy bằng ``make e2e``.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path

import httpx
import psycopg
import pytest
import uvicorn
from websockets.sync.client import connect

from tests.conftest import make_settings
from tests.e2e.fake_openai import FakeOpenAI
from tests.integration.conftest import pg_url  # noqa: F401  (fixture dùng chung: bỏ qua khi không có Postgres)
from vin15.config.container import Container
from vin15.devtools.dev_seed import STUDENT_A_EMAIL, run_seed
from vin15.infrastructure.persistence.database import Database
from vin15.main import create_app

REPO = Path(__file__).resolve().parents[3]
AGENT_PYTHON = REPO / "agent" / ".venv" / "bin" / "python"
SERVICE_TOKEN = "e2e-service-token"
ORIGIN = "http://localhost:3000"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, timeout: float = 30.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if httpx.get(url, timeout=1.0).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError(f"Không lên được: {url}")


class Stack:
    def __init__(self, fake: FakeOpenAI, agent_url: str, be_url: str, container: Container, database: Database):
        self.fake, self.agent_url, self.be_url, self.container, self.database = fake, agent_url, be_url, container, database

    def ask(self, question: str, *, cancel_after_first_frame: bool = False, timeout: float = 30.0) -> list[dict]:
        """Hỏi qua WebSocket FE↔BE như trình duyệt (ticket → auth → ask). Trả mọi khung tới ``final``/``error``."""
        ticket = httpx.post(f"{self.be_url}/api/assistant/ws-ticket", timeout=10).json()["ticket"]
        frames: list[dict] = []
        with connect(self.be_url.replace("http", "ws") + "/api/assistant/ws", origin=ORIGIN, open_timeout=10) as ws:
            ws.send(json.dumps({"type": "auth", "ticket": ticket}))
            assert json.loads(ws.recv(timeout=10))["type"] == "ready"
            ws.send(json.dumps({"type": "ask", "conversation_id": None, "turn_id": "t" + uuid.uuid4().hex[:8], "question": question}))
            cancelled = False
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                frame = json.loads(ws.recv(timeout=timeout))
                frames.append(frame)
                if cancel_after_first_frame and not cancelled:
                    cancelled = True
                    ws.send(json.dumps({"type": "cancel", "turn_id": frame["turn_id"]}))
                if frame["type"] in ("final", "error"):
                    return frames
        raise AssertionError(f"Hết hạn chờ khung kết thúc; đã nhận: {[f['type'] for f in frames]}")


@pytest.fixture(scope="session")
def stack(pg_url):  # noqa: F811
    if not AGENT_PYTHON.exists():
        pytest.skip("Chưa cài môi trường agent (agent/.venv): make install")
    schema = "vin15_e2e_" + uuid.uuid4().hex[:8]
    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute(f'create schema "{schema}"')

    fake = FakeOpenAI(free_port())
    fake.start()
    agent_port, be_port = free_port(), free_port()
    agent_url, be_url = f"http://127.0.0.1:{agent_port}", f"http://127.0.0.1:{be_port}"

    env = {
        **os.environ,
        "APP_ENV": "development",
        "OPENAI_API_KEY": "fake-key",
        "OPENAI_BASE_URL": fake.base_url,
        "OPENAI_MODEL": "fake-model",
        "AICLIENT_BASE_URL": "",
        "AGENT_API_HOST": "127.0.0.1",
        "AGENT_API_PORT": str(agent_port),
        "AGENT_API_SERVICE_TOKEN": SERVICE_TOKEN,
        "BE_API_URL": be_url,
        "AGENT_TURN_SECONDS": "20",
        "LOG_LEVEL": "WARNING",
    }
    agent = subprocess.Popen(
        [str(AGENT_PYTHON), "-c", "from vin15_agent.runtime.api_main import main; main()"],
        cwd=REPO / "agent",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    settings = make_settings(
        database_url=pg_url,
        agent_api_url=agent_url,
        agent_api_service_token=SERVICE_TOKEN,
        jwt_secret="j" * 40,
        agent_dev_default_user_email=STUDENT_A_EMAIL,
        cors_origins=ORIGIN,
        assistant_ask_per_minute=1000,
    )
    container = Container(settings)
    database = Database(pg_url, 1, 6, schema=schema)
    container.database = database
    server = uvicorn.Server(uvicorn.Config(create_app(settings, container), host="127.0.0.1", port=be_port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    try:
        wait_http(f"{agent_url}/healthz")
        thread.start()
        wait_http(f"{be_url}/api/health")
        asyncio.run(run_seed(container))  # migrate (idempotent) + người dùng + quy chế mẫu, embed qua agent thật → máy chủ giả
        yield Stack(fake, agent_url, be_url, container, database)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        agent.terminate()
        try:
            agent.wait(timeout=10)
        except subprocess.TimeoutExpired:
            agent.kill()
        fake.stop()
        with psycopg.connect(pg_url, autocommit=True) as conn:
            conn.execute(f'drop schema if exists "{schema}" cascade')


@pytest.fixture
def fresh(stack: Stack) -> Stack:
    stack.fake.reset()
    return stack
