# 월간 전국 토지 데이터 업데이트 SOP

> **목표:** 매월 초 **전국 토지** 원장·정제·V2 사전통계를 **재현 가능한 절차**로 갱신하고, 검증·승인 후 외부에 반영한다.  
> **전제:** 완전 무인·증분 갱신 최적화는 후순위. 우선 **단순성·재현성·검증·롤백**을 만족한다.  
> **기준 루트:** 저장소 루트 (`--repo-root`). 예: `C:\ch2\ch2_Macro` · `E:\ch2\ch2_Macro`.
>
> **운영 SSOT:** 1페이지 [`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md).  
> **매월 러너:** `scripts/monthly/run_land_cycle_csv.py` — V2 windows **3,5,7** · §7.1 group · cache TRUNCATE 포함.  
> 신규 해시 대장 연결과 축약대장 달력: [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md).

### 월간 신규 대장 공급

1. 실행 순서는 토지 → 복합 → 집합이다. 각 러너는 재적재 전의 키를 해당 작업월의 기준 파일에 저장하고, 원장·마트 작업 뒤에 새로 생긴 해시 또는 주거 집합 건물 키만 계산한다.
2. 토지는 `LAND_CODE_HISTORY_LAYER_V2+LAND_LINK_RULE_V1`(광주·전남처럼 대장이 아직 옛 시도코드인 동안 1:1 옛 코드로 찾음), 복합은 ENGINE_V2, 주거 집합은 동결 slim 대표필지 가격을 사용한다. 기존 공급 행을 덮지 않는다. 재적재로 없어진 해시는 공급표에 보존하고 고아로 표시한다.
   - 토지 V2에는 대응표 `C:\CH2\parcel_master\honam_code_bridge_v1.sqlite`가 **필수**다(대장 SQLite `land_trait_observations.sqlite`와 같은 폴더). 없으면 공급은 계속되지만 경고를 남기고 광주·전남 2026-07 이후 거래가 모두 미연결로 들어간다. 계획·되돌리기: [`lab/LAND_LINK_V2_ROLLOUT_PLAN_20261110.md`](lab/LAND_LINK_V2_ROLLOUT_PLAN_20261110.md).
3. 공급 단계가 실패하면 공급 트랜잭션을 롤백하고 경고를 남긴다. 일반 월간 작업은 계속된다. 명시적으로 공급을 건너뛰려면 러너에 `--skip-enrich`를 붙인다.
4. 결과는 `clean_snapshots/YYYYMM/ledger_supply/*_coverage.json`에서 확인한다. 계약월별 연결·대상 건수와 연결률을 비교하며 최근월이 직전 3개월 단순 평균보다 10%p 이상 낮으면 경고한다. 같은 작업월을 재시도할 때는 첫 기준 파일을 사용한다.

> `run_monthly_cycle.py`(xlsx)는 **복구·레거시** — §5·§6 명령으로 월간을 시작하지 말 것. git deploy ≠ 월갱신 (Promote 필수).

---

## 1. 용어

| 용어 | 설명 |
|------|------|
| **cycle_id** | 월간 작업 번들 ID. **`YYYYMM`** (예: `202605` = 2026년 5월에 수행하는 이번 배치). |
| **수집 연월 범위** | 합의 예: `202605` 배치 시 **계약연월 `202505`~`202604`**(직전 12개월). 파일·국토부 UI 기준으로 조정 가능. |
| **`as_of_month` (V2)** | `build_stats_v2.py --as-of YYYY-MM-01` — 해당 **달 말일까지**가 통계 기간 끝으로 해석된다 (`build_stats_v2` 주석·`V2_STATS_DESIGN` 참고). |
| **기본 `--as-of` 매핑** | *수집 끝 연월이 `cycle`의 **직전 달**과 같다*고 가정할 때: `cycle_id=202605` → 마지막 월 `202604` → **`--as-of 2026-04-01`**. 자동화: `scripts/monthly/cycle_utils.stats_as_of_iso_from_cycle_id`. **실제 수집 끝 월이 다르면 `--v2-as-of`로 수동 지정.** |

> **D-026 지목군:** 기본=용도×지목 · 옵션=용도×지목군. Master 재적재 불필요; group mart는 **원장 단가 재집계**.  
> **월간:** `run_land_cycle_csv` 가 category V2 **와** §7.1 group·annual을 이어서 돌린다. `--skip-jimok-group` 은 비권장. xlsx `run_monthly_cycle` 만 돌린 복구 시에만 §7.1을 수동으로 보강한다.  
> SSOT: [`LAND_JIMOK_GROUP_DESIGN.md`](./LAND_JIMOK_GROUP_DESIGN.md) · [`DECISIONS.md`](./DECISIONS.md) D-026. Profile·Twin은 연간(D-054), 월간에 넣지 않는다.  
>
> **이력 (2026-06 재구축):** `land_stats_next`·당시 as_of 혼선은 [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) §12. **지금 cycle의 기준월을 2026-05로 되돌리지 말 것.**

---

## 2. 디렉터리 구조 (권장)

저장소 루트 기준:

```
{repo}/
  raw\토지\{cycle_id}\            # 현행: 시도×연월 CSV (molit_csv_collector)
  raw\토지\{cycle_id}\            # 레거시 복구: 시·도별 xlsx (평탄화)
  clean_snapshots\{cycle_id}\    # manifest, land_tx_counts_after.json 등
  stats_snapshots\{cycle_id}\    # V2 요약 JSON (스크립트가 기록)
  logs\
  backups\
  scripts\monthly\
  pipeline\
  docs\
```

### 2.1 raw 예시 (CSV · 현행)

수집기는 `raw/토지/{cycle_id}/` 또는 `raw/{cycle}업데이트/토지_{from}_{to}/` 관례를 쓴다. 러너가 `cycle_utils.resolve_land_csv_raw_dir` 로 찾는다.

### 2.2 raw 예시 (xlsx · 레거시)

```
raw\토지\202605\
  서울.xlsx
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

## 4. 실행 흐름 (반자동 · CSV)

1. 운영자: 국토부 **CSV**(검증 포함 `molit_csv_collector`) — 직전 12개월. [`MOLIT_CSV_COLLECTOR_WARNINGS.md`](MOLIT_CSV_COLLECTOR_WARNINGS.md).
2. **CSV 수 확인** — 체크리스트 **0.7**. 유형 폴더마다 16개(전남광주통합 1파일). 빠진 지역이 있으면 **러너를 돌리지 말고** 사용자에게 먼저 알린다. purge가 창을 비우기 전에 멈춘다.
3. `py scripts/monthly/run_land_cycle_csv.py --cycle-id YYYYMM`  
   purge → collect/clean/dedupe → V2 **3,5,7** category → §7.1 group·annual → cache TRUNCATE → 스냅샷.
4. 검증: `verify_monthly_integrity.py` · 건수 비교 · 체크리스트 §1.
5. **OK** 후 **Promote** (§9). 이어서 복합·집합 CSV 러너 ([`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md) §2–3). 복합·집합도 같은 CSV 묶음이므로 0.7을 통과한 뒤에만 시작한다.

xlsx 복구만: 아래 §5·§6 `run_monthly_cycle.py` 후 **반드시 §7.1 수동** (xlsx cycle은 group 미포함).

---

## 5. 수집 단계 (`raw`)

**현행:** `deploy/molit_csv_collector` (검증 포함). 이전 다운로드 완료 전 rename·짧은 sleep은 **시도/연도 오염 CSV**. [`MOLIT_CSV_COLLECTOR_WARNINGS.md`](MOLIT_CSV_COLLECTOR_WARNINGS.md).

아래 엑셀 Selenium·`run_monthly_cycle` 서술은 **복구·레거시**.

- **실거래가 엑셀(토지 매매)** 복구: `scripts/monthly/download_molit_land_xlsx.py` (`selenium>=4.15`).  
  예: `py scripts/monthly/download_molit_land_xlsx.py --cycle-id 202605`  
- **통합 · 정제(노트북 규격, 템플릿용)** 는 `docs/LAND_NOTEBOOK_EXCEL_PREP.md` (DB 적재와 별도).
- **xlsx 성공/실패 기록:** `run_monthly_cycle.py` → `clean_snapshots\{cycle_id}\raw_manifest.json`.

---

## 6. 통합·정제·DB 업데이트 (xlsx 레거시)

**매월은 §4 CSV 러너.** 이 절은 xlsx 복구 전용.

### 6.1 하위폴더 탐색

- `pipeline/collect.py` 의 `--directory` 는 **직접 자식만** 스캔한다.
- 깊게 두었으면 `flatten_raw_xlsx.py` → `clean_snapshots\{cycle_id}\flat_in\`.  
  xlsx 원스톱: `run_monthly_cycle.py` (`--skip-flatten` 생략 가능).

### 6.2 파이프라인 (xlsx)

```powershell
py scripts\monthly\run_monthly_cycle.py --cycle-id YYYYMM
```

동작: manifest → flatten → `run_pipeline` (excel + V2 category, **xlsx 기본 windows는 러너 인자** — 복구 시에도 **3,5,7** 맞출 것) → 건수·V2 요약 JSON. **group은 안 돈다 → §7.1 수동.**

### 6.3 `run_pipeline.py`

- `--v2-as-of YYYY-MM-DD` 는 `build_stats_v2` 에 그대로 (환경 변수보다 우선).

---

## 7. 사전통계 생성 (V2 · 용도×지목)

- **CSV:** `run_land_cycle_csv.py` 가 `build_stats_v2` + `build_upper_stats_v2` 를 `--windows 3,5,7` 로 실행한 뒤 §7.1 group을 이어서 돈다.
- **xlsx 복구:** `run_monthly_cycle.py` 는 category(+upper)만. 끄려면 `--skip-upper-v2`.
- 수동: `python pipeline/build_upper_stats_v2.py --as-of … --windows 3,5,7`
- 기본 `--col-axis` 는 **`category`**. 지목군은 §7.1. CSV에서는 자동, xlsx에서는 수동.

---

## 7.1 용도×지목군 (D-026) — CSV는 자동 · xlsx 복구만 수동

> **목적:** 용도×지목군 mart + 장기추세 annual(group).  
> **CSV:** `run_land_cycle_csv.py` 기본 포함. 이 절의 명령은 실패 재실행·xlsx 복구용.  
> **금지:** 지목(category) mart 평균을 합쳐 지목군 평균을 만들지 말 것 — **원장 단가 재집계** (`--col-axis group`).  
> **UI:** 기본=용도×지목. 지목군은 매트릭스 버튼만. 지역을 바꾸면 용도×지목으로 복귀.

### 7.1.0 운영 사고·주의 (2026-07-26)

배포판에서 「용도×지목군」조회 시  
`matrix_mode=group … V2 집계가 없습니다`(404) 가 난 사례가 있다.

| 원인 | 내용 |
|------|------|
| **부분 적재** | `land_basic_stats_v2` `col_axis=group` 이 일부 시도(예: 41·43)만 있고 **전국 미완료** |
| **upper 누락** | `land_upper_stats_v2` 에 `col_axis=group` **0행** → 시군구·읍면동 지목군 표 불가 |
| **월간 자동화 공백** | xlsx `run_monthly_cycle` 은 category만 → **§7.1을 빼먹으면 재발**. CSV `run_land_cycle_csv` 는 group 기본 포함 (`--skip-jimok-group` 끄지 말 것) |

**조치(전국):** category와 **동일 as_of·windows** 로

1. `build_stats_v2.py --col-axis group`  
2. `build_upper_stats_v2.py --col-axis group`  

**VPS 실행 시:** `pipeline/.env` 의 `DATABASE_URL`(postgres 로컬 비번)과 `backend/.env`(ch2app)가 다를 수 있다.  
빌더는 **`backend/.env`를 source** 한 뒤 `backend/.venv` 파이썬으로 돌릴 것. (`STATS_V2_SIDO_CODE` 가 켜져 있으면 전국이 아니라 단일 시도만 돌므로 **unset**.)

검증은 “시도 샘플 몇 건”만 보지 말고, 아래처럼 **ALL×ALL 지역 수 category ≈ group** 을 맞출 것 (§7.1.4).

### 7.1.1 선행 DDL (최초 1회 · 스키마 확인)

로컬·VPS DB에 아래가 없으면 `pipeline/` 에서 적용:

| 파일 | 역할 |
|------|------|
| `db/037_land_jimok_group_map.sql` | 지목→지목군 맵 |
| `db/038_land_transactions_resolved_jimok_group.sql` | resolved VIEW + `jimok_group_*` |
| `db/040_land_stats_col_axis.sql` | V2 `col_axis` |
| `db/041_land_annual_col_axis.sql` | annual `col_axis` |

```powershell
cd C:\ch2\ch2_Macro\pipeline
python -c @"
from pathlib import Path
from sqlalchemy import text
from db_utils import get_engine
root = Path('..') / 'db'
for name in ('037_land_jimok_group_map.sql','038_land_transactions_resolved_jimok_group.sql','040_land_stats_col_axis.sql','041_land_annual_col_axis.sql'):
    p = root / name
    print('apply', p.name)
    with get_engine().begin() as c:
        c.execute(text(p.read_text(encoding='utf-8')))
print('ddl ok')
"@
```

매월: 맵/VIEW가 이미 있으면 **스킵**. `jimok_key` 매핑 변경 시에만 037 재적용 후 **영향 연도·as_of group 재빌드**.

### 7.1.2 V2 지목군 mart (전국 · 이번 as_of)

`AS_OF` = 이번 cycle의 `--v2-as-of` (예: `2026-06-01`).  
category 를 이번 cycle에서 이미 돌렸으면 **`group`만** (중복 category 재빌드 회피).

```powershell
cd C:\ch2\ch2_Macro\pipeline
$env:PYTHONUNBUFFERED="1"
# 기본통계 V2 — 용도×지목군
python -u build_stats_v2.py --as-of $AS_OF --windows 3,5,7 --col-axis group
# 상위행정 V2 — 용도×지목군
python -u build_upper_stats_v2.py --as-of $AS_OF --windows 3,5,7 --col-axis group
```

- category 와 group을 한 번에: `--col-axis both` (시간↑).  
- 예상 시간(참고): 전국 group V2 는 환경에 따라 **수십 분~1시간대** (과거 로컬 ~40분대 사례).  
- 로그 권장: `Tee-Object` 또는 `> logs\jimok_group_v2_{cycle}.log`.

### 7.1.3 장기추세 annual (증분 · category + group)

| 정책 | 내용 |
|------|------|
| **매월** | **당해 달력 연도만** UPSERT 재집계 (`--years YYYY`). 전 기간(2010~) `--full` 재빌드 **금지**(초기/복구·맵 대변경 시에만). |
| **1월 또는 직전 연도 보정 반영 시** | `--years (YYYY-1)-YYYY` 로 직전+당해 연도. |
| **grain** | `(calendar_year, …, col_axis)` UPSERT — 지정 연도·축만 교체. |
| **축** | 월간은 `--col-axis both` (지목 + 지목군). group만 보강이면 `--col-axis group`. |

```powershell
cd C:\ch2\ch2_Macro\pipeline
$YEAR = (Get-Date).Year   # 또는 수집 계약이 걸친 달력 연도
python -u build_annual_stats.py --years $YEAR --full --col-axis both --with-upper
```

- `--full` = **전국 시도** (연도 범위는 `--years`로 제한).  
- 예상 시간(참고): 당해 연도 both+upper 전국은 **수 십분 이내**가 보통. 2010~전 기간 group은 **~2시간대**(과거 로컬 ~1.9h).

### 7.1.4 검증 (지목군)

```powershell
cd C:\ch2\ch2_Macro\pipeline
# as_of·window 는 verify 스크립트 상수 또는 인자 — 이번 AS_OF 와 맞출 것
python verify_jimok_group_integrity.py
```

수동/에이전트 체크:

- [ ] `land_basic_stats_v2` / `land_upper_stats_v2` 에 `col_axis='group'` 이고 `as_of_month=$AS_OF` 행 존재
- [ ] **전국성:** `window_years=5`·`zone_type=ALL`·`land_category=ALL` 기준  
      `COUNT(DISTINCT beopjungri_code)` (basic) 가 **category와 group이 같거나 거의 같음**  
      (부분 시도만 돌리면 UI에서 대부분 지역이 404)
- [ ] upper: `region_level='sigungu'` ALL×ALL group 행이 **전국 시군구 규모**로 존재
- [ ] `land_annual_stats` / `land_annual_upper_stats` 에 `col_axis='group'` 이고 `calendar_year=$YEAR` 행 존재
- [ ] API: free/upper `matrix_mode=group` · 필터분석 토글 · 장기추세 탭(지목군 셀) 404 아님
- [ ] UI: 기본=용도×지목 · 버튼으로만 지목군 · **지역 변경 시 용도×지목으로 복귀**
- [ ] integrity: zone×group `count` ≈ 소속 지목 category `count` 합 (스크립트 mismatch=0)

### 7.1.5 에이전트 체크리스트 (복붙용)

```
[ ] cycle_id / AS_OF 확인 (category V2 완료 후)
[ ] DDL 037·038·040·041 존재 확인 (없으면 적용)
[ ] build_stats_v2 --col-axis group --as-of AS_OF --windows 3,5,7   # 전국 · STATS_V2_SIDO_CODE unset
[ ] build_upper_stats_v2 --col-axis group --as-of AS_OF --windows 3,5,7
[ ] (VPS) DATABASE_URL = backend/.env (ch2app) 사용
[ ] basic ALL 지역수 category≈group · upper sigungu group 존재
[ ] build_annual_stats --years YEAR --full --col-axis both --with-upper
[ ] verify_jimok_group_integrity (또는 동등 count 합 검증)
[ ] UI/API matrix_mode=group 스모크 · 지역 변경 시 category 복귀 확인
[ ] (Promote 시) group mart·annual 이 dump/재실행에 포함되는지 확인
```

### 7.1.6 CSV vs xlsx

- **CSV `run_land_cycle_csv.py`:** group V2·upper·annual(both)·integrity **기본 포함**. `--skip-jimok-group` 비권장.
- **xlsx `run_monthly_cycle.py`:** category만. 복구 시에만 본 절을 수동 실행.
- `run_pipeline.py` 에 `--col-axis` 배선은 없어도 된다. 월간 SSOT는 CSV 러너.

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
- [ ] **§7.1 지목군** — `col_axis=group` V2·annual 당해 연도 존재 + integrity/스모크  

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

### 9.4 코드 배포 ≠ DB Promote (2608 교훈)

**`deploy-from-windows.ps1` 은 backend·frontend 코드만 반영한다.** `land_stats` 원장·V2 mart 는 **별도 월간 cycle + Promote** 없이는 운영 DB에 7월(또는 이번 `as_of_month`)이 나타나지 않는다.

| 단계 | 무엇이 바뀌는가 | 2608(`cycle_id=202608`) |
|------|----------------|-------------------------|
| **① ingest** | `land_transactions` 에 **신규 계약연월** 거래 적재 | `raw/2608 업데이트/토지_202508_202607/*.csv` → `run_land_cycle_csv.py --cycle-id 202608` |
| **② mart** | `land_basic_stats_v2` 등 **`as_of_month=2026-07-01`** 행 생성 | cycle 스크립트 내 V2·§7.1 group·annual |
| **③ Promote** | 검증된 **`land_stats` DB** 를 VPS에 restore | 로컬 dump → VPS `promote_restore.sh` (§9.2 안 A) |
| **④ env** | `STATS_V2_DEFAULT_AS_OF_MONTH=2026-07-01` | Promote 직후 backend 재기동 |

**mart만 재계산(ingest 생략)하면** 원장에 7월 거래가 없을 때 화면에 7월이 **절대** 보이지 않는다.

**Promote dump 호환 (2026-08-09):**

- Windows PG18 **custom `-Fc` dump** → VPS 기본 `/usr/bin/pg_restore`(PG16) **실패** → `/usr/lib/postgresql/18/bin/pg_restore` 사용 또는 **plain SQL `.sql.gz`** ( `transaction_timeout` 등 PG18 전용 GUC 줄 제거 후 `psql` ).
- `py scripts/monthly/dump_land_for_promote.py --cycle-id 202608`은 `backups/land_stats_promote_202608.sql.gz`에 저장한다. 출력 경로를 바꾸려면 `--output`을 지정한다. 작업 ID는 파일명에 쓰이고 덤프 범위는 `land_stats` 전체다.
- VPS: `deploy/scripts/promote_restore.sh` (PG18 bin·`as_of` 자동·pre-backup은 `/tmp` 경유)
- 새 Promote 스크립트와 `/health.configured_land_as_of_month`를 제공하는 백엔드를 함께 배포하고, 기존 서비스의 응답을 먼저 확인한다. 덤프 검사 또는 헬스 계약 확인에 실패하면 서비스 중단 전에 종료한다. 재시작 명령이 끝난 뒤 최대 120초 동안 2초 간격으로 systemd 활성 상태, HTTP 200, JSON `status=ok`, 서비스가 읽은 기준월 및 복원 DB의 최신 적재월을 확인한다. 모두 맞으면 즉시 완료한다. 기준월을 명시한 경우 최신 적재월과 달라도 되지만 복원 DB에 그 달의 데이터가 있어야 한다.
- 202612 실행 전 최신 코드의 전용 worktree에서 `DATABASE_URL`이 재판정 이력이 있는 로컬 `land_stats`를 가리키는지 확인한다. 덤프 CLI의 `localhost`와 `PGPORT`도 같은 PostgreSQL 인스턴스를 가리켜야 한다. DB 접속 환경은 실행 프로세스에 주입한다.
- 계약월 202512~202611 CSV 폴더를 `--raw-dir`로 명시하고 기준월 2026-11-01을 확인한다. 토지 원장 SQLite와 광주·전남 대응표를 확인한 뒤 월간 공급 로그와 `clean_snapshots/202612/ledger_supply/land_coverage.json`을 점검한다.
- 새 전체 덤프는 `dump_land_for_promote.py --cycle-id 202612 --output <전용-worktree>/backups/land_stats_promote_202612.sql.gz`로 생성한다. 스테이징 복원에서 `honam_v2-local-20261110` 이벤트 8,232건, 대응하는 연결표의 상태·가격, 집계 기준월을 대조한다. 검증을 마친 아카이브의 SHA-256을 운영 Promote 직전에 재확인한다.

**2608 Promote 완료 (2026-08-09):** 로컬 검증 DB(`as_of=2026-07-01`, 7월 거래 17,985건) → VPS `land_stats` restore → `/health.latest_as_of_month=2026-07-01`.

---

## 10. 백업 및 수동 롤백

Promote는 사전 논리 덤프를 만든 뒤 기존 `land_stats`의 세션을 종료하고 DB를 삭제·재생성한다. 기존 DB 인스턴스는 보존되지 않는다. SQL 복원은 전체 트랜잭션으로 묶이지 않아 실패 시 새 DB가 비거나 일부 테이블·행·인덱스만 남을 수 있다. 사전 덤프는 `--no-owner --no-acl`로 생성되므로 객체 소유자와 개별 권한은 별도로 기록한다.

### 10.1 시작 전 준비

- 한 번에 한 명만 수행한다. DB에 쓰는 월간 작업·스케줄러·외부 세션을 멈추고 복구 확인까지 재개하지 않는다. 사전 덤프는 백엔드 중단 **전**에 뜨므로, 덤프의 스냅샷 이후 DB 삭제 사이에 들어간 쓰기는 복구본에 없다.
- 접근 제한된 작업별 폴더에 `backend/.env` 원본을 메타데이터와 함께 보관한다. 예를 들어 `sudo install -d -m 0700 "$RECOVERY_DIR"` 후 `sudo cp -a -- /opt/ch2_Macro/backend/.env "$RECOVERY_DIR/backend.env.before"`를 실행한다. 파일 내용은 콘솔에 출력하지 않는다.
- 현재 서비스 기준월·최신 적재월·핵심 테이블 행 수와 별도 권한을 기록한다. 실행마다 별도 백업 폴더를 준비해 `CH2_PROMOTE_BACKUP_DIR`로 지정한다. 이 실행에서 출력한 사전 덤프의 정확한 경로를 기록하고 보존한다. 운영 승인 전에 같은 형식의 덤프를 별도 DB에 복원할 수 있는지 점검한다. 압축 검사와 `pg_restore --list`는 형식 검사다.

### 10.2 재시도와 복구 판단

| 관찰한 마지막 단계 | 다음 조치 |
|---|---|
| 사전 검사·사전 백업 실패, DB 재생성 전 | 기존 DB와 서비스 상태를 확인한다. 원인 수정 및 입력 검증 뒤 Promote를 재시도할 수 있다. 서비스 중지만 일어났다면 DB를 확인하고 서비스를 먼저 재기동한다. |
| DB 재생성 또는 SQL 복원 실패, 복원 완료 여부 불명 | 서비스와 쓰기를 차단한 상태로 유지하고 이 실행의 사전 덤프에서 수동 복구한다. 부분 DB를 대상으로 Promote를 다시 실행하면 부분 DB가 새 사전 백업으로 기록될 수 있다. |
| SQL 복원 완료, 권한·기준월·재시작·헬스 단계 실패 | 덤프 대조와 권한·기준월을 확인한다. 데이터가 검증됐고 서비스 원인만 확인되면 해당 원인을 고친 뒤 재시작과 헬스 확인만 재시도한다. 기준월 불일치라면 systemd의 환경 오버라이드도 확인한다. 데이터가 불완전하거나 확인할 수 없거나 서비스 복구가 불가능하면 사전 덤프와 설정으로 수동 복구한다. |

### 10.3 승인된 수동 복구

1. 기록한 **이 실행의** 사전 덤프와 .env 사본을 지정한다. 로그를 보존하고 대상 호스트와 DB 이름을 확인한다. 백업 생성에 사용한 버전에 맞는 `pg_restore`의 절대 경로를 지정한다. 예를 들어 PG18이면 `/usr/lib/postgresql/18/bin/pg_restore`를 사용한다.
2. 아래 VPS 명령을 실행하기 전에 `PRE_DUMP`, `ENV_BACKUP`, `RESTORE_BIN`을 검증한 절대 경로로 설정한다. 읽기 가능한 사본과 TOC를 확인한 뒤 DB를 교체한다. 서비스 중지 이후 명령이 실패하면 서비스를 중지한 상태에서 원인을 해결한다.

```bash
set -e
: "${PRE_DUMP:?}" "${ENV_BACKUP:?}" "${RESTORE_BIN:?}"
sudo test -s "$ENV_BACKUP"
sudo -u postgres test -s "$PRE_DUMP"
sudo -u postgres "$RESTORE_BIN" --list "$PRE_DUMP" >/dev/null
sudo systemctl stop ch2-macro-backend.service
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d postgres <<'SQL'
DROP DATABASE IF EXISTS land_stats WITH (FORCE);
CREATE DATABASE land_stats OWNER ch2app;
SQL
sudo -u postgres "$RESTORE_BIN" --exit-on-error --no-owner --no-acl -d land_stats "$PRE_DUMP"
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d land_stats <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL
sudo cp -a -- "$ENV_BACKUP" /opt/ch2_Macro/backend/.env
```

3. 별도 소유자·권한을 사용했다면 기록에 따라 재적용한다. 복구된 행 수, 기준월과 `ch2app` 읽기 권한을 사전 기록과 대조한다. `sudo systemctl restart ch2-macro-backend.service`를 실행하고 서비스 활성 상태와 `/health`의 `status`, `configured_land_as_of_month`, `latest_as_of_month`를 사전 기록과 대조한다. 확인이 끝나면 쓰기를 재개한다.

---

## 11. 빠른 참조 — 명령 모음

| 목적 | 명령 |
|------|------|
| **월간 토지 (SSOT)** | `py scripts\monthly\run_land_cycle_csv.py --cycle-id YYYYMM` |
| 복합 (토지 이후) | `py scripts\monthly\run_built_cycle_csv.py --cycle-id YYYYMM` |
| 집합 (토지 이후) | `py scripts\monthly\run_collective_cycle_csv.py --cycle-id YYYYMM` |
| 지목군만 재실행 | `py pipeline\build_stats_v2.py --as-of YYYY-MM-01 --windows 3,5,7 --col-axis group` |
| 지목군 upper | `py pipeline\build_upper_stats_v2.py --as-of YYYY-MM-01 --windows 3,5,7 --col-axis group` |
| annual 당해연도 both | `py pipeline\build_annual_stats.py --years YYYY --full --col-axis both --with-upper` |
| 지목군 integrity | `py pipeline\verify_jimok_group_integrity.py` |
| 시도 건수 스냅샷 | `py scripts\monthly\snapshot_land_tx_counts.py --output clean_snapshots\{cycle}\land_tx_counts_after.json` |
| 스냅샷 비교 | `py scripts\monthly\compare_count_snapshots.py --before … --after …` |
| **Promote 게이트** | `py pipeline\verify_monthly_integrity.py --as-of YYYY-MM-01` |
| **Promote dump** | `py scripts\monthly\dump_land_for_promote.py --cycle-id YYYYMM` → `backups\land_stats_promote_{cycle}.sql.gz` |
| xlsx 복구 (group 없음) | `py scripts\monthly\run_monthly_cycle.py --cycle-id YYYYMM` 후 §7.1 수동 |

---

## 11.1 임대 상권 — 분기 갱신 (월간과 별개)

한국부동산원 상업용 임대동향은 **분기** 공표다. 토지/복합/집합 월간 CSV 사이클에 묶지 않는다.

1. 새 분기 공식 xlsx를 `임대시장/B.상업용/`에 둔다 (파일이 과거 분기를 포함).
2. `py pipeline/rent/import_sangkwon.py` — 폴더에서 mtime 최신 xlsx + `상권구획도2024.shp`.
3. 상권 모달 기본표는 **최신 분기 기준 4분기 롤링**. 추세선은 달력 연간.
4. `rent_stats` dump 후 VPS Promote. 체크리스트 §4.

SSOT: [`REB_COMMERCIAL_RENT_SURVEY.md`](./REB_COMMERCIAL_RENT_SURVEY.md) §7 · [`RENT_MARKET_PLAN.md`](./RENT_MARKET_PLAN.md) · [`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md) §4.

---

## 12. 관련 문서

- [`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md) — 월간 1페이지  
- [`MONTHLY_UPDATE_PIPELINE.md`](./MONTHLY_UPDATE_PIPELINE.md) — 실패 시나리오 부록 (xlsx 13단계는 레거시)  
- `docs/V2_OPERATOR_CHECKLIST.md` — 월초 갱신 단일 SOP(전국·검증·백엔드)  
- `docs/V2_STATS_PRODUCTION.md` — `build_stats_v2` 운영  
- `docs/LAND_JIMOK_GROUP_DESIGN.md` — 지목군 7분류 · mart/API 정책 (D-026)  
- `docs/LONG_TERM_TREND_DESIGN.md` — 장기추세 annual · 월간은 **당해 연도 UPSERT**  
- `docs/DECISIONS.md` — D-007 `API_TOKEN`, D-003 캐시, **D-026 지목군**  
- `NEXT_STEPS.md` — 백로그(알림·백업 자동화 등)

---

## 13. 개정 이력

| 날짜 | 내용 |
|------|------|
| 2026-10-02 | **§4 CSV 수 확인** — 유형당 16개. 빠진 지역이 있으면 적재 전에 사용자에게 알리고 러너를 시작하지 않음. 체크리스트 0.7 |
| 2026-09-01 | **CSV SSOT 본문 정렬** — 실행 흐름·§7.1·빠른 참조를 `run_land_cycle_csv`·windows **3,5,7**에 맞춤. xlsx는 복구. 2026-06 재구축 as_of 문단은 이력으로 격하 |
| 2026-08-16 | **§11.1 임대 상권 분기 갱신** — 기본표 4분기 롤링, 추세는 연간 |
| 2026-08-09 | **§9.4 코드 배포 vs DB Promote** — 2608 토지 7월 미노출 원인·ingest→mart→dump→VPS restore 체크리스트·PG18 dump 호환 |
| 2026-07-26 | **§7.1.0** 배포 404 사고(부분 group·upper 0) · VPS `backend/.env` · 전국성 검증 · UI 기본=용도×지목·지역 변경 시 category 복귀 |
| 2026-07-17 | **§7.1 용도×지목군 월간 필수** — 에이전트용 DDL·V2 group·annual 증분·검증 체크리스트. 실행 흐름·빠른 참조 반영 |
| 2026-05-24 | `run_monthly_cycle` 기본에 `build_upper_stats_v2`(상위통계) 포함, `--skip-upper-v2` 로 생략 |
