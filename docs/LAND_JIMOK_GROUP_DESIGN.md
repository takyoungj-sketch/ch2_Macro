# 토지 지목군(7그룹) — 설계·매핑·구현 계획

> **작성:** 2026-06-30 · **개정:** 2026-07-17  
> **상태:** 분류표·제품 정책 **확정** · DDL `037`/`038` **준비됨** · mart·API·UI **미구현** (착수 대기)  
> **SSOT:** 본 문서 · [`DECISIONS.md`](./DECISIONS.md) **D-026** (+ 2026-07-17 개정)  
> **관련:** [`NEXT_STEPS.md`](../NEXT_STEPS.md) §5 · [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) §12.6 · [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md)

---

## 1. 배경·목표

현행 토지 통계 매트릭스는 **행 = 용도지역(`zone_type`)**, **열 = 지목(`land_category`)** 이다.  
지목 열이 많아 시장 구조를 한눈에 보기 어렵고, 향후 지역 간 비교(Profile·Twin)에서도 차원이 과도하게 쪼개진다.

**목표**

| # | 목표 |
|---|------|
| G1 | 국토 지목을 **7개 지목군**으로 묶는 `jimok_group` 도입 |
| G2 | **기본 UI는 용도 × 지목 유지**, 옵션으로 **용도 × 지목군** 전환 |
| G3 | **원장 Master(`land_transactions`)는 수정하지 않음** (D-025) — 매핑·VIEW·mart만 확장 |
| G4 | 동일 거래 데이터를 **두 관점**(지목 / 지목군)으로 집계 — 대체재가 아닌 **상위 분석 레이어** |

**비목표 (이번 구현 범위)**

- MOLIT 원장 전량 재적재
- 복합·집합 제품 변경
- **Regional Profile · Twin에 지목군 Feature 연결** (통계·UI 검증 후 후속)

---

## 2. 제품 정책 (2026-07-17 확정)

### 2.1 매트릭스 뷰

| 모드 | grain | UI | 역할 |
|------|-------|-----|------|
| **기본** | `zone_type` × `land_category` | **용도 × 지목** | CH2 토지통계 핵심 분석 체계 (현행 유지) |
| **옵션** | `zone_type` × `jimok_group` | **용도 × 지목군** | 7개 상위 유형으로 묶어 시장구조 단순 파악 |

- 지목군은 기존 지목 통계의 **대체재가 아니다.**
- 전환: 토글/버튼 (예: `matrix_mode=category|group`).

### 2.2 데이터 흐름

```
원장 land_category (Master 보존)
  → land_category_resolved          (D-025 Correction Rule)
  → land_jimok_group_map            (지목 → 지목군)
  → 용도 × 지목 mart                (기본 UI)
  → 용도 × 지목군 mart              (옵션 UI, 원장 단가 재집계)
```

### 2.3 UI·DB 명칭

| 구분 | 명칭 | 비고 |
|------|------|------|
| DB | `jimok_group` / `jimok_group_code` / `jimok_group_label` | 내부 SSOT |
| UI (권장) | **용도 × 지목** / **용도 × 지목군** | 「이용」단독 표기는 감정평가 **이용상황**과 혼동 가능 → 비권장 |
| UI (대안) | 용도 × 이용유형 | 가능하나 툴팁 권장 |

툴팁 예: *「국토부 지목을 7개 상위 유형으로 묶어 집계합니다. 원장 지목은 그대로 유지됩니다.」*

### 2.4 Profile · Twin (후속)

지목군 비중은 전국 지역 비교 Feature로 **나중에** 쓸 수 있다.  
**지금은 연결하지 않는다.** 토지 매트릭스에서 지목군 mart·UI가 안정된 뒤 검토.

---

## 3. 지목군 분류표 (확정 · 2026-07-17)

국토부 표기 기준 **28지목** → ①~⑥ 고정 매핑 · ⑦은 잔여.

| 코드 | 명칭 | 포함 지목 (국토부 표기) | 개수 |
|------|------|-------------------------|------|
| `agri` | ① 농경지 | 전, 답, 과수원, **양어장, 목장용지** | 5 |
| `forest` | ② 산림지 | 임야 | 1 |
| `dev` | ③ 개발지(건축가능지) | 대, 공장용지, 학교용지, 주차장, 주유소용지, 창고용지, 잡종지 | 7 |
| `infra` | ④ 기반시설 | 도로, 철도용지, 제방, 구거, 수도용지 | 5 |
| `water` | ⑤ 수면 | 하천, 유지 | 2 |
| `special` | ⑥ 특수용도 | 공원, 체육용지, 유원지, 종교용지, 사적지, 묘지, 광천지, 염전 | 8 |
| `other` | ⑦ 기타(미분류) | 매핑 테이블에 없는 지목 · NULL · 미분류 잔여 | — |

**합계:** 5+1+7+5+2+8 = **28** (⑦ 제외).

### 3.1 분류 개정 이력

| 일자 | 내용 |
|------|------|
| 2026-06-30 | 초안. 광천지·염전 → **⑥ 특수용도** 확정 (⑦과 중복 해소). |
| **2026-07-17** | **양어장·목장용지**를 ③ 개발지 → **① 농경지**로 이동. |

### 3.2 DB 저장값 ↔ 표기 (축약 코드)

`pipeline/clean.py` 는 일부 지목을 **1글자 축약**해 `land_category`에 넣는다 (`LAND_CATEGORY_COMPACT_MAP`).  
`land_jimok_group_map` 은 **원문·축약 모두** 키로 등록한다. 구현 파일: [`db/037_land_jimok_group_map.sql`](../db/037_land_jimok_group_map.sql).

| 국토부 표기 | DB `land_category` (대표) | 지목군 |
|-------------|---------------------------|--------|
| 전 | `전` | `agri` |
| 답 | `답` | `agri` |
| 과수원 | `과` | `agri` |
| **양어장** | `양` | **`agri`** |
| **목장용지** | `목` | **`agri`** |
| 임야 | `임` | `forest` |
| 대 | `대` | `dev` |
| 공장용지 | `장` | `dev` |
| 학교용지 | `학` | `dev` |
| 주차장 | `차` | `dev` |
| 주유소용지 | `주` | `dev` |
| 창고용지 | `창` | `dev` |
| 잡종지 | `잡` | `dev` |
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
| 사적지 | `사적지` | `special` |
| 묘지 | `묘` | `special` |
| 광천지 | `광천지` | `special` |
| 염전 | `염전` | `special` |

**구현 전:** `SELECT land_category_resolved, COUNT(*) … GROUP BY 1` 로 미매핑 지목을 확인하고 map에 추가한다.

---

## 4. 데이터 모델

### 4.1 원장 — 변경 없음

- `land_transactions.land_category` — Master 원본 유지 (D-025)
- `land_transactions_resolved.land_category_resolved` — 분석용 지목 (Rule 반영)

### 4.2 참조 테이블 — `db/037_land_jimok_group_map.sql` ✅

```sql
CREATE TABLE land_jimok_group_map (
    jimok_key       VARCHAR(20) PRIMARY KEY,
    jimok_label     VARCHAR(40) NOT NULL,
    group_code      VARCHAR(16) NOT NULL,  -- agri | forest | dev | …
    group_label     VARCHAR(40) NOT NULL,
    sort_order      SMALLINT NOT NULL DEFAULT 0
);
```

### 4.3 VIEW — `db/038_land_transactions_resolved_jimok_group.sql` ✅

파생 컬럼: `jimok_group_code`, `jimok_group_label`  
매핑 미스 → `other` / `기타`.

`scripts/monthly/run_land_cycle_csv.py` 에 DDL 파일명 연결됨.

---

## 5. 사전통계(mart)

현행 grain: `(…, zone_type, land_category)`.

| mart | 현재 | 변경 방향 |
|------|------|-----------|
| `land_basic_stats_v2` | zone × 지목 | **유지** + **zone × jimok_group** 병행 grain (또는 별도 테이블/파티션 — 구현 시 정련) |
| `land_upper_stats_v2` | 동일 | 동일 |
| `land_annual_*` | 장기추세 | group grain **병행** (옵션 장기추세 시) |

**주의:** 지목별 mart 평균을 합쳐 지목군 평균을 만들면 **틀림**.  
반드시 **원장 단가(`unit_price_per_sqm`)를 `zone_type × jimok_group`으로 재집계**.

**검증:** zone×group 의 `count` = 해당 group에 속한 zone×지목 `count` 합.

**파이프라인**

- `pipeline/build_stats_v2.py`
- `pipeline/build_upper_stats_v2.py`
- `land_annual_*` 빌더 (장기추세 옵션 시)
- `scripts/monthly/run_monthly_cycle.py` / `run_land_cycle_csv.py`

---

## 6. API·UI

| 영역 | 변경 |
|------|------|
| `free_v2` / `upper_stats` / `paid` | `matrix_mode=category`(기본) \| `group`(옵션). group 시 열 = 지목군 |
| `MatrixStatsTable` | 전환 토글: **용도×지목** / **용도×지목군** |
| `PaidMatrixYearlyModal` · 장기추세 | group 모드 시 `jimok_group` 요청 |
| Profile·Twin | **이번 범위 제외** |

---

## 7. 구현 작업 분해 (순서)

| # | 작업 | 상태 |
|---|------|------|
| J0 | 분류표·제품 정책 문서화 (본 문서) | ✅ 2026-07-17 |
| J1 | `land_jimok_group_map` 시드 (양어장·목장 → agri 반영) | ✅ DDL + 로컬 적용 |
| J2 | resolved VIEW `jimok_group_*` | ✅ |
| J3 | `build_stats_v2` / `build_upper_stats_v2` (+ annual) **group grain 병행** | ✅ `--col-axis group|both` · 충북(43) 로컬 적재 |
| J4 | paid / free_v2 / upper_stats API (`matrix_mode`) | ✅ |
| J5 | Matrix UI 전환 토글 | ✅ 용도×지목 / 용도×지목군 |
| J6 | 로컬 시험 빌드 + integrity (zone×group vs 지목 합) | ✅ 충북 sample mismatch=0 |
| J7 | 월간 cycle 반영 · Promote · 프론트 배포 | ⬜ |

---

## 8. 체크리스트

```
[x] 분류표·UI 정책 확정 (기본=지목, 옵션=지목군)
[x] 양어장·목장용지 → 농경지
[x] db/037 시드 개정 적용 (양·목 → agri)
[x] 운영/로컬 DISTINCT land_category_resolved → 미매핑 점검 (충북 unmapped=0)
[x] build_stats_v2 / build_upper_stats_v2 group grain (`--col-axis`, db/040 col_axis)
[x] paid / free_v2 / upper_stats matrix_mode
[x] MatrixStatsTable 토글 (용도×지목 | 용도×지목군)
[ ] land_annual_* group (옵션)
[x] DATA_INTEGRITY Level 2 group 검증 (충북 sample)
[ ] cycle + Promote + VPS 프론트 (전국 group mart)
[ ] (후속) Profile·Twin Feature 검토 — 이번 범위 아님
```

---

## 9. 작업량·리스크

| 구분 | 판단 |
|------|------|
| 원장 재구축 | **불필요** |
| 사전통계 재구축 | **필수** (지목 mart 유지 + group mart 추가) |
| 코드·UI | **중** (토글·병행 grain; 기본 경로 비파괴) |
| 리스크 | 미매핑 지목, 축약/원문 혼재, group 평균을 지목 mart에서 합산하는 실수 |

---

## 관련 문서

- 결정: [`DECISIONS.md`](./DECISIONS.md) **D-026**
- 작업계획: [`NEXT_STEPS.md`](../NEXT_STEPS.md) **§5**
- 월간 SOP: [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md)
- 매트릭스: [`V2_STATS_DESIGN.md`](./V2_STATS_DESIGN.md), [`UPPER_STATS_DESIGN.md`](./UPPER_STATS_DESIGN.md)
