from __future__ import annotations

import json

import pytest
from app.services.generation.providers import LLMResponse, Usage
from app.services.retrieval.types import RetrievedChunk


def make_chunk(
    child_id: str = "child-1",
    *,
    parent_id: str | None = "parent-1",
    content: str = (
        "S3 Standard được thiết kế cho dữ liệu truy cập thường xuyên, độ bền 99,999999999%."
    ),
    document: str = "data/raw/S3_Storage_Classes.pdf",
    document_title: str | None = "S3 Storage Classes",
    section: str | None = "S3 Standard",
    heading: str | None = None,
    rank: int = 1,
) -> RetrievedChunk:
    return RetrievedChunk(
        rank=rank,
        child_id=child_id,
        parent_id=parent_id,
        content=content,
        child_content=content,
        document=document,
        section=section,
        heading=heading,
        page=1,
        score=0.9,
        scores={"vector": 0.9},
        document_title=document_title,
    )


def answer_json(**overrides: object) -> str:
    data = {
        "answer": (
            "S3 Standard phù hợp dữ liệu truy cập thường xuyên "
            "[S3 Storage Classes – S3 Standard]."
        ),
        "reasoning_steps": [
            {
                "buoc": 1,
                "noi_dung": "Đối chiếu đặc điểm dữ liệu với mô tả S3 Standard.",
                "can_cu": ["S3 Storage Classes – S3 Standard"],
            }
        ],
        "citations": [
            {
                "source": "S3 Storage Classes – S3 Standard",
                "quote": "S3 Standard được thiết kế cho dữ liệu truy cập thường xuyên",
            }
        ],
        "confidence": 0.9,
        "abstained": False,
        "abstention_type": "none",
        "nearest_topics": [],
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.calls: list[list] = []
        self.closed = False

    def complete(self, messages, **kwargs) -> LLMResponse:
        self.calls.append(list(messages))
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            usage=Usage.from_counts(100, 50),
            latency_ms=12.5,
            cost_usd=0.0001,
        )

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def chunk() -> RetrievedChunk:
    return make_chunk()
