# 토지 지목 대분류(7그룹) — 설계·매핑·구현 계획

> **작성:** 2026-06-30  
> **상태:** 설계 확정(분류표) · 구현 **보류** — **202607 월간 cycle**과 함께 반영  
> **관련:** [`DECISIONS.md`](./DECISIONS.md) D-026 · [`NEXT_STEPS.md`](../NEXT_STEPS.md) §5 · [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) §12 · [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md)

---

## 1. 배경·목표

현행 토지 통계 매트릭스는 **행 = 용도지역(`zone_type`)**, **열 = 지목(`land_category`)** 이다.  
지목 종류가 많아 열이 넓고, 정책·해석 관점의 **용도별(대분류) 비교**가 어렵다.

**목표**

| # | 목표 |
|---|------|
| G1 | 국토 지목을 **7개 대분류**로 묶는 `jimok_group` (가칭) 도입 |
| G2 | 통계 매트릭스를 **용도지역 × 지목 대분류**로 재구성 (지목 상세는 드릴다운·토글로 유지 검토) |
| G3 | **원장 Master(`land_transactions`)는 수정하지 않음** (D-025) — 매핑·VIEW·mart만 확장 |
| G4 | **202607(7월 초) 월간 업데이트** 시 데이터 갱신·사전통계 재구축과 **한 번에** 반영 |

**비목표 (이번 사이클)**

- MOLIT 원장 전량 재적재 (이미 `land_category` 존재)
- 복합·집합 제품 변경

---

## 2. 지목 대분류 (확정 분류표)

운영·통계·UI에서 사용하는 **공식 7분류**이다.

| 코드 | 명칭 | 포함 지목 (국토부 표기) |
|------|------|-------------------------|
| `agri` | ① 농경지 | 전, 답, 과수원 |
| `forest` | ② 산림지 | 임야 |
| `dev` | ③ 개발지(건축가능지) | 대, 공장용지, 학교용지, 주차장, 주유소용지, 창고용지, 양어장, 잡종지, 목장용지 |
| `infra` | ④ 기반시설 | 도로, 철도용지, 제방, 구거, 수도용지 |
| `water` | ⑤ 수면 | 하천, 유지 |
| `special` | ⑥ 특수용도 | 공원, 체육용지, 유원지, 종교용지, 사적지, 묘지, 광천지, 염전 |
| `other` | ⑦ 기타(보전·미분류) | 매핑 테이블에 없는 지목 · NULL · 미분류 잔여 |

### 2.1 작성 시 중복 항목 (광천지·염전)

초안 표에 **⑥·⑦ 모두** `광천지`, `염전`이 기재되어 있었다.  
**확정 정책 (2026-06-30):**

- `광천지`, `염전` → **`special` (⑥ 특수용도)** 에 귀속
- `other` (⑦) → **위 ①~⑥에 매핑되지 않은 값**만 (예: 신규·오타·빈 값)

### 2.2 DB 저장값 ↔ 표기 (축약 코드)

`pipeline/clean.py` 는 일부 지목을 **1글자 축약**해 `land_category`에 넣는다 (`pipeline/constants.py` `LAND_CATEGORY_COMPACT_MAP`).  
매핑 테이블은 **원문·축약 모두** 키로 등록한다.

| 국토부 표기 | DB `land_category` (대표) | 대분류 |
|-------------|---------------------------|--------|
| 전 | `전` | `agri` |
| 답 | `답` | `agri` |
| 과수원 | `과` | `agri` |
| 임야 | `임` | `forest` |
| 대 | `대` | `dev` |
| 공장용지 | `장` | `dev` |
| 학교용지 | `학` | `dev` |
| 주차장 | `차` | `dev` |
| 주유소용지 | `주` | `dev` |
| 창고용지 | `창` | `dev` |
| 양어장 | `양` | `dev` |
| 잡종지 | `잡` | `dev` |
| 목장용지 | `목` | `dev` |
| 도로 | `도` | `infra` |
| 철도용지 | `철` | `infra` |
| 제방 | `제` | `infra` |
| 구거 | `구` | `infra` |
| 수도용지 | `수` | `infra` |
| 하천 | `천` | `water` |
| 유지 | `유` | `water` |
| 공원 | `공` | `special` |
| 체육용지 | `체` | `special` |
| 유원지 | `원` | `special` |
| 종교용지 | `종` | `special` |
| 사적지 | `사적지` (축약 없음) | `special` |
| 묘지 | `묘` | `special` |
| 광천지 | `광천지` (축약 없음, 예상) | `special` |
| 염전 | `염전` (축약 없음, 실데이터 확인됨) | `special` |

**7월 cycle 전 필수:** 운영 DB에서 `SELECT land_category_resolved, COUNT(*) … GROUP BY 1` 로 **미매핑 지목** 목록을 확정하고 `land_jimok_group_map` 에 추가한다.

---

## 3. 데이터 모델 (계획)

### 3.1 원장 — 변경 없음

- `land_transactions.land_category` — Master 원본 유지 (D-025)
- `land_transactions_resolved.land_category_resolved` — 분석용 지목 (Rule 반영)

### 3.2 신규 참조 테이블 (예정 DDL: `db/037_land_jimok_group_map.sql`)

```sql
-- 개념 스키마 (구현 시 정련)
CREATE TABLE land_jimok_group_map (
    jimok_key       VARCHAR(20) PRIMARY KEY,  -- DB land_category 값 (전, 임, 사적지, …)
    jimok_label     VARCHAR(40) NOT NULL,   -- 화면용 국토부 표기
    group_code      VARCHAR(16) NOT NULL,   -- agri | forest | dev | …
    group_label     VARCHAR(40) NOT NULL,   -- 농경지 | 산림지 | …
    sort_order      SMALLINT NOT NULL DEFAULT 0
);
```

### 3.3 VIEW 확장 (예정: `db/038_land_transactions_resolved_jimok_group.sql`)

`land_transactions_resolved` 에 파생 컬럼 추가 (또는 별도 VIEW):

- `jimok_group_code`
- `jimok_group_label`

매핑 미스 시 → `other` / `기타(보전·미분류)`.

---

## 4. 사전통계(mart) 영향

현행 grain: `(…, zone_type, land_category)` — [`db/010_land_upper_stats_v2.sql`](./010_land_upper_stats_v2.sql), [`db/007`](./007_land_basic_stats_v2.sql) 계열, `land_annual_*`.

| mart | 현재 | 변경 방향 |
|------|------|-----------|
| `land_basic_stats_v2` | zone × 지목 | **`jimok_group` 차원 추가** (병행 또는 대체 — UI 정책에 따름) |
| `land_upper_stats_v2` | 동일 | 동일 |
| `land_annual_stats` | 장기추세 | `jimok_group` grain 추가 |
| `land_annual_upper_stats` | 상위 장기추세 | 동일 |

**주의:** 기존 mart 행의 평균을 합쳐서 대분류 평균을 만들면 **통계적으로 틀림**.  
반드시 **원장 단가(`unit_price_per_sqm`)를 `zone_type × jimok_group` 으로 재집계**한다.

**파이프라인 수정 대상**

- `pipeline/build_stats_v2.py`
- `pipeline/build_upper_stats_v2.py`
- `land_annual_*` 빌더 (장기추세 사용 시)
- `scripts/monthly/run_monthly_cycle.py` — V2 단계에 group mart 포함

**검증:** [`DATA_INTEGRITY_CHECKLIST.md`](./DATA_INTEGRITY_CHECKLIST.md) Level 2 — zone×group 합이 zone×지목 합과 표본 수 일치.

---

## 5. API·UI 영향 (개요)

| 영역 | 파일·엔드포인트 | 변경 |
|------|-----------------|------|
| 무료 V2 | `free_v2.py` | matrix 키 `land_category` → `jimok_group` (또는 병행 필드) |
| 유료 기본 | `upper_stats.py` | mart 조회 grain |
| 유료 필터 | `paid.py` `_analyze_core_*` | `GROUP BY zone_type, jimok_group` |
| 매트릭스 UI | `MatrixStatsTable.tsx` | 열 헤더 7그룹 (+ 지목 드릴다운 옵션) |
| 셀 모달 | `PaidMatrixYearlyModal.tsx` | 요청 body `jimok_group` |
| 장기추세 | `paid.py` long-term | `land_annual_*` grain |
| 회귀·AI·Twin | 각 컨텍스트 빌더 | 셀 정의 `(zone, group)` |

**UI 정책 (7월 전 결정):**

- **A (권장 초안):** 기본 매트릭스 열 = 7대분류, 셀 클릭 시 지목별 하위 표 또는 토글
- **B:** 7대분류 / 지목별 **뷰 전환** 토글만

---

## 6. 202607 월간 cycle 연동 일정

[`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) §12 · [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md) 와 동일 타임라인.

| 시점 | `cycle_id` | `as_of_month` | 작업 |
|------|------------|---------------|------|
| **7월 초 (계획)** | `202607` | `2026-06-01` | 수집 `202507`~`202606` + clean + **지목 대분류 mart 포함 V2 재구축** + Promote |

### 6.1 202607 전 (코드·DDL — 6월 말~7월 초)

1. `land_jimok_group_map` 시드 SQL + `constants` 동기화
2. `land_transactions_resolved` VIEW 확장
3. `build_stats_v2` / `build_upper_stats_v2` (± annual) 수정
4. API·프론트 매트릭스 1차 (최소: 유료·무료 matrix 응답)
5. 로컬 `land_stats_next` 에서 **group mart 시험 빌드**
6. `verify_monthly_integrity` / 샘플 대조

### 6.2 202607 당일 (운영)

```powershell
# DDL 적용 → 코드 배포 → (이미 반영된 pipeline으로)
py scripts\monthly\run_monthly_cycle.py --cycle-id 202607
# 검증 후 Promote, STATS_V2_DEFAULT_AS_OF_MONTH=2026-06-01
```

### 6.3 202607 이후

- VPS 프론트 배포 (매트릭스 UI)
- 미매핑 지목 모니터링 → `land_jimok_group_map` 패치

---

## 7. 작업량·리스크 (요약)

| 구분 | 판단 |
|------|------|
| 원장 재구축 | **불필요** |
| clean 재실행 | **202607 cycle에 포함** (월간 갱신과 동일) |
| 사전통계 재구축 | **필수** (전국 `build_stats_v2` + `build_upper_stats_v2` + annual) |
| 코드·UI | **중~대** (2~3주, 지목 드릴다운 범위에 따라 ±) |
| 리스크 | 미매핑 지목, 축약/원문 혼재, ⑥⑦ 중복 해소 완료, Promote 시 as_of 정합 (§12) |

---

## 8. 체크리스트

```
[ ] 운영 DB DISTINCT land_category_resolved 조사 → map 시드 완료
[ ] db/037, db/038 DDL + pipeline/constants 동기화
[ ] build_stats_v2 / build_upper_stats_v2 group grain
[ ] paid / free_v2 / upper_stats API
[ ] MatrixStatsTable + PaidMatrixYearlyModal
[ ] land_annual_* (장기추세) — 필요 시 동일 cycle
[ ] DATA_INTEGRITY Level 2 group 검증 쿼리 추가
[ ] 202607 run_monthly_cycle + Promote
```

---

## 관련 문서

- 결정: [`DECISIONS.md`](./DECISIONS.md) **D-026**
- 작업계획: [`NEXT_STEPS.md`](../NEXT_STEPS.md) **§5**
- 월간 SOP: [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md)
- 매트릭스 설계: [`V2_STATS_DESIGN.md`](./V2_STATS_DESIGN.md), [`UPPER_STATS_DESIGN.md`](./UPPER_STATS_DESIGN.md)
