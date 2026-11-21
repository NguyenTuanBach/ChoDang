from __future__ import annotations

from pathlib import Path


class LocalFileStorage:
    """Đĩa cục bộ (dev/test hoặc khi chưa có R2). Khóa là đường dẫn tương đối do hệ thống sinh, được chặn thoát khỏi thư mục gốc."""

    def __init__(self, root: Path):
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if self._root != path and self._root not in path.parents:
            raise ValueError("Khóa tệp không hợp lệ")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
