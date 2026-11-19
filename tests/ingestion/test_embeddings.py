from __future__ import annotations

import json

import httpx
import pytest

from ingestion.embeddings import (
    EmbeddingClient,
    EmbeddingError,
    EmbeddingQuotaError,
    vector_literal,
)


def _client(
    handler,
    api_key: str | list[str] = "test-key",
    batch_size: int = 2,
    sleep=None,
    tokens_per_minute: int | None = None,
    max_tokens_per_request: int = 20_000,
) -> EmbeddingClient:
    return EmbeddingClient(
        api_key,
        batch_size=batch_size,
        tokens_per_minute=tokens_per_minute,
        max_tokens_per_request=max_tokens_per_request,
        transport=httpx.MockTransport(handler),
        sleep=sleep or (lambda _seconds: None),
    )


def _daily_quota_response() -> httpx.Response:
    return httpx.Response(
        429,
        text='{"error": {"code": 429, "message": "Quota exceeded for metric: '
        "generativelanguage.googleapis.com/embed_content_free_tier_requests, "
        'limit: 1000 ... per day limit exceeded on Free Tier."}}',
    )


def _response(count: int, dims: int = 768) -> httpx.Response:
    return httpx.Response(
        200,
        json={"embeddings": [{"values": [0.01] * dims} for _ in range(count)]},
    )


def test_chia_lo_va_dung_dinh_dang_request():
    payloads: list[dict] = []
    headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        headers.append(request.headers["x-goog-api-key"])
        payload = json.loads(request.content)
        payloads.append(payload)
        return _response(len(payload["requests"]))

    client = _client(handler, batch_size=2)
    result = client.embed_texts(["một", "hai", "ba"])
    assert len(result.vectors) == 3
    assert all(len(vector) == 768 for vector in result.vectors)
    assert result.batches == 2
    assert result.retries == 0
    assert [len(payload["requests"]) for payload in payloads] == [2, 1]
    first = payloads[0]["requests"][0]
    assert first["model"] == "models/gemini-embedding-001"
    assert first["taskType"] == "RETRIEVAL_DOCUMENT"
    assert first["outputDimensionality"] == 768
    assert headers == ["test-key", "test-key"]


def test_retry_khi_gap_429_va_503():
    attempts = {"count": 0}
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, headers={"retry-after": "2"}, text="quota")
        if attempts["count"] == 2:
            return httpx.Response(503, text="tạm thời")
        return _response(1)

    client = _client(handler, sleep=delays.append)
    result = client.embed_texts(["một đoạn"])
    assert len(result.vectors) == 1
    assert result.retries == 2
    assert attempts["count"] == 3
    assert delays[0] == 2.0
    assert delays[1] >= 3.0


def test_doc_retry_in_tu_body_khi_khong_co_header():
    attempts = {"count": 0}
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(
                429,
                text='{"error": {"message": "Please retry in 7.5s."}}',
            )
        return _response(1)

    client = _client(handler, sleep=delays.append)
    result = client.embed_texts(["một đoạn"])
    assert result.retries == 1
    assert delays[0] == 7.5


def test_chia_lo_theo_gioi_han_token_moi_request():
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        return _response(len(payload["requests"]))

    text = "x" * 230
    client = _client(handler, batch_size=10, max_tokens_per_request=100)
    result = client.embed_texts([text, text, text])
    assert result.batches == 3
    assert [len(payload["requests"]) for payload in payloads] == [1, 1, 1]


def test_gian_nhip_theo_tpm():
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return _response(len(payload["requests"]))

    text = "y" * 23
    client = _client(handler, batch_size=1, sleep=delays.append, tokens_per_minute=60_000)
    client.embed_texts([text, text])
    assert len(delays) == 1
    assert delays[0] == pytest.approx(10 * 60.0 / 60_000)


def test_chuyen_sang_khoa_ke_tiep_khi_can_han_muc_ngay():
    headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.headers["x-goog-api-key"]
        headers.append(key)
        if key == "khoa-1":
            return _daily_quota_response()
        payload = json.loads(request.content)
        return _response(len(payload["requests"]))

    client = _client(handler, api_key="khoa-1,khoa-2", batch_size=2)
    result = client.embed_texts(["một", "hai", "ba"])
    assert len(result.vectors) == 3
    assert result.batches == 2
    assert headers == ["khoa-1", "khoa-1", "khoa-2", "khoa-2"]


def test_toan_bo_khoa_can_han_muc_ngay_thi_bao_loi_ro_rang():
    def handler(request: httpx.Request) -> httpx.Response:
        return _daily_quota_response()

    client = _client(handler, api_key=["khoa-1", "khoa-2"])
    with pytest.raises(EmbeddingQuotaError, match="[Hh]ạn mức") as info:
        client.embed_texts(["một đoạn"])
    assert info.value.done == 0
    assert info.value.total == 1


def test_checkpoint_duoc_goi_sau_moi_lo():
    checkpoints: list[tuple[int, int]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return _response(len(payload["requests"]))

    def checkpoint(done: int, batch_vectors: list[list[float]]) -> None:
        checkpoints.append((done, len(batch_vectors)))

    client = _client(handler, batch_size=2)
    result = client.embed_texts(["một", "hai", "ba"], checkpoint=checkpoint)
    assert checkpoints == [(2, 2), (3, 1)]
    assert len(result.vectors) == 3


def test_tu_choi_doan_vuot_gioi_han_token_mo_hinh():
    client = _client(lambda request: _response(1))
    with pytest.raises(EmbeddingError, match="2048"):
        client.embed_texts(["z" * 5000])


def test_loi_4xx_khong_retry():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(400, text="sai yêu cầu")

    client = _client(handler)
    with pytest.raises(EmbeddingError, match="400"):
        client.embed_texts(["một đoạn"])
    assert attempts["count"] == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"embeddings": [{"values": [0.1] * 767}]}),
        httpx.Response(200, json={"embeddings": []}),
        httpx.Response(200, json={"embeddings": [{"values": ["x"] * 768}]}),
        httpx.Response(200, json={"embeddings": [{"values": [float("nan")] * 768}]}),
    ],
)
def test_kiem_tra_so_chieu_va_gia_tri(response):
    client = _client(lambda request: response)
    with pytest.raises(EmbeddingError):
        client.embed_texts(["một đoạn"])


def test_tu_choi_doan_rong():
    client = _client(lambda request: _response(1))
    with pytest.raises(EmbeddingError, match="rỗng"):
        client.embed_texts(["   "])


def test_embed_texts_rong_khong_goi_api():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return _response(0)

    result = _client(handler).embed_texts([])
    assert result.vectors == []
    assert result.batches == 0
    assert calls["count"] == 0


def test_vector_literal_dung_dinh_dang_pgvector():
    assert vector_literal([1.5, -2.25]) == "[1.5,-2.25]"
    text = vector_literal([0.123456789] * 768)
    assert text.startswith("[") and text.endswith("]")
    assert text.count(",") == 767
