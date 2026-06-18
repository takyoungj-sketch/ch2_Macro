# 집합부동산 — 인수·기술 메모

> **고도화·Profile·mart 설계:** [`REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) (D-016)

## 아키텍처

```
collective_stats
  collective_transactions  (거래 원장, building_key)
land_stats.region_codes  → sync → collective_stats.region_codes
/api/collective/*  →  frontend-collective (/collective/)
```

## 통일 정제 (canonical)

| 필드 | 설명 |
|------|------|
| building_name | 단지명(아파트·오피스텔) 또는 건물명(연립) |
| exclusive_area, price, unit_price | 전용면적, 만원, 만원/㎡ |
| land_area | 대지권면적(㎡) — **연립·다세대만** |
| floor, dong | 층·동 (아파트 dong은 raw col10) |
| area_bucket, age_bucket | round(면적/30)*30, round(연식/10)*10 |

## building_key / display_name

구현: [`pipeline/collective/building_keys.py`](../pipeline/collective/building_keys.py)

## 통계

토지와 동일 95% t-CI: [`backend/app/stats_utils.py`](../backend/app/stats_utils.py), `MIN_RELIABLE_COUNT=15`

### 고급 분석 게이트 (방안 1)

선택 연도 구간 기준 — [`analysis_gates.py`](../backend/app/collective/analysis_gates.py)

| 기능 | 조건 |
|------|------|
| 건물表 CI | n≥15 |
| **층·동 효용지수** | n≥50 |
| **회귀** | n≥30 **且** 최근 3년 n≥15 |

- API: `GET /buildings/{key}/floor-index` (403 if gated)
- 회귀: `POST .../regression/run` (403 if gated) · 층 `floor_mode=relative`(기본): max층 대비 1·최상·저·중·고 더미
- `/buildings` 응답 `analysis` 필드로 UI 버튼 disabled

### 층·동 효용지수 (Track 1)

단지 중앙값 ㎡당가 = 100. 셀 n&lt;15 경고. 인근 단지 fallback(방안 2)은 미구현.

## 월간

[`COLLECTIVE_MONTHLY_UPDATE_SOP.md`](COLLECTIVE_MONTHLY_UPDATE_SOP.md) · `run_collective_monthly_cycle.py`

## 적재 정책 (2026-06)

집합부동산은 **토지와 다르게** semantic hash dedupe 하지 않는다.

- **해제 거래만** `refine` 단계에서 제외
- 그 외 원본 행은 **전량 INSERT** (`transaction_hash` = `asset_type|파일명|순번`, UNIQUE 아님)
- 마이그레이션: [`db/017_collective_tx_row_identity.sql`](../db/017_collective_tx_row_identity.sql)

| 유형 | 상태 |
|------|------|
| 오피스텔 | `원본/오피스텔/*.csv` — 신규 정책 적용 완료 (209,082건) |
| 아파트 | `원본/아파트/*.xlsx` — **재적재 완료 (2026-06-04, 2,288,749건)** |
| 연립 | `원본/연립다세대/*.csv` — **적재 완료 (2026-06-05, 552,849건, land_area 포함)** |

### 연립·다세대 적재 (완료)

1. CSV 수집: `download_molit_rowhouse_csv.py` — 85파일 (2021–2025 전국)
2. 적재: `import_refined.py --rowhouse-only` — **552,849건**
3. `land_area`(대지권면적) 전 건 non-null · `housing_subtype`은 MOLIT CSV에 컬럼 없음(NULL)
4. 로그: `pipeline/collective/rowhouse_download.log`, `rowhouse_import.log`

### 아파트 재적재 (완료)

- **이전:** semantic hash + `ON CONFLICT DO NOTHING` → **2,118,163건**
- **이후:** `asset_type\|파일명\|순번` 행 식별 + 전량 INSERT → **2,288,749건** (+170,586)
- **명령:** `py pipeline/collective/import_refined.py --apartment-only`
- **로그:** `pipeline/collective/apartment_reimport.log`

## 202607 업데이트

1. 토지 `run_monthly_cycle.py --cycle-id 202607` → Promote
2. GUKTO 정제 xlsx 갱신
3. `run_collective_monthly_cycle.py --cycle-id 202607 --require-land-cycle`
4. snapshot/compare → VPS Promote (built와 독립)

## VPS 배포 체크리스트 (2026-06 집합 UI·API 변경)

로컬 검증 후 [`deploy/AGENT_DEPLOY_RUNBOOK.md`](../deploy/AGENT_DEPLOY_RUNBOOK.md) — `-Scope collective`.

| # | 작업 | 명령·메모 |
|---|------|-----------|
| 1 | DB 마이그레이션 | `psql -U postgres -d collective_stats -f db/028_collective_building_stats_addr5.sql` |
| 2 | mart 재집계 (권장) | `cd pipeline/collective` → `python build_collective_building_stats.py` (addr5·지번/도로명 2열) |
| 3 | 백엔드 반영 | `backend/app/collective/` — 주소 분리, 통합 정렬, 효용지수 회귀, 코호트 추세 API |
| 4 | 프론트 빌드 | `frontend-collective` — 전체 목록 fetch, 지번/도로명 열, 코호트·효용지수 UI |
| 5 | systemd 재시작 | VPS `ch2-macro-backend` restart |
| 6 | 스모크 | `/collective/` 목록·정렬·건물 모달(코호트·효용지수·회귀) |

**참고:** 연도 필터를 켠 live 경로는 mart 없이도 `addr5`를 원장에서 조회 가능. mart-only 조회 DB는 **028 + 재집계** 없으면 리(里)가 빠질 수 있음.
