"""Nạp prompt từ ``agent/prompts/*.md``: có cache, thay ``{{placeholder}}``, báo lỗi khi thiếu/thừa placeholder.

Thay một lượt duy nhất: giá trị được chèn vào KHÔNG bị thay tiếp (một giá trị chứa ``{{x}}`` không thành chỗ chèn mới).
"""

from __future__ import annotations

import re
from pathlib import Path

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class PromptError(ValueError):
    """Prompt thiếu tệp, thiếu hoặc thừa placeholder."""


def find_prompts_dir(configured: str = "") -> Path:
    """Thư mục prompt: cấu hình → ``agent/prompts`` trong repo → ``./prompts`` (Docker: ``/app/prompts``)."""
    candidates = [Path(configured)] if configured else []
    candidates += [Path(__file__).resolve().parents[3] / "prompts", Path.cwd() / "prompts"]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise PromptError("Không tìm thấy thư mục prompts (đặt AGENT_PROMPTS_DIR)")


class PromptLoader:
    def __init__(self, directory: Path | str | None = None) -> None:
        self._dir = Path(directory) if directory else find_prompts_dir()
        self._cache: dict[str, str] = {}

    def raw(self, name: str) -> str:
        if name not in self._cache:
            path = self._dir / f"{name}.md"
            try:
                self._cache[name] = path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise PromptError(f"Không đọc được prompt '{name}' ({path})") from exc
        return self._cache[name]

    def placeholders(self, name: str) -> set[str]:
        return set(_PLACEHOLDER.findall(self.raw(name)))

    def render(self, name: str, /, **values: str) -> str:
        text = self.raw(name)
        expected = set(_PLACEHOLDER.findall(text))
        missing, extra = expected - values.keys(), values.keys() - expected
        if missing:
            raise PromptError(f"Prompt '{name}' thiếu giá trị cho placeholder: {', '.join(sorted(missing))}")
        if extra:
            raise PromptError(f"Prompt '{name}' không có placeholder: {', '.join(sorted(extra))}")
        return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), text)

    def sections(self, name: str, tag: str = "template") -> dict[str, str]:
        """Tách các khối ``<tag id="x">...</tag>`` của một tệp thành ``{x: nội dung}`` (dùng cho mẫu câu cố định)."""
        pattern = re.compile(rf'<{tag}\s+id="(\w+)"\s*>(.*?)</{tag}>', re.DOTALL)
        return {m.group(1): m.group(2).strip() for m in pattern.finditer(self.raw(name))}

    def without_sections(self, name: str, tag: str = "template") -> str:
        """Nội dung tệp sau khi bỏ các khối ``<tag id=...>`` (phần hướng dẫn đưa cho LLM, không kèm mẫu câu)."""
        pattern = re.compile(rf'<{tag}\s+id="\w+"\s*>.*?</{tag}>', re.DOTALL)
        return re.sub(r"\n{3,}", "\n\n", pattern.sub("", self.raw(name))).strip()
