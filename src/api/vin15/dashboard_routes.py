"""Dashboard phân tích chất lượng thực tập toàn khóa (GV/QTV) — chỉ đọc, tổng hợp theo phạm vi người gọi."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core import clock
from src.core.auth import require_role
from src.db import get_db
from src.models.orm import User
from src.services.analytics import cohort_dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(user: User = Depends(require_role("lecturer", "admin")), db: Session = Depends(get_db)) -> dict:
    return cohort_dashboard(db, user, clock.today())
