# 월간 갱신 파이프라인 (Monthly Update Pipeline)

> 최종 업데이트: 2026-06-24  
> 운영 SOP(절차 상세)는 `docs/MONTHLY_UPDATE_SOP.md` 참조.  
> 이 문서는 **각 단계의 역할·실패 시나리오·체크포인트** 중심.

---

## 1. 전체 단계

```
1. Raw Download    국토부 엑셀 수집
2. Flatten         시도별 xlsx 평탄화
3. Collect         raw → land_transactions_raw
4. Clean           raw → land_transactions (UPSERT)
5. Dedupe          중복 행 제거
6. build_stats_v2  → land_basic_stats_v2
7. build_upper     → land_upper_stats_v2
8. build_annual    → land_annual_stats (선택)
9. build_market    → market_stats (선택, Profile/Twin용)
10. build_twin     → twin_neighbor_v8 (선택)
11. Cache Clear    analysis_cache + analysis_base_cache TRUNCATE
12. Validation     rehearse + verify_monthly_integrity
13. Promote        pg_dump → VPS pg_restore
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

**`as_of_month` 결정 규칙:**
```
STATS_V2_DEFAULT_AS_OF_MONTH 환경변수가 있으면 그 값
없으면 실행일 기준 직전 달 1일
(예: 2026-06-24 실행 → 2026-05-01)
```
> **⚠ 주의:** 환경변수를 잘못 설정하면 엉뚱한 기준월로 집계됨.  
> 갱신 전 반드시 `$env:STATS_V2_DEFAULT_AS_OF_MONTH='2026-MM-01'` 확인.

**소요 시간:** build_stats_v2 약 2시간, build_upper_stats_v2 약 2.5시간 (전국, 로컬 기준)

**실패 시나리오:**
| 시나리오 | 증상 | 대응 |
|---------|------|------|
| 잘못된 as_of_month | 화면에 오래된 기준월 표시 | 환경변수 재설정 후 재실행 (멱등) |
| 특정 시도 OOM | 시도 청크 실패 | `--sido-code 41` 등 개별 재실행 |
| 집계 행 수 급감 | dedupe 후 원장 감소 반영 | 정상 (원장 감소분 반영됨) |

---

### 단계 8~10: 선택적 빌드 (market_stats, twin_v8, annual)

**실행 여부:** 매월 필수 아님. 쌍둥이·Profile 갱신 시에만 실행.

**twin_v8 소요:** 충청권 약 10분, 전국 예상 수 시간

---

### 단계 11: Cache Clear

```powershell
python backend/scripts/clear_analysis_cache.py --with-base-cache
```

**⚠ 필수:** 원장·통계 갱신 후 반드시 실행. 미실행 시 stale 캐시 제공.

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

```powershell
# 로컬
pg_dump -Fc -d land_stats -f backups/land_stats_YYYYMMDD.dump
scp backups/land_stats_YYYYMMDD.dump vps:/home/ubuntu/

# VPS
pg_restore -d land_stats_prod /home/ubuntu/land_stats_YYYYMMDD.dump
sudo systemctl restart ch2macro

# 검증
curl https://api.ch2data.com/health
```

---

## 3. 월간 갱신 체크리스트 (요약)

```
[ ] 1. raw/토지/{cycle_id}/ 에 시도별 xlsx 모두 있는가?
[ ] 2. STATS_V2_DEFAULT_AS_OF_MONTH 환경변수 정확한가?
[ ] 3. pg_dump 백업 완료했는가?
[ ] 4. run_monthly_cycle.py 성공 (exit_code=0)?
[ ] 5. dedupe --dry-run → extra_rows=0?
[ ] 6. land_transactions 건수 이전 월 대비 합리적?
[ ] 7. needs_review 비율 < 1%?
[ ] 8. build_stats_v2 as_of_month 정확한가?
[ ] 9. analysis_cache TRUNCATE 완료?
[ ] 10. rehearse_v2_update.py errors=0?
[ ] 11. /health latest_as_of_month 정확한가?
[ ] 12. UI에서 「YYYY년 M월 말 기준」 정상 표시?
[ ] 13. Promote 후 VPS /health 정상?
```

---

## 4. 복합부동산·집합부동산 갱신

토지와 **별도 cycle**. 각 SOP 참조:
- 복합: `docs/BUILT_MONTHLY_UPDATE_SOP.md`, `scripts/monthly/run_built_monthly_cycle.py`
- 집합: `docs/COLLECTIVE_MONTHLY_UPDATE_SOP.md`, `scripts/monthly/run_collective_monthly_cycle.py`

**공통 주의:** `region_codes`는 land SSOT → built/collective는 land DB에서 복사.
