# Built · Collective canonical 영향 조사 (재빌드 없음)

조사일: 2026-07-22  
전제: 새 resolver 금지 — `pipeline/region_canonical.py` / `backend/app/region_canonical.py`만 재사용.  
원장 `beopjungri_code` 불변. unresolved **2건** 제외 유지.

---

## 1. 한 줄 결론

| 항목 | 결과 |
|------|------|
| 원장 historical 존재 | **있음** — Built 6,288 / Collective 17,901 / Collective商 1,782 (191 from_code 기준) |
| mart에 historical eup grain | **있음** — `market_stats` 등 8자리 stale eup 행 잔류, **canonical eup 행 0** |
| Built/Collective DB에 `region_code_history` | **없음** (blocker) — 빌더 SQL의 history JOIN이 지금 상태로는 실행 불가 |
| 즉시 재빌드 | **하지 않음** (본 조사만) |

핵심 선행 작업: **land → built_stats / collective_stats 로 `region_code_history`(191) 동기화** (또는 빌드 시 land 연결로 history map 적재). `region_codes`만 복사하는 현 sync로는 부족.

---

## 2. 191구코드 × DB 실측

Phase 1a `code_reissue` **191**쌍. land `region_code_history` **191**행.

### 원장 (historical `beopjungri_code` = from_code)

| DB | 테이블 | hist rows | hist codes | canon(to) rows |
|----|--------|-----------|------------|----------------|
| built_stats | `built_transactions` | **6,288** | **169** | 0 |
| collective_stats | `collective_transactions` | **17,901** | **76** | 0 |
| collective_stats | `collective_commercial_transactions` | **1,782** | **42** | 0 |
| collective_stats | `collective_building_annual_stats` | 2,956 | 84 | 0 |
| collective_stats | `collective_presale_lifetime_stats` | 38 | 12 | 0 |

- Built/Collective 원장의 191-hit는 **전부 시도 41(경기·화성 분구 계열)**.
- 수태리 신·구(`4377025626`/`4377034026`) 거래는 Built/Collective **0건**. 음성군 prefix(`43770`) 거래는 있으나 이번 대소 검증 케이스와는 무관.
- 원장에 **canonical to_code 거래 0건** → GIS가 신코드를 보내면 **expand_to_ledger** 없으면 분석 누락.

### mart (region_code 길이 2/5/8 — 10자리 hist 직접 매칭은 0)

면→읍·분구로 **eup 8자리가 바뀌는 stale prefix 15개** 기준:

| DB | 테이블 | stale eup8 rows | canon eup8 rows |
|----|--------|-----------------|-----------------|
| collective_stats | `market_stats` | **358** | **0** |
| collective_stats | `market_annual_stats` | **205** | **0** |
| collective_stats | `collective_commercial_region_annual_stats` | **68** | **0** |
| built_stats | `built_annual_stats` | **234** | **0** |

→ 현재 mart는 historical prefix로 쌓여 있고, canonical 쪽 grain은 비어 있음.

### grain이 코드가 아닌 것 (이번 canonical 범위 밖·우선순위 낮음)

| 테이블 | grain |
|--------|--------|
| `collective_cluster_annual_stats` | `cluster_key` |
| `collective_commercial_cluster_annual_stats` | `cluster_key` |
| `collective_building_rolling_stats` | `building_key` |

`beopjungri_code` 컬럼이 있어도 **분석 키는 cluster/building**. 부분 remap은 후순위.

---

## 3. 코드 경로 점검 (공통 resolver 재사용)

### 이미 적용됨 (커밋 `8bf451f` 포함)

| 경로 | 상태 |
|------|------|
| `backend/app/region_scope.py` beopjungri → `expand_to_ledger_codes` | ✅ (conn 있을 때) |
| Built `transaction_scope` / regression `conn=` 전달 | ✅ |
| `pipeline/build_collective_market_stats.py` | ✅ SQL에 `canonical_select_expr` / history JOIN |
| Land paid/free | ✅ (이번 Built 범위 밖) |

### 미적용·갭

| 경로 | 갭 |
|------|-----|
| Built/Collective DB | **`region_code_history` 미존재** → 위 빌더 재실행 시 실패 또는 identity만 |
| `built/resolve_codes.py`, `collective/resolve_codes.py` | 지도용 코드를 원장 그대로 반환 → GIS 신코드와 불일치 가능; **resolve_to_canonical** 미적용 |
| regression pandas 필터 (`engine.py` mask by codes) | SQL scope는 expand, **DataFrame 재필터는 expand 없음** |
| Collective `filters.py` | addr 기반 `apply_region_scope` 위주 — GIS beopjungri 선택은 Built만큼 안 탐 |
| Profile이 소비하는 market/annual | stale eup grain이면 Profile도 오염 (Profile 재빌드는 별 단계) |

### untracked 스크립트 — **canonical 전환 대상인가?**

| 파일 | 판정 | 이유 |
|------|------|------|
| `pipeline/build_built_market_stats.py` | **예 (대상)** | `built_transactions` → `market_stats`(collective DB) + `built_annual_stats`. 이미 `canonical_select_expr` 배선됨. **미커밋·미재빌드**라 mart는 아직 historical. |
| `pipeline/build_collective_commercial_market_stats.py` | **예 (대상)** | commercial → `market_stats` + `collective_commercial_region_annual_stats`. 동일. |

새 resolver를 만들지 말고, 이 두 파일을 **공용 `region_canonical` 유지한 채 커밋·history sync 후 부분 재빌드**하면 됨.

---

## 4. 재빌드 대상 테이블 (실행하지 않음 — 제안만)

**선행 (필수)**  
1. `region_code_history` 191행을 `built_stats` · `collective_stats`에 동기화 (DDL+copy).  
2. `region_codes` active/inactive가 land와 정합한지 확인 (이미 sync 경로 있음).

**원장**  
- UPDATE 금지. historical 코드 유지.

**부분 재빌드 후보 (영향 큰 순)**

| 우선 | 테이블 | DB | 빌더 | 비고 |
|------|--------|-----|------|------|
| P0 | `market_stats` | collective | `build_collective_market_stats` + `build_built_market_stats` + commercial | stale eup8 358행 |
| P0 | `market_annual_stats` | collective | 동상 | stale 205 |
| P0 | `built_annual_stats` | built | `build_built_market_stats` | stale 234 |
| P0 | `collective_commercial_region_annual_stats` | collective | `build_collective_commercial_market_stats` | stale 68 |
| P1 | API 조회 경로 | — | `resolve_*_map_codes` + regression DF expand | 재빌드 없이 코드만 |
| P2 | `collective_building_annual_stats` 등 | collective | building/presale 빌더 | beopjungri는 부속; grain 재검토 후 |

**부분 재빌드 힌트 (효율)**  
- 시도 **41**만 먼저 (원장 hist 전량이 41).  
- stale eup 15 prefix / 해당 from→to 191코드의 eup·sigungu 버킷만 DELETE 후 upsert.  
- 전국 full rebuild는 비권장.

**제외 유지**  
- unresolved 2건 (통영 당포리/삼덕리) — history 없음, auto remap 금지.

---

## 5. 권장 다음 단계 (아직 실행하지 말 것)

1. history sync 설계·스크립트 (land → built/collective).  
2. untracked 두 market 빌더 커밋 (canonical 배선 유지).  
3. API: map resolve / regression DF에 `resolve_to_canonical` + `expand_to_ledger_codes`.  
4. 시도 41 한정 스모크 재빌드 → GIS 신코드 선택 시 market hit 확인.  
5. 이상 없으면 잔여 sido / building 부속 정리.

산출 JSON: [`REGION_CODE_BUILT_COLLECTIVE_IMPACT.json`](./REGION_CODE_BUILT_COLLECTIVE_IMPACT.json)
