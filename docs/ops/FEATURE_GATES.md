# 관리자 전용 기능 스위치 — 운영·공개 절차 (D-085)

개선 중인 기능을 관리자에게만 열고 사용자에게는 숨긴다. 공개·비공개 전환은 **환경변수 하나 + API 재시작**이다. 코드·DB 변경은 없다.

## 1. 스위치

| 이름 | 기능 | 꺼졌을 때 사용자 화면 | 서버 |
|---|---|---|---|
| `rent_regression` | 임대 단지 전세 보증금 회귀 | 회귀 탭 자리에 안내문 | `POST /api/rent/buildings/{key}/regression/run`, `POST /api/rent/regression/run` → 403 |
| `land_regression` | 토지 회귀식 탭·실행·추천·예측 | 회귀 탭 미노출(안내문 없음) | `POST /api/paid/matrix-cell-transactions/regression`, `…/suggest`, `…/predict` → 403 |
| `land_ledger_link` | 토지 거래–대장 연결(공시지가·연결 상태·복원 지번·CSV 열·연결 건수·회귀 변수 개별공시지가) | 「공시지가 표시」·회귀 변수 미노출 | 목록 응답에서 대장 8칸 제거. `trait_enrich=true`(목록·CSV)·`variables.assessed_land_price=true`(회귀·예측) → 403 |

- 모드: `public`(모두) · `admin`(관리자만, **기본**) · `off`(관리자도 닫음).
- 관리자: 로그인 계정 `users.role = admin`(OAuth 관리자 또는 staff 로그인) 또는 QA 토큰(`X-Qa-Audit-Token`). `/lab/` Nginx 비밀번호(D-061)와는 별개다.
- 403 문구: 「아직 공개하지 않은 기능입니다.」
- 레지스트리: `backend/app/feature_gates.py`. 새 스위치는 `FEATURES` 에 추가한다.

## 2. 상태 확인

```bash
curl -s https://macro.ch2data.com/api/features
```

- 비로그인·일반 사용자: `{"features": [], "private": []}` (전부 비공개일 때)
- 관리자: `features` 에 켜진 이름, `private` 에 아직 관리자 전용인 이름(배지 대상)
- 응답 헤더 `Cache-Control: no-store, private`, `Vary: Cookie, Authorization` 가 있어야 한다.

## 3. 공개 절차 (예: 임대 회귀)

1. **공개 조건 확인.** 관리자 화면에서 기능을 확인하고 공개 조건을 기록한다. 임대 회귀는 A안(쿼리 개선)과 503 문구 수정이 끝난 뒤 공개한다(`docs/lab/RENT_REGRESSION_504_20261112.md`).
2. **T 승인**을 받고 `docs/DECISIONS.md` D-085 에 공개 날짜·범위를 한 줄 더한다.
3. **환경변수 설정.** VPS `/opt/ch2_Macro/backend/.env` 에 한 줄 추가한다(API 서비스는 pydantic 이 이 파일을 읽는다. 프로세스 환경변수로 줘도 되고, 그쪽이 우선한다). 값을 출력하거나 다른 키를 바꾸지 않는다.
   ```
   FEATURE_RENT_REGRESSION=public
   ```
4. **API 재시작.** 배포 런북(`deploy/AGENT_DEPLOY_RUNBOOK.md`)의 API 재시작 절차를 따른다. 프론트 재빌드는 필요 없다.
5. **스모크.**
   - 비로그인 `GET /api/features` → `rent_regression` 이 들어 있다.
   - 비로그인 회귀 요청 → 403 「아직 공개하지 않은 기능입니다.」가 아니라 기존 구독 게이트(401/403 「로그인/구독이 필요합니다.」)가 나온다.
   - 구독 계정 화면 → 임대 상세에 「회귀 분석」 탭이 열리고 「비공개」 배지가 없다.
6. **되돌리기.** 그 줄을 지우거나 `admin` 으로 바꾸고 API 를 재시작한다. 열려 있던 화면은 창이 다시 보일 때 기능 목록을 다시 읽고, 바뀌었으면 새로 불러온다.

## 4. 점검 체크리스트

- [ ] 비관리자 회귀 API 403 (임대 2개·토지 3개)
- [ ] 비관리자 토지 거래목록 응답에 `official_price_won`·`trait_*`·`recovered_lot` 키 없음
- [ ] 비관리자 `trait_enrich=true`·`assessed_land_price=true` → 403
- [ ] 비관리자 CSV 에 「연결상태·공시지가(원/㎡)·공시기준연도·공시지가구분·특성기준일」 열 없음
- [ ] 관리자 화면 탭·체크 옆 「비공개」 배지
- [ ] AI: 비관리자가 숨김 패널 facts 를 보내도 근거로 쓰지 않음(`backend/app/ai/feature_filter.py`)

## 5. 로컬 개발

로그인 없이 개발하면 기능이 숨는다. `backend/.env`(자기 worktree)에 필요한 스위치만 `public` 으로 둔다.

```
FEATURE_RENT_REGRESSION=public
FEATURE_LAND_REGRESSION=public
FEATURE_LAND_LEDGER_LINK=public
```

이 값은 커밋하지 않는다.
