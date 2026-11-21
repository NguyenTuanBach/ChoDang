"""``make seed-dev``: nạp dữ liệu giả (người dùng, hồ sơ thực tập, bộ quy chế mẫu) vào database của dev. Từ chối khi production."""

from __future__ import annotations

import asyncio
import logging
import sys

from vin15.config.container import Container
from vin15.config.settings import get_settings
from vin15.devtools.dev_seed import STUDENT_A_EMAIL, SeedRefusedError, run_seed
from vin15.domain.exception import DatabaseUnavailableError


def main() -> int:
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
    container = Container(get_settings())
    database = None
    try:
        database = container.require_database()
        database.open()
        report = asyncio.run(run_seed(container))
    except SeedRefusedError as error:
        print(f"TỪ CHỐI: {error}", file=sys.stderr)
        return 2
    except DatabaseUnavailableError as error:
        print(f"LỖI: {error}. Đặt DATABASE_URL (Supabase Postgres) trong .env.", file=sys.stderr)
        return 1
    finally:
        if database is not None:
            database.close()
    print(
        f"Đã seed: {report.users} người dùng, {report.internships} hồ sơ thực tập, {report.policy_versions} phiên bản quy chế mẫu "
        f"({report.policy_published_now} mới xuất bản, {report.embedded_chunks} đoạn mới có embedding)."
    )
    for note in report.notes:
        print(f"Lưu ý: {note}")
    print(f"Dev: đặt AGENT_DEV_DEFAULT_USER_EMAIL={STUDENT_A_EMAIL} để agent dùng SV A làm người hỏi mặc định (chỉ ngoài production).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
