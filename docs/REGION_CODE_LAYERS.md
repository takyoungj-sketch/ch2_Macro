# 지역코드 3계층 — raw / historical / canonical

> **결정:** [`DECISIONS.md`](./DECISIONS.md) **D-028** (2026-07-21)  
> **계기:** 음성군 대소면→대소읍 승격 후 GIS 신코드(`4377025626`)와 통계 구코드(`4377034026`) 충돌.  
> **선행:** Regional Profile · Twin 전국 확장 **전**에 본 원칙을 적용한다.

관련: [`LONG_TERM_TREND_DESIGN.md`](./LONG_TERM_TREND_DESIGN.md) §2 · DDL `region_code_history` (`db/014_land_annual_stats.sql`) · Master 불변 **D-025**.

---

## 1. 원칙 (한 줄)

**원본·당시 코드는 보존하고, 분석·통계·지도 조회·Profile·Twin은 항상 현행 canonical code만 쓴다.**

금지: 읍·면 이름만 바꾸고 폐지 코드를 활성 canonical처럼 남기는 수리  
(`repair_eup_myeon_promotion.py`의 “코드 유지·이름만 갱신” 패턴 — **폐기**).

---

## 2. 세 계층

| 계층 | 이름 | 저장 위치 (목표) | 역할 |
|------|------|------------------|------|
| **R** | raw | `land_transactions_raw.raw_data` (주소 문자열 등) | 국토부 원문. 덮어쓰지 않음. |
| **H** | historical | 원장 `beopjungri_code` (ingest 시점 매핑 결과) | “그때 파이프라인이 붙인 코드”. **Master 불변(D-025)** — 분석 키로 쓰지 않음. |
| **C** | canonical | `region_codes` 중 `is_active` + `region_code_history`로 산출 | **모든** 사전집계·API·GIS 정규화·Profile·Twin 키 |

```
GIS li_cd / UI 선택 코드
        ↓  resolve (history + region_codes)
   canonical_region_code
        ↓
 land_basic_stats_v2 · upper · annual · Profile · Twin
```

예: 2020년 대소면 수태리 거래

- R: `… 대소면 수태리` (원문 유지)
- H: ingest 당시 코드 (구코드일 수 있음)
- C: `4377025626` (대소읍 수태리) → 2021~현재 통계 grain

---

## 3. 변경 유형 — 일괄 is_active 복구 금지

마스터「존재 누락 192 / 폐지 잔류 192」는 **건별 분류** 후 매핑한다.

| `change_type` | 의미 | 분석 remap |
|---------------|------|------------|
| `code_reissue` | 면→읍 등 **1:1 코드 재부여** (대소) | `from_code → to_code` 단순 치환 |
| `rename` | 명칭만 변경, 코드 동일 | history 선택; grain 불변 |
| `merge` | N:1 흡수 | N개 from → 1 to |
| `split` | **1:N 분할** | **자동 치환 금지**. 필지·주소·수동 규칙 없으면 예외 큐 |
| `boundary` | 경계만 변경 | case-by-case |

`region_code_history`에 행을 넣고, stats 빌더는 **항상 `to_code`(현행)** 로 GROUP BY한다.  
분할(`split`)은 Phase 2+ — 이번 대소 수리 Phase 1 범위에서 제외하고 목록만 분리 보관.

---

## 4. 파이프라인 규칙

1. **`region_codes`**: 법정동 마스터 `존재`만 활성 적재. `폐지`는 `is_active=FALSE` (`seed_region_codes.py --mark-abolished-inactive`).
2. **이름 수리 ≠ 코드 수리**: 표기(면↔읍)만 맞추고 폐지 PK를 살려 두지 않는다.
3. **clean 매핑**: 주소 → **현행 active** `region_codes`만. 면↔읍 별칭은 신코드가 있을 때만 유효.
4. **Master**: `land_transactions.beopjungri_code`를 “고치기 위해 UPDATE”하지 않는 것을 기본으로 한다(D-025).  
   분석은 `region_code_history` JOIN / resolved VIEW / 빌드 시 remap으로 **C**를 쓴다.  
   (이미 구코드에 쌓인 통계만 긴급 재빌드할 때는 history 적재 후 mart만 재생성.)
5. **GIS**: 경계 `li_cd` → canonical resolve → API. 미해석 코드는 통계 제외 전에 매핑 누락으로 드러낸다.
6. **Profile / Twin / 8대 유형**: `region_code` = **C only**. raw/H를 feature 키로 쓰지 않음.

---

## 5. 실행 순서 (Profile 개발 게이트)

| Phase | 내용 | 산출 |
|-------|------|------|
| **0** | 본 문서·D-028 확정 | 설계 SSOT |
| **1a** | 192(+대칭 폐지) **분류 리포트** — `code_reissue` / `rename` / `merge` / `split` / `unresolved` | [`reports/REGION_CODE_PHASE1A_CLASSIFICATION.md`](./reports/REGION_CODE_PHASE1A_CLASSIFICATION.md) |
| **1b** | 확정 `code_reissue`만 `region_code_history` 적재 | [`reports/REGION_CODE_PHASE1B_VERIFY.md`](./reports/REGION_CODE_PHASE1B_VERIFY.md) (191건) |
| **1c–1d** | 영향 canonical `region_codes` upsert + historical deactivate + **부분** `land_basic_stats_v2` 재빌드 | [`reports/REGION_CODE_PHASE2_VERIFY.md`](./reports/REGION_CODE_PHASE2_VERIFY.md) |
| **1e / Phase 2 API** | GIS→canonical resolve (`app/region_canonical.py`, `free_v2`) | 수태리+신척리 bulk OK |
| **2** | built/collective 동일 resolver 공유 · 분할·흡수 수동 규칙 | 8대 유형 정합 |
| **3** | Profile v2 / Twin — canonical SSOT 전제 착수 | D-027 후속 |

Phase 1a에서 `split`/`merge` 미판정은 **자동 seed 대상에서 제외**하고 별도 큐에 둔다.

---

## 6. 대소 검증 케이스 (회귀)

| 항목 | 기대 |
|------|------|
| 마스터 | `4377025626` 존재, `4377034026` 폐지 |
| `region_codes` | 신코드 active, 구코드 inactive |
| history | `4377034026 → 4377025626`, `code_reissue` |
| GIS 선택 `4377025626` | 사전집계 hit (수태리 통계 표시) |
| 원장 raw | 주소 문자열 불변 |

---

## 7. 하지 않을 것

- 원장 실시간 폴백으로 GIS·통계 불일치 가리기
- 192건 `is_active=TRUE` 일괄 복구
- 폐지 코드에 읍 이름만 붙여 canonical로 재사용
- Profile/Twin을 H코드 기준으로 먼저 빌드
