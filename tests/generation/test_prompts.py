from __future__ import annotations

from pathlib import Path

import pytest
from app.services.generation.config import PROMPT_ROOT
from app.services.generation.prompts import PromptLibrary, mode_for_query_type

V1 = PROMPT_ROOT / "v1"


@pytest.mark.parametrize(
    "name",
    ["system_base", "system_cot", "multi_constraint", "compare", "abstain"],
)
def test_required_prompt_files_exist(name: str) -> None:
    text = (V1 / f"{name}.md").read_text(encoding="utf-8")
    assert len(text) > 200


def test_mode_mapping() -> None:
    assert mode_for_query_type("so_sanh") == "compare"
    assert mode_for_query_type("nhieu_rang_buoc") == "multi_constraint"
    assert mode_for_query_type("tra_cuu") == "base"
    assert mode_for_query_type(None) == "base"


def test_system_always_contains_abstain_rules() -> None:
    library = PromptLibrary(V1)
    system = library.system_prompt(mode="base", use_cot=False)
    assert "TỪ CHỐI" in system
    assert "no_evidence" in system
    assert "out_of_scope" in system
    assert "Chain-of-Thought" not in system


def test_cot_toggle_changes_system() -> None:
    library = PromptLibrary(V1)
    with_cot = library.system_prompt(mode="base", use_cot=True)
    assert "Chain-of-Thought" in with_cot
    assert "Bảng kiểm ràng buộc" in with_cot


def test_mode_addendum_included_once() -> None:
    library = PromptLibrary(V1)
    system = library.system_prompt(mode="multi_constraint")
    assert system.count("# Câu hỏi tình huống nhiều ràng buộc (K3)") == 1
    compare = library.system_prompt(mode="compare")
    assert "Câu hỏi so sánh" in compare
    assert "Câu hỏi tình huống nhiều ràng buộc (K3)" not in compare


def test_build_messages_carries_context_and_question() -> None:
    library = PromptLibrary(V1)
    messages = library.build(
        question="S3 Standard là gì?",
        context_text="Tài liệu: X\nMục: Y\nNội dung: Z",
        mode="base",
    )
    assert [message.role for message in messages] == ["system", "user"]
    assert "S3 Standard là gì?" in messages[1].content
    assert "Tài liệu: X" in messages[1].content
    assert "JSON" in messages[1].content


def test_empty_context_is_explicit() -> None:
    library = PromptLibrary(V1)
    messages = library.build(question="Hỏi", context_text="", mode="base")
    assert "không có đoạn tài liệu nào" in messages[1].content


def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValueError, match="mode"):
        PromptLibrary(V1).system_prompt(mode="unknown")


def test_missing_prompt_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        PromptLibrary(tmp_path).load("system_base")
