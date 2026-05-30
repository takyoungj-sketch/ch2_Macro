# V2 통계 — 운영자 단일 SOP

> 목표: **월초 전국 V2 통계(무료·유료)를 안전하게 갱신**하고 사용자 화면에 즉시 반영.  
> 큰 결정은 [`DECISIONS.md`](./DECISIONS.md) · 상세 설계는 [`V2_STATS_DESIGN.md`](./V2_STATS_DESIGN.md) · 갱신 명령 모음은 [`V2_STATS_PRODUCTION.md`](./V2_STATS_PRODUCTION.md).
>
> **이 문서가 단일 SOP** — README / NEXT_STEPS 는 여기로 포인터만 둔다.

---

## 0. 갱신 신선도 SLA (사용자 약속)

- 매월 **1일 09:00 KST 시작 ~ 5일 자정** 사이에 직전 월 말까지의 거래 반영.
- 화면 우상단 **「YYYY년 M월 말 기준」** = `stats_reference_date` (= `as_of_month` 의 다음 달 1일).
- 모니터링: `GET /health` 의 `latest_as_of_month` 가 직전 달 1일이어야 함.
- 5일 이상 지연 예상 시 별도 공지(추후 Slack/메일 자동화 자리 — `NEXT_STEPS` #6).

---

## A. 전국 최초 배치 전 (승인 후 실행)

| 단계 | 확인 | 비고 |
|------|------|------|
| A1 | `db/007_land_basic_stats_v2.sql` 적용됨 | 테이블·UNIQUE·인덱스 |
| A2 | `db/008_land_transactions_v2_batch_index.sql` 적용됨 | `ix_land_tx_v2_batch_sido_contract` |
| A3 | `psql ... -f db/preflight_v2_national.sql` 실행 | `ANALYZE` + 인덱스·행수·용량 스냅샷 |
| A4 | `pipeline/.env` 에 `STATS_V2_SIDO_CODE` **없음** | 전국이면 비울 것 |
| A5 | `work_mem` 등 DB 튜닝 검토 | 아래 [PostgreSQL 권장](#postgresql-권장-튜닝) |
| A6 | 디스크 여유·백업 정책 확인 | V2 테이블·WAL 증가 |
| A7 | 배치 명령·로그 저장 경로 합의 | 예: `tee logs/v2_national_YYYYMMDD.log` |

**프로덕션 명령 (기준일 2026-01-01 가정 스냅샷 예시):**

```bash
cd pipeline
python build_stats_v2.py --as-of 2025-12-01 --windows 3,5 2>&1 | tee ../logs/v2_national_%date%.log
```

( Linux/macOS 는 `tee logs/v2_national_$(date +%Y%m%d).log` )

| 단계 | 확인 |
|------|------|
| A8 | 로그에 `배치 wall-clock 시작`, 시도별 `[시도 시작]`/`[시도 완료]`, `예상종료` 확인 |
| A9 | 완료 로그: `land_basic_stats_v2` 행수·용량 증가분 |
| A10 | 백엔드 기동 로그의 V2 기본 `as_of_month` 가 정책과 일치 |
| A11 | `python verify_v2_national_samples.py --as-of-month 2025-12-01` 전부 OK |
| A12 | 프론트에서 동일 스냅샷으로 무료 3·5년 표시 확인 |

---

## B. 월별 표준 갱신 (신규 원장 반영 후)

> **권장 흐름**: 시도별 폴더로 받은 엑셀이 여러 개여도 **한 번에 모아 한 번만 `build_stats_v2`** 가 돌게 한다.
> 시도별로 나눌 때는 `run_pipeline.py --excel-dir ... --skip-build-stats` 로 정제까지만 끝낸 뒤, **마지막에 1회** `build_stats_v2.py` 단독 실행.
>
> **B0 (리허설, 읽기 전용)**: 실제 갱신 전, `python pipeline/rehearse_v2_update.py [--health-url http://127.0.0.1:8000/health]` 로
> .env / DB / 마이그레이션 / SOP 명령 `--help` / `/health.latest_as_of_month` 가 모두 정상인지 점검.
> 결과는 `logs/rehearse_v2_update.txt` 에 자동 저장. 이 단계는 DB 를 변경하지 않는다.

| 순서 | 작업 | 명령/메모 |
|------|------|-----------|
| B1 | 새 원본 엑셀 수집 | 현재는 수동 다운로드 → `원본/토지/` 평면 폴더에 모음 (자동화는 `NEXT_STEPS` #9) |
| B2 | (필요 시) `region_codes` 갱신 | 행정 개편 있으면 `seed_region_codes.py` 재실행 |
| B3 | `run_pipeline.py --excel-dir <원본 폴더> --excel-format auto` | 내부에서 `collect → clean → build_stats(V1) → analysis_cache + analysis_base_cache 자동 비움` |
| B3a | **`dedupe_land_transactions.py --execute --rehash`** | **2026-06~** — [`TRANSACTION_HASH_DEDUPE.md`](./TRANSACTION_HASH_DEDUPE.md). B5 V2 배치 **전**. 비하동 보녹·답 **2건** 확인. |
| B4 | **§3에 맞는 `as_of_month`(해당 월 1일)** 확정 | 보통 직전 월 1일 |
| B5 | `ANALYZE land_transactions;` | `db/preflight_v2_national.sql` 에 포함 |
| B6 | V2 배치 실행 | `python build_stats_v2.py --as-of YYYY-MM-01 --windows 3,5` (또는 B3 에서 `--with-v2 --v2-windows 3,5` 로 합쳐도 됨) |
| B7 | 인구 CSV 신규본 적재 | `python seed_population_csv.py --file ../data/population/...` (DECISIONS D-004 — `--codes-prefix` 미지정 시 전국 적재) |
| B8 | **백엔드 재시작** | `.env` 의 `STATS_V2_DEFAULT_AS_OF_MONTH` 반영. 재시작 후 `/health` 의 `latest_as_of_month` 확인 |
| B9 | **프론트 재시작** (Vite) | `VITE_STATS_V2_ASSUMED_TODAY` 변경 시 |
| B10 | `verify_v2_national_samples.py` | `--as-of-month` 를 신규 스냅샷으로 |
| B11 | 프론트·API 샘플 수동 확인 | 주요 지역·3/5년 |
| B12 | (옵션) 사용자 캐시 클리어 안내 | 브라우저 강제 새로고침. 백엔드 캐시는 B3 에서 자동 비워짐 |

---

## C. 재실행·장애 (Idempotency)

| 상황 | 조치 |
|------|------|
| 배치 중 오류 | 로그의 `[배치 실패] 시도 código=XX` 확인 → 원인 제거 후 **동일 명령 재실행** |
| Ctrl+C | `[KeyboardInterrupt]` 로그 — 완료된 시도는 이미 커밋. 재실행으로 잔여 시도 처리 |
| 동일 명령 2회 실행 | `ON CONFLICT DO UPDATE` 로 **데이터 동일 시 결과 동일**(멱등) |

---

## D. PostgreSQL 권장 튜닝

> 배치 **세션/역할** 또는 일시 `SET` 으로 적용하는 것을 권장. **서버 전역** 변경은 다른 워크로드와 충돌 시 주의.

| 파라미터 | 권장 범위 (참고) | 설명 |
|----------|------------------|------|
| `work_mem` | 64MB ~ 512MB | 배치 세션에서 정렬·해시가 디스크로 스필 나지 않게. RAM·동시 세션 수에 맞춤. |
| `maintenance_work_mem` | 512MB ~ 2GB | `CREATE INDEX` · `VACUUM` 대량 작업 시(인덱스 재생성·정리 창). |
| `effective_cache_size` | RAM의 50~75% 수준 (추정) | 플래너 힌트; 실제 메모리와 혼동 금지. |

배치 전 **최소한** `ANALYZE land_transactions` 는 `preflight_v2_national.sql` 에 포함.

---

## E. 최종 목표 (로드맵)

- **단기:** 무료 V2 전국 **월초 갱신 파이프라인** 안정화 (본 체크리스트).
- **중기:** 스케줄러(CRON/워크플로)로 B절 자동화, 알림·대시보드.
- **유료 V2 (1~5년):** 전국 무료 안정화 **이후** 확장.
