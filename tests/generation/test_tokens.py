from __future__ import annotations

from app.services.generation.config import GenerationConfig
from app.services.generation.context import build_context, fit_context_to_tokens
from app.services.generation.providers import FallbackChain, LLMMessage
from app.services.generation.service import GenerationService
from app.services.generation.tokens import PromptTokenCounter, audit_prompt
from conftest import FakeProvider, answer_json, make_chunk


class _WordCounter:
    exact = True

    def count(self, text: str) -> int:
        return len(text.split())


class _FakePrompts:
    def build(
        self,
        *,
        question: str,
        context_text: str,
        mode: str,
        use_cot: bool,
        conversation: str | None = None,
    ) -> list[LLMMessage]:
        system = "HỆ THỐNG\n\n---\n\n# Ví dụ ngắn\nví dụ một\n\n---\n\n# Quy tắc\nngắn gọn"
        parts: list[str] = []
        if conversation:
            parts.append("# NGỮ CẢNH HỘI THOẠI\n" + conversation)
        parts.append("# NGỮ CẢNH\n" + context_text)
        parts.append("# CÂU HỎI\n" + question)
        parts.append("# YÊU CẦU ĐẦU RA\nJSON")
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content="\n\n".join(parts)),
        ]


def _service(**overrides) -> GenerationService:
    config = GenerationConfig.from_dict({"prompt_version": "v1", **overrides})
    texts = [answer_json()]
    return GenerationService(config, FallbackChain([FakeProvider(texts)]), prompts=_FakePrompts())


def _chunks(count: int, *, chars: int = 300) -> list:
    return [
        make_chunk(
            f"child-{index}",
            section=f"Mục 1.{index}",
            content=("nội dung " + "dữ liệu " * (chars // 7)).strip(),
            rank=index,
        )
        for index in range(1, count + 1)
    ]


def test_audit_prompt_tach_thanh_phan() -> None:
    counter = _WordCounter()
    system = "vai trò\n\nhướng dẫn"
    conversation = "người dùng hỏi trước đó"
    context = "[ĐOẠN 1]\nTài liệu: A\nMục: 1.1\nNội dung:\nS3 Standard"
    question = "S3 Standard là gì?"
    instruction = "Trả JSON"
    user = "\n\n".join(
        [
            "# NGỮ CẢNH HỘI THOẠI\n" + conversation,
            "# NGỮ CẢNH\n" + context,
            "# CÂU HỎI\n" + question,
            "# YÊU CẦU ĐẦU RA\n" + instruction,
        ]
    )
    messages = [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content=user),
    ]
    audit = audit_prompt(messages, counter, limit_tokens=100)
    assert audit.exact is True
    assert audit.few_shot_tokens == 0
    assert audit.system_tokens == counter.count(system)
    assert audit.conversation_tokens == counter.count(conversation)
    assert audit.context_tokens == counter.count(context)
    assert audit.question_tokens == counter.count(question)
    assert audit.instruction_tokens == counter.count(instruction)
    assert audit.total_tokens == counter.count(system) + counter.count(user) + audit.overhead_tokens
    assert audit.over_limit is False


def test_audit_prompt_tach_few_shot_khoi_system() -> None:
    counter = _WordCounter()
    system = "# Vai trò\nquy tắc\n\n---\n\n# Ví dụ ngắn\na b c\n\n---\n\n# Ghi chú\ncuối"
    messages = [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content="# CÂU HỎI\nhỏi"),
    ]
    audit = audit_prompt(messages, counter)
    assert audit.few_shot_tokens == counter.count("# Ví dụ ngắn\na b c")
    assert audit.system_tokens == counter.count(system) - audit.few_shot_tokens


def test_audit_prompt_danh_dau_vuot_tran() -> None:
    messages = [LLMMessage(role="user", content="# CÂU HỎI\nmột hai ba")]
    assert audit_prompt(messages, _WordCounter(), limit_tokens=2).over_limit is True
    assert audit_prompt(messages, _WordCounter(), limit_tokens=100).over_limit is False


def test_prompt_audit_duoc_ghi_vao_ket_qua() -> None:
    service = _service()
    result = service.answer("hỏi", chunks=_chunks(1))
    audit = result.extra["prompt_audit"]
    assert audit is not None
    assert audit["total_tokens"] > 0
    assert audit["exact"] is True


def test_build_prompt_thu_ngu_canh_khi_vuot_tran() -> None:
    service = _service(max_context_tokens=1200, chars_per_token=1.0, max_prompt_tokens=150)
    service.token_counter = _WordCounter()
    chunks = _chunks(4)
    initial = build_context(chunks, max_context_tokens=1200, chars_per_token=1.0)
    assert len(initial.blocks) >= 2
    _, context, audit, warnings = service._build_prompt(
        question="hỏi",
        context=initial,
        prompt_mode="default",
        use_cot=True,
        conversation=None,
    )
    assert len(context.blocks) < len(initial.blocks)
    assert audit.over_limit is False
    assert any("thu ngữ cảnh" in warning for warning in warnings)


def test_build_prompt_bo_hoi_thoai_khi_khong_the_thu_them() -> None:
    service = _service(max_context_tokens=400, chars_per_token=1.0, max_prompt_tokens=160)
    service.token_counter = _WordCounter()
    chunks = _chunks(1)
    initial = build_context(chunks, max_context_tokens=400, chars_per_token=1.0)
    conversation = "lượt cũ " * 400
    messages, _, audit, warnings = service._build_prompt(
        question="hỏi",
        context=initial,
        prompt_mode="default",
        use_cot=True,
        conversation=conversation,
    )
    assert audit.over_limit is False
    assert audit.conversation_tokens == 0
    assert conversation.strip() not in messages[1].content
    assert any("bỏ ngữ cảnh hội thoại" in warning for warning in warnings)


def test_build_prompt_cat_ngu_canh_bang_tokenizer_that_khi_uoc_luong_thap() -> None:
    service = _service(max_context_tokens=1200, chars_per_token=3.5, max_prompt_tokens=60)
    service.token_counter = _WordCounter()
    chunks = _chunks(1)
    initial = build_context(chunks, max_context_tokens=1200, chars_per_token=3.5)
    _, context, audit, warnings = service._build_prompt(
        question="hỏi",
        context=initial,
        prompt_mode="default",
        use_cot=True,
        conversation=None,
    )
    assert len(context.text) < len(initial.text)
    assert audit.over_limit is False
    assert any("thu ngữ cảnh" in warning for warning in warnings)


def test_fit_context_to_tokens_tra_rong_khi_khong_con_ngan_sach() -> None:
    context = build_context(_chunks(1), max_context_tokens=1200, chars_per_token=3.5)
    fitted = fit_context_to_tokens(context, count_tokens=_WordCounter().count, max_tokens=0)
    assert fitted.is_empty is True
    assert fitted.text == ""
    assert fitted.dropped_blocks == len(context.blocks)


def test_token_counter_lui_ve_uoc_luong_khi_thieu_tokenizer(tmp_path) -> None:
    counter = PromptTokenCounter(chars_per_token=2.0, tokenizer_path=tmp_path / "khong-co.json")
    assert counter.exact is False
    assert counter.count("abcd") == 2
