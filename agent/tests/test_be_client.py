"""BeToolsClient (task 8.1): xác thực, ánh xạ lỗi, kiểm chunk_id. BE giả qua httpx.MockTransport."""

import asyncio

import httpx
import pytest

from fakes import FakeBe
from vin15_agent.policy_assistant.be_client import BeToolError, BeToolsClient, is_valid_chunk_id


def client(be, agent_token="", **kw):
    return BeToolsClient("http://be", "tok", agent_token, transport=be.transport(), **kw)


def run(coro):
    return asyncio.run(coro)


def test_sends_service_token_and_optional_on_behalf_of():
    be = FakeBe()
    run(client(be).search("thời lượng", None))
    run(client(be, agent_token="AT-123").me("progress"))
    assert be.requests[0].headers["authorization"] == "Bearer tok" and "x-on-behalf-of" not in be.requests[0].headers
    assert be.requests[1].headers["x-on-behalf-of"] == "AT-123"


def test_search_body_has_no_date_or_subject():
    be = FakeBe()
    run(client(be).search("thời lượng thực tập", [0.1, 0.2], 3))
    import json

    assert json.loads(be.requests[0].content) == {"query": "thời lượng thực tập", "query_vector": [0.1, 0.2], "top_k": 3}


def test_get_chunk_path_and_neighbors_flag():
    be = FakeBe()
    data = run(client(be).get_chunk("QC-TT@v1/d3/k1", True))
    assert data["chunk"]["chunk_id"] == "QC-TT@v1/d3/k1" and data["neighbors"]
    assert be.requests[0].url.path == "/api/agent-tools/policy/chunks/QC-TT@v1/d3/k1"
    assert be.requests[0].url.params["with_neighbors"] == "true"


@pytest.mark.parametrize(
    "status,code",
    [(401, "unauthorized"), (403, "forbidden"), (404, "not_found"), (429, "rate_limited"), (500, "be_error"), (503, "be_error")],
)
def test_error_statuses_are_mapped(status, code):
    be = FakeBe(fail_status=status)
    with pytest.raises(BeToolError) as e:
        run(client(be).search("x", None))
    assert e.value.code in {code, "be_error"} and e.value.status == status


def test_be_error_body_code_is_preserved_and_5xx_message_hidden():
    be = FakeBe()
    with pytest.raises(BeToolError) as e:
        run(client(be).get_chunk("khong-co", False))
    assert e.value.code == "not_found" and "Không có đoạn này" in e.value.message
    secret = FakeBe(fail_status=500)
    with pytest.raises(BeToolError) as e:
        run(client(secret).search("x", None))
    assert e.value.message == "Hệ thống gặp lỗi, thử lại sau"


def test_wrong_service_token_is_401():
    with pytest.raises(BeToolError) as e:
        run(BeToolsClient("http://be", "sai", transport=FakeBe().transport()).search("x", None))
    assert e.value.code == "unauthorized"


def test_timeout_and_connection_errors_are_normalized():
    def boom(request):
        raise httpx.ConnectTimeout("t")

    c = BeToolsClient("http://be", "tok", transport=httpx.MockTransport(boom))
    with pytest.raises(BeToolError) as e:
        run(c.search("x", None))
    assert e.value.code == "be_timeout"

    def down(request):
        raise httpx.ConnectError("x")

    with pytest.raises(BeToolError) as e:
        run(BeToolsClient("http://be", "tok", transport=httpx.MockTransport(down)).me("progress"))
    assert e.value.code == "be_unavailable"


def test_non_json_response_is_normalized():
    c = BeToolsClient("http://be", "tok", transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>")))
    with pytest.raises(BeToolError) as e:
        run(c.search("x", None))
    assert e.value.code == "be_bad_response"


@pytest.mark.parametrize("bad", ["", "../me/internship", "a/../b", "/abs", "có dấu", "a b", "x" * 300, "a?b=1", "a#b"])
def test_chunk_id_validation_blocks_path_tricks(bad):
    assert not is_valid_chunk_id(bad)
    with pytest.raises(BeToolError):
        run(client(FakeBe()).get_chunk(bad))


def test_unknown_personal_endpoint_rejected_and_repr_hides_token():
    with pytest.raises(ValueError):
        run(client(FakeBe()).me("../admin"))
    assert "tok" not in repr(BeToolsClient("http://be", "tok-secret-xyz", "AT-secret"))
