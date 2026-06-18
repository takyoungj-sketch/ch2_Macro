# 집합부동산(주거 4유형) 원장·사전통계 전면 재구축 계획

> **작성:** 2026-06-17  
> **상태:** 착수 대기  
> **범위:** **주거 집합 4유형만** — `apartment` · `rowhouse` · `officetel` · `presale`  
> **비범위:** 집합상가·공장(`collective_commercial_*`), 복합(`built_stats`), 토지(`land_stats`)  
> **관련:** [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) · [`REGIONAL_PROFILE_ARCHITECTURE.md`](./REGIONAL_PROFILE_ARCHITECTURE.md) · [`COLLECTIVE_HANDOFF.md`](./COLLECTIVE_HANDOFF.md) · [`LONG_TERM_TREND_DESIGN.md`](./LONG_TERM_TREND_DESIGN.md)

---

## 1. 목표

| # | 목표 | 확정 |
|---|------|------|
| G1 | `raw/raw base/{유형}_2021_2026` CSV 기준 **`collective_transactions` 전량 재적재** | ✅ |
| G2 | 토지와 동일 **`as_of_month` + 롤링 3·5년** 사전통계 mart 재빌드 | ✅ |
| G3 | **통합 유형 화면** — 4유형 한 목록, 첫 컬럼에 유형 표시 | ✅ |
| G4 | 모달 **추세·요약** = as_of 기준 12개월 롤백 버킷 / **장기 추세** = 만년력 연도(2010~) | ✅ |
| G5 | 토지 수준 **표시 풍부화** — 목록 주소 `(도로명)`, 거래목록 계약일·매수·매도 | ✅ |
| G6 | **Promote는 보류** — 로컬 재구축·UI 검증 후 운영 반영 | ✅ |

---

## 2. 의사결정 요약 (2026-06-17 확정)

### 2.1 데이터·DB

| 항목 | 결정 |
|------|------|
| 재적재 방식 | **전량 재적재** (기존 주거 원장·mart TRUNCATE 후 raw base ingest) |
| `as_of_month` | **토지와 동일** — **6월 중순 운영 정상 `2026-05-01`**. 재구축 mart가 `2026-06-01`이면 [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) §12 — **7월 초 `202607` cycle에서 `2026-06-01`로 정상화** |
| 2026 CSV 처리 | 토지 재구축과 **동일** — as_of 시점 이후 월 거래는 mart 롤링 창에서 제외, 원장에는 보관 |
| `building_key` | **기존 규칙 유지** (`building_keys.py` SSOT) — long term·base 연속성 |
| 범위 | **주거 4유형만** (상업·공장 제외) |
| old/new diff | **불필요** |
| Promote | **나중에** (VPS·`collective_stats` 교체는 별도 작업) |

### 2.2 UI·분석

| 항목 | 결정 |
|------|------|
| 통합 목록 grain | **유형 × 건물** (`building_key` + `asset_type`) |
| 통합 페이징 상한 | **추가 없음** (기존 API 페이징 유지) |
| 지역 칩 건수 | **선택 유형만** (통합 모드에서도 칩 API에 `asset_type` 전달) |
| 연도 from/to | 통합·단일 유형 **공통 적용** |
| 코호트(통합분석) | **유형 혼합 허용** (아파트+오피스텔 동일 단지 등) |
| 분양권 mart | **building_stats · market_stats(presale_market) 포함** |
| 장기 추세 탭 | 연도 필터와 **무관하게 항상 표시** |
| 기본 추세 데이터 | mart 우선, 없으면 live (구현 시 판단) |

---

## 3. 전략 요약

```
[입력]  raw/raw base/{아파트|연립다세대|오피스텔|분양입주권}_2021_2026/*.csv
        raw/raw long term/{유형}_2010_2020/*.csv   ← annual backfill (원장 X)

[DB]    collective_stats (작업 DB — 전량 TRUNCATE 후 재적재)
        ※ Promote 전까지 VPS 프로덕션 DB는 기존 유지 권장

[파이프라인]
  ingest (4유형) → region_codes sync → region_sigungu_meta
  → building_stats (3·5y) + building_annual_stats (2021~ + long term)
  → building_rolling_buckets (신규, 모달 기본 추세)
  → market_stats (4 market_domain) → regional_profile (선택)

[UI]    frontend-collective — 통합 유형 · 주소/거래목록 풍부화 · 모달 2축 추세
```

토지 [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) §2 의 **병렬 DB(`*_next`)** 패턴은 이번에 **필수 아님** (old/new 비교 생략).  
로컬에서 `collective_stats` 직접 재적재. 운영 Promote 직전에 pg_dump 백업만 권장.

---

## 4. 입력 데이터

### 4.1 1차 소스 — 롤링·live·annual(2021~)

| 폴더 | 유형 | 파일 패턴 |
|------|------|-----------|
| `raw/raw base/아파트_2021_2026/` | apartment | `{시도}_아파트_매매_{2021..2026}.csv` |
| `raw/raw base/연립다세대_2021_2026/` | rowhouse | `{시도}_연립다세대_매매_{2021..2026}.csv` |
| `raw/raw base/오피스텔_2021_2026/` | officetel | `{시도}_오피스텔_매매_{2021..2026}.csv` |
| `raw/raw base/분양입주권_2021_2026/` | presale | `{시도}_분양입주권_매매_{2021..2026}.csv` |

- 형식: 국토부 Molit CSV (`skiprows=16`, `molit_schemas.py` iloc 매핑)
- 아파트: 구 `원본/아파트/*.xlsx` 대신 **CSV 통일** (raw base SSOT)

### 4.2 2차 소스 — 장기 추세(2010~2020)

| 폴더 | 용도 |
|------|------|
| `raw/raw long term/아파트_2010_2020/` | `collective_building_annual_stats` backfill |
| `raw/raw long term/연립다세대_2010_2020/` | 동일 |
| `raw/raw long term/오피스텔_2010_2020/` | 동일 |
| `raw/raw long term/분양입주권_2010_2020/` | 동일 |

- **원장(`collective_transactions`)에는 넣지 않음** — 토지 `land_annual_stats` 패턴과 동일
- 2021~ 구간은 base 원장에서 annual 집계, 2010~2020은 long term ingest 후 **같은 annual 테이블**에 merge

### 4.3 선행 마스터

| 테이블 | 조치 |
|--------|------|
| `region_codes` | `land_stats` → `sync_region_codes_from_land` (기존 스크립트) |
| `region_sigungu_meta` | ingest 후 `build_region_sigungu_meta.py --collective` (유형별·통합 meta) |

---

## 5. 산출물 — DB·스키마

### 5.1 원장 확장 (DDL 신규 migration)

현행 `016_collective_transactions.sql`에 **표시·모달용 컬럼 추가**:

| 컬럼 | 타입 | 출처(CSV) | 비고 |
|------|------|-----------|------|
| `buyer_type` | VARCHAR(20) | 매수자 | 예: 개인, 법인 |
| `seller_type` | VARCHAR(20) | 매도자 | |
| `deal_type` | VARCHAR(40) | 거래유형 | 중개거래, 직거래 등 |
| `contract_date` | DATE | (기존) | ingest 시 **연·월·일 완전 채움** |

- `refine.py` / `molit_schemas.py`: 4유형별 매수·매도·거래유형 col index 추가
- 해제·적재 정책: **기존 유지** (해제만 제외, semantic dedupe 없음)

### 5.2 사전통계 mart (기존 + 신규)

| 테이블 | grain | 용도 |
|--------|-------|------|
| `collective_building_stats` | building × as_of × window(3,5) | **목록 기본 통계** (4유형 + presale) |
| `collective_building_annual_stats` | building × calendar_year | **장기 추세 탭** (2010~as_of연도) |
| **`collective_building_rolling_stats`** *(신규)* | building × as_of × window × bucket_index | **모달 추세·요약** (12개월 롤백) |
| `market_stats` | region × market_domain × as_of × window | Profile·시장 (`presale_market` 추가) |
| `market_annual_stats` | region × domain × calendar_year | (기존, 필요 시 rebuild) |

**롤링 버킷 정의 (토지 매트릭스 모달과 동일):**

- 3년 창 → `bucket_index` 1..3 (각 12개월, as_of 역순)
- 5년 창 → `bucket_index` 1..5
- 집계: `contract_date` ∈ 버킷 구간, `unit_price` 통계(`compute_stats`)

### 5.3 `building_key` · annual 연속성

- base ingest와 long term ingest **동일 `attach_building_identity`** 사용
- long term CSV에 도로명·동 컬럼이 빠진 경우: 기존 아파트 ingest 스크립트의 **최소 컬럼 정규화** 확장 → 4유형 공통 모듈화

---

## 6. 산출물 — API

### 6.1 목록·메타

| 엔드포인트 | 변경 |
|------------|------|
| `GET /filter-meta` | `asset_types`에 **`all`(통합)** 추가 |
| `GET /regions/*` | `asset_type=all` → **해당 유형 필터만** (통합 시에도 칩은 단일 유형 기준 — UI가 유형 선택 후 칩 갱신) |
| `GET /buildings` | `asset_type` 생략 또는 `all` → **4유형 union**, 응답 `asset_type` 필드 필수, 정렬: 유형 → display_name |
| | `address` = 지번 주소 + **` (도로명)`** suffix (`format_building_address` 확장) |

### 6.2 모달

| 엔드포인트 | 변경 |
|------------|------|
| `GET /buildings/{key}/stats/by-year` | 유지 + data_source mart/live |
| **`GET /buildings/{key}/stats/rolling`** *(신규)* | window_years·as_of → bucket별 mean/count (mart 우선) |
| **`GET /buildings/long-term-trend`** *(신규, 또는 by-year 확장)* | annual mart 2010~ 한 번에 |
| `GET /buildings/{key}/transactions` | `contract_date`, `buyer_type`, `seller_type`, `deal_type`, `road_name` 반환 |
| `POST /analysis/cohort/*` | **`asset_type` optional** — 혼합 유형 시 building_keys만으로 집계 (동일 단지 cross-type) |

### 6.3 표시 규칙 (토지 정렬)

**목록 주소 (`address`):**

```
{addr3} {addr4} {lot_number} ({road_name})
```

- 도로명 없으면 괄호 생략
- 구현: `backend/app/collective/address.py`

**거래목록 계약일:**

- `contract_date` 있음 → `YYYY-MM-DD`
- 없음 → `YYYY.MM` fallback (토지 거래목록과 동일)

---

## 7. 산출물 — UI (`frontend-collective`)

### 7.1 메인 통계 화면

| 항목 | 내용 |
|------|------|
| 유형 선택 | **통합** 옵션 추가 (4유형 union) |
| 테이블 첫 컬럼 | **유형** (아파트 / 오피스텔 / 연립다세대 / 분양권) |
| 마지막 컬럼 | **주소** — API `address` (도로명 괄호 포함) |
| 3·5년 토글 | 기존 `StatsWindowToggle` — mart `as_of_month` 연동 |
| 연도 from/to | 통합·단일 공통 |

### 7.2 `BuildingDetailModal`

| 탭 | X축 | 데이터 |
|----|-----|--------|
| **추세·요약** (기본) | as_of 기준 **12개월×N 버킷** | `stats/rolling` mart |
| **장기 추세** *(탭 추가)* | **calendar_year** 2010~ | `building_annual_stats` (+ long term) |
| 거래 목록 | — | 계약일 YYYY-MM-DD, 매수·매도, 거래유형 컬럼 추가 |

- 연도 필터 활성화 시에도 **장기 추세 탭 유지** (필터는 거래목록·live 분석에만 반영)
- 코호트: 아파트 화면에서 **오피스텔 등 다른 유형 building_key 추가 가능** (혼합 cohort API)

---

## 8. 작업 단계 (권장 순서)

### Phase 0 — 준비 (0.5일)

- [ ] 브랜치 확인 (`feature/collective-work` 또는 `feature/collective-rebuild`)
- [ ] (선택) `pg_dump collective_stats` 백업
- [ ] DDL migration 초안: `026_collective_tx_display_columns.sql`, `027_collective_building_rolling_stats.sql`
- [ ] ingest 경로 상수: `import_refined.py` 기본 디렉터리 → `raw/raw base/{유형}_2021_2026`

### Phase 1 — 원장 전량 ingest (1~2일)

- [ ] `collective_transactions` TRUNCATE (주거 4유형; commercial 테이블 **미접촉**)
- [ ] 4유형 순차 ingest:
  ```powershell
  cd c:\ch2\ch2_Macro\pipeline
  py collective/import_refined.py --apartment-dir "..\raw\raw base\아파트_2021_2026" --apartment-only
  py collective/import_refined.py --rowhouse-dir "..\raw\raw base\연립다세대_2021_2026" --rowhouse-only
  py collective/import_refined.py --officetel-dir "..\raw\raw base\오피스텔_2021_2026" --officetel-only
  py collective/import_refined.py --presale-dir "..\raw\raw base\분양입주권_2021_2026" --presale-only
  ```
- [ ] `sync_region_codes` + `build_region_sigungu_meta.py --collective`
- [ ] 커버리지 로그: 유형별 건수, `contract_date`/`road_name`/매수·매도 채움률

### Phase 2 — 사전통계 mart (1~2일)

- [ ] `build_collective_building_stats.py --as-of 2026-05-01 --windows 3,5`  
      — `ASSET_TYPES`에 **`presale` 추가**
- [ ] `build_collective_building_rolling_stats.py` *(신규)* — 버킷 mart
- [ ] `build_collective_market_stats.py` — `presale_market` domain 추가
- [ ] (선택) `build_regional_profile.py` — market rebuild 후

### Phase 3 — 장기 annual backfill (0.5~1일)

- [ ] `ingest_collective_long_term_annual.py` → **4유형 generalize** (`rglob` 하위 폴더)
- [ ] base 원장에서 2021~ annual + long term 2010~2020 merge 검증 (building_key 샘플 spot check)

### Phase 4 — Backend API (1~2일)

- [ ] `format_building_address` — 도로명 괄호
- [ ] `/buildings` 통합 유형·address·mart 메타
- [ ] `/stats/rolling`, long-term trend API
- [ ] transaction schema 확장 + cohort 혼합 유형
- [ ] filter-meta / region catalog `asset_type` 확장

### Phase 5 — Frontend (1~2일)

- [ ] `AssetType` + `all` · 유형 컬럼 · 주소 표시
- [ ] 모달: rolling chart + **장기 추세 탭**
- [ ] 거래목록: 계약일·매수·매도·거래유형
- [ ] 통합 모드 코호트 UX (유형 혼합 선택)

### Phase 6 — 스모크·문서 (0.5일)

- [ ] `finish_collective_pre_promote.py` 또는 전용 smoke script
- [ ] [`COLLECTIVE_HANDOFF.md`](./COLLECTIVE_HANDOFF.md) ingest 경로·건수 갱신
- [ ] **Promote 보류** — 7월 21.7~26.6 갱신 시 as_of 재배치 TODO 메모

---

## 9. 토지 대비 갭 · 이번에 메우는 항목

| 토지 | 집합 (현재 → 목표) |
|------|---------------------|
| 목록 주소 + 도로명 | 지번만 → **지번 (도로명)** |
| 거래목록 contract_date | 연월만 → **YYYY-MM-DD** |
| 매수·매도·거래유형 | 있음 → **원장·UI 추가** |
| 기본통계 롤링 as_of | V2 mart → **building_stats mart** |
| 모달 기본 추세 | 12개월 버킷 → **rolling_stats mart (신규)** |
| 모달 장기 추세 | land_annual_stats → **building_annual_stats + long term** |
| 유형 통합 보기 | N/A → **all 유형 union 목록** |

---

## 10. 리스크·완화

| 리스크 | 완화 |
|--------|------|
| 전량 TRUNCATE 실수 | commercial 테이블 분리; ingest 전 pg_dump |
| 아파트 xlsx→CSV 스키마 차 | `read_source_file` + `molit_schemas` smoke (1시도 1년) |
| long term building_key 불일치 | 동일 `building_keys.py`; 샘플 단지 cross-check |
| 통합 목록 성능 | mart-first 유지; 연도 필터 시 live fallback (기존 패턴) |
| 혼합 cohort 해석 | UI에 유형별 n 표시; 회귀는 building dummy로 수준 차 통제 (기존 설계) |
| as_of 5월 vs 6월 데이터 | 7월 주기 갱신 SOP에 `--as-of` 재실행 명시 |

---

## 11. 완료 기준 (Promote 전 로컬)

- [ ] 4유형 raw base ingest 완료, 2026년 파일 포함
- [ ] `collective_building_stats` @ `2026-05-01`, windows 3·5, **presale 포함**
- [ ] `collective_building_rolling_stats` @ 동일 as_of
- [ ] `collective_building_annual_stats` 2010~2025(+) building 샘플 조회
- [ ] UI: 통합 유형 · 유형 컬럼 · 주소 `(도로명)` · 거래목록 풍부화
- [ ] UI: 모달 추세·요약 = 롤링 버킷, 장기 추세 = 만년력
- [ ] cohort 아파트+오피스텔 혼합 smoke

---

## 12. 다음 액션 (즉시)

1. **Phase 0** — DDL `026`·`027` 초안 + `import_refined.py` raw base 경로 연결  
2. **Phase 1 smoke** — 서울 아파트 2026 CSV 1파일 ingest → 컬럼·건수 확인  
3. smoke OK → **4유형 전국 ingest** → Phase 2 mart 배치  

---

## 13. 관련 경로

| 구분 | 경로 |
|------|------|
| ingest | `pipeline/collective/import_refined.py` |
| 정제 | `pipeline/collective/refine.py`, `molit_schemas.py` |
| mart | `pipeline/build_collective_building_stats.py`, `build_collective_market_stats.py` |
| long term | `pipeline/ingest_collective_long_term_annual.py` |
| API | `backend/app/collective/router.py`, `cohort_router.py`, `building_stats_query.py` |
| UI | `frontend-collective/src/App.tsx`, `BuildingDetailModal.tsx` |
| raw base | `raw/raw base/{유형}_2021_2026/` |
| long term | `raw/raw long term/{유형}_2010_2020/` |
