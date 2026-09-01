# 월간 업데이트 1페이지 체크리스트

> **SSOT 경로:** CSV 러너 (`run_*_cycle_csv.py`). xlsx / `run_monthly_cycle` 은 **복구·레거시**.  
> **원칙:** git/deploy ≠ 월갱신. Facts First — mart 후 **analysis cache 비움** 필수.  
> **지역프로필은 월간에 넣지 않는다** (D-054). 연초 1회만 아래 §7.  
> **상위:** [CH2_MIDCHECK_IMPROVEMENT_PLAN.md](./CH2_MIDCHECK_IMPROVEMENT_PLAN.md) · [MONTHLY_UPDATE_SOP.md](./MONTHLY_UPDATE_SOP.md)

### 사전 점검 (cycle 전 · 코드/문서)

```bash
py scripts/monthly/verify_monthly_checklist_ready.py
```

| 날짜 | 결과 | 비고 |
|------|------|------|
| 2026-08-13 | PASS | CSV 러너 3종 · H2 cache TRUNCATE · windows 3,5,7 · SOP/체크리스트 경로 |

> 위는 **리포 준비도**만 확인한다. 실제 월갱신(수집→promote→3DB as_of)은 아래 표로 완주한다.

---

## 0. 시작 전

| # | 확인 |
|---|------|
| 0.1 | `cycle_id` = `YYYYMM` (예: `202609`) |
| 0.2 | 매핑 `as_of` = cycle 직전 달 1일 (예: `2026-08-01`). 수집 끝 월이 다르면 `--v2-as-of` 수동 |
| 0.3 | 이번 달은 **CSV 경로**로 진행한다 (xlsx `run_monthly_cycle` 쓰지 않음) |
| 0.4 | 「코드만 배포하면 월이 바뀐다」는 **거짓** — Promote 필수 |
| 0.5 | 이번 cycle 종류: **실거래 달** / **대장 달**(분기) / **공부 달**(연 1회). 대장·보강 절차는 [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md). 실거래 러너는 **skip-enrich 기본** — `--enrich` 켜지 말 것 |
| 0.6 | **이 1페이지에 없는 것(의도):** 주거 전월세 원장 월갱신, K-apt 월 파일, 검증로봇 랜덤 샘플. 상권은 분기만 §4. 프로필은 연초만 §7. 칸을 만들기 전까지 월간 완주 범위가 아님 |

---

## 1. 토지 (`land_stats`)

| # | 단계 | 명령·메모 | ✓ |
|---|------|-----------|---|
| 1.1 | MOLIT CSV 수집·검증 | `molit_csv_collector` / 검증 포함 버전. [MOLIT_CSV_COLLECTOR_WARNINGS.md](./MOLIT_CSV_COLLECTOR_WARNINGS.md) | |
| 1.2 | Land CSV cycle | `py scripts/monthly/run_land_cycle_csv.py --cycle-id {cycle}` (windows **3,5,7** · §7.1 group 포함) | |
| 1.3 | **Cache clear** | 러너가 끝에 TRUNCATE 하는지 로그 확인. 없으면 수동 `analysis_cache` + `analysis_base_cache` | |
| 1.4 | Integrity | `verify_monthly_integrity.py --as-of-month {as_of}` | |
| 1.5 | Count compare | before/after 스냅샷 | |
| 1.6 | Dump | `dump_db_for_promote.py` → `.sql.gz` (PG18 호환) | |
| 1.7 | Promote | VPS restore + `STATS_V2_DEFAULT_AS_OF_MONTH` | |
| 1.8 | Smoke | `/health` · UI 「N월 말 기준」 = as_of | |

---

## 2. 복합 (`built_stats`) — land 이후

| # | 단계 | 메모 | ✓ |
|---|------|------|---|
| 2.1 | Built CSV cycle | `run_built_cycle_csv.py --cycle-id {cycle}` · region_codes refresh | |
| 2.2 | 건수·beopjungri gate | SOP 기준 | |
| 2.3 | Dump · Promote | `built_stats` | |
| 2.4 | Smoke | `/api/built` · 회귀 1 scope | |
| 2.5 | enrich | 러너 기본 skip. 로컬 UI 동의(D-051)와 운영 `--enrich`는 별개. 운영 적재는 P5. [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md) §3 | |

---

## 3. 집합 (`collective_stats`) — land 이후

| # | 단계 | 메모 | ✓ |
|---|------|------|---|
| 3.1 | Collective CSV cycle | `run_collective_cycle_csv.py --cycle-id {cycle}` | |
| 3.2 | 분양권 building_key | 분열 단지 스모크 | |
| 3.3 | Dump · Promote | `collective_stats` | |
| 3.4 | Smoke | building/cluster 목록 · 회귀 1건 | |
| 3.5 | enrich | 러너 기본 skip. 신규 키만 `--enrich-new-keys`. 대장 T·공부 공시지가는 수동. [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md) §4 | |
| 3.6 | Regional Profile | **월간에 돌리지 않음** (D-054). 연초 1회만 §7 | |

---

## 4. 임대 상권 (분기 · `rent_stats`) — 부동산원 공표가 나온 달만

부동산원 상업용 임대동향은 **분기** 공표다. 월간 토지/복합/집합 사이클과 별개. 새 분기 xlsx가 있으면 이번 cycle에 포함한다.

| # | 단계 | 명령·메모 | ✓ |
|---|------|-----------|---|
| 4.1 | 원천 파일 | `임대시장/B.상업용/`에 최신 분기 공식 xlsx 추가 (과거 분기 컬럼 포함본) | |
| 4.2 | 적재 | `py pipeline/rent/import_sangkwon.py` — 폴더 **mtime 최신** xlsx 1개 + 상권구획 shp | |
| 4.3 | 확인 | `rent_sangkwon_import_meta.latest_year/quarter` = 이번 공표. 기본표 창 = 직전 4분기 롤링 (예: 2026.2Q → 2025.3Q~2026.2Q). 추세선은 연간 유지 | |
| 4.4 | Promote | `rent_stats` dump → VPS restore. 코드 배포만으로 숫자가 바뀌지 않음 | |
| 4.5 | Smoke | `/rent/` 상권분석 모달 · 광화문 등 1상권 표·추세 | |

공표가 없는 달: 이 절은 건너뛴다.

---

## 5. 3 DB as_of 스모크 (필수)

| DB | latest as_of | UI 문구 | health/API | 비고 |
|----|--------------|---------|------------|------|
| land_stats | | | | |
| built_stats | | | | |
| collective_stats | | | | |

불일치 시: **부분 promote 의심** — 해당 DB만 재promote 또는 롤백.

---

## 6. 이번 cycle 이슈 로그

| 날짜 | 증상 | 원인 | 조치 |
|------|------|------|------|
| | | | |

---

## 7. 연간 지역프로필 (매년 초 1회 · D-054)

토지/복합/집합 **월간 사이클에 넣지 않는다.** 직전 달력 해가 닫힌 뒤(통상 1–2월) 한 번.

| # | 단계 | 메모 | ✓ |
|---|------|------|---|
| 7.1 | 창 | 완결 달력 연도 3년. 예: 2026년 초 → 2023·2024·2025. `as_of` 예: `2026-01-01` | |
| 7.2 | 빌드 | `rebuild_regional_profile_national.py` (프로필 끝이 rank 마트). Twin도 같은 스냅샷 | |
| 7.3 | Promote | `collective_stats` dump → VPS. 코드만 배포해서 프로필 숫자가 바뀌지 않음 | |
| 7.4 | Smoke | `/profile/` 8대 연도표 연도 = 7.1 · 전국 순위 유니버스 · 관악·읍·리 1곳 | |

SSOT [`DECISIONS.md`](./DECISIONS.md) D-054 · [`PROFILE_NATIONAL_RANK_PLAN.md`](./PROFILE_NATIONAL_RANK_PLAN.md) §4.4

---

## 레거시 (쓰지 말 것 · 복구만)

- `run_monthly_cycle.py` (xlsx) — §7.1·purge·cache 경로가 CSV와 다름  
- 검증 없는 Selenium rename  
- `-Fc` dump를 PG16에서 restore (PG18 bin 또는 plain sql.gz)
