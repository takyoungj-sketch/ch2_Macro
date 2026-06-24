# CH2_MACRO 아키텍처 리뷰 보고서

> 작성: 2026-06-24  
> 목적: 현재 CH2_MACRO 구조를 AI 아키텍트 관점에서 비판적으로 검토  
> 관점: "왜 괜찮은가"가 아닌 **"어디가 위험한가"** 위주

---

## 1. 현재 구조 강점

### 1-1. 불변 식별자 (`transaction_hash`)

`transaction_hash.py`를 통해 거래 식별자를 SSOT로 분리했다. 엑셀 순번을 hash에서 제거한 2026-06 결정(D-012)은 재적재 멱등성의 핵심 전제로 **올바른 방향**이다. `ON CONFLICT DO UPDATE` 패턴도 UPSERT 기반 idempotent ETL의 표준적인 구현이다.

### 1-2. `as_of_month` 타임 축 설계

사전집계에 `(as_of_month, window_years)` 복합 키를 도입해 통계 스냅샷이 시계열로 공존한다. 월별 덮어쓰기 없이 이력 보존이 가능하고, rolling window 통계의 재현성이 보장된다. 이는 금융 데이터 파이프라인에서 쓰는 "partition by effective date" 패턴과 동일하다.

### 1-3. V1 폐기 계획 명시 (D-001)

사전에 V2로 API를 단일화하고 V1을 명시적 sunset 일정으로 폐기하는 설계는 API 버전 관리의 교과서적 방식이다. 운영 중인 서비스가 자체적으로 이 결정을 내린 것은 장기 부채 관리 측면에서 평가할 만하다.

### 1-4. DECISIONS.md 기록 문화

D-001~D-024b까지 의사결정을 날짜·이유·관련 문서 포인터와 함께 기록한다. AI나 신규 개발자가 "왜 이렇게 됐는가"를 역추적할 수 있다. 이런 결정 이력이 없으면 레거시 코드의 맥락을 잃어버리는 전형적인 패턴으로 빠진다.

---

## 2. 현재 구조의 위험 요소

### 2-1. [CRITICAL] hash 재생성 이력 관리 부재

`transaction_hash` 공식은 두 번 바뀌었다 (순번 포함 → 제외, `lot_display` 포함 여부). 각 공식 변경마다 전체 rehash가 수 시간 소요되고 DB를 잠근다.

**근본 문제:** hash 공식이 코드 1곳(`transaction_hash.py`)에만 있고, 이전 버전과의 호환성 테스트가 없다. 공식 변경 후 rehash를 놓치면 동일 거래에 대해 old hash 행과 new hash 행이 공존해 중복이 재발한다.

**2026-06 실측:** dedupe+rehash 완료 후 `biha_borok_dap_valid` 샘플이 기대치 2건 대신 3건으로 나타남 — 정확한 원인 미분석 상태.

### 2-2. [CRITICAL] `analysis_base_cache` 설계 결함

`analysis_base_cache`는 `land_transactions.id`(bigserial) 배열을 캐시한다. 이 설계는 두 가지 가정에 의존한다:
1. `id`가 갱신 사이에 안정적이다
2. 운영자가 갱신 후 항상 TRUNCATE를 실행한다

**문제:** bigserial `id`는 DELETE+reinsert 시 달라진다. 수동 TRUNCATE를 잊으면 **다른 거래의 통계가 반환된다**. 이는 UI에서 발각하기 매우 어렵다.

**권장 대안:** row_ids 대신 `transaction_hash` 배열을 캐시하거나, 원장 테이블에 갱신 timestamp를 두고 cache invalidation을 자동화.

### 2-3. [HIGH] 월간 갱신이 운영자 1인 수동 의존

전체 갱신 파이프라인이 명령어 수동 실행 기반이다. 환경변수(`STATS_V2_DEFAULT_AS_OF_MONTH`) 수동 설정, 수동 검증, 수동 Promote. 운영자 부재·실수 시 SLA(월 1~5일) 위반이 확실하다.

**실측:** 이번 사이클에서 as_of_month 설정 관련 주의 메모가 SOP에 명시적으로 기록된 것 자체가 실수 위험의 증거다.

**더 큰 문제:** 갱신 중단 시 재개 지점이 불명확하다. `run_monthly_cycle.py`가 실패하면 어느 단계까지 완료됐는지 파악하기 위해 로그를 직접 분석해야 한다.

### 2-4. [HIGH] DB 3개 분리 + region_codes 비동기화

`land_stats`, `built_stats`, `collective_stats`가 각각 독립 PostgreSQL DB이고, `region_codes`(행정코드 마스터)는 land를 SSOT로 나머지에 수동 복사한다.

**문제:** 행정구역 변경(분구·통합) 시 land만 업데이트되고 built·collective 복사본이 지연되면, 해당 코드로 built/collective 조회 시 404 또는 매핑 오류가 발생한다.

**더 나쁜 점:** 이 비동기화 상태가 모니터링되지 않는다. 사용자가 오류를 발견하기 전까지 인지 불가능.

### 2-5. [HIGH] 파이프라인 오류 복구 플랜 없음

`build_stats_v2.py` 전국 실행 중 특정 시도에서 실패하면 그 시도만 집계 누락된 채 완료된 것처럼 보인다(다른 시도는 정상). 로그를 직접 확인하지 않으면 모른다.

**twin_v8 빌드**도 마찬가지: 충청권 특정 레벨(sigungu/eupmyeondong/beopjungri) 중 하나가 실패해도 partial 데이터로 배치가 생성된다.

---

## 3. 반드시 수정해야 할 사항

### 수정 1 (즉시): `transaction_hash` 단위 테스트

```python
# tests/test_transaction_hash.py
def test_hash_stable():
    """hash 공식 변경 시 이 테스트가 깨져야 한다 — 의도적 경보"""
    row = { "beopjungri_code": "4313100700", ... }
    assert make_hash(row) == "abcd1234..."  # 고정값

def test_hash_no_row_number():
    """순번이 달라도 같은 hash여야 한다"""
    row_a = { ..., "source_row_no": 1 }
    row_b = { ..., "source_row_no": 99 }
    assert make_hash(row_a) == make_hash(row_b)
```

### 수정 2 (단기): cache invalidation 자동화

```python
# pipeline/dedupe_land_transactions.py 끝에 추가
if args.execute or args.rehash_only:
    clear_analysis_caches(conn)  # analysis_cache + analysis_base_cache TRUNCATE
    print("[INFO] caches cleared after dedupe/rehash")
```

### 수정 3 (단기): `STATS_V2_DEFAULT_AS_OF_MONTH` 방어 코드

```python
# pipeline/build_stats_v2.py 상단
as_of = os.getenv("STATS_V2_DEFAULT_AS_OF_MONTH")
if as_of:
    parsed = date.fromisoformat(as_of)
    today = date.today()
    if parsed > today:
        raise ValueError(f"as_of_month {as_of} is in the future. Check env.")
    if (today - parsed).days > 180:
        print(f"[WARN] as_of_month {as_of} is more than 180 days ago. Intended?")
```

### 수정 4 (단기): `biha_borok_dap_valid` 3건 원인 분석

```sql
SELECT id, transaction_hash, contract_date, area_sqm, total_price_10k,
       lot_display, deal_type, partial_ownership_label
FROM land_transactions
WHERE beopjungri_code = '4311313800'
  AND zone_type = '보녹' AND land_category = '답' AND is_valid = TRUE
ORDER BY contract_date;
```

3건이 모두 실제 거래인지, 1건이 중복인지 판별 후 처리.

### 수정 5 (중기): 파이프라인 체크포인트

```json
// clean_snapshots/{cycle_id}/pipeline_state.json
{
  "cycle_id": "202606",
  "steps": {
    "flatten": "done",
    "collect": "done",
    "clean": "done",
    "dedupe": "skipped",
    "build_stats_v2": "done",
    "build_upper_stats_v2": "in_progress",
    "cache_clear": "pending",
    "validate": "pending",
    "promote": "pending"
  },
  "as_of_month": "2026-05-01",
  "land_tx_count_before": 9602613,
  "land_tx_count_after": null
}
```

---

## 4. 향후 1년 확장 시 예상 문제

### 4-1. 데이터 볼륨 증가

현재 원장 9.6M건. 월 약 5만~10만건 증가 예상. 3년 후 ~12M건.

**위험:**
- `paid.py`의 동적 집계(percentile_cont) 쿼리가 연간 거래만 필터링해도 수백만 행 스캔
- `analysis_base_cache` row_ids 배열 크기 증가로 캐시 hit율 저하
- `build_stats_v2` 전국 실행 시간이 현재 ~2시간에서 3시간+ 예상

**대응 방향:** 파티셔닝 (`PARTITION BY contract_year`) 검토, summary table 확대

### 4-2. 상품 확장 (built, collective)

built·collective DB가 독립 확장됨. 각각 다른 스키마, 다른 region_codes 동기화 상태.

**위험:** 서로 다른 `region_codes` 버전을 가진 세 DB에서 cross-domain 쿼리 (예: 특정 지역의 토지+아파트 통합 분석)가 불가능하거나 오류 유발.

**대응 방향:** region_codes 단일 DB(land)에서 FDW(Foreign Data Wrapper) 또는 마이크로서비스 API로 참조

### 4-3. 사용자 수 증가 → API 부하

FastAPI 단일 인스턴스, uvicorn 기본 설정. 동시 유료 분석 요청 5~10개면 `work_mem` 충돌로 OOM 위험.

**대응 방향:** gunicorn workers 분리, connection pool (pgBouncer), `PAID_ANALYZE_WORK_MEM_MB` 환경변수 튜닝 (`deploy/templates/backend.env.production.example` 기존 준비됨)

### 4-4. Twin v8 전국 + 권역별 옵션

충청권(41K행)→전국 예상 ~500K행 이상. `batch_key` 기반 조회는 인덱스 있으나, 권역별 필터 추가 시 인덱스 미준비.

**대응 방향:** `(scope_label, region_level, anchor_region_code)` 복합 인덱스 추가

### 4-5. Regional Profile 전국화

`regional_profile.features` JSONB 전국 모든 레벨로 확장 시 수백만 행.

**위험:** JSONB 검색·비교 쿼리 성능 저하. Profile 버전 충돌(v1.0-chungbuk vs v1.1-national).

**대응 방향:** Profile 소비(Twin, 회귀)는 항상 `(profile_version, as_of_month, window_years)` 고정 조회 (D-017) — 이미 설계에 반영됨.

---

## 5. 종합 평가

| 관점 | 상태 | 비고 |
|------|------|------|
| 데이터 무결성 | ⚠️ 조건부 양호 | hash 단위 테스트·cache 자동화 필요 |
| 파이프라인 신뢰성 | ⚠️ 취약 | 수동 운영, 체크포인트 없음 |
| 확장성 | ⚠️ 12개월 내 병목 가능 | 볼륨·동시 사용자 증가 대비 필요 |
| 유지보수성 | ✅ 양호 | DECISIONS.md·SOP 문서 체계 우수 |
| 보안 | ⚠️ 최소 수준 | API_TOKEN 단일 인증, Rate limit 없음 |
| 배포 안정성 | ⚠️ 단일 VPS·수동 Promote | 장애 복구 수분~수십분 |

**AI 아키텍트 결론:**  
CH2_MACRO는 MVP로서 데이터 설계(hash, as_of_month, 도메인 분리)를 잘 잡았다. 그러나 운영 자동화·캐시 안전성·hash 공식 관리가 수동·암묵적 규칙에 의존한다. 사용자 수와 데이터 볼륨이 현재의 2~3배로 증가하는 시점에, 지금의 수동 운영 체계와 단일 인스턴스 구조는 **SLA 위반 + 데이터 오염 + 서비스 중단**의 3중 위험으로 나타날 것이다. 우선순위는 (1) hash 단위 테스트, (2) cache 자동화, (3) 파이프라인 체크포인트, (4) 인프라 이중화 순이다.
