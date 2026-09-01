# 월간 갱신 파이프라인 — 실패 시나리오 부록

> **운영 SSOT:** [`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md)  
> **러너:** `run_land_cycle_csv.py` / `run_built_cycle_csv.py` / `run_collective_cycle_csv.py` (토지 V2 windows **3,5,7** · group 포함)  
> 상세 절차: [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md). xlsx `run_monthly_cycle` 은 복구.  
> **이 문서의 §1 13단계는 토지 xlsx 레거시 단계명이다. 매월 그 순서로 돌리지 말 것.**  
> 실패 표(오염 CSV, hash, 캐시, needs_review)는 현행 collect/clean에도 유효.  
> 본문 정리: 2026-09-01 (원문 단계표는 2026-06-24).

---

## 0. 현행 CSV 흐름 (매월)

```
1. MOLIT CSV 수집 (molit_csv_collector · 검증 포함)
2. run_land_cycle_csv  — purge → collect/clean/dedupe → V2 3,5,7 category+group → annual → cache TRUNCATE
3. run_built_cycle_csv  — 토지 이후 · skip-enrich 기본
4. run_collective_cycle_csv
5. verify_monthly_integrity · 건수 비교
6. dump → VPS Promote → 3 DB as_of 스모크 (체크리스트 §5)
```

지역프로필·Twin mart는 **월간에 넣지 않는다** (D-054, 연초 §7). git/deploy ≠ 월갱신.

---

## 1. 레거시 xlsx 단계 (참고 · 실패 시나리오는 아래)

```
1. Raw Download    국토부 수집 (현행은 CSV collector)
2. Flatten         시도별 xlsx 평탄화 (CSV 경로에선 생략)
3. Collect         raw → land_transactions_raw
4. Clean           raw → land_transactions (UPSERT)
5. Dedupe          중복 행 제거
6. build_stats_v2  → land_basic_stats_v2   (현행 windows 3,5,7)
7. build_upper     → land_upper_stats_v2
8. build_annual    → land_annual_stats (CSV 러너가 당해 연도)
9. build_market    → market_stats — 월간 아님 (D-054)
10. build_twin     → twin_neighbor — 월간 아님 (D-054)
11. Cache Clear    analysis_cache + analysis_base_cache TRUNCATE
12. Validation     rehearse + verify_monthly_integrity
13. Promote        dump → VPS restore (PG18: sql.gz / promote_restore.sh)
```

---

## 2. 단계별 상세 및 실패 시나리오

### 단계 1: Raw Download

**도구:** 국토부 MOLIT 포털 / `deploy/molit_csv_collector`

**실패 시나리오:**
| 시나리오 | 증상 | 대응 |
|---------|------|------|
| 이전 다운로드 미완료 후 rename | 시도·연도 오염 CSV 생성 | `docs/MOLIT_CSV_COLLECTOR_WARNINGS.md` 참조; 검증 포함 버전 사용 필수 |
| 특정 시도 파일 누락 | 해당 시도 거래 없음 (통계 공백) | 수집 후 시도별 파일 수 확인 |
| 이전 cycle 파일 혼입 | 기존 거래 재적재 (hash 충돌 → UPDATE) | `raw/토지/{cycle_id}/` 폴더 분리 |

---

### 단계 2: Flatten

**도구:** `scripts/monthly/flatten_raw_xlsx.py`

**실패 시나리오:**
| 시나리오 | 증상 | 대응 |
|---------|------|------|
| 하위 폴더 구조 미지원 | 일부 파일 누락 | `--flat-in` 경로 확인 |
| xlsx 파일 손상 | openpyxl 오류 | 원본 재다운로드 |

---

### 단계 3: Collect (`collect.py`)

**역할:** xlsx 파싱 → `land_transactions_raw` INSERT (중복 허용, raw JSONB 저장)

**실패 시나리오:**
| 시나리오 | 증상 | 대응 |
|---------|------|------|
| 국토부 컬럼 구조 변경 | KeyError / 파싱 오류 | `clean.py`의 컬럼 매핑 수정 필요 |
| 메모리 초과 (대용량) | OOM Kill | 청크 크기 조정 (`CLEAN_UPSERT_PAGE_SIZE`) |

---

### 단계 4: Clean (`clean.py`)

**역할:** raw 정제 → `land_transactions` UPSERT  
**가장 중요한 단계** — 주소 매핑·hash·정규화 모두 여기서 결정

**실패 시나리오:**
| 시나리오 | 증상 | 대응 |
|---------|------|------|
| 잘못된 지역코드 (`needs_review=true`) | `region_codes` 미매핑 | `beopjungri_mapping_report.py` 실행 후 수동 검토 |
| 동명이리 오매핑 | 법정동별 통계 왜곡 | D-012 disambiguation 로직 확인 |
| hash 공식 불일치 | 동일 거래 2중 INSERT | dedupe 후 rehash 필수 |
| `is_cancelled` 오판 | 해제 거래 포함 | 원본 엑셀 해제구분 컬럼 확인 |

**검증 지표:** `needs_review` 비율 < 0.3% (충북 기준)

---

### 단계 5: Dedupe (`dedupe_land_transactions.py`)

**역할:** business key 기준 중복 행 삭제

**실패 시나리오:**
| 시나리오 | 증상 | 대응 |
|---------|------|------|
| 대용량 DELETE 락 | 다른 쿼리 차단 | 배치 DELETE 사용 (`--batch-size 25000`) |
| rehash 중 추가 삭제 | 원장 건수 예상보다 감소 | 로그의 "changed" 수 확인 — 정상 |
| work table 잔류 | `_land_tx_dup_ids_work` 미삭제 | `DROP TABLE IF EXISTS _land_tx_dup_ids_work` 수동 실행 |

**검증:** `dry-run` → `extra_rows=0` 확인

---

### 단계 6~7: build_stats_v2 / build_upper_stats_v2

**역할:** 원장 → 사전집계 (시도 단위 청크, `ON CONFLICT DO UPDATE`)

**`as_of_month` 결정 규칙:** CSV 러너는 `cycle_utils.stats_as_of_iso_from_cycle_id` (cycle 직전 달 1일). 수집 끝 월이 다르면 `--v2-as-of`.  
환경변수 `STATS_V2_DEFAULT_AS_OF_MONTH` 는 **Promote 후 백엔드** 기본값이다. 빌드 as_of와 어긋나면 화면 월이 틀린다.

**windows:** **3,5,7** (체크리스트·CSV 러너). 3,5만 돌리면 7년 표가 비거나 이전 as_of가 남는다.

**소요 시간:** build_stats_v2 약 2시간, build_upper_stats_v2 약 2.5시간 (전국, 로컬 기준). group 축은 추가.

**실패 시나리오:**
| 시나리오 | 증상 | 대응 |
|---------|------|------|
| 잘못된 as_of_month | 화면에 오래된 기준월 표시 | 환경변수 재설정 후 재실행 (멱등) |
| 특정 시도 OOM | 시도 청크 실패 | `--sido-code 41` 등 개별 재실행 |
| 집계 행 수 급감 | dedupe 후 원장 감소 반영 | 정상 (원장 감소분 반영됨) |

---

### 단계 8~10: annual · market_stats · twin

- **annual:** CSV 토지 러너가 **당해 달력 연도** both(+upper)를 돌린다. 전 기간 `--full` 재빌드 금지.
- **market_stats / Profile Twin:** **월간 아님** (D-054). 연초 체크리스트 §7.

---

### 단계 11: Cache Clear

CSV `run_land_cycle_csv.py` 가 끝에 TRUNCATE. `--skip-cache-clear` 비권장. 수동:

```powershell
python backend/scripts/clear_analysis_cache.py --with-base-cache
```

**필수:** 미실행 시 stale 캐시.

---

### 단계 12: Validation

**도구:**
- `pipeline/rehearse_v2_update.py` — 환경 점검 (읽기 전용)
- `pipeline/verify_monthly_integrity.py` — L1/L2 데이터 정합성 게이트

**핵심 체크:**
- `extra_rows=0` (중복 없음)
- `biha_borok_dap_valid=2` (회귀 샘플 비하동 보녹·답 2건)
- `land_transactions=9,XXX,XXX` (이전 월 대비 증감 확인)
- `as_of_month=2026-MM-01` (기준월 정상)

---

### 단계 13: Promote

Windows PG18 `-Fc` → VPS PG16 `pg_restore` 는 실패할 수 있다. **plain `sql.gz`** + `deploy/scripts/promote_restore.sh` (SOP §9.4).

```powershell
py scripts/monthly/dump_land_for_promote.py
# VPS restore 후
curl -sf https://macro.ch2data.com/api/  # 또는 VPS: curl http://127.0.0.1:8000/health
```

`STATS_V2_DEFAULT_AS_OF_MONTH` 를 이번 as_of 로 맞춘 뒤 백엔드 재기동.

---

## 3. 운영 체크리스트

복붙용 1페이지: [`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md). 요약:

```
[ ] cycle_id YYYYMM · as_of = 직전 달 1일 (또는 --v2-as-of)
[ ] CSV 수집 (검증 포함 collector)
[ ] run_land_cycle_csv.py 성공 · cache TRUNCATE 로그
[ ] run_built_cycle_csv.py · run_collective_cycle_csv.py
[ ] verify_monthly_integrity · 건수 비교
[ ] dump → VPS Promote · 3 DB as_of · UI 「N월 말 기준」
```

xlsx `run_monthly_cycle` 로 돌리지 말 것.

---

## 4. 복합·집합

토지 **이후**. CSV SSOT:

- 복합: [`BUILT_MONTHLY_UPDATE_SOP.md`](./BUILT_MONTHLY_UPDATE_SOP.md) · `run_built_cycle_csv.py`
- 집합: [`COLLECTIVE_MONTHLY_UPDATE_SOP.md`](./COLLECTIVE_MONTHLY_UPDATE_SOP.md) · `run_collective_cycle_csv.py`

`region_codes` 는 land 정본 → built/collective 가 복사. xlsx `run_*_monthly_cycle.py` 는 복구.
