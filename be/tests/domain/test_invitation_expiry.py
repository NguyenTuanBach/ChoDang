"""Hạn lời mời 3 giờ: chỉ lời mời còn ở trạng thái ``invited`` mới có thể hết hạn."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from tests.fakes import make_user
from vin15.domain.model.user import INVITATION_TTL, Role, UserStatus

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def _invited(age: timedelta, status: UserStatus = UserStatus.INVITED):
    return replace(make_user(10, "sv@truong.edu.vn", Role.STUDENT, status), invited_at=NOW - age)


def test_ttl_is_three_hours():
    assert INVITATION_TTL == timedelta(hours=3)


def test_invitation_within_ttl_is_valid():
    assert not _invited(timedelta(hours=2, minutes=59)).invitation_expired(NOW)


def test_invitation_past_ttl_is_expired():
    assert _invited(timedelta(hours=3, minutes=1)).invitation_expired(NOW)


def test_active_or_revoked_never_expires():
    assert not _invited(timedelta(days=9), UserStatus.ACTIVE).invitation_expired(NOW)
    assert not _invited(timedelta(days=9), UserStatus.REVOKED).invitation_expired(NOW)


def test_missing_invited_at_is_not_expired():
    assert not make_user(11, "x@truong.edu.vn", Role.STUDENT, UserStatus.INVITED).invitation_expired(NOW)
