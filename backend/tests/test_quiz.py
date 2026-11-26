from uuid import uuid4

from app.models.quiz_schemas import QuizSubmitRequest
from app.services.quiz import (
    GradedAnswer,
    _same_answer,
    _shuffle_options,
    attempt_details,
    attempt_score,
)


def test_shuffle_giu_du_bon_phuong_an_va_gan_nhan_lai() -> None:
    raw = [
        {"text": "Đáp án đúng", "label": "A", "is_correct": True},
        {"text": "Nhiễu 1", "label": "B"},
        {"text": "Nhiễu 2", "label": "C"},
        {"text": "Nhiễu 3", "label": "D"},
    ]
    options = _shuffle_options(raw)
    assert [option["label"] for option in options] == ["A", "B", "C", "D"]
    assert {option["text"] for option in options} == {
        "Đáp án đúng",
        "Nhiễu 1",
        "Nhiễu 2",
        "Nhiễu 3",
    }


def test_shuffle_bo_phuong_an_rong() -> None:
    options = _shuffle_options([{"text": "  "}, {"text": "Chỉ một"}])
    assert options == [{"label": "A", "text": "Chỉ một"}]


def test_cham_theo_nguyen_van_dap_an() -> None:
    assert _same_answer("AWS Lambda", "AWS Lambda")
    assert _same_answer("  AWS Lambda  ", "AWS Lambda")
    assert not _same_answer("aws lambda", "AWS Lambda")
    assert not _same_answer(None, "AWS Lambda")
    assert not _same_answer("", "AWS Lambda")


def test_diem_va_details_dung_dinh_dang() -> None:
    assert attempt_score(3, 5) == 0.6
    assert attempt_score(0, 0) == 0.0
    question_id = uuid4()
    graded = [
        GradedAnswer(
            question_id=question_id,
            question="Câu hỏi?",
            domain="Secure",
            selected="Sai",
            correct_answer="Đúng",
            is_correct=False,
            explanation="Vì vậy.",
            source="aws-saa-question-bank",
        )
    ]
    details = attempt_details(graded)
    assert details == [
        {
            "question_id": str(question_id),
            "question": "Câu hỏi?",
            "domain": "Secure",
            "selected": "Sai",
            "correct_answer": "Đúng",
            "is_correct": False,
            "explanation": "Vì vậy.",
            "source": "aws-saa-question-bank",
        }
    ]


def test_request_tu_choi_cau_hoi_trung_lap() -> None:
    question_id = uuid4()
    try:
        QuizSubmitRequest(
            answers=[
                {"question_id": question_id, "selected": "A"},
                {"question_id": question_id, "selected": "B"},
            ]
        )
    except ValueError:
        return
    raise AssertionError("Phải từ chối câu hỏi trùng trong cùng lượt chấm")
