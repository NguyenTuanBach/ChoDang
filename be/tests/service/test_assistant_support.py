from vin15.domain.pii import PiiRedactor
from vin15.service.agent.assistant_limits import AskRateLimiter, ConnectionLimiter
from vin15.service.agent.ws_ticket_store import WsTicketStore


def test_ticket_is_single_use():
    store = WsTicketStore()
    ticket = store.issue(7)
    assert store.consume(ticket) == 7
    assert store.consume(ticket) is None


def test_ticket_expires_after_ttl_and_unknown_is_rejected():
    now = [0.0]
    store = WsTicketStore(ttl_seconds=30, clock=lambda: now[0])
    ticket = store.issue(7)
    now[0] = 31.0
    assert store.consume(ticket) is None
    assert store.consume("khong-co") is None
    fresh = store.issue(8)
    now[0] = 60.0
    assert store.consume(fresh) == 8  # 29 giây sau khi cấp: còn hạn


def test_tickets_are_unguessable_and_distinct():
    store = WsTicketStore()
    tickets = {store.issue(1) for _ in range(50)}
    assert len(tickets) == 50 and all(len(t) >= 24 for t in tickets)


def test_ask_rate_limiter_sliding_window_per_user():
    now = [0.0]
    limiter = AskRateLimiter(2, clock=lambda: now[0])
    assert limiter.try_acquire(1) == (True, 0) and limiter.try_acquire(1) == (True, 0)
    allowed, wait = limiter.try_acquire(1)
    assert not allowed and 1 <= wait <= 61
    assert limiter.try_acquire(2)[0]  # người khác không bị ảnh hưởng
    now[0] = 61.0
    assert limiter.try_acquire(1)[0]


def test_connection_limiter():
    limiter = ConnectionLimiter(2)
    assert limiter.acquire(1) and limiter.acquire(1) and not limiter.acquire(1)
    assert limiter.acquire(2)
    limiter.release(1)
    assert limiter.acquire(1)
    limiter.release(9)  # release thừa không lỗi


def test_pii_redactor_masks_email_phone_tax_and_student_id():
    redactor = PiiRedactor(r"\bSV\d{6}\b")
    text, mapping = redactor.redact(
        "Liên hệ a.b@truong.edu.vn hoặc 0912 345 678, +84912345678; MST 0123456789-001; mã SV202345; lại a.b@truong.edu.vn"
    )
    assert "truong.edu.vn" not in text and "0912" not in text and "0123456789" not in text and "SV202345" not in text
    assert text.count("[EMAIL_1]") == 2  # cùng giá trị cùng nhãn
    assert {"[EMAIL_1]", "[SDT_1]", "[SDT_2]", "[MST_1]", "[MASV_1]"} <= set(mapping)
    assert mapping["[EMAIL_1]"] == "a.b@truong.edu.vn"


def test_pii_redactor_leaves_normal_text_and_ignores_bad_pattern():
    assert (
        PiiRedactor("(").redact_text("Thời lượng tối thiểu 8 tuần, hạn 2026-11-21, Điều 5.")
        == "Thời lượng tối thiểu 8 tuần, hạn 2026-11-21, Điều 5."
    )
