from __future__ import annotations

_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}
_HEX = frozenset("0123456789abcdefABCDEF")


class AnswerStreamExtractor:
    """Trích trường "answer" của JSON ngay khi mô hình còn đang sinh.

    Bộ quét tôn trọng dấu ngoặc kép đã escape nên chuỗi `"answer"` nằm trong
    reasoning_steps không bị nhận nhầm là khóa cấp một. Chỉ nhận khóa ở độ sâu
    đối tượng bằng 1 (đối tượng gốc).
    """

    def __init__(self) -> None:
        self._in_string = False
        self._escape = False
        self._unicode_digits: str | None = None
        self._high_surrogate: int | None = None
        self._string_chars: list[str] = []
        self._pending_key = False
        self._depth = 0
        self._state = "seeking"  # seeking | awaiting_value | value | done
        self._answer: list[str] = []

    @property
    def answered(self) -> bool:
        return self._state in ("value", "done")

    @property
    def finished(self) -> bool:
        return self._state == "done"

    @property
    def answer(self) -> str:
        return "".join(self._answer)

    def feed(self, chunk: str) -> str:
        out: list[str] = []
        for char in chunk:
            self._consume(char, out)
        return "".join(out)

    def _consume(self, char: str, out: list[str]) -> None:
        if self._in_string:
            if self._unicode_digits is not None:
                if char in _HEX:
                    self._unicode_digits += char
                    if len(self._unicode_digits) == 4:
                        self._flush_unicode(out)
                    return
                self._flush_unicode(out, invalid=True)
            if self._escape:
                self._escape = False
                if char == "u":
                    self._unicode_digits = ""
                    return
                self._append(_ESCAPES.get(char, char), out)
                return
            if char == "\\":
                self._escape = True
                return
            if char == '"':
                self._close_string(out)
                return
            self._append(char, out)
            return

        if self._pending_key:
            if char.isspace():
                return
            self._pending_key = False
            if char == ":":
                if self._state == "seeking":
                    self._state = "awaiting_value"
                return
        if self._state == "awaiting_value":
            if char.isspace():
                return
            if char == '"':
                self._state = "value"
                self._in_string = True
                self._escape = False
                self._string_chars = []
                return
            # answer không phải chuỗi: bỏ qua, chờ lần sinh lại
            self._state = "seeking"
            return
        if char == '"':
            self._in_string = True
            self._escape = False
            self._string_chars = []
            return
        if char == "{":
            self._depth += 1
            return
        if char == "}":
            self._depth = max(0, self._depth - 1)

    def _close_string(self, out: list[str]) -> None:
        self._in_string = False
        if self._state == "value":
            self._state = "done"
            if self._high_surrogate is not None:
                self._answer.append("�")
                out.append("�")
                self._high_surrogate = None
            self._string_chars = []
            return
        completed = "".join(self._string_chars)
        self._string_chars = []
        if completed == "answer" and self._depth == 1 and self._state == "seeking":
            self._pending_key = True

    def _append(self, text: str, out: list[str]) -> None:
        if self._state != "value":
            self._string_chars.append(text)
            return
        self._answer.append(text)
        out.append(text)

    def _flush_unicode(self, out: list[str], *, invalid: bool = False) -> None:
        digits = self._unicode_digits or ""
        self._unicode_digits = None
        if invalid or len(digits) != 4:
            self._emit_code_point("�", out)
            return
        code = int(digits, 16)
        if 0xD800 <= code <= 0xDBFF:
            if self._high_surrogate is not None:
                self._emit_code_point("�", out)
            self._high_surrogate = code
            return
        if 0xDC00 <= code <= 0xDFFF:
            if self._high_surrogate is None:
                self._emit_code_point("�", out)
                return
            combined = 0x10000 + ((self._high_surrogate - 0xD800) << 10) + (code - 0xDC00)
            self._high_surrogate = None
            self._emit_code_point(chr(combined), out)
            return
        if self._high_surrogate is not None:
            self._emit_code_point("�", out)
            self._high_surrogate = None
        self._emit_code_point(chr(code), out)

    def _emit_code_point(self, char: str, out: list[str]) -> None:
        self._append(char, out)
