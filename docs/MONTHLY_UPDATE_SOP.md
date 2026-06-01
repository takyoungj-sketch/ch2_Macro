# 월간 전국 토지 데이터 업데이트 SOP

> **목표:** 매월 초 **전국 토지** 원장·정제·V2 사전통계를 **재현 가능한 절차**로 갱신하고, 검증·승인 후 외부에 반영한다.  
> **전제:** 완전 무인·증분 갱신 최적화는 후순위. 우선 **단순성·재현성·검증·롤백**을 만족한다.  
> **기준 루트:** `C:\ch2\ch2_Macro` (다른 PC면 `--repo-root` 로 동일 구조를 맞춘다.)

---

## 1. 용어

| 용어 | 설명 |
|------|------|
| **cycle_id** | 월간 작업 번들 ID. **`YYYYMM`** (예: `202605` = 2026년 5월에 수행하는 이번 배치). |
| **수집 연월 범위** | 합의 예: `202605` 배치 시 **계약연월 `202505`~`202604`**(직전 12개월). 파일·국토부 UI 기준으로 조정 가능. |
| **`as_of_month` (V2)** | `build_stats_v2.py --as-of YYYY-MM-01` — 해당 **달 말일까지**가 통계 기간 끝으로 해석된다 (`build_stats_v2` 주석·`V2_STATS_DESIGN` 참고). |
| **기본 `--as-of` 매핑** | *수집 끝 연월이 `cycle`의 **직전 달**과 같다*고 가정할 때: `cycle_id=202605` → 마지막 월 `202604` → **`--as-of 2026-04-01`**. 자동화: `scripts/monthly/cycle_utils.stats_as_of_iso_from_cycle_id`. **실제 수집 끝 월이 다르면 `--v2-as-of`로 수동 지정.** |

---

## 2. 디렉터리 구조 (권장)

저장소 루트 기준:

```
C:\ch2\ch2_Macro\
  raw\토지\{cycle_id}\          # 시·도별 xlsx (하위 폴더 허용 — 평탄화 단계에서 처리)
  clean_snapshots\{cycle_id}\   # manifest, flat_in, land_tx_counts_after.json 등
  stats_snapshots\{cycle_id}\    # V2 요약 JSON (스크립트가 기록)
  logs\                          # 월간 실행 로그(선택)
  backups\                       # pg_dump 등
  scripts\monthly\               # 본 SOP 자동화 스크립트
  pipeline\                       # 기존 수집·정제·통계 파이프라인
  docs\                          # 본 문서
```

### 2.1 raw 예시

```
raw\토지\202605\
  서울.xlsx
  경기.xlsx
  충북.xlsx
  ...
```

- **ZIP/원본 다운로드 보존:** 디스크 여유가 있으면 `raw\토지\202605\_downloads\` 등에 두고 목록만 `raw_manifest.json`에 메모 가능. 레포에는 커밋하지 않음(`.gitignore`).

---

## 3. 로컬 DB vs staging/current (원칙)

본 레포 기본 패턴은 **`land_stats` 단일 PostgreSQL**에 적재하고, 버전 관리를 **통계 테이블의 `(as_of_month, window_years)`** 로 한다.

| 방식 | 설명 |
|------|------|
| **현실적 운영(권장, 단순)** | 로컬·서버 각각 같은 스키마. 갱신 전 **`pg_dump` 백업**으로 논리적 rollback. 통계 행은 `as_of_month`별로 공존. |
| **이중 DB (staging / prod)** | 로컬 `land_stats_staging` 으로 먼저 돌린 뒤 dump → prod 로칭복원. 초기에는 운영 부담만 커져 **후순위**. |

본 SOP 초안은 **단일 DB + 백업**을 표준으로 둔다.

---

## 4. 실행 흐름 (반자동)

1. 운영자: 국토부 등에서 **직전 12개월** 엑셀을 받아 `raw\토지\{cycle_id}\` 에 둔다 (하위 폴더 가능).
2. **Cursor / 운영자:** `CycleId`(예:`202605`) 지시 후 아래 명령 실행.
3. 스크립트: **평탄화 → `run_pipeline`(excel + V2, `--v2-as-of`) → 검증용 스냅샷 JSON**.
4. 운영자: **검증 체크리스트** 및 샘플 육안.
5. **OK** 후 **Promote** (§7) 로 외부 반영.

---

## 5. 수집 단계 (`raw`)

- **실거래가 엑셀(토지 매매)** 는 국토교통부 페이지에서 브라우저로 받는 형태(**Selenium**)가 보통 안정적이다. 참고 레시피: `참고/0.수집.ipynb` 와 같은 흐름을 스크립트로 옮긴 것이 **`scripts/monthly/download_molit_land_xlsx.py`** 이다.  
  의존성: `py -m pip install "selenium>=4.15"` (Chrome 설치 필요, Selenium 4 가 드라이버를 관리한다).  
  예(2026년 5월 초 배치 가정 · **계약일 2025-05-01 ~ 2026-04-30** 전국):  
  `py scripts/monthly/download_molit_land_xlsx.py --cycle-id 202605`  
  검증만 할 때 한두 시도: `--limit-regions 1` 또는 `--regions "세종특별자치시"`  
  **시도당 `--start-date`~`--end-date` 구간을 한 번에 요청**(국토부 UI가 허용하는 범위에서 달력연도 분할 없음); 파일명에 구간 태그가 붙는다(`…_토지_매매_20250501_20260430.xlsx`).  
- **통합 · 정제(노트북 규격, 템플릿용)** 는 `docs/LAND_NOTEBOOK_EXCEL_PREP.md` 와  
  `py scripts/monthly/run_land_notebook_excel_prep.py --cycle-id …` 참고 (**DB 적재와 별도 디렉터리** 출력).
- **성공/실패 기록:** `clean_snapshots\{cycle_id}\raw_manifest.json` — `scripts/monthly/run_monthly_cycle.py` 가 `.xlsx` 목록과 개수 기록.

---

## 6. 통합·정제·DB 업데이트

### 6.1 하위폴더 탐색

- `pipeline/collect.py` 의 `--directory` 는 **직접 자식만** 스캔한다 (`resolve_excel_paths` → `root.iterdir()`).
- 따라서 깊게 두었으면 **`scripts/monthly/flatten_raw_xlsx.py`** 로 `clean_snapshots\{cycle_id}\flat_in\` 에 평탄화 후 파이프라인에 넘긴다.  
  **원스톱:** `run_monthly_cycle.py` 가 평탄화까지 수행한다( `--skip-flatten` 으로 생략 가능).

### 6.2 파이프라인

엑셀 기준 표준 실행(로컬, `pipeline` 디렉터리가 `DATABASE_URL` 을 읽음):

```powershell
cd C:\ch2\ch2_Macro
py scripts\monthly\run_monthly_cycle.py --cycle-id 202605
```

동작 요약:

1. `clean_snapshots\{cycle_id}\raw_manifest.json` 작성  
2. `flatten_raw_xlsx` → `clean_snapshots\{cycle_id}\flat_in\`  
3. `run_pipeline.py --excel-dir …\flat_in --excel-format auto --with-v2 --v2-windows 3,5 --v2-as-of <매핑>` **및 기본으로** `--with-upper-v2`(상위 행정 사전집계). 생략하려면 `run_monthly_cycle.py --skip-upper-v2`.  
4. `clean_snapshots\{cycle_id}\land_tx_counts_after.json` — 시도별 `land_transactions` 건수  
5. `stats_snapshots\{cycle_id}\land_basic_stats_v2_summary.json` — 해당 `as_of` V2 행수 요약  

> **통합 엑셀(`전국통합.xlsx`)** 은 선택. 필요 시 별도 수작업·추후 `COPY`/pandas export 스크립트 추가. 현재 스냅샷은 **JSON 요약 중심**.

### 6.3 `run_pipeline.py` 수정 사항

- **`--v2-as-of YYYY-MM-DD`** 를 지정하면 `build_stats_v2` 에 그대로 전달된다(환경 변수보다 우선).

---

## 7. 사전통계 생성 (V2)

- `--with-v2` 로 `build_stats_v2.py` 실행. **`--as-of` 는 반드시 이번 데이터에 맞게 고정**(CLI 또는 `--v2-as-of`).
- **상위 행정(시도·시군구·읍면동·city 버킷)** 은 `run_monthly_cycle.py` 가 **기본으로** `run_pipeline.py --with-upper-v2` 를 넣어 `build_upper_stats_v2.py` 까지 실행한다. **끄려면** `--skip-upper-v2`.
- 수동만 필요할 때: `python pipeline/build_upper_stats_v2.py --as-of … --windows 3,5` (전국; 시도 한정은 `--sido-code`).

---

## 8. 검증 (로컬, 최소)

### 8.1 자동/반자동

```powershell
cd C:\ch2\ch2_Macro\pipeline
py rehearse_v2_update.py --health-url http://127.0.0.1:8000/health
```

```powershell
py verify_monthly_integrity.py --as-of-month 2026-05-01
```

(`--as-of-month` 생략 시 `STATS_V2_DEFAULT_AS_OF_MONTH` 또는 DB `MAX(as_of_month)` 사용.  
`--base-url http://127.0.0.1:8000` 추가 시 API `total.count` ↔ DB 대조.  
배치 직후 golden count 갱신: `--update-golden`)

```powershell
py verify_v2_national_samples.py --base-url http://127.0.0.1:8000 --as-of-month 2026-04-01
```

(`--as-of-month` 는 **이번에 선택한 `--v2-as-of` 와 같은 달의 1일**)

- **전월 대비 거래량 휴리스틱:** 이전 배치에서 저장해 둔 `land_tx_counts_after.json` 을 복사해 두었다면  

  ```powershell
  py scripts\monthly\compare_count_snapshots.py --before clean_snapshots\202604\land_tx_counts_after.json --after clean_snapshots\202605\land_tx_counts_after.json
  ```

### 8.2 수동 체크리스트 (최소)

- [ ] **`verify_monthly_integrity.py`** exit 0 (Promote 게이트)  
- [ ] **거래량 급변** 시도 없음 (`compare_*` 또는 `--count-before`/`--after`)  
- [ ] **`raw_manifest`** 의 기대 행정구역 파일 수와 실제 제공 범위 일치  
- [ ] **평균 단가 급변** 이슈 — 대표 동 2~3곳 재조회 (프론트·API)  
- [ ] **`/health.latest_as_of_month`** 의 정책과 `--v2-as-of` 의도 일치 확인  
- [ ] **`land_transactions` 행폭증·급감** — 직전 월 배치 요약 파일과 비교  

---

## 9. 승인 (Promote) 및 외부 서버 반영

### 9.1 반영 전 **필수: 백업**

```powershell
$env:PGPASSWORD="…"
pg_dump -h 호스트 -U 유저 -d land_stats -Fc -f C:\ch2\ch2_Macro\backups\land_stats_pre_promote_202605.dump
```

### 9.2 승격 방식 (택 1을 팀 규약으로 고정)

| 선택 | 절차 | 비고 |
|------|------|------|
| **안 A** | 검증된 DB dump를 서버로 restore | 프로덕션이 검증 상태와 바이트 동일하게 맞춰짐. 전송·복원 시간 큼. |
| **안 B** | 서버에 동일 월 원본 폴더·동일 명령(`run_monthly_cycle` 상당) 재실행 | 원본 파일 전송 필요. 재현성 좋음, 서버·로컬 환경 차이 시 편차 가능. |

**초기 권장:** 팀에 DB 운영 경험이 있으면 **A**, 동일 스크립트를 서버에도 두고 싶으면 **B**. **한 팀은 한 가지로 고정**해 Playbook을 줄인다.

### 9.3 앱

- 백엔드 **재시작** 후 `STATS_V2_DEFAULT_AS_OF_MONTH` 등 `.env` 가 이번 `as_of` 와 합치는지 확인.  
- 프론트: `VITE_STATS_V2_ASSUMED_TODAY` 등 빌드형 변수 쓰는 경우 rebuild.  
- 상세: `docs/V2_OPERATOR_CHECKLIST.md` §B8~B9.

---

## 10. 백업 및 롤백

- **백업:** Promote 직전 `pg_dump` (`backups\`).  
- **롤백:** 문제 발견 시 Promote 이전 dump 로 DB 복원 후 백엔드 재기동.  
- **부분 롤백:** `land_basic_stats_v2` 특정 `as_of_month` 행만 삭제 등은 설계·FK에 따라 위험 — **가능하면 전체 restore** 우선.

---

## 11. 빠른 참조 — 명령 모음

| 목적 | 명령 |
|------|------|
| 월간 로컬 한 번에 | `py scripts\monthly\run_monthly_cycle.py --cycle-id 202605` |
| 상위통계 생략(드물게) | `… run_monthly_cycle.py --cycle-id 202605 --skip-upper-v2` |
| 수집 목록만 | `py scripts\monthly\run_monthly_cycle.py --cycle-id 202605 --manifest-only` |
| 평탄화만 | `py scripts\monthly\flatten_raw_xlsx.py --source raw\토지\202605 --dest clean_snapshots\202605\flat_in` |
| 시도 건수 스냅샷 | `py scripts\monthly\snapshot_land_tx_counts.py --output clean_snapshots\202605\land_tx_counts_after.json` |
| 스냅샷 비교 | `py scripts\monthly\compare_count_snapshots.py --before … --after …` |
| **Promote 게이트** | `py pipeline\verify_monthly_integrity.py --as-of YYYY-MM-01` |

PowerShell 래퍼: `scripts\monthly\run_monthly_cycle.ps1 -CycleId 202605` (상위 생략: `-SkipUpperV2`)

---

## 12. 관련 문서

- `docs/V2_OPERATOR_CHECKLIST.md` — 월초 갱신 단일 SOP(전국·검증·백엔드)  
- `docs/V2_STATS_PRODUCTION.md` — `build_stats_v2` 운영  
- `docs/DECISIONS.md` — D-007 `API_TOKEN`, D-003 캐시 무효화 등  
- `NEXT_STEPS.md` — 백로그(알림·백업 자동화 등)

---

## 13. 개정 이력

| 날짜 | 내용 |
|------|------|
| 2026-05-24 | `run_monthly_cycle` 기본에 `build_upper_stats_v2`(상위통계) 포함, `--skip-upper-v2` 로 생략 |
