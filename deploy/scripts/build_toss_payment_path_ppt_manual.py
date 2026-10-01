#!/usr/bin/env python3
"""사용자 캡처 이미지로 토스 결제경로 PPT 생성."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "hub" / "toss-review"
SHOT_DIR = OUT_DIR / "screenshots"
PPT_PATH = OUT_DIR / "CH2DATA_payment_path.pptx"

ASSETS = Path(
    r"C:\Users\PC\.cursor\projects\e-ch2\assets"
)

MERCHANT = {
    "name": "씨에이치투",
    "biz_no": "607-23-96932",
    "url": "https://ch2data.com/",
    "test_id": "review@ch2data.com",
    "test_pw": "Ch2T0ssReview2026",
}

BLUE = RGBColor(0x31, 0x82, 0xCE)
BLACK = RGBColor(0x11, 0x18, 0x27)
GRAY = RGBColor(0x64, 0x74, 0x8B)

SOURCE_MAP = {
    "02_footer.png": "c__Users_PC_AppData_Roaming_Cursor_User_workspaceStorage_3e120280fe3abf62629deb41caacdaa1_images_image-8206ab85-4465-42d9-b04e-88509a2ffc58.png",
    "03_refund.png": "c__Users_PC_AppData_Roaming_Cursor_User_workspaceStorage_3e120280fe3abf62629deb41caacdaa1_images_image-1c0d3e71-4e31-4012-bf25-427bb48544f3.png",
    "04_login.png": "c__Users_PC_AppData_Roaming_Cursor_User_workspaceStorage_3e120280fe3abf62629deb41caacdaa1_images_image-6b7c9d61-1bed-4547-84ef-a143a3d4cf3b.png",
    "05_subscription_1.png": "c__Users_PC_AppData_Roaming_Cursor_User_workspaceStorage_3e120280fe3abf62629deb41caacdaa1_images_image-a15e90d8-dc5e-49f9-8a74-dace6f8bcec6.png",
    "05_subscription_2.png": "c__Users_PC_AppData_Roaming_Cursor_User_workspaceStorage_3e120280fe3abf62629deb41caacdaa1_images_image-1746adb2-7369-4c80-98af-fee83b4aa582.png",
    "06_subscribe.png": "c__Users_PC_AppData_Roaming_Cursor_User_workspaceStorage_3e120280fe3abf62629deb41caacdaa1_images_image-358aa73c-2e53-4c65-a7ba-1c218d016074.png",
}

SLIDE_W = Inches(10)
SLIDE_H = Inches(7.5)
IMG_LEFT = Inches(0.35)
IMG_TOP = Inches(1.05)
IMG_MAX_W = Inches(9.3)
IMG_MAX_H = Inches(6.35)


def copy_sources() -> None:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    for dest, src_name in SOURCE_MAP.items():
        src = ASSETS / src_name
        if not src.exists():
            raise FileNotFoundError(f"캡처 없음: {src}")
        shutil.copy2(src, SHOT_DIR / dest)


def _fit_picture(slide, image_path: Path):
    pic = slide.shapes.add_picture(str(image_path), IMG_LEFT, IMG_TOP)
    ratio = pic.width / pic.height
    max_w = IMG_MAX_W
    max_h = IMG_MAX_H
    if pic.width > max_w:
        pic.width = int(max_w)
        pic.height = int(max_w / ratio)
    if pic.height > max_h:
        pic.height = int(max_h)
        pic.width = int(max_h * ratio)
    pic.left = int((SLIDE_W - pic.width) / 2)
    pic.top = int(IMG_TOP)


def _add_title_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.2), Inches(8.4), Inches(4.5))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "① 가맹점 정보"
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = BLUE
    for line in [
        f"(1) 상호명: {MERCHANT['name']}",
        f"(2) 사업자번호: {MERCHANT['biz_no']}",
        f"(3) URL: {MERCHANT['url']}",
        f"(4) Test ID: {MERCHANT['test_id']}",
        f"(5) Test PW: {MERCHANT['test_pw']}",
    ]:
        para = tf.add_paragraph()
        para.text = line
        para.font.size = Pt(20)
        para.font.color.rgb = BLACK
        para.space_before = Pt(10)


def _add_image_slide(prs: Presentation, title: str, subtitle: str, image_name: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.2), Inches(9.2), Inches(0.45))
    tp = title_box.text_frame.paragraphs[0]
    tp.text = title
    tp.font.size = Pt(20)
    tp.font.bold = True
    tp.font.color.rgb = BLUE

    sub_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.62), Inches(9.2), Inches(0.35))
    sp = sub_box.text_frame.paragraphs[0]
    sp.text = subtitle
    sp.font.size = Pt(11)
    sp.font.color.rgb = GRAY

    image_path = SHOT_DIR / image_name
    _fit_picture(slide, image_path)


def _add_payment_note_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.2), Inches(8.4), Inches(3))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "⑥ 카드 결제경로"
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = BLUE
    for line in [
        "토스 상점 키 심사 전에는 실제 결제창 캡처가 어렵습니다.",
        "현재 구독 페이지에서 카드·카카오페이 버튼은 '준비 중' 상태입니다.",
        "심사·키 발급 후 결제창 캡처를 추가 제출할 수 있습니다.",
        "토스 가이드: 테스트 결제창 연동 시 심사 가능",
        "https://docs.tosspayments.com/preview/1",
    ]:
        para = tf.add_paragraph()
        para.text = line
        para.font.size = Pt(16)
        para.font.color.rgb = BLACK
        para.space_before = Pt(10)


def build() -> None:
    copy_sources()
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    _add_title_slide(prs)
    _add_image_slide(prs, "② 하단 정보", "홈페이지 하단 사업자 정보", "02_footer.png")
    _add_image_slide(prs, "③ 환불규정 (무형상품)", "디지털 콘텐츠 월 구독 환불 정책", "03_refund.png")
    _add_image_slide(prs, "④ 로그인", "심사용 이메일·비밀번호 로그인", "04_login.png")
    _add_image_slide(prs, "⑤ 구독 정책 (1/2)", "상품·요금·무료 체험", "05_subscription_1.png")
    _add_image_slide(prs, "⑤ 구독 정책 (2/2)", "제품 추가·해제·결제 채널·해지", "05_subscription_2.png")
    _add_image_slide(prs, "⑤ 구매 과정", "로그인 후 상품·금액·결제 수단 선택", "06_subscribe.png")
    _add_payment_note_slide(prs)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prs.save(str(PPT_PATH))
    print(f"OK: {PPT_PATH} ({datetime.now():%Y-%m-%d %H:%M})")


if __name__ == "__main__":
    build()
