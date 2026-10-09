# 토스 가맹계약팀 회신 초안 (복사 후 수정)

**제목:** [재제출] ch2data.com 결제경로 PPT · 테스트 키 결제창 연동 (MID ch2datoe5e)

---

안녕하세요, 씨에이치투(정탁영)입니다.

문의 주신 내용에 따라 **테스트 키 결제창 연동**을 완료했고, **결제경로 PPT**를 갱신해 다시 첨부합니다.

**1. 상품 유형**  
- **월 정기 구독(무형 SaaS)** 입니다. (Macro 월 10,000원 / Macro+FieldNote 월 15,000원, 연간 상품 없음)  
- PG는 **토스페이먼츠 API 개별 연동**(MID `ch2datoe5e`)이며, **테스트 키**로 결제창이 열립니다.  
- **운영 목표**는 **카드 자동결제(빌링)** 입니다. 빌링 가맹 계약 활성화를 요청드립니다.

**2. 결제경로 (PPT ⑥)**  
- `https://ch2data.com/subscribe/` → 심사용 로그인 → **「카드 결제창 (심사용)」** → 토스 테스트 결제창  
- 캡처는 첨부 PPT에 포함했습니다.

**3. 확인 URL · 계정** (기존과 동일)  
- 구독·결제: https://ch2data.com/subscribe/  
- 구독 정책: https://ch2data.com/subscription/  
- 환불: https://ch2data.com/refund/  
- Test ID / PW: PPT ① 가맹점 정보

검토 부탁드립니다.

씨에이치투 정탁영  
ch2data.dev@gmail.com

**첨부:** `deploy/hub/toss-review/CH2DATA_payment_path.pptx`
