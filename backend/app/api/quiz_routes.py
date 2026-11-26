from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import api_error, get_current_user
from app.core.auth import AuthUser
from app.models.quiz_schemas import (
    DeleteQuizAttemptsResponse,
    QuizAttemptsResponse,
    QuizAttemptSummary,
    QuizDomain,
    QuizDomainsResponse,
    QuizQuestion,
    QuizQuestionOption,
    QuizQuestionsRequest,
    QuizQuestionsResponse,
    QuizResultItem,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services.quiz import (
    DOMAIN_LABELS,
    QuizNotConfigured,
    QuizService,
    attempt_details,
    attempt_score,
)

router = APIRouter(tags=["quiz"])


def get_quiz_service() -> QuizService:
    return QuizService()


@router.get(
    "/quiz/domains",
    response_model=QuizDomainsResponse,
    summary="Số câu hỏi khả dụng theo từng lĩnh vực",
)
def quiz_domains(
    user: AuthUser = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
) -> QuizDomainsResponse:
    try:
        items = service.domains()
    except QuizNotConfigured as exc:
        raise api_error(503, "quiz_unavailable", str(exc)) from None
    return QuizDomainsResponse(
        items=[QuizDomain(**item) for item in items],
        total=sum(item["count"] for item in items),
    )


@router.post(
    "/quiz/questions",
    response_model=QuizQuestionsResponse,
    summary="Lấy một lượt câu hỏi ngẫu nhiên (chưa lộ đáp án)",
)
def quiz_questions(
    payload: QuizQuestionsRequest,
    user: AuthUser = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
) -> QuizQuestionsResponse:
    domain = (payload.domain or "").strip() or None
    try:
        questions = service.pick(domain, payload.count)
    except ValueError as exc:
        raise api_error(400, "invalid_domain", str(exc)) from None
    return QuizQuestionsResponse(
        items=[
            QuizQuestion(
                id=question.id,
                question=question.question,
                domain=question.domain,
                options=[QuizQuestionOption(**option) for option in question.options],
            )
            for question in questions
        ]
    )


@router.post(
    "/quiz/submit",
    response_model=QuizSubmitResponse,
    summary="Chấm bài và lưu lịch sử làm bài",
)
def quiz_submit(
    payload: QuizSubmitRequest,
    user: AuthUser = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
) -> QuizSubmitResponse:
    graded = service.grade([(answer.question_id, answer.selected) for answer in payload.answers])
    if not graded:
        raise api_error(
            400,
            "no_valid_questions",
            "Không tìm thấy câu hỏi hợp lệ để chấm. Bạn tải lại đề và thử lại.",
        )
    correct = sum(1 for item in graded if item.is_correct)
    total = len(graded)
    domain = payload.domain if payload.domain in DOMAIN_LABELS else None
    if domain is None:
        domains = {item.domain for item in graded}
        domain = domains.pop() if len(domains) == 1 and None not in domains else None
    attempt_id = service.save_attempt(
        user.id,
        domain=domain,
        total=total,
        correct=correct,
        details=attempt_details(graded),
        duration_seconds=payload.duration_seconds,
    )
    return QuizSubmitResponse(
        attempt_id=attempt_id,
        domain=domain,
        total=total,
        correct=correct,
        score=attempt_score(correct, total),
        items=[
            QuizResultItem(
                question_id=item.question_id,
                question=item.question,
                domain=item.domain,
                selected=item.selected,
                correct_answer=item.correct_answer,
                is_correct=item.is_correct,
                explanation=item.explanation,
                source=item.source,
            )
            for item in graded
        ],
    )


@router.get(
    "/quiz/attempts",
    response_model=QuizAttemptsResponse,
    summary="Lịch sử làm bài của tôi",
)
def quiz_attempts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
) -> QuizAttemptsResponse:
    rows, total = service.list_attempts(user.id, limit=limit, offset=offset)
    return QuizAttemptsResponse(
        items=[
            QuizAttemptSummary(
                id=row["id"],
                domain=row["domain"],
                total=row["total_questions"],
                correct=row["correct_count"],
                score=attempt_score(row["correct_count"], row["total_questions"]),
                created_at=row["created_at"],
            )
            for row in rows
        ],
        total=total,
    )


@router.delete(
    "/quiz/attempts",
    response_model=DeleteQuizAttemptsResponse,
    summary="Xóa toàn bộ lịch sử làm bài của tôi",
)
def delete_quiz_attempts(
    user: AuthUser = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
) -> DeleteQuizAttemptsResponse:
    return DeleteQuizAttemptsResponse(deleted=service.delete_attempts(user.id))
