from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .sessions.pool import ConnectionPool, get_pool

DOMAIN_LABELS = {
    "Secure": "Thiết kế kiến trúc bảo mật",
    "Resilient": "Thiết kế kiến trúc kiên cường",
    "High-Performing": "Thiết kế kiến trúc hiệu năng cao",
    "Cost-Optimized": "Thiết kế kiến trúc tối ưu chi phí",
}

# Chỉ câu có đủ 4 phương án và đáp án xác định mới đưa vào bài luyện.
_ELIGIBLE = """
    correct_answer is not null
    and jsonb_typeof(options) = 'array'
    and jsonb_array_length(options) = 4
"""

_OPTION_LABELS = ("A", "B", "C", "D")


class QuizNotConfigured(RuntimeError):
    """Thiếu cấu hình cơ sở dữ liệu cho quiz."""


@dataclass(frozen=True)
class QuizQuestionRecord:
    id: UUID
    question: str
    domain: str | None
    options: list[dict[str, str]]
    correct_answer: str
    explanation: str | None
    source: str | None


@dataclass(frozen=True)
class GradedAnswer:
    question_id: UUID
    question: str
    domain: str | None
    selected: str | None
    correct_answer: str
    is_correct: bool
    explanation: str | None
    source: str | None


class QuizService:
    def __init__(self, pool: ConnectionPool | None = None) -> None:
        self._pool = pool

    def _connection_pool(self) -> ConnectionPool:
        if self._pool is not None:
            return self._pool
        try:
            return get_pool()
        except ValueError as exc:
            raise QuizNotConfigured("Chưa cấu hình DATABASE_URL cho quiz") from exc

    def domains(self) -> list[dict[str, Any]]:
        with self._connection_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    select domain, count(*)::int as count
                    from public.questions
                    where {_ELIGIBLE} and domain is not null
                    group by domain
                    """
                )
                counts = {row["domain"]: int(row["count"]) for row in cur.fetchall()}
        items = [
            {"code": code, "label": label, "count": counts.get(code, 0)}
            for code, label in DOMAIN_LABELS.items()
        ]
        for code, count in counts.items():
            if code not in DOMAIN_LABELS:
                items.append({"code": code, "label": code, "count": count})
        return items

    def pick(self, domain: str | None, count: int) -> list[QuizQuestionRecord]:
        if domain is not None and domain not in DOMAIN_LABELS:
            raise ValueError(f"Lĩnh vực không hợp lệ: {domain}")
        with self._connection_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    select id, question, domain, options, correct_answer, explanation, source
                    from public.questions
                    where {_ELIGIBLE}
                      and (%s::text is null or domain = %s)
                    order by random()
                    limit %s
                    """,
                    (domain, domain, count),
                )
                rows = cur.fetchall()
        questions: list[QuizQuestionRecord] = []
        for row in rows:
            options = _shuffle_options(row["options"])
            if len(options) < 4:
                continue
            questions.append(_record(row, options))
        return questions

    def grade(self, answers: list[tuple[UUID, str | None]]) -> list[GradedAnswer]:
        if not answers:
            return []
        selected_by_id = dict(answers)
        with self._connection_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    select id, question, domain, correct_answer, explanation, source
                    from public.questions
                    where id = any(%s)
                    """,
                    (list(selected_by_id),),
                )
                rows = {row["id"]: row for row in cur.fetchall()}
        graded: list[GradedAnswer] = []
        for question_id, selected in answers:
            row = rows.get(question_id)
            if row is None:
                continue
            correct_answer = str(row["correct_answer"])
            graded.append(
                GradedAnswer(
                    question_id=question_id,
                    question=row["question"],
                    domain=row["domain"],
                    selected=selected,
                    correct_answer=correct_answer,
                    is_correct=_same_answer(selected, correct_answer),
                    explanation=row["explanation"],
                    source=row["source"],
                )
            )
        return graded

    def save_attempt(
        self,
        user_id: UUID,
        *,
        domain: str | None,
        total: int,
        correct: int,
        details: list[dict[str, Any]],
        duration_seconds: int | None = None,
    ) -> UUID:
        attempt_id = uuid4()
        with self._connection_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.quiz_attempts (
                        id, user_id, domain, total_questions, correct_count,
                        duration_seconds, details
                    ) values (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        attempt_id,
                        user_id,
                        domain,
                        total,
                        correct,
                        duration_seconds,
                        Jsonb(details),
                    ),
                )
        return attempt_id

    def list_attempts(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        with self._connection_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "select count(*)::int as total from public.quiz_attempts where user_id = %s",
                    (user_id,),
                )
                total = int((cur.fetchone() or {"total": 0})["total"])
                cur.execute(
                    """
                    select id, domain, total_questions, correct_count, created_at
                    from public.quiz_attempts
                    where user_id = %s
                    order by created_at desc
                    limit %s offset %s
                    """,
                    (user_id, limit, offset),
                )
                rows = [dict(row) for row in cur.fetchall()]
        return rows, total

    def delete_attempts(self, user_id: UUID) -> int:
        with self._connection_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from public.quiz_attempts where user_id = %s returning id",
                    (user_id,),
                )
                return len(cur.fetchall())


def _record(row: dict[str, Any], options: list[dict[str, str]]) -> QuizQuestionRecord:
    return QuizQuestionRecord(
        id=row["id"],
        question=row["question"],
        domain=row["domain"],
        options=options,
        correct_answer=str(row["correct_answer"]),
        explanation=row["explanation"],
        source=row["source"],
    )


def _shuffle_options(raw: Any) -> list[dict[str, str]]:
    texts = [
        str(item.get("text") or "").strip()
        for item in raw
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    # Đáp án đúng trong dữ liệu luôn ở vị trí A; xáo trộn để tránh đoán mò.
    random.SystemRandom().shuffle(texts)
    return [
        {"label": _OPTION_LABELS[index], "text": text}
        for index, text in enumerate(texts[: len(_OPTION_LABELS)])
    ]


def _same_answer(selected: str | None, correct: str) -> bool:
    return bool(selected) and selected.strip() == correct.strip()


def attempt_score(correct: int, total: int) -> float:
    return round(correct / total, 4) if total else 0.0


def attempt_details(graded: list[GradedAnswer]) -> list[dict[str, Any]]:
    return [
        {
            "question_id": str(item.question_id),
            "question": item.question,
            "domain": item.domain,
            "selected": item.selected,
            "correct_answer": item.correct_answer,
            "is_correct": item.is_correct,
            "explanation": item.explanation,
            "source": item.source,
        }
        for item in graded
    ]
