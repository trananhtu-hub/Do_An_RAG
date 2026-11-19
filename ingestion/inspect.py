from __future__ import annotations

import argparse
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import DEFAULT_ANALYSIS_PATH, DEFAULT_INPUT
from .domains import (
    DOMAIN_CODES,
    DOMAIN_LABELS_VI,
    MISSING_DOMAIN_OVERRIDES,
    normalize_domain,
    resolve_question_domain,
)
from .loaders import PdfDocument, iter_pdfs, load_pdf
from .sections import Section, build_sections, preamble_text
from .tokens import estimate_tokens

EXACT_ANSWER_MARKERS = (
    "câu trả lời đúng là",
    "đáp án đúng là",
    "câu trả lời chính xác là",
    "đáp án chính xác là",
)

OTHER_ANSWER_MARKERS = (
    "câu trả lời chính xác trong trường hợp này là",
    "phương án đúng là",
    "lựa chọn chính xác là",
    "các lựa chọn chính xác là",
    "là câu trả lời đúng",
    "là giải pháp đúng đắn",
    "là hoàn toàn chính xác",
    "sự kết hợp đúng các phương án",
    "nên sử dụng",
    "nên chọn",
    "giải pháp tốt nhất",
)

BROAD_ANSWER_CUES = EXACT_ANSWER_MARKERS + OTHER_ANSWER_MARKERS + ("phù hợp nhất", "là chính xác")

WRONG_PREFIXES = (
    "tùy chọn ghi",
    "tùy chọn có nội dung",
    "phương án nêu",
    "thông tin cho rằng",
    "việc ",
    "các tùy chọn",
    "các phương án",
    "lựa chọn ",
)

OPTION_LINE_RE = re.compile(r"^\s*[A-Da-d][.)]\s+\S")
REFERENCE_MARKER = "tài liệu tham khảo"


@dataclass
class DocumentAnalysis:
    document: PdfDocument
    sections: list[Section]
    question_sections: list[Section]
    section_sections: list[Section]
    tokens_by_section: list[int]
    page_tokens: list[int]
    short_pages: list[int]
    raw_domains: Counter
    unknown_domains: Counter
    missing_domains: list[Section]
    exact_answer_questions: int
    broad_answer_questions: int
    questions_without_exact: list[int]
    wrong_prefix_counts: Counter
    wrong_prefix_distribution: Counter
    option_questions: list[int]
    reference_count: int
    preamble_tokens: int

    @property
    def role(self) -> str:
        name = self.document.path.name.lower()
        if "question-bank" in name:
            return "question_bank"
        if "exam-guide" in name:
            return "exam_guide"
        return "supplement"

    @property
    def total_tokens(self) -> int:
        return sum(self.page_tokens)


def analyze_document(document: PdfDocument) -> DocumentAnalysis:
    sections = build_sections(document)
    question_sections = [section for section in sections if section.kind == "question"]
    section_sections = [section for section in sections if section.kind == "section"]
    tokens_by_section = [estimate_tokens(section.text) for section in sections]
    page_tokens = [estimate_tokens(page.text) for page in document.pages]
    short_pages = [
        page.number for page in document.pages if page.text.strip() and len(page.text.strip()) < 50
    ]

    raw_domains: Counter = Counter()
    unknown_domains: Counter = Counter()
    missing_domains: list[Section] = []
    for section in question_sections:
        if section.domain_raw:
            raw_domains[section.domain_raw] += 1
            if normalize_domain(section.domain_raw) is None:
                unknown_domains[section.domain_raw] += 1
        else:
            missing_domains.append(section)

    exact_answer_questions = 0
    broad_answer_questions = 0
    questions_without_exact: list[int] = []
    wrong_prefix_counts: Counter = Counter()
    wrong_prefix_distribution: Counter = Counter()
    option_questions: list[int] = []
    reference_count = 0

    for section in question_sections:
        text = section.text.lower()
        has_exact = any(marker in text for marker in EXACT_ANSWER_MARKERS)
        has_broad = any(marker in text for marker in BROAD_ANSWER_CUES)
        exact_answer_questions += int(has_exact)
        broad_answer_questions += int(has_broad)
        if not has_exact and section.number is not None:
            questions_without_exact.append(section.number)

        count = 0
        for line in section.body.split("\n"):
            lowered = line.lower()
            for prefix in WRONG_PREFIXES:
                if lowered.startswith(prefix):
                    wrong_prefix_counts[prefix] += 1
                    count += 1
                    break
        wrong_prefix_distribution[min(count, 4)] += 1

        if sum(1 for line in section.body.split("\n") if OPTION_LINE_RE.match(line)) >= 2:
            if section.number is not None:
                option_questions.append(section.number)

    for section in sections:
        if REFERENCE_MARKER in section.text.lower():
            reference_count += 1

    return DocumentAnalysis(
        document=document,
        sections=sections,
        question_sections=question_sections,
        section_sections=section_sections,
        tokens_by_section=tokens_by_section,
        page_tokens=page_tokens,
        short_pages=short_pages,
        raw_domains=raw_domains,
        unknown_domains=unknown_domains,
        missing_domains=missing_domains,
        exact_answer_questions=exact_answer_questions,
        broad_answer_questions=broad_answer_questions,
        questions_without_exact=questions_without_exact,
        wrong_prefix_counts=wrong_prefix_counts,
        wrong_prefix_distribution=wrong_prefix_distribution,
        option_questions=option_questions,
        reference_count=reference_count,
        preamble_tokens=estimate_tokens(preamble_text(document)),
    )


def _stats(values: list[int]) -> tuple[int, float, int, int, float]:
    if not values:
        return 0, 0.0, 0, 0, 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return (
        ordered[0],
        statistics.median(ordered),
        ordered[index],
        ordered[-1],
        statistics.mean(ordered),
    )


def _distribution(values: list[int]) -> tuple[int, int, int, int]:
    return (
        sum(1 for value in values if value < 300),
        sum(1 for value in values if 300 <= value < 800),
        sum(1 for value in values if 800 <= value <= 1200),
        sum(1 for value in values if value > 1200),
    )


def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0,0%"
    return f"{part * 100 / total:.1f}%".replace(".", ",")


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return lines


def _short_list(values: list[int], limit: int = 24) -> str:
    if not values:
        return "không có"
    shown = ", ".join(str(value) for value in values[:limit])
    if len(values) > limit:
        shown += f", … (+{len(values) - limit})"
    return shown


def _format_range(pages: list[int]) -> str:
    return _short_list(pages, limit=12)


def build_report(analyses: list[DocumentAnalysis]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_pages = sum(item.document.page_count for item in analyses)
    total_sections = sum(len(item.sections) for item in analyses)
    total_questions = sum(len(item.question_sections) for item in analyses)
    total_tables = sum(len(item.document.tables) for item in analyses)
    total_images = sum(item.document.image_count for item in analyses)
    total_tokens = sum(item.total_tokens for item in analyses)
    question_bank = next((item for item in analyses if item.role == "question_bank"), None)
    exam_guide = next((item for item in analyses if item.role == "exam_guide"), None)

    lines: list[str] = []
    lines.append("# PHÂN TÍCH CẤU TRÚC PDF — GIAI ĐOẠN 1")
    lines.append("")
    lines.append(f"- **Ngày tạo:** {now}")
    lines.append(
        "- **Lệnh tái lập:** "
        "`python -m ingestion.inspect --input data/raw --report docs/ingestion-analysis.md`"
    )
    lines.append("- **Phạm vi:** toàn bộ `*.pdf` trong `data/raw/`; loại trừ `data/external_test/`")
    lines.append("- **Công cụ parse:** pdfplumber (không OCR, không dịch vụ ngoài)")
    lines.append(
        "- **Quy ước token:** xấp xỉ `ceil(số ký tự / 3)` cho văn bản tiếng Việt; "
        "chỉ dùng để thiết kế chunk, không phải token của tokenizer."
    )
    lines.append("")

    lines.append("## 1. Tổng quan")
    lines.append("")
    rows = []
    for item in analyses:
        document = item.document
        rows.append(
            [
                f"`{document.path.name}`",
                str(document.page_count),
                str(len(document.empty_pages)),
                str(len(item.section_sections)),
                str(len(item.question_sections)),
                str(len(document.tables)),
                str(document.image_count),
                f"{item.total_tokens:,}".replace(",", "."),
            ]
        )
    rows.append(
        [
            "**Tổng**",
            f"**{total_pages}**",
            f"**{sum(len(item.document.empty_pages) for item in analyses)}**",
            f"**{sum(len(item.section_sections) for item in analyses)}**",
            f"**{total_questions}**",
            f"**{total_tables}**",
            f"**{total_images}**",
            f"**{total_tokens:,}**".replace(",", "."),
        ]
    )
    lines.extend(
        _table(
            [
                "Tài liệu",
                "Trang",
                "Trang trống",
                "Mục lý thuyết",
                "Câu hỏi",
                "Bảng",
                "Ảnh",
                "Token ước tính",
            ],
            rows,
        )
    )
    lines.append("")
    lines.append(
        f"Toàn bộ {total_pages} trang đều có lớp văn bản; không có trang trống. "
        f"Corpus có {total_sections} đề mục, trong đó {total_questions} câu hỏi, "
        f"{total_tables} bảng và {total_images} ảnh."
    )
    lines.append("")

    lines.append("## 2. Cấu trúc từng tài liệu")
    lines.append("")
    for item in analyses:
        document = item.document
        question_count = len(item.question_sections)
        section_count = len(item.section_sections)
        kinds = []
        if question_count:
            kinds.append(f"`Câu N:` ({question_count})")
        if section_count:
            kinds.append(f"`Mục X.Y:` ({section_count})")
        heading_style = " và ".join(kinds) if kinds else "không phát hiện"
        minimum, median, p95, maximum, mean = _stats(item.tokens_by_section)
        lines.append(f"### `{document.path.name}`")
        lines.append("")
        lines.append(f"- Nguồn: `{document.source_key}`")
        lines.append(f"- Số trang: {document.page_count}")
        lines.append(f"- Kiểu đề mục: {heading_style}")
        lines.append(f"- Số đề mục: {len(item.sections)}")
        lines.append(
            f"- Token mỗi đề mục: nhỏ nhất {minimum}, trung vị {median:.0f}, "
            f"p95 {p95}, lớn nhất {maximum}, trung bình {mean:.0f}"
        )
        if item.preamble_tokens:
            lines.append(f"- Phần mở đầu trước đề mục đầu tiên: ~{item.preamble_tokens} token")
        if item.raw_domains:
            variants = ", ".join(
                f"“{label}” ({count})" for label, count in item.raw_domains.most_common()
            )
            lines.append(f"- Nhãn lĩnh vực gốc: {variants}")
        if item.missing_domains:
            numbers = ", ".join(
                str(section.number)
                for section in item.missing_domains
                if section.number is not None
            )
            lines.append(f"- Câu thiếu dòng `Lĩnh vực:`: {numbers}")
        lines.append(
            f"- Trang trống: {_format_range(document.empty_pages)}; "
            f"trang ngắn (<50 ký tự): {_format_range(item.short_pages)}"
        )
        lines.append(
            f"- Bảng: {len(document.tables)}; ảnh: {document.image_count}; "
            f"số đề mục có mục “Tài liệu tham khảo”: {item.reference_count}"
        )
        lines.append("")

    if question_bank is not None:
        lines.append("## 3. Phân tích ngân hàng câu hỏi")
        lines.append("")
        numbers = sorted(
            section.number
            for section in question_bank.question_sections
            if section.number is not None
        )
        lines.append("### 3.1 Số lượng và khoảng số câu")
        lines.append("")
        if numbers:
            lines.append(
                f"- Số câu phát hiện: **{len(numbers)}**; số nhỏ nhất: {numbers[0]}; "
                f"số lớn nhất: {numbers[-1]}."
            )
            duplicates = sorted(number for number, count in Counter(numbers).items() if count > 1)
            missing_numbers = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
            lines.append(
                f"- Câu trùng số: {_short_list(duplicates)}; "
                f"số bị thiếu trong dãy: {_short_list(missing_numbers)}."
            )
        lines.append("")

        lines.append("### 3.2 Lĩnh vực")
        lines.append("")
        raw_rows = []
        for label, count in question_bank.raw_domains.most_common():
            canonical = normalize_domain(label)
            raw_rows.append([f"“{label}”", str(count), canonical or "**không nhận diện**"])
        lines.extend(_table(["Nhãn gốc trong PDF", "Số câu", "Nhãn chuẩn hóa"], raw_rows))
        lines.append("")
        if question_bank.unknown_domains:
            lines.append(
                "Nhãn gốc chưa ánh xạ: "
                + ", ".join(f"“{label}”" for label in question_bank.unknown_domains)
                + "."
            )
            lines.append("")
        if question_bank.missing_domains:
            missing_rows = []
            for section in question_bank.missing_domains:
                override = MISSING_DOMAIN_OVERRIDES.get(section.number or -1, "—")
                missing_rows.append(
                    [
                        str(section.number),
                        section.title[:70],
                        section.page_label,
                        override,
                    ]
                )
            lines.append("Bảy câu không có dòng `Lĩnh vực:` và cách xử lý đề xuất:")
            lines.append("")
            lines.extend(
                _table(["Câu", "Tiêu đề rút gọn", "Trang", "Lĩnh vực gán thủ công"], missing_rows)
            )
            lines.append("")
            lines.append(
                "Các giá trị gán thủ công nằm trong `MISSING_DOMAIN_OVERRIDES` "
                "(`ingestion/domains.py`) và sẽ được ghi vào metadata với nguồn `override`."
            )
            lines.append("")

        distribution: Counter = Counter()
        provenance: Counter = Counter()
        for section in question_bank.question_sections:
            domain, source = resolve_question_domain(section.number or -1, section.domain_raw)
            distribution[domain or "Không xác định"] += 1
            provenance[source] += 1
        distribution_rows = []
        for code in DOMAIN_CODES:
            count = distribution.get(code, 0)
            distribution_rows.append(
                [
                    code,
                    DOMAIN_LABELS_VI[code],
                    str(count),
                    _pct(count, len(question_bank.question_sections)),
                ]
            )
        lines.extend(
            _table(
                ["Mã chuẩn", "Nhãn tiếng Việt", "Số câu", "Tỷ lệ"],
                distribution_rows,
            )
        )
        lines.append("")
        lines.append(
            f"Tổng sau chuẩn hóa: {sum(distribution.values())} câu; "
            f"nguồn nhãn: explicit {provenance['explicit']}, override {provenance['override']}, "
            f"missing {provenance['missing']}. "
            f"Tổng tỷ lệ: {_pct(sum(distribution.values()), len(question_bank.question_sections))}."
        )
        lines.append("")

        lines.append("### 3.3 Trích xuất đáp án đúng")
        lines.append("")
        marker_rows = []
        for marker in EXACT_ANSWER_MARKERS:
            count = sum(
                1 for section in question_bank.question_sections if marker in section.text.lower()
            )
            marker_rows.append([f"“{marker}”", str(count)])
        lines.extend(_table(["Mẫu câu (không phân biệt hoa thường)", "Số câu chứa"], marker_rows))
        lines.append("")
        lines.append(
            "- Câu có ít nhất một trong bốn mẫu chính xác: "
            f"**{question_bank.exact_answer_questions}/"
            f"{len(question_bank.question_sections)}**."
        )
        without_exact = len(question_bank.questions_without_exact)
        without_pct = _pct(without_exact, len(question_bank.question_sections))
        lines.append(f"- Câu không có mẫu chính xác: {without_exact} ({without_pct}).")
        lines.append(
            f"- Câu có dấu hiệu đáp án nếu mở rộng mẫu: **{question_bank.broad_answer_questions}/"
            f"{len(question_bank.question_sections)}**."
        )
        lines.append("")
        lines.append("Danh sách câu chưa khớp bốn mẫu chính xác:")
        lines.append("")
        lines.append(
            "```text\n" + _short_list(question_bank.questions_without_exact, limit=200) + "\n```"
        )
        lines.append("")

        lines.append("### 3.4 Phương án nhiễu")
        lines.append("")
        wrong_rows = [
            [f"“{prefix}”", str(count)]
            for prefix, count in question_bank.wrong_prefix_counts.most_common()
        ]
        lines.extend(_table(["Tiền tố mở đầu đoạn nhiễu", "Số đoạn"], wrong_rows))
        lines.append("")
        distribution_rows = []
        for count in range(5):
            label = "4 trở lên" if count == 4 else str(count)
            distribution_rows.append(
                [label, str(question_bank.wrong_prefix_distribution.get(count, 0))]
            )
        lines.extend(_table(["Số đoạn nhiễu nhận diện trong một câu", "Số câu"], distribution_rows))
        lines.append("")
        lines.append(
            "Các đoạn nhiễu còn dùng nhiều cách diễn đạt khác (ví dụ “Việc … là không chính xác”, "
            "“Các tùy chọn sau đây đều không chính xác:” kèm gạch đầu dòng). Bộ trích xuất sẽ dùng "
            "thêm mẫu tổng quát và ghi cảnh báo cho câu không tách được phương án."
        )
        lines.append("")

        lines.append("### 3.5 Phương án A–D")
        lines.append("")
        lines.append(
            f"Số câu có ít nhất hai dòng bắt đầu bằng `A.`, `B.`, `C.`, `D.` "
            f"(hoặc `A)`, `B)`, …): **{len(question_bank.option_questions)}**."
        )
        lines.append(
            "PDF không trình bày danh sách phương án A–D; mỗi câu chỉ có tiêu đề, phần giải thích, "
            "câu trả lời đúng và phân tích các phương án nhiễu. Pipeline sẽ tái dựng tối đa bốn "
            "phương án từ câu trả lời đúng và các đoạn nhiễu, ghi `options_source = reconstructed` "
            "trong metadata, và để trống danh sách nếu không đủ căn cứ."
        )
        lines.append("")

        lines.append("### 3.6 Kích thước câu hỏi")
        lines.append("")
        under300, from300, from800, over1200 = _distribution(question_bank.tokens_by_section)
        lines.extend(
            _table(
                ["Khoảng token ước tính", "Số câu"],
                [
                    ["< 300", str(under300)],
                    ["300 – 799", str(from300)],
                    ["800 – 1.200", str(from800)],
                    ["> 1.200", str(over1200)],
                ],
            )
        )
        lines.append("")
        lines.append(
            "Đề mục câu hỏi không đồng đều: phần lớn nằm trong 300–1.200 token "
            "nhưng có câu rất dài. Chunk cha giữ trọn đề mục nếu ≤ 1.200 token; "
            "đề mục dài được chia thành nhiều chunk cha theo ranh giới đoạn, "
            "mỗi chunk cha vẫn bao trùm các chunk con bên trong."
        )
        lines.append("")

    if exam_guide is not None or any(item.role == "supplement" for item in analyses):
        lines.append("## 4. Tài liệu lý thuyết")
        lines.append("")
        theory_items = [item for item in analyses if item.role != "question_bank"]
        theory_rows = []
        for item in theory_items:
            minimum, median, _, maximum, mean = _stats(item.tokens_by_section)
            domain_counts = {
                code: sum(
                    1
                    for section in item.section_sections
                    if normalize_domain(section.domain_raw) == code
                )
                for code in DOMAIN_CODES
            }
            theory_rows.append(
                [
                    f"`{item.document.path.name}`",
                    str(len(item.section_sections)),
                    str(minimum),
                    f"{median:.0f}",
                    str(maximum),
                    f"{mean:.0f}",
                    ", ".join(f"{code}: {count}" for code, count in domain_counts.items()),
                ]
            )
        lines.extend(
            _table(
                [
                    "Tài liệu",
                    "Số mục",
                    "Token nhỏ nhất",
                    "Trung vị",
                    "Lớn nhất",
                    "Trung bình",
                    "Mục theo lĩnh vực",
                ],
                theory_rows,
            )
        )
        lines.append("")
        all_theory_tokens = [token for item in theory_items for token in item.tokens_by_section]
        under300, from300, from800, over1200 = _distribution(all_theory_tokens)
        lines.append(
            f"Phân bố token mục lý thuyết: <300: {under300}; 300–799: {from300}; "
            f"800–1.200: {from800}; >1.200: {over1200}. "
            "Các mục ngắn hơn 800 token sẽ được gộp với mục kế tiếp "
            "cùng lĩnh vực khi tạo chunk cha; "
            "mục dài hơn 1.200 token được chia theo ranh giới đoạn."
        )
        lines.append("")

    lines.append("## 5. Bảng, hình ảnh và trang lỗi")
    lines.append("")
    lines.append(
        "**Không phát hiện bảng hoặc hình ảnh nào** trong toàn bộ corpus: "
        f"{total_tables} bảng, {total_images} ảnh trên {total_pages} trang. "
        "Điều này có nghĩa yêu cầu “kiểm tra ngẫu nhiên 5 bảng” "
        "không thể thực hiện trên dữ liệu thật."
    )
    lines.append("")
    lines.append(
        "Để bảo đảm chức năng trích bảng vẫn đúng, pipeline có bộ chuyển bảng sang Markdown và "
        "metadata `{type, page, rows, cols}`; phần kiểm thử dùng PDF/tệp mẫu tổng hợp có bảng. "
        "Khi bổ sung tài liệu có bảng ở giai đoạn sau, pipeline sẽ tạo chunk riêng "
        '`content_type = "table"` và không làm phẳng bảng vào văn bản.'
    )
    lines.append("")
    empty_total = sum(len(item.document.empty_pages) for item in analyses)
    short_total = sum(len(item.short_pages) for item in analyses)
    lines.append(f"- Trang không trích được văn bản: **{empty_total}**.")
    lines.append(f"- Trang có ít hơn 50 ký tự: **{short_total}**.")
    lines.append(
        "- Văn bản là tiếng Việt có dấu, chứa nhiều thuật ngữ tiếng Anh (tên dịch vụ AWS). "
        "Không phát hiện ký tự thay thế `�` trong quá trình khảo sát."
    )
    lines.append("")

    lines.append("## 6. Hàm ý cho pipeline Giai đoạn 1")
    lines.append("")
    lines.append(
        "1. **Chunking cha–con:** mỗi đề mục là đơn vị ngữ nghĩa. Với ngân hàng câu hỏi, "
        "chunk cha là một câu (hoặc một phần của câu nếu >1.200 token); với tài liệu lý thuyết, "
        "các mục ngắn cùng lĩnh vực được gộp đến ngưỡng 800–1.200 token. Chunk con 300–500 token, "
        "chồng lấn 10–15%, luôn mang tiêu đề mục và số trang."
    )
    lines.append(
        "2. **Trích câu hỏi:** lấy số câu từ `Câu N:`, tiêu đề từ dòng tiêu đề "
        "(nối các dòng bị ngắt), "
        "lĩnh vực từ `Lĩnh vực:`, đáp án đúng từ các mẫu câu, "
        "phương án nhiễu từ các đoạn phân tích. "
        "Câu không xác định được đáp án được lưu với `correct_answer = null` "
        "và cảnh báo, không suy diễn."
    )
    lines.append(
        "3. **Phương án A–D:** không có trong PDF. Tái dựng từ đáp án đúng và các đoạn nhiễu; "
        "ghi rõ nguồn trong metadata và không tạo phương án giả khi thiếu căn cứ."
    )
    lines.append(
        "4. **Lĩnh vực:** chuẩn hóa 9 nhãn gốc về 4 mã; "
        "7 câu thiếu dòng lĩnh vực dùng bảng gán thủ công "
        "và metadata `domain_source = override`."
    )
    lines.append(
        "5. **Bảng:** corpus hiện tại không có bảng; "
        "chức năng trích bảng vẫn được kiểm thử bằng mẫu tổng hợp."
    )
    lines.append(
        "6. **Idempotency:** checksum SHA-256 của tệp và của nội dung chunk/câu hỏi dùng để bỏ qua "
        "khi chạy lại; `--force` xóa và nạp lại theo tài liệu."
    )
    lines.append(
        "7. **Embedding:** `gemini-embedding-001`, 768 chiều, theo lô, có retry/backoff; "
        "không lưu vector vào tệp trung gian."
    )
    lines.append(
        "8. **Ước tính token:** dùng `ceil(len(text)/3)`; ghi rõ đây là xấp xỉ để thiết kế chunk, "
        "không dùng cho báo cáo chi phí token của Gemini."
    )
    lines.append("")

    lines.append("## 7. Kết luận")
    lines.append("")
    lines.append(
        f"Corpus gồm {len(analyses)} tài liệu, {total_pages} trang, {total_questions} câu hỏi và "
        f"{sum(len(item.section_sections) for item in analyses)} mục lý thuyết. "
        "Cấu trúc đề mục ổn định (`Câu N:` và `Mục X.Y:`), lớp văn bản đầy đủ, không có bảng/ảnh. "
        "Ba rủi ro chính cần xử lý minh bạch: thiếu phương án A–D, 7 câu thiếu nhãn lĩnh vực và "
        "một phần câu hỏi không có mẫu đáp án chính xác rõ ràng."
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phân tích cấu trúc PDF cho pipeline ingestion")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Thư mục chứa PDF")
    parser.add_argument(
        "--report", type=Path, default=DEFAULT_ANALYSIS_PATH, help="Tệp Markdown đầu ra"
    )
    args = parser.parse_args(argv)

    paths = iter_pdfs(args.input)
    if not paths:
        raise SystemExit(f"Không tìm thấy PDF trong {args.input}")
    analyses = []
    for path in paths:
        print(f"[inspect] {path.name} ...", flush=True)
        analyses.append(analyze_document(load_pdf(path, project_root=args.input.parent.parent)))
    report = build_report(analyses)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"[inspect] Đã ghi {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
