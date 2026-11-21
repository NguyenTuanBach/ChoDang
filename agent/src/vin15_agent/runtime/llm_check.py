"""Gọi thử LLM một câu để xác nhận khóa và đường dự phòng: ``uv run python -m vin15_agent.runtime.llm_check``."""

from __future__ import annotations

import asyncio
import sys

from vin15_agent.core.ai_client import AiClient, LlmUnavailableError
from vin15_agent.shared.settings import get_settings


async def _run() -> int:
    client = AiClient.from_settings(get_settings())
    print("Đường LLM đã cấu hình:", ", ".join(client.providers) or "(không có)")
    try:
        result = await client.complete([{"role": "user", "content": "Trả lời đúng một từ: pong"}])
    except LlmUnavailableError as exc:
        print("THẤT BẠI:", exc)
        return 1
    except Exception as exc:  # lỗi không tạm thời: khóa sai, model không tồn tại...
        print(f"THẤT BẠI ({type(exc).__name__}):", exc)
        return 1
    print(f"OK qua '{result.provider}' ({result.model}): {result.text!r}; token {result.prompt_tokens}+{result.completion_tokens}")
    return 0


def main() -> None:
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
