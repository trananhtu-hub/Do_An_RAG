from __future__ import annotations

from .normalize import normalize_text

DOMAIN_CODES = ("Secure", "Resilient", "High-Performing", "Cost-Optimized")

DOMAIN_LABELS_VI = {
    "Secure": "Thiết kế kiến trúc bảo mật",
    "Resilient": "Thiết kế kiến trúc kiên cường",
    "High-Performing": "Thiết kế kiến trúc hiệu năng cao",
    "Cost-Optimized": "Thiết kế kiến trúc tối ưu chi phí",
}

DOMAIN_WEIGHTS = {
    "Secure": 30,
    "Resilient": 26,
    "High-Performing": 24,
    "Cost-Optimized": 20,
}

_ALIASES = {
    "thiết kế kiến trúc bảo mật": "Secure",
    "thiết kế kiến trúc an toàn": "Secure",
    "thiết kế các ứng dụng và kiến trúc bảo mật": "Secure",
    "design secure architectures": "Secure",
    "thiết kế kiến trúc kiên cường": "Resilient",
    "design resilient architectures": "Resilient",
    "thiết kế kiến trúc hiệu năng cao": "High-Performing",
    "design high-performing architectures": "High-Performing",
    "thiết kế kiến trúc tối ưu chi phí": "Cost-Optimized",
    "design cost-optimized architectures": "Cost-Optimized",
}

# Bảy câu trong PDF không có dòng "Lĩnh vực"; gán theo nội dung và ghi rõ nguồn gốc.
MISSING_DOMAIN_OVERRIDES = {
    18: "High-Performing",
    65: "Secure",
    241: "High-Performing",
    245: "Cost-Optimized",
    249: "High-Performing",
    307: "High-Performing",
    368: "Cost-Optimized",
}

_KEYWORDS = {
    "Secure": (
        "iam",
        "bảo mật",
        "mã hóa",
        "quyền",
        "chính sách",
        "kms",
        "cloudhsm",
        "waf",
        "shield",
        "tường lửa",
        "chứng chỉ",
        "xác thực",
    ),
    "Resilient": (
        "multi-az",
        "dự phòng",
        "sao lưu",
        "khả dụng",
        "chịu lỗi",
        "sao chép",
        "failover",
        "backup",
        "route 53",
        "kiên cường",
    ),
    "High-Performing": (
        "hiệu năng",
        "mở rộng",
        "iops",
        "độ trễ",
        "thông lượng",
        "tải",
        "cache",
        "caching",
        "autoscaling",
        "tự động mở rộng",
        "throughput",
    ),
    "Cost-Optimized": (
        "chi phí",
        "tiết kiệm",
        "tối ưu chi phí",
        "giá",
        "rẻ",
        "spot",
        "reserved",
        "savings plan",
        "vòng đời",
    ),
}


def normalize_domain(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = normalize_text(raw).lower()
    key = " ".join(key.split())
    return _ALIASES.get(key)


def infer_domain(text: str) -> str | None:
    lowered = normalize_text(text).lower()
    scores = {
        code: sum(lowered.count(keyword) for keyword in keywords)
        for code, keywords in _KEYWORDS.items()
    }
    best = max(scores, key=lambda code: (scores[code], DOMAIN_CODES.index(code)))
    return best if scores[best] > 0 else None


def resolve_question_domain(number: int, raw: str | None) -> tuple[str | None, str]:
    explicit = normalize_domain(raw)
    if explicit:
        return explicit, "explicit"
    override = MISSING_DOMAIN_OVERRIDES.get(number)
    if override:
        return override, "override"
    return None, "missing"
