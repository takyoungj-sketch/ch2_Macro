# 토스페이먼츠 심사 · 웹 구독 연동

> MID 예: `ch2datoe5e` · 상점 URL `https://ch2data.com/`

## 상품 설명 (회신 메일용)

- **월 정기 구독 SaaS**(무형상품). 연간 상품 없음.
- **PG 연동**: 토스페이먼츠 **자동결제(빌링)** — 카드 등록창(`requestBillingAuth`) → 빌링키 발급 → 첫 달 결제 → **매월 서버에서 자동 승인**.
- **해지**: 다음 결제일부터 자동 결제 중단, **이번 기간 말까지 이용**(환불 없음). `/subscribe/` 에서 해지 예약.
- **심사용 로그인**: `review@ch2data.com` (env `PLATFORM_REVIEW_*`, git에 넣지 않음).

토스가 「단건 vs 구독」을 물을 때: **사업은 월 구독**, **결제는 토스 자동결제(빌링) API**로 처리한다고 답하면 됩니다.

### 빌링 계약 오류 (`자동 결제(빌링) 계약이 안 되어 있습니다`)

테스트 키만으로는 **자동결제(빌링) 상품 계약**이 안 열린 MID에서는 `requestBillingAuth`가 실패합니다.

| 조치 | 설명 |
|------|------|
| **가맹계약팀 회신** | 월 구독 SaaS · **자동결제(빌링) 계약 활성화** 요청 (MID `ch2datoe5e`) |
| **심사·PPT 당장** | `/subscribe/` → **「카드 결제창 (심사용)」** → 일반 결제창(`requestPayment`) 캡처 → PPT ⑥ |

운영 목표는 빌링이지만, 토스가 요청한 **「테스트 키 결제창 연동」** 증빙은 심사용 단건 결제창으로 먼저 제출 가능합니다.

## 운영자가 해야 할 일

### 1. DB 마이그레이션 (ch2_platform)

```bash
sudo -u postgres psql -d ch2_platform -f /opt/ch2_Macro/db/072_platform_toss_billing.sql
```

### 2. 어떤 키를 쓰나 (MID `ch2datoe5e`)

| 개발자센터 구역 | 접두사 | 이 프로젝트 |
|-----------------|--------|-------------|
| **API 개별 연동 키** (자동결제·결제창 SDK) | `test_ck_` / `test_sk_` | **✅ 사용** |
| 주문서형·결제위젯 연동 키 | `test_gck_` / `test_gsk_` | ❌ 미사용 (`/v2/standard` + REST 빌링) |

환경변수 이름 (`backend/app/config.py`):

- `TOSS_CLIENT_KEY` — 브라우저 SDK에 전달 (공개 가능한 클라이언트 키)
- `TOSS_SECRET_KEY` — 서버만 (빌링키 발급·승인·confirm). **git·채팅·로그 금지**
- `TOSS_WEBHOOK_SECRET` — (선택) 라이브 웹훅 검증용. 심사 단계는 비워도 됨

### 3. VPS `backend/.env` — **테스트 키** (심사)

개발자센터 → **씨에이치투** → **[테스트]** → **API 개별 연동 키** (`ch2datoe5e`):

```env
TOSS_CLIENT_KEY=test_ck_...
TOSS_SECRET_KEY=test_sk_...
# 웹훅은 라이브 전까지 비워도 됨
# TOSS_WEBHOOK_SECRET=
PLATFORM_REVIEW_EMAIL=review@ch2data.com
PLATFORM_REVIEW_PASSWORD=...
```

백엔드 재시작 후 확인:

```bash
sudo systemctl restart ch2-macro-backend
sudo bash /opt/ch2_Macro/deploy/scripts/verify_toss_billing_ready.sh
```

공개 확인: `curl -s https://ch2data.com/api/billing/toss/config` → `"enabled":true` (clientKey만 노출)

### 4. 심사 흐름 확인

1. `https://ch2data.com/subscribe/` → 심사용 로그인  
2. **카드로 구독하기** → 토스 **카드 등록·결제창**  
3. 테스트 카드로 완료 → `billing-success.html` → 구독 활성

### 5. 결제경로 PPT 재생성

```bash
cd deploy/scripts
# PLATFORM_REVIEW_* 등 env 설정 후
python build_toss_payment_path_ppt.py
```

출력: `deploy/hub/toss-review/CH2DATA_결제경로.pptx`  
가맹계약팀에 **⑥ 카드 결제경로** 캡처 포함본 재첨부.

### 6. 자동 갱신 cron (라이브 전에 설정)

```bash
# 예: 매일 09:05 KST
5 0 * * * cd /opt/ch2_Macro/backend && . .env && python scripts/platform_billing_renewal.py
```

### 7. 라이브 전환

심사 승인 후 **라이브** `TOSS_CLIENT_KEY` / `TOSS_SECRET_KEY` 로 교체. PPT를 라이브 화면으로 한 번 더 갱신.

## 코드 위치

| 항목 | 경로 |
|------|------|
| 빌링 API | `backend/app/platform/billing_router.py` |
| 빌링키·갱신 | `backend/app/platform/web_subscription.py` |
| 토스 HTTP | `backend/app/platform/toss_client.py` |
| 구독 UI | `deploy/hub/subscribe/` |
| DDL | `db/072_platform_toss_billing.sql` |
