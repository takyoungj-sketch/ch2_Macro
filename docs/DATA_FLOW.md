# CH2_MACRO 데이터 흐름 (Data Flow)

> 최종 업데이트: 2026-06-24

---

## 1. 전체 흐름 개요

```
[국토부 MOLIT]
    │ xlsx / CSV 다운로드
    ▼
[Raw Storage]  raw/토지/{cycle_id}/*.xlsx
    │ flatten_raw_xlsx.py
    ▼
[Flat xlsx]    clean_snapshots/{cycle_id}/flat_in/*.xlsx
    │ collect.py (엑셀 파싱 → raw JSONB)
    ▼
[land_transactions_raw]  (raw_data JSONB, source_year/month)
    │ clean.py (정제·주소매핑·hash·UPSERT)
    ▼
[land_transactions]  (정제 원장, transaction_hash UNIQUE)
    │ dedupe_land_transactions.py  (중복 DELETE + rehash)
    ▼
[정제 원장 (clean)]  9.6M건 (2026-06 기준)
    │
    ├─ build_stats_v2.py ──────────────▶ [land_basic_stats_v2]
    │   (as_of_month + window_years)         법정동/리 grain
    │
    ├─ build_upper_stats_v2.py ────────▶ [land_upper_stats_v2]
    │   (시도·시군구·읍면동 집계)              상위 행정구역 grain
    │
    ├─ build_annual_stats.py ──────────▶ [land_annual_stats]
    │                                        연도별 장기 추세
    │
    ├─ build_land_market_stats.py ─────▶ [market_stats]  (land domain)
    │
    ├─ build_regional_profile.py ──────▶ [regional_profile]
    │   (market_stats + population →           feature JSONB)
    │
    └─ build_twin_v8.py ───────────────▶ [twin_neighbor_v8]
        (land_upper/basic + market_stats         충청권 현재·전국 예정)
```

---

## 2. 토지 원장 정제 흐름 상세

### 2-1. collect.py

```
엑셀 행 하나 = 거래 한 건
  → 시도·시군구·법정동 주소 파싱
  → land_transactions_raw INSERT (raw_data JSONB, 중복 허용)
```

### 2-2. clean.py

각 raw 행을 정제 원장으로 변환:

1. **주소 정규화** — 한자 병기 제거, 분구 토큰 drop, 전북특별자치도→전라북도 등 별칭
2. **법정동 코드 매핑** — `region_codes`에서 `beopjungri_code` 조회  
   동명이리 disambiguation: 괄호 한자 부분 비교 (D-012)
3. **`lot_display`** 파생 — 지번 표시용 (원본 마스킹 지번 우선)
4. **`transaction_hash`** 산출 — `transaction_hash.py` SSOT  
   키 = `beopjungri_code|year|month|day|lot_key|area_sqm|total_price_10k|cancel_flag`  
   (엑셀 순번·raw_id **미포함** — D-012, `TRANSACTION_HASH_DEDUPE.md`)
5. **UPSERT** — `ON CONFLICT (transaction_hash) DO UPDATE SET`  
   충돌 시 `lot_display`, `beopjungri_code`, 통계 필드 갱신 (raw_id 제외)

### 2-3. dedupe_land_transactions.py

재적재 과정에서 hash 공식 변경·표시 컬럼 보강으로 발생한 의미상 중복을 정리:

1. **DELETE** — business key 기준 중복 그룹에서 최우선 행 1개만 남김  
   tie-break: `lot_display`·`partial_ownership_label`·`deal_type`이 있는 행 우선, 그 다음 `id DESC`
2. **rehash** (`--rehash-only`) — 남은 전 행의 hash를 현재 공식으로 재계산  
   신규 hash와 충돌하는 행은 추가 DELETE

---

## 3. 복합부동산·집합부동산 흐름

```
MOLIT CSV (상업업무·공장창고·단독다가구)
    │ built/import_molit.py (hash dedupe: ON CONFLICT DO NOTHING)
    ▼
[built_transactions]  419,040건 (2026-06 기준)
    │ built/build_scope_stats.py
    ▼
[built_scope_stats]  (addr1·addr2·as_of_month grain)

집합 xlsx (아파트·연립·오피스텔·상가·공장)
    │ collective/import_refined.py
    ▼
[collective_transactions]  (building_key grain)
    │ build_collective_building_stats.py
    ▼
[collective_building_stats]  (rolling 12개월)
    │ build_collective_market_stats.py
    ▼
[market_stats]  (apartment_market, region_level grain → Profile용)

비주거 집합 (상가·공장 MOLIT CSV)
    │ collective_commercial/import_refined.py
    ▼
[commercial_clusters · collective_commercial_transactions]
```

---

## 4. API 응답 흐름 (토지 유료 분석)

```
User: POST /api/paid/analyze { region_codes, years, filters }
    │
    ├─ analysis_base_cache 조회 (4h TTL)
    │    있으면: row_ids 재사용
    │    없으면: land_transactions WHERE is_valid=true AND …
    │             → row_ids → cache 저장
    │
    ├─ analysis_cache 조회 (24h TTL)
    │    있으면: 저장된 JSON 반환
    │    없으면:
    │
    ├─ 집계 (window function, percentile_cont)
    │    total, by_year, by_zone, by_land_category, matrix
    │
    └─ 응답 + analysis_cache 저장
         as_of_month, stats_reference_date 포함
```

**캐시 무효화:** 월간 갱신 후 `analysis_cache` + `analysis_base_cache` TRUNCATE (D-003).

---

## 5. 무료 V2 흐름

```
User: GET /api/free/v2/stats/{beopjungri_code}?window_years=5
    │
    └─ land_basic_stats_v2 WHERE beopjungri_code=? AND as_of_month=? AND window_years=?
         사전집계 테이블 직접 조회 (동적 집계 없음)
         → total, by_year, by_zone, by_land_category, matrix
```

---

## 6. Twin v8 흐름

```
build_twin_v8.py (충청권 현재)
    │
    ├─ land_upper_stats_v2  (시군구·읍면동)
    ├─ land_basic_stats_v2  (리)
    ├─ market_stats (apartment_market)
    └─ population_stats
    │
    ▼
RegionProfile (메모리 객체)
    │
    ├─ 토지 구조 점수 (Top-N Jaccard, 가중치 20)
    ├─ 토지 가격 점수 (교집합 셀 log-ratio sim, 가중치 40)  [※현재 코드는 30, 변경 예정]
    └─ 집합 점수 (p25·median·p75 log-ratio, 가중치 40)
    │
    ▼
twin_neighbor_v8  (batch_key, region_level, anchor/twin 코드, score, confidence)
```

---

## 7. Regional Profile 흐름 (참고, 계획 중)

```
market_stats (land + collective domain)
    + population_stats
    + (예정) 거래비중·구성비 파생
    │
    ▼
regional_profile.features (JSONB, profile_version·as_of·window grain)
    │
    ├─ twin_eupmyeondong_neighbor_mvp (Profile 소비 twin)
    └─ 회귀 pooling (계획)
```

---

## 8. 데이터 흐름 이슈 맵

| 이슈 | 위치 | 현황 |
|------|------|------|
| 중복 적재 | `clean.py` UPSERT → hash 공식 변경 시 2중 INSERT | dedupe+rehash로 정리 완료 (2026-06) |
| needs_review 주소 미매핑 | `clean.py` | 충북 기준 <0.3% 수준 유지 |
| 캐시 stale | `analysis_base_cache` (id 재사용 위험) | 갱신 직후 TRUNCATE 의무 |
| V1 테이블 폐기 일정 | `land_basic_stats` V1 | 2026-06-30 예정 (`DECISIONS.md` D-001) |
| 원장 건수 감소 오해 | rehash 중 hash 충돌 추가 삭제 | 로그에 "changed" 수 확인 |
