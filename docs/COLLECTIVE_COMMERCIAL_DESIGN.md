# 집합상가(commercial shop) 분석 설계

> GPT·Gemini 의견을 반영한 로드맵. **1단계(현재)** 는 도로명(cluster) 기준 통계로 마무리하고, 사용 피드백 후 단계적으로 확장한다.

---

## 1. 사용자가 답하고 싶은 질문

| 순위 | 질문 | 1단계 제공 |
|------|------|------------|
| 1 | 이 상권(도로) 시세는? | 도로 cluster 추세·분포·CI |
| 2 | 이 건물 시세는? | **2단계** (building_key) |
| 3 | 이 층·호실 단가는 적정? | **1단계** 도로 cluster 층·면적 효용지수 |

아파트와 달리 집합상가는 **단지 단위 표본이 작다**. 따라서 **도로명 cluster = 기본 해상도**가 현실적이다.

---

## 2. 해상도 전략 (2-tier)

```
[Main]  도로 cluster  — 추세, 분포, 도로 회귀, 도로 층·면적 효용지수
[Sub]   building_key  — n·품질 게이트 통과 시만 (2단계)
```

- **GPT**: 상가는 회귀식보다 **층별 효용지수·프리미엄 지수**가 실무 가치가 크다.
- **Gemini**: 마스킹 번지는 tier로 분리하고, UI 라벨로 불확실성을 명시한다.

---

## 3. 1단계 (현재 — 도로명 기준)

### 3.1 cluster 정의

```
cluster_key = hash(asset_type, addr1, addr2, addr3, addr4, road_name)
resolution_mode = road
```

- GUKTO 원본 xlsx → `gukto_raw_shop.py` → `collective_commercial_transactions`
- 필드: 번지(마스킹 포함), 층, 준공, 용도지역, 건축물용도, 도로폭 구간 등

### 3.2 모달 탭 (CommercialClusterDetailModal)

| 탭 | API | 비고 |
|----|-----|------|
| 추세·요약 | `GET .../stats/by-year` | 연도별 건수·평균 단가 |
| 단가 분포 | `GET .../histogram` | 전체/연도별 |
| 거래 목록 | `GET .../transactions` | 풍부 컬럼 |
| 번지별 요약 | `GET .../addresses` | **마스킹 번지 그룹** (shop만) |
| **층·면적 효용지수** | `GET .../floor-index` | 도로 중앙값=100 |
| 회귀 분석 | `POST .../regression/run` | 도로 cluster OLS |

지역·연도 필터는 목록 조회와 동일하게 적용.

### 3.3 층·면적 효용지수 (1단계 핵심)

- 아파트 `compute_floor_index` 재사용
- 기준: **해당 도로 cluster 내 ㎡당 단가 중앙값 = 100**
- 차원: `floor`(층별), `area`(연면적 30㎡ 구간)
- 게이트: n≥50 권장 (미달 시 `experiment`로 참고 조회)
- 셀 신뢰: n≥15

### 3.4 번지별 요약 해석 주의

- `7**` 등 **마스킹 번지**는 여러 실제 번지가 한 그룹
- 23년 이전은 addr4(동) 품질도 낮음
- UI: “마스킹 번지·동 조합” 명시 (건물 단위 아님)

---

## 4. 2단계 — building_key_v1 (보류)

### 4.1 식별 키 (Gemini 초안)

**High tier** — 비마스킹 번지 + 준공:

```
building_key_v1 = hash(road_name, addr4, lot_number, building_year, building_use)
```

조건: `lot_number`에 `*` 없음, `building_year` 유효.

**Medium tier** — 마스킹 번지 (`7**`):

- 1단계에서는 **건물 회귀·건물 효용지수 미제공**
- 2단계(C)에서 fingerprint + 더 빡센 게이트(n≥50)로 **추정 그룹** (UI: “추정” 배지)

**Low tier** — 번지·준공 불명 → 도로 cluster만.

### 4.2 n gate & 품질 gate

| 게이트 | Gemini | GPT 보완 |
|--------|--------|----------|
| 건물 회귀 노출 | n≥30 + High tier | **R²·SE·유의성**도 함께 (n=50, R²=0.22 → 미노출) |
| 층 효용지수 | n≥50 | 1단계는 도로 cluster |
| 셀 신뢰 | n≥15 | 동일 |

### 4.3 UI 라우팅 (2단계)

| tier | pass_n_gate | 모달 기본 |
|------|-------------|-----------|
| High | ✓ | **건물** 회귀·효용지수 + 도로 탭 전환 |
| High | ✗ | 도로 통합 모델 (건물 표본 부족) |
| Medium/Low | — | 도로 통합만 (마스킹 번지) |

---

## 5. 3단계 — 프리미엄 지수 (GPT)

회귀보다 **상대 지수**가 감정 실무에 가깝다:

- **도로 프리미엄**: 구·동 평균 대비 이 도로 %
- **건물 프리미엄**: 동일 도로 평균 대비 이 건물 %
- **층 프리미엄**: 건물·도로 평균 대비 해당 층 %

1단계 효용지수가 도로·층 프리미엄의 전단이다.

---

## 6. 데이터 한계 (공통)

| 항목 | 채움률(대략) | 영향 |
|------|-------------|------|
| 도로명 | ~100% | cluster 기본 OK |
| 번지 마스킹 | 다수 `*` | building_key High tier 제한 |
| 층 | ~71% | 효용지수 floor 차원 |
| 준공 | ~95% | building_key·회귀 |
| addr4 | ~37% | 지역 필터·동 그룹 |

2024~2025 원본은 **비마스킹 번지** 비율이 높아 2단계 파일럿에 유리 (GPT).

---

## 7. 구현 파일 맵

```
pipeline/collective_commercial/
  gukto_raw_shop.py      # ingest
  cluster_keys.py        # make_road_cluster_key (+ 향후 building_key_v1)

backend/app/collective_commercial/
  router.py              # clusters, addresses, floor-index, regression, ...
  regression/engine.py
  schemas.py

frontend-collective/src/
  CommercialApp.tsx
  components/CommercialClusterDetailModal.tsx
  components/CommercialFloorIndexPanel.tsx
  components/CommercialRegressionPanel.tsx
```

---

## 8. 1단계 완료 기준 & 다음 액션

**완료 (현재)**

- [x] 도로 cluster 목록·모달 (추세·분포·거래·번지별·회귀)
- [x] 도로 cluster **층·면적 효용지수** 탭
- [x] 지역·연도 필터 일관 적용

**사용 후 결정 (2단계 착수 조건)**

- 비마스킹 번지 building_key_v1 적재
- High tier + pass_n_gate 건물에 서브 모달 또는 drill-down
- 회귀 품질 gate (R² 하한)

**의도적 보류**

- 마스킹 `7**` 건물 **지번 exact 분해**
- 건축물대장 조인 — **[`BUILDING_REGISTER_ROADMAP.md`](BUILDING_REGISTER_ROADMAP.md)** (1~4순위, 구현 보류)
- 층·동·면적 효용지수의 **건물** 단위 버전 (4순위 building_key_v2 이후)

---

## 9. 참고: GPT vs Gemini 합의점

- **도로 = Main, 건물 = Sub (고빈도·고확신만)**
- **상가는 층 효용지수가 회귀보다 우선**
- **마스킹 번지 tier 분리 필수** — 1단계 번지별 탭은 “그룹 통계”로 한정
- **n만이 아니라 모델 품질(R²)로 회귀 노출** (2단계)

---

*최종 갱신: 2026-06 — 1단계 도로 cluster + 층·면적 효용지수 탭 반영*
