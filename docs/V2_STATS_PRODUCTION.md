# V2 무료 통계 — 프로덕션 전국 배치·운영

> **전제 (현재 검증 가정):** 서비스 기준일 **2026-01-01** → 스냅샷 키 **`as_of_month = 2025-12-01`**, 무료 창 **`window_years ∈ {3, 5}`**.  
> 설계: [V2_STATS_DESIGN.md](./V2_STATS_DESIGN.md)  
> **운영 체크리스트:** [V2_OPERATOR_CHECKLIST.md](./V2_OPERATOR_CHECKLIST.md)

**최종 목표:** 월초 **전국 무료 V2 통계 자동 갱신 가능한 production pipeline**. 유료 V2(1~5년)는 전국 무료 안정화 후.

---

## 1. 전국 최초 구축 — 필수 사전 작업

| 순서 | 작업 |
|------|------|
| 1 | `db/007_land_basic_stats_v2.sql` 적용 |
| 2 | **`db/008_land_transactions_v2_batch_index.sql` 실제 적용** (V2 배치 조회 최적화) |
| 3 | **`db/preflight_v2_national.sql`** 실행 → `ANALYZE land_transactions` + 인덱스·`land_basic_stats_v2` 행수/용량 점검 |
| 4 | (권장) PostgreSQL `work_mem` / `maintenance_work_mem` — 상세는 [V2_OPERATOR_CHECKLIST.md](./V2_OPERATOR_CHECKLIST.md) §D |

### 1.1 환경 변수 (`pipeline/.env` 등)

| 변수 | 전국 최초 | 비고 |
|------|-----------|------|
| `DATABASE_URL` | 필수 | |
| `STATS_V2_DEFAULT_AS_OF_MONTH` | 권장 스냅샷 `YYYY-MM-01` | `--as-of`와 정합 |
| `STATS_V2_ASSUMED_TODAY` | 선택 | API/로컬 검증용; **배치는 `--as-of` 명시 권장** |
| `STATS_V2_SIDO_CODE` | **비우기** | 있으면 해당 시도만 단일 실행 |
| `STATS_V2_UPSERT_CHUNK` | 선택 (기본 400) | |

### 1.2 프로덕션 명령 (무료 3·5년)

```bash
cd pipeline
python build_stats_v2.py --as-of 2025-12-01 --windows 3,5
```

- **시도 청크:** 긴 창 내 거래가 있는 `sido_code`만 순회, **시도마다 조회→집계→UPSERT 청크 커밋→`gc`**.
- **로그:** `배치 wall-clock 시작`, 시도별 시작/완료 시각·소요, **진행 %·예상 종료 시각**, 종료 시 **V2 총 행수·테이블 용량 증가(MiB)**.
- **Ctrl+C:** `KeyboardInterrupt` 안내 후 종료(코드 130); 이미 끝난 시도는 DB 반영됨.
- **실패:** 예외 시 **실패한 시도 코드** 로그 후 종료(코드 1); 재실행 **멱등**(ON CONFLICT).
- **재실행 검증:** 동일 명령 재시행 시 행·용량이 **데이터 동일면 유지**(합의된 §4 구간 동일 전제).

### 1.3 단일 시도 / 단일 동 / 통조회

```bash
python build_stats_v2.py --as-of 2025-12-01 --windows 3,5 --sido-code 11
python build_stats_v2.py --as-of 2025-12-01 --windows 3,5 --region 4311311300
python build_stats_v2.py --as-of 2025-12-01 --windows 3,5 --single-fetch   # 비권장
```

---

## 2. 전국 배치 후 자동 검증

백엔드 기동 후:

```bash
cd pipeline
python verify_v2_national_samples.py --base-url http://127.0.0.1:8000 --as-of-month 2025-12-01
```

- 서울·경기·부산·충북·제주 대표 **법정동**, **3년·5년** 각 `GET /api/free/v2/stats/...` 검사.
- `9999999999` 코드에 대해 **404** 기대(빈/무효 코드).

법정동 코드는 원장에 따라 404일 수 있음 — 그 경우 `verify_v2_national_samples.py` 의 `DEFAULT_SAMPLES` 만 조정.

---

## 3. 월초 표준 갱신 (요약)

1. 신규 연도·직전 월 원장 → `land_transactions` 반영  
2. `ANALYZE land_transactions`  
3. `build_stats_v2.py --as-of <새 스냅샷 월 1일> --windows 3,5`  
4. **백엔드 재시작** (`.env` 스냅샷 정책)  
5. (필요 시) **프론트 재시작** (`VITE_STATS_V2_ASSUMED_TODAY` 등)  
6. `verify_v2_national_samples.py` + 프론트 확인  

전체 표: [V2_OPERATOR_CHECKLIST.md](./V2_OPERATOR_CHECKLIST.md) §B.

---

## 4. 예상 소요·리스크

| 요소 | 설명 |
|------|------|
| 시간 | 시도별 거래량 편차 큼. **수 시간~24h+** 주문 가능. |
| 인덱스 | `008` 미적용 시 I/O 병목. |
| 메모리 | 시도 청크로 완화; 극단적 시도는 향후 시군구 분할 검토. |
| v1 | **미변경** — `land_basic_stats` / v1 API 훼손 없음. |

---

## 5. 인덱스

| 객체 | 내용 |
|------|------|
| `land_basic_stats_v2` | `007`: `(as_of_month, window_years, beopjungri_code)` 등 |
| `land_transactions` | `008`: `(sido_code, contract_date)` 부분 인덱스 |

---

## 6. 이후 로드맵

- 유료 V2(1~5년)는 **무료 전국 안정화 후**.
