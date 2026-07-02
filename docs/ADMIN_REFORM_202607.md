# 2026-07 행정개편 대응 (인천·전남광주)

> **상태:** `feature/admin-reform-202607` 브랜치 작업 중  
> **시행:** 2026-07-01 (MOLIT 수집기·법정동 마스터 반영)  
> **범위:** 토지(`land_stats`) + 복합(`built_stats`) + 집합(`collective_stats`) 행정개편 반영

---

## 1. 변경 요약

| 지역 | 변경 | 시도 코드 | 조치 |
|------|------|-----------|------|
| 전남광주 통합 | 광주·전남 → **전남광주통합특별시** | **12** (신), 29·46 (폐지) | 통합 CSV로 raw 교체, 29·46 `region_codes` 비활성 |
| 인천 | 구·군 명칭·경계 조정 (미추홀·제물포·검단·영종 등) | **28** (동일) | 신규 MOLIT CSV로 raw 교체, `clean.py` 구 별칭 fallback |

**raw 검증 결과** ( `_compare_land_csv_regions.py` ):

- 전남광주: 신규 통합 파일 행 수 ≈ 구 광주+전남 합, 주소 접두만 변경 → **통합 파일로 교체**
- 인천: 시도명 동일, 구 표기 소급 변경 → **신규 CSV + region_codes(260701)로 재적재** (구→신 단순 rename 불가)

---

## 2. 선행 파일

| 파일 | 용도 |
|------|------|
| `data/region_codes/법정동코드 전체자료(260701).txt` | `seed_region_codes.py` 입력 |
| `raw/토지(인천,전남광주)_201001_202605/` | 토지 staging (2010~2026.05) |
| `raw/인천 행정구역 개편후(201001_202605)/` | 복합·집합 인천 staging (7유형 × 17년) |
| `raw/전남광주 행정구역 개편후(201001_202605)/` | 복합·집합 전남광주 staging |

---

## 3. 토지 실행 절차

```powershell
cd c:\ch2\ch2_Macro\pipeline

# 1) 검증 (선택)
py _compare_land_csv_regions.py

# 2) 전체 오케스트레이션 (dry-run)
py admin_reform_202607.py --dry-run --step all

# 3) 실제 반영 (로컬 DB — DATABASE_URL 확인)
py admin_reform_202607.py --step all --as-of 2025-12-01
```

단계별:

| step | 내용 |
|------|------|
| `seed` | `region_codes` UPSERT(12·28) + 폐지 비활성 + 29·46 retire |
| `sync-raw` | staging → `raw base` / `raw long term`, 구 광주·전남 CSV 삭제 |
| `purge` | `land_transactions`·연결 `raw` (sido 12·28·29·46) |
| `ingest` | `collect.py` + `clean.py` |
| `stats` | `build_stats_v2` · `build_upper_stats_v2` (sido 12·28) |
| `annual` | `land_annual_stats` · `land_annual_upper_stats` (sido 12·28, 2010~2026) |

전국 `region_codes` 갱신이 필요하면:

```powershell
py admin_reform_202607.py --step seed --national-seed
```

### 3.1 복합 (`built_stats`)

```powershell
cd c:\ch2\ch2_Macro\pipeline
py admin_reform_built_202607.py --step all --as-of 2025-12-01
```

| step | 내용 |
|------|------|
| `purge` | `built_transactions` sido 12·28·29·46 삭제 |
| `sync-region` | `land_stats.region_codes` → `built_stats` 복제 |
| `ingest` | 상가·공장·단독 staging CSV (유형별 34개) |
| `stats` | `build_scope_stats.py` (3·5년 창) |

로컬 검증 (2026-07-02): sido **12** 188,929건 · **28** 59,655건, 29·46=0, 매핑 100%.

### 3.2 집합 (`collective_stats`)

```powershell
cd c:\ch2\ch2_Macro\pipeline
py admin_reform_collective_202607.py --step all --as-of 2025-12-01
```

| step | 내용 |
|------|------|
| `purge` | `collective_transactions`·`collective_commercial_transactions`·`commercial_clusters` (sido 12·28·29·46) |
| `ingest` | 주거 4유형 + 집합상가·공장 staging CSV 204개 |
| `marts` | `build_region_sigungu_meta` · building/market/cluster stats |
| `long-term` | `reform_collective_annual_long_term.py` — annual mart purge(12·28·29·46) + 12·28 재빌드 |

**주의:** mart `as_of` 기본값은 `default_as_of_month()` (서비스 직전 월말). 개편 후 `2026-05-01` mart 재빌드 필요.

**버그 수정:** `collective/refine.py` — MOLIT CSV 20열 연립다세대 ingest 시 `_source_key`가 `housing_subtype` iloc에 섞이던 문제 수정.

로컬 검증 (2026-07-02): residential purge·재적재 ~142만건(영향 시도), `verify_beopjungri_mapping` gate **PASS** (전체 99.94%, collective 99.83%).

---

## 4. 코드 변경 위치

| 파일 | 변경 |
|------|------|
| `pipeline/seed_region_codes.py` | `전남광주통합특별시: 12`, `--mark-abolished-inactive`, `--retire-sido` |
| `pipeline/clean.py` | 시도 별칭(광주·전남→통합), 인천 구 fallback |
| `pipeline/admin_reform_202607.py` | 토지 오케스트레이션 |
| `pipeline/reform_paths_202607.py` | staging 루트·CSV 목록 (복합·집합 공통) |
| `pipeline/admin_reform_built_202607.py` | 복합 오케스트레이션 |
| `pipeline/admin_reform_collective_202607.py` | 집합 오케스트레이션 |
| `pipeline/built/import_molit.py` | `--paths-file` · `--purge-sido` |
| `pipeline/collective/import_refined.py` | staging CSV 직접 ingest |
| `pipeline/collective_commercial/import_refined.py` | 집합 비주거 ingest |
| `pipeline/reform_collective_annual_long_term.py` | 집합 장기추세 annual purge·재빌드 |
| `backend/app/collective/router.py` | mart 빈 지역 live fallback |
| `pipeline/region_scope.py` · `sido_adjacency.py` | 호남권·인접 시도 12 반영 |
| `deploy/molit_csv_collector/` | 수집 시도 목록 (이미 반영) |

---

## 5. Promote 전 체크리스트

- [x] `verify_beopjungri_mapping.py` — gate PASS (전체 99.94%)
- [ ] `land_annual_stats` · `land_annual_upper_stats` — 12·28 연도별 spot check
- [ ] `land_basic_stats_v2` · `land_upper_stats_v2` — 12·28 샘플 spot check
- [x] built — sido 12·28 원장·scope_stats 재빌드
- [x] collective — 원장·mart(`2026-05-01`)·장기추세 annual 재빌드
- [ ] collective UI spot check (인천·전남광주 시군구)
- [ ] VPS 배포는 사용자 요청 시 (`deploy-from-windows.ps1`)

---

## 6. 비범위

- `scripts/monthly/` 시도 목록 — 월간 운영 시 별도 갱신
- 전국 `land_annual_stats` 일괄 재빌드 — 영향 시도(12·28)만 `reform_annual_long_term.py`
- `pipeline/_land_annual.sql` — 커밋 금지 (대용량 덤프)
