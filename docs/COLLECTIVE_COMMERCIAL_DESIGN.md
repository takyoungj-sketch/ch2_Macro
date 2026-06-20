# 집합상가(commercial shop) 분석 설계

> GPT·Gemini 의견을 반영한 로드맵. **분석 해상도는 도로명 cluster 단일** — 건물 grain은 데이터·표본 한계로 **계획에서 제외**(D-020).  
> **재구축(2026-06):** MOLIT raw base CSV ingest·UI 정렬 — [`COLLECTIVE_COMMERCIAL_REBUILD_PLAN.md`](./COLLECTIVE_COMMERCIAL_REBUILD_PLAN.md) (D-018~D-019). **Phase 0~4 완료** (장기 추세 포함).

---

## 1. 사용자가 답하고 싶은 질문

| 순위 | 질문 | 제공 |
|------|------|------|
| 1 | 이 상권(도로) 시세는? | 도로 cluster 추세·분포·CI |
| 2 | 이 층·면적 대비 단가는? | 도로 cluster 층·면적 효용지수 |
| — | 이 **건물** 시세는? | **범위 밖** — MOLIT 마스킹 번지·표본 부족 (D-020) |

아파트와 달리 집합상가는 **단지·건물 단위 표본이 작고 번지가 마스킹**된다. **도로명 cluster = 유일한 분석 해상도**다.

---

## 2. 해상도 전략 (도로 cluster 단일)

```
도로 cluster — 추세·롤링·장기 추세·분포·회귀·층·면적 효용지수·코호트·번지별 요약(shop)
resolution_mode = road
```

- **GPT**: 상가는 회귀식보다 **층별 효용지수·프리미엄 지수**가 실무 가치가 크다 → **도로 cluster**에서 제공.
- **Gemini**: 마스킹 번지는 **번지별 요약** 탭에서 그룹 통계로만 제공; UI 라벨로 불확실성 명시.
- **건물 grain(`building_key`)**: 계획 **제외** — 구현 난이도·데이터 품질 대비 실익 낮음 (D-020).

---

## 3. 도로 cluster 기준 (현행 SSOT)

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

### 3.3 층·면적 효용지수

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

## 4. 프리미엄 지수 (GPT — 도로·층, 선택 과제)

회귀보다 **상대 지수**가 감정 실무에 가깝다:

- **도로 프리미엄**: 구·동 평균 대비 이 도로 %
- **층 프리미엄**: 동일 도로 평균 대비 해당 층 %

현행 효용지수가 도로·층 프리미엄의 전단이다. **건물 프리미엄은 범위 밖.**

---

## 5. 데이터 한계 (공통)

| 항목 | 채움률(대략) | 영향 |
|------|-------------|------|
| 도로명 | ~100% | cluster 기본 OK |
| 번지 마스킹 | 다수 `*` | **건물 식별 불가** → 도로 cluster·번지 그룹만 |
| 층 | ~71% | 효용지수 floor 차원 |
| 준공 | ~95% | 회귀·cluster 메타 |
| addr4 | ~37% | 지역 필터·동 그룹 |

---

## 6. 구현 파일 맵

```
pipeline/collective_commercial/
  gukto_raw_shop.py      # ingest
  cluster_keys.py        # make_road_cluster_key

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

## 7. 완료 기준

**완료 (Phase 0~4, 2026-06-20)**

- [x] 도로 cluster 목록·모달 (추세·분포·거래·번지별·회귀·**장기 추세**)
- [x] 도로 cluster **층·면적 효용지수** 탭 + 코호트 통합분석
- [x] 지역·연도 필터 일관 적용 · 회귀 예측구간(PI)
- [x] `collective_cluster_annual_stats` 2010~ (집합 long-term CSV + 2021~ transactions)

**Promote 전:** `py pipeline/finish_collective_commercial.py --api-base http://127.0.0.1:8000`

**범위 밖 (재검토 없음, D-020)**

- 건물 grain · `building_key_v1/v2` · 건물 단위 회귀·효용지수
- 마스킹 `7**` **지번 exact 분해**
- 건축물대장 조인으로 상가 **건물** 해상도 상향 — [`BUILDING_REGISTER_ROADMAP.md`](BUILDING_REGISTER_ROADMAP.md) §7은 **주거 집합**만 해당

---

## 8. 참고: GPT vs Gemini 합의점 (도로 cluster 한정)

- **도로 cluster = 유일 Main 해상도**
- **상가는 층 효용지수가 회귀보다 우선**
- **마스킹 번지** — 번지별 탭은 “그룹 통계”로 한정, 건물 drill-down 없음
- **n + 모델 품질(R²)** 로 회귀·효용 게이트

---

*최종 갱신: 2026-06-20 — Phase 0~4 완료; 건물 grain 계획 제외 (D-020)*
