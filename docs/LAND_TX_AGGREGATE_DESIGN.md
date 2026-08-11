# 토지 거래목록 집계(피벗 Lite) 설계

> **상태:** Phase 2 구현 (2026-08-11) — 2축 교차 · Phase 2b(서버 집계) 미구현  
> **범위:** 유료 매트릭스 칸 모달 · **거래 목록** 탭 내 **집계** 서브뷰  
> **목표:** 엑셀 피벗 대체가 아니라 **하위 행정구역(읍·면·동)별 단가·거래량 차이**를 빠르게 보는 도구

---

## 1. 배경·사용 시나리오

필터분석 매트릭스에서 칸을 클릭하면 `PaidMatrixYearlyModal` 이 열리고, **거래 목록** 탭에서 해당 용도×지목(또는 지목군) 조건의 원장 거래를 볼 수 있다.

| 시나리오 | 기존 목록만 | 집계(Phase 1) |
|----------|-------------|---------------|
| 읍·면·동별 단가·건수 비교 | 컬럼 필터 + 눈대중 | **한 표**로 그룹 요약 |
| 도로·거래유형별 차이 | 동일 | 축 전환 탭 |
| 특정 구간 원장 확인 | 목록 필터 | 집계 행 **클릭 → 목록 드릴다운** |

엑셀 피벗과 **동일 UX·기능을 목표로 하지 않는다.** 다축 교차·피벗 필드 드래그·피벗 차트 등은 후속 Phase에서 필요 시 검토.

---

## 2. Phase 1 범위 (1축)

### 2.1 UI

- 거래 목록 탭: **목록 | 집계** 토글
- 집계 **1축**: **단일 축** preset 탭
  - 읍·면·동 (기본·주 사용)
  - 동·리
  - 도로
  - 거래유형
  - 계약연도
  - 지목 (지목군 모드만)
- 지표: **건수**, **중앙 단가**, **평균 단가**, **면적합(㎡)** — 단가 단위 만원/㎡
- 정렬: 건수 내림차순 → 라벨(가나다)
- **드릴다운:** 행 클릭 → 목록 탭 + 해당 축 **포함 필터** 1개 적용

---

## 2b. Phase 2 범위 (2축 교차) — 구현됨

### UI

- 집계 서브뷰: **1축 | 2축 교차** 토글
- **Preset:** 읍·면·동×거래유형 · ×도로 · ×연도 · (지목군) ×지목
- **행·열** 축 개별 선택 (같은 축 선택 시 자동 교체)
- 교차표 셀: **건수** + **중앙 단가** (만원/㎡)
- **드릴다운:**
  - 셀 클릭 → 행+열 **2개 필터**
  - 행/열 헤더 클릭 → 해당 축 **1개 필터**
- 행·열 정렬: 해당 축 **건수 합** 내림차순

### 데이터

- Phase 1과 동일 — **클라이언트 only**, 추가 API 없음
- `aggregateLandTransactionsCross()` · `buildLandTxDrillDownFilters()`

### 2.3 거래 목록 개선 (Phase 1 동시 반영)

- 페이지네이션 루프 제거 → bulk 2-request 패턴으로 **서버 부하·대기 시간** 감소
- `MatrixCellTransactionTable`: `externalSelectFilters` + `externalFilterToken` — 집계 드릴다운 연동
- 1만 건 초과 시 목록·집계 모두 **truncated 경고** 표시

### 데이터·API (Phase 1·2 공통)

| 항목 | 내용 |
|------|------|
| 집계 연산 | **클라이언트 only** |
| 추가 API | **없음** — 목록 bulk load 결과 재사용 |
| bulk load | probe 1건 + **최대 1만 건** 1회 (API 2회 상한) |
| CSV | **전체 건** 서버 export |

---

## 3. 코드 위치

| 파일 | 역할 |
|------|------|
| `frontend/src/utils/landTxAggregate.ts` | 축 정의, 그룹 집계, 드릴다운 컬럼 매핑 |
| `frontend/src/components/MatrixCellTransactionAggregate.tsx` | 집계 UI |
| `frontend/src/components/MatrixCellTransactionTable.tsx` | 목록 + 외부 필터 |
| `frontend/src/components/PaidMatrixYearlyModal.tsx` | 목록/집계 토글·로드·드릴다운 |
| `frontend/src/api/client.ts` | `fetchAllMatrixCellTransactions`, `MATRIX_TX_BULK_MAX = 10_000` |
| `frontend/src/constants/landStatsExplain.ts` | `buildTransactionAggregateExplain` |

---

## 4. 집계 규칙

### 4.1 그룹 키

- **읍·면·동 / 동·리:** `landTxAdminCols(item)` — 법정동 표시와 목록 컬럼과 동일
- **도로:** `road_condition`, 빈 값 → `—`
- **거래유형:** `deal_type`
- **계약연도:** `contract_year` (드릴다운 시 목록 `contract_date` 필터 = 연도 문자열)
- **지목:** `land_category` (지목군 모드)

### 4.2 지표

- **건수:** 그룹 내 행 수
- **중앙/평균 단가:** `unit_price_per_sqm` 이 유효한 건만 — 결측은 지표 계산에서 제외(건수에는 포함)
- **면적합:** `area_sqm` 유효값 합

### 4.3 필터·이상치

집계 대상 `items` 는 목록과 **동일 API 응답**이다. 매트릭스 칸의 `exclude_outlier`, IQR 배수, 용도·지목·연도·롤링 버킷 등 **서버 필터는 이미 적용된 상태**.

---

## 5. 제한·주의

1. **1만 건 상한** — 표본이 더 크면 집계·목록 필터 모두 로드분만 반영. 전수는 CSV.
2. **2축도 로드분 한정** — Phase 2b(서버 GROUP BY) 전까지 DB 전수 교차표 미지원.
3. **클라이언트 집계** — 로드분 한정이면 DB 전체 집계와 불일치 가능.
4. **소표본** — 건수 1~2건 그룹·셀의 중앙값 해석 주의.

---

## 6. 후속 Phase (미구현)

| Phase | 내용 | 상태 |
|-------|------|------|
| **2** | 2축 교차 + preset + 셀/헤더 드릴다운 | **구현됨** |
| **2b** | 서버-side `GROUP BY` API — 대용량 칸·전수 집계 | 미구현 |
| **3** | 피벗 필드 UI, 차트(막대·히트), 저장 preset | 미구현 |

서버 집계 API 설계 시 `paid.py` 의 `_fetch_matrix_cell_filtered_transactions` WHERE 절을 **재사용**하고 `SELECT dim, COUNT(*), percentile_cont…` 형태로 확장하는 것이 자연스럽다.

---

## 7. 검증 체크리스트

- [ ] 토지 앱 → 필터분석 → 매트릭스 칸 클릭 → 거래 목록
- [ ] **집계** 탭 → 읍·면·동별 건수·단가 표시
- [ ] **2축 교차** → preset · 행/열 선택 · 셀 클릭 드릴다운
- [ ] 행 클릭 → **목록** 탭 + 해당 필터 + 건수 일치
- [ ] 1만+ 건 칸(있으면) truncated 경고
- [ ] CSV는 여전히 전체 건
- [ ] 지목군 모드에서 **지목** 축 노출

---

## 8. 관련 문서

- 거래 목록 도움말: `buildTransactionListExplain` / `buildTransactionAggregateExplain`
- 토지 원장·필터 파이프라인: `landStatsExplain.ts` 내 `buildLedgerPipelineExplain`
