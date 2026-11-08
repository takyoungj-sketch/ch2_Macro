"""구조 코드의 화면 표기. 저장값·더미 열 이름(struct_RC)은 바꾸지 않는다."""

STRUCTURE_DISPLAY = {
    "RC": "철콘",
    "SRC": "철골철콘",
}


def structure_display(value: object) -> str:
    text = str(value or "").strip()
    return STRUCTURE_DISPLAY.get(text, text)
