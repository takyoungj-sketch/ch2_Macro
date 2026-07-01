# 2026-07 행정개편 대응 (인천·전남광주)

> **상태:** `feature/admin-reform-202607` 브랜치 작업 중  
> **시행:** 2026-07-01 (MOLIT 수집기·법정동 마스터 반영)  
> **범위:** 토지(`land_stats`) `region_codes` + raw + 원장 + V2 사전통계

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
| `raw/토지(인천,전남광주)_201001_202605/` | staging (2010~2026.05) |

---

## 3. 실행 절차

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

---

## 4. 코드 변경 위치

| 파일 | 변경 |
|------|------|
| `pipeline/seed_region_codes.py` | `전남광주통합특별시: 12`, `--mark-abolished-inactive`, `--retire-sido` |
| `pipeline/clean.py` | 시도 별칭(광주·전남→통합), 인천 구 fallback |
| `pipeline/admin_reform_202607.py` | 오케스트레이션 |
| `pipeline/region_scope.py` · `sido_adjacency.py` | 호남권·인접 시도 12 반영 |
| `deploy/molit_csv_collector/` | 수집 시도 목록 (이미 반영) |

---

## 5. Promote 전 체크리스트

- [ ] `verify_beopjungri_mapping.py` — 인천·전남광주 매칭률 ≥ 99.7%
- [ ] `land_annual_stats` · `land_annual_upper_stats` — 12·28 연도별 spot check
- [ ] `land_basic_stats_v2` · `land_upper_stats_v2` — 12·28 샘플 spot check
- [ ] built/collective `region_codes` sync (land → 복제) — 별도 단계
- [ ] VPS 배포는 사용자 요청 시 (`deploy-from-windows.ps1`)

---

## 6. 비범위

- `scripts/monthly/` 시도 목록 — 월간 운영 시 별도 갱신
- 전국 `land_annual_stats` 일괄 재빌드 — 영향 시도(12·28)만 `reform_annual_long_term.py`
- `pipeline/_land_annual.sql` — 커밋 금지 (대용량 덤프)
