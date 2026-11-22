from __future__ import annotations

from pathlib import Path

from .config import PROMPT_ROOT
from .providers import LLMMessage

MODES = ("base", "compare", "multi_constraint", "abstain")
QUERY_TYPE_MODES = {
    "tra_cuu": "base",
    "tron_thuat_ngu": "base",
    "so_sanh": "compare",
    "nhieu_rang_buoc": "multi_constraint",
}

SCHEMA_REMINDER = (
    "Trả về DUY NHẤT một đối tượng JSON hợp lệ với các khóa: "
    "answer, reasoning_steps, citations, confidence, abstained, abstention_type, nearest_topics. "
    "Không bọc trong khối mã markdown, không thêm văn bản ngoài JSON."
)


class PromptLibrary:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else PROMPT_ROOT
        self._cache: dict[str, str] = {}

    def load(self, name: str) -> str:
        if name not in self._cache:
            path = self.root / f"{name}.md"
            if not path.exists():
                raise FileNotFoundError(f"Không tìm thấy prompt: {path}")
            self._cache[name] = path.read_text(encoding="utf-8").strip()
        return self._cache[name]

    def system_prompt(self, *, mode: str = "base", use_cot: bool = True) -> str:
        if mode not in MODES:
            raise ValueError(f"Prompt mode không hợp lệ: {mode}")
        parts = [self.load("system_base")]
        if use_cot:
            parts.append(self.load("system_cot"))
        if mode in ("compare", "multi_constraint", "abstain"):
            parts.append(self.load(mode))
        parts.append(self.load("abstain"))
        return "\n\n---\n\n".join(dict.fromkeys(parts))

    def build(
        self,
        *,
        question: str,
        context_text: str,
        mode: str = "base",
        use_cot: bool = True,
        extra_instruction: str | None = None,
        conversation: str | None = None,
    ) -> list[LLMMessage]:
        system = self.system_prompt(mode=mode, use_cot=use_cot)
        body_sections = []
        if context_text.strip():
            body_sections.append(f"# NGỮ CẢNH\n\n{context_text.strip()}")
        else:
            body_sections.append("# NGỮ CẢNH\n\n(không có đoạn tài liệu nào được truy xuất)")
        if conversation and conversation.strip():
            body_sections.append(
                "# NGỮ CẢNH HỘI THOẠI\n\n"
                f"{conversation.strip()}\n\n"
                "Chỉ dùng phần hội thoại để hiểu câu hỏi. Mọi khẳng định kỹ thuật phải dựa "
                "trên # NGỮ CẢNH tài liệu; không coi hội thoại là nguồn trích dẫn."
            )
        body_sections.append(f"# CÂU HỎI\n\n{question.strip()}")
        instructions = [SCHEMA_REMINDER]
        if extra_instruction:
            instructions.append(extra_instruction.strip())
        body_sections.append("# YÊU CẦU ĐẦU RA\n\n" + "\n".join(instructions))
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content="\n\n".join(body_sections)),
        ]


def mode_for_query_type(query_type: str | None) -> str:
    return QUERY_TYPE_MODES.get(query_type or "", "base")
