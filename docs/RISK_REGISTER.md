# 위험 요소 레지스터 (Risk Register)

> 최종 업데이트: 2026-06-24  
> AI 아키텍트 관점에서 현재 CH2_MACRO 구조의 **위험 요소**만 비판적으로 정리.  
> 강점보다 **어디가 위험한가**에 집중.

---

## 위험도 기준

| 등급 | 정의 |
|------|------|
| 🔴 CRITICAL | 즉시 서비스 장애 또는 데이터 신뢰도 붕괴 가능 |
| 🟠 HIGH | 월간 갱신 실패 또는 심각한 오류 가능성 |
| 🟡 MEDIUM | 운영 부담 증가, 잠재적 버그 |
| 🟢 LOW | 장기 유지보수 문제 |

---

## R-001 🔴 transaction_hash 충돌 잔존 위험

**위치:** `pipeline/transaction_hash.py`, `pipeline/clean.py`

**설명:**  
`transaction_hash`의 공식이 2026-06 이전 이력과 이후 이력 사이에 다를 수 있다. dedupe+rehash 완료 후에도 향후 새 적재 시 old hash가 있는 행과의 충돌 여부를 정기적으로 점검해야 한다.

**현재 완화:** dedupe+rehash 완료 (2026-06-24), `extra_rows=0` 확인.

**잔존 위험:**
- 이후 `lot_display`나 다른 파생 컬럼이 hash에 추가되면 동일 문제 재발
- `transaction_hash.py`가 변경될 때 자동 테스트 없음

**권장 조치:**
1. `transaction_hash.py`에 대한 단위 테스트 작성
2. hash 공식 변경 시 DECISIONS에 기록 + 즉시 dedupe+rehash 실행 계획 수립

---

## R-002 🔴 analysis_base_cache stale 위험

**위치:** `backend/app/analysis_base_cache.py`

**설명:**  
`analysis_base_cache`는 `land_transactions.id`(bigserial) 목록을 4시간 캐시한다. rehash 또는 dedupe 후 동일 행의 `id`가 달라지거나 (DELETE→reinsert 시) 다른 거래의 `id`를 가리킬 수 있다.

**발생 시 증상:** 유료 분석 결과에 엉뚱한 거래가 포함되거나 "없는 id" 오류.

**현재 완화:** 갱신 후 TRUNCATE 운영 정책 (D-003).

**잔존 위험:**
- 수동 TRUNCATE를 잊을 경우 → 자동화 필요
- `run_pipeline.py` 끝에 TRUNCATE가 있지만, pipeline 외 DB 작업(dedupe 등) 후 별도 실행 누락 가능

**권장 조치:**
1. `dedupe_land_transactions.py --execute` 완료 후 자동 cache clear 추가
2. `/health` 엔드포인트에 cache 마지막 clear 시각 노출

---

## R-003 🟠 단일 PostgreSQL 장애 시 전체 서비스 중단

**위치:** 배포 구조 (VPS 1대)

**설명:**  
`land_stats` DB가 단일 인스턴스. DB 장애 시 백엔드 전체 404/500. Read replica 없음.

**현재 완화:** 없음. pg_dump 백업만 있음 (복구에 수분~수십분 소요).

**권장 조치:**
1. AWS RDS Aurora Serverless 또는 Lightsail Managed DB 검토
2. 단기: 백업 자동화 스케줄 + 복구 절차 문서화

---

## R-004 🟠 월간 갱신 완전 수동 운영

**위치:** `scripts/monthly/run_monthly_cycle.py`

**설명:**  
월간 갱신의 모든 단계(다운로드, 실행, 검증, Promote)가 사람이 명령을 직접 입력해야 함. 담당자 부재 또는 실수 시 SLA 위반.

**현재 완화:** SOP 문서화 (`MONTHLY_UPDATE_SOP.md`).

**잔존 위험:**
- 인력 의존도 100%
- 특정 단계 실패 후 재개 절차가 복잡 (어디서 중단됐는지 추적 어려움)

**권장 조치:**
1. GitHub Actions / cron 기반 파이프라인 오케스트레이터 검토
2. 단계별 체크포인트 파일 (`pipeline_state.json`) 기록

---

## R-005 🟠 국토부 컬럼 구조 변경 대응 취약

**위치:** `pipeline/collect.py`, `pipeline/clean.py`

**설명:**  
국토부 MOLIT이 xlsx 컬럼명·순서를 변경하면 파싱 오류로 수집 전체 실패. 이런 변경은 사전 공지 없이 발생.

**현재 완화:** 없음. 발견 후 수동 수정.

**권장 조치:**
1. 컬럼 매핑 설정 파일 분리 (`pipeline/config/molit_columns.yaml`)
2. 첫 10행 파싱 결과 자동 로깅 + 예상 컬럼 검증

---

## R-006 🟠 Twin v8 전국 확장 미완료

**위치:** `pipeline/build_twin_v8.py`, `pipeline/twin_v8/scoring.py`

**설명:**  
현재 Twin v8은 충청권만 적재됨. UI는 충청권 외 지역에 "전국 확장 예정" 안내를 표시하지만, 사용자가 원하는 서비스를 제공하지 못함.

**현재 상태:** `SCOPE_LABEL='충청권'` 하드코딩.

**권장 조치:** 전국 빌드 실행 + 권역별/전국별 UI 옵션 추가 (NEXT_STEPS 참조).

---

## R-007 🟡 `analysis_cache` 키 구조 미문서화

**위치:** `backend/app/routers/paid.py`

**설명:**  
`analysis_cache`의 `cache_key` 생성 방식이 문서화되지 않음. 캐시 키 충돌 시 다른 지역·필터 조건의 결과가 혼용될 수 있음.

**권장 조치:** cache_key 생성 로직 `DECISIONS.md`에 기록 + 단위 테스트

---

## R-008 🟡 복수 DB (land/built/collective) 간 region_codes 동기화 수동

**위치:** 배포 문서 / `pipeline/seed_region_codes.py`

**설명:**  
행정구역 변경(분구·통합·폐지) 시 `land_stats.region_codes`만 업데이트되고 `built_stats`·`collective_stats`의 복사본은 수동으로 동기화해야 함.

**발생 시 증상:** 특정 지역 코드로 built/collective 조회 시 404 또는 잘못된 지역 반환.

**권장 조치:** 동기화 스크립트 자동화 또는 단일 region_codes DB로 통합

---

## R-009 🟡 Frontend 3앱 배포 독립 관리 복잡도

**위치:** `frontend/`, `frontend-built/`, `frontend-collective/`

**설명:**  
프론트엔드가 3개 독립 Vite 앱으로 분리. 공통 컴포넌트(RegionSelector 등) 변경 시 3곳 모두 수정 필요. 코드 중복 위험.

**권장 조치:** Monorepo(Turborepo/nx) 또는 shared 패키지 구조 검토

---

## R-010 🟡 API_TOKEN 보안 수준 미흡

**위치:** `backend/.env`, `backend/app/main.py`

**설명:**  
현재 보안은 단일 `API_TOKEN` 헤더 검사뿐. Rate limiting, 계정별 인증, RBAC 없음. 배포 후 토큰 유출 시 전체 API 무제한 접근 가능.

**현재 완화:** D-007 설명 "결제·로그인 도입 전 1단 보호"로 명시.

**권장 조치:** 단기: Rate limiting (nginx limit_req), 중기: JWT 인증 추가

---

## R-011 🟡 `biha_borok_dap_valid` 회귀 샘플 3건 잔존

**위치:** `land_transactions`, 충주 비하동 보녹·답

**설명:**  
dedupe+rehash 완료 후에도 청주 비하동 보녹·답 샘플이 기대값 2건이 아닌 3건으로 나타남. 이유 미확인.

**권장 조치:** 해당 3건의 `transaction_hash`, `contract_date`, `area_sqm` 직접 조회 후 실제 거래인지 오류인지 판별

---

## R-012 🟢 V1 라우터 폐기 지연

**위치:** `backend/app/routers/free.py`

**설명:**  
D-001에 의해 2026-06-30 코드 제거 예정이지만 아직 존재. 운영 중 쿼리가 V1을 호출하면 stale 데이터 반환.

**권장 조치:** 2026-06-30 전 제거 + V2 마이그레이션 완료 확인

---

## R-013 🟢 `regional_profile` 미완성 상태

**위치:** `pipeline/build_regional_profile.py`, `db/025_regional_profile.sql`

**설명:**  
전국 Profile은 충북 파일럿만 완료. `twin_from_profile.py`(v5)의 실 서비스 연결 없음. Twin v8이 Profile을 소비하지 않고 직접 market_stats를 사용.

**권장 조치:** Profile 전국 확장 후 Twin v8의 집합 스코어 소스를 Profile로 통합

---

## 요약 우선순위

| 순위 | 위험 | 조치 시급성 |
|------|------|------------|
| 1 | R-001 hash 충돌 재발 | 단위 테스트 즉시 |
| 2 | R-002 base cache stale | dedupe 후 자동 clear 즉시 |
| 3 | R-004 수동 갱신 SLA 위험 | 반자동화 단기 |
| 4 | R-005 MOLIT 컬럼 변경 | 방어 코드 단기 |
| 5 | R-006 Twin v8 전국 미완료 | 기능 완성 단기 |
| 6 | R-003 단일 DB 장애 | 인프라 중기 |
| 7 | R-008 region_codes 비동기 | 스크립트 중기 |
