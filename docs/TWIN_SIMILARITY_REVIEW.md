# Twin 유사도 — 검토 기록 (2026-06-21)

> **상태:** 검토·논의 중 — **구현 보류**. 현재 운영 알고리즘은 **hybrid v2 (`algorithm_version=6`)** 유지.  
> **관련:** [`PROFILE_TWIN_HYBRID.md`](PROFILE_TWIN_HYBRID.md), [`TWIN_REGION_SIMILARITY_ENGINE.md`](TWIN_REGION_SIMILARITY_ENGINE.md), D-023 / D-023b

---

## 1. 배경

2026-06-21 UI·데이터 검증 중 **“통계적으로 유사하지만 감정 comp로는 납득하기 어려운 twin”** 사례가 확인됨.  
hybrid v6(토지 50% + 집합 30% + Profile 20%)의 **가중·log-sim·전체 cosine** 방식을 재검토하고, 대안 프레임을 논의함. **대안 구현은 추가 고민 후** 진행.

---

## 2. 사례 — 청주 흥덕구 비하동 (43113138)

### 2.1 hybrid v6 결과 (로컬 DB, `v1.1-national`, 5y, `as_of=2026-05-01`)

| scope | Top 후보 (요지) | 유사도 |
|-------|-----------------|--------|
| **region** (충청권) | 대전 서구 내동, 보령 명천동, 서산 대산읍 … | ~0.72–0.75 |
| **national** | **경기 분당구 대장동**, **분당동**, 대전 내동 … | ~0.75–0.78 |

### 2.2 왜 분당·대장이 전국 1·2위인가 (알고리즘 관점)

- **토지 블록:** zone×지목 **전체 구성비 cosine** — “주거 + 녹지·임야 혼합” 패턴이 수도권 신도시 외곽과 형태적으로 가깝게 나옴.
- **집합 블록:** 아파트/연립/오피스텔 **건수 비율 cosine** + 아파트 mean **log-sim** — “아파트 비중 높은 동”끼리 `coll_pattern`이 높음. 가격 log-sim은 분당에서 낮아도(예: ~0.45) 패턴 점수가 순위를 끌어올림.
- **Profile:** 인구 log-sim — ±40% **필터 통과 후**에도 점수에 재반영.
- **시장 tier·경제권**(청주 vs 수도권)을 **배제하는 gate 없음**.

### 2.3 실무 판단 (2026-06-21 합의)

- **“비하동의 comp = 분당동·대장동”** → **동의하지 않음** (capital vs regional city tier 상이).
- **“hybrid v6가 그렇게 순위를 매긴 것”** → **사실** — 버그라기보다 **유사도 정의와 comp 직관의 괴리**.

---

## 3. 관련 사례 — Profile `land_residential` (분당동)

토지 **통계 화면**과 **지역 프로필** 불일치 별도 이슈 (twin과 직접 연동되지는 않으나 같은 “grain·표시” 주제).

- 분당동(41135101): 토지 매트릭스는 **보녹·임야** 위주, composition **농림·녹지 100%**.
- Profile **주거용지 15건 / 614.6** → `market_stats.land_residential`이 **읍면동에 없어** `build_regional_profile.py` **`escalate_land`로 분당구(41135) `1주×대` 통계**를 끼워 넣음 (`land_residential_source_level: sigungu`).
- UI는 `source_level` 미표시 → **설계/UX 미스** (산술 오류 아님).  
  → Profile 쪽 개선은 [`REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) P0( domain 추출·승격 표시)와 연계.

---

## 4. hybrid v6 현재 방식 (요약)

| 블록 | 가중 | 데이터 | 유사도 |
|------|------|--------|--------|
| 토지 | 50% | `land_transactions` → zone×지목 share + 중위 단가 | struct cosine 72% + price log-sim 28% |
| 집합 | 30% | `regional_profile` apt/rowhouse/officetel count·mean | pattern cosine 70% + apt price log-sim 30% |
| Profile | 20% | population, density | log-sim 평균 |

- **필터:** 토지 거래 ≥20건, 활동량(land_residential+apartment) ≥15, 인구 ±40%.
- **scope:** `region`(권역, UI 기본) / `national`(전국).
- **구현:** `pipeline/build_twin_hybrid.py`, `algorithm_version=6`, `detail.algorithm=hybrid_v2`.

---

## 5. 에이전트 검토 의견 (2026-06-21) — hybrid v6 튜닝

### 5.1 블록 가중 (50/30/20)

- **조정 필요** (comp 목적일 때): 토지↑, 집합↓(특히 가격 sim), Profile은 **게이트 위주**.
- 집합 **구성비**와 **가격 tier**는 분리 — 가격은 **순위보다 gate**가 적합.

### 5.2 log-sim

- **전면 제거 비추천** — pairwise log는 z-score 대비 아웃라이어에 강건 (D-023b 취지).
- **약화·게이트화 추천:** `|log1p(a)-log1p(b)|` 상한 초과 시 후보 제외 또는 해당 sub-signal 0.
- denom=2.5는 **~12배 가격차**까지 유사도 잔존 → cross-tier 오매칭에 기여.

### 5.3 기타 개선 후보 (구현 보류)

- 토지 struct **최소 셀 overlap** / Jaccard 보조 (sparse cosine 과대평가 완화).
- 토지 twin 창 vs Profile 창 **집계 SSOT 통일**.
- national 결과 **tier mismatch UI 경고**; region 기본 유지.
- human-labeled comp set으로 Top-k hit rate 평가.

---

## 6. 사용자 제안 프레임 (2026-06-21) — **추가 고민**

> **“이 방식은 좀 더 고민해 보자”** — 구현·스펙 확정 전 논의용 초안.

유사하다고 **느끼는** comp 기준을 다음 3축으로 재정의:

### 6.1 인구

- **큰 차이 없어야 함** → **hard gate** (현 ±40%와 유사; 점수 합산에서 인구 log-sim 중복은 불필요).

### 6.2 토지 — Top3 용도×지목 셀

- 토지 **통계 화면과 동일 grain** (`land_upper_stats_v2` 등)에서 **거래 건수 상위 3개 셀**.
- A·B 각각 Top3를 고른 뒤:
  - **셀 유형(용도×지목) 유사** (교집합·Jaccard 등),
  - **매칭된 셀의 평균단가 유사**.
- “A 1위 vs B 1위” 단순 1:1이 아니라 **교집합 매칭** 규칙 필요 (미정).

### 6.3 집합 — 아파트 3-tier

- 대표 자산: **아파트**.
- 지역 내 아파트 거래를 **상·중·하 3등분**(단가 기준 tercile).
- **상위권 / 중위권 / 하위권** 각각 **평균(또는 중위) 단가** 유사도 비교.
- 표본 부족 시( tier당·전체 최소 건수) 블록 **스킵** 또는 “집합 comp 불가”.

### 6.4 초안 합의 방향 (에이전트)

- comp **설명력·토지 UI 정합** 측면에서 **hybrid v6보다 낫다**고 평가.
- 구현 전 **확정 필요:**
  - Top3 **매칭 알고리즘**·표본 하한,
  - tier **등분 정의**·절대가 gate,
  - 3축 **가중 vs 순차 gate**,
  - 아파트 미약 동 fallback.

---

## 7. 미결정 / 다음에 고민할 것

1. 제안 3축을 **hybrid_v3 스펙**으로 확정할지, legacy land-only twin과 **병행**할지.
2. **national scope**에서 cross-tier 허용 범위 (참고용 vs comp용).
3. **시군구 grain**에 동일 3축 적용 여부.
4. 충북 anchor **human comp** 라벨 세트 + before/after Top-5 스크립트.
5. Profile `escalate_land` 표시 — twin과 별개지만 UX 일관성.

---

## 8. 오늘(2026-06-21) 세션 기타 (참고)

| 프로젝트 | 작업 | 상태 |
|----------|------|------|
| ch2_FieldNote | WMTS 서버 프록시, VPS 배포 | 완료·푸시 |
| ch2_Viewer | 지오코드 캐시 강화 | 완료·푸시 |
| ch2_Macro | 토지 백엔드/프론트 로컬 실행 | 완료 |
| ch2_Macro | Twin·Profile 유사도 검토 | **본 문서** |

---

## 9. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-21 | 초안 — 비하동 사례, hybrid v6 검토, 사용자 3축 제안, 구현 보류 |
