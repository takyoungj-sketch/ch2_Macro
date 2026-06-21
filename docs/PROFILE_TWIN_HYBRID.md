# Regional Profile · Twin — 작업 기록 및 하이브리드 설계

> **상태 (2026-06-20):** Phase 1 전국 Profile + Profile Twin v1 **적재 완료**. UI 연동·하이브리드 Twin은 **v1.2 예정**.  
> **관련:** [`DECISIONS.md`](DECISIONS.md) D-021·D-022·**D-023**, [`REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md), [`TWIN_REGION_SIMILARITY_ENGINE.md`](TWIN_REGION_SIMILARITY_ENGINE.md)

---

## 1. 오늘 완료한 작업 (2026-06-20)

### 1.1 Regional Profile UI (v1.1, 미커밋 다수)

| 항목 | 내용 |
|------|------|
| 탭 | **프로필 요약** / **Feature Browser** |
| 카탈로그 SSOT | `pipeline/config/profile_feature_catalog.yaml` ↔ `frontend/src/constants/profileFeatureCatalog.ts` |
| 조회 지역명 | regions 카탈로그 → 헤더·메타바 **「조회 지역」** |
| 지역 선택 UX | 유료 시군구 미만: **검색 시 교체**, 「+ 추가」 시 복수 추가 |
| Insight | `buildProfileInsights()` — 지역 유형·주의 등 |

### 1.2 전국 Profile Phase 1 (D-022)

| 산출물 | 결과 |
|--------|------|
| `rebuild_regional_profile_national.py` | land market → collective market → profile → twin orchestrator |
| `profile_version` | **`v1.1-national`** |
| land `market_stats` (전국) | +6,119 rows (land domain 추출) |
| `regional_profile` 5y | **5,235** rows |
| `regional_profile` 3y | **5,191** rows |
| 빌더 | `build_regional_profile.py` — `--sido-code` 미지정=전국, 기본 version `v1.1-national` |

### 1.3 Profile Twin v1 (`build_twin_from_profile.py`)

| 항목 | 값 |
|------|-----|
| algorithm_version | **5** |
| 입력 | `regional_profile` eupmyeondong (Feature 재생성 금지) |
| 전국 5y Twin rows | **16,485** (Top 5 × ~3,306 anchors) |
| batch_key (예) | `profile_v1.1-national_202605_w5_8bbe63af` |
| API | `GET /api/regional-profile/twins/{eup_code}` |
| UI | 프로필 요약 사이드바 **「쌍둥이 지역 (Profile)」** |

### 1.4 충북 파일럿 Twin (smoke)

- `v1.0-chungbuk` · 451 rows — API·UI 검증용

### 1.5 로컬 실행 메모

- Twin API 포함 백엔드: **`http://127.0.0.1:8001`** (8000에 구버전 프로세스 잔존 이슈)
- 프론트 dev proxy: `frontend/vite.config.ts` → 기본 `8001`
- Twin 테이블 DDL: `db/013_twin_eupmyeondong_neighbor_mvp.sql` → **collective_stats** DB에 적용

---

## 2. Profile Twin v1 알고리즘 (algorithm_version=5)

### 2.1 입력 feature (Profile JSON)

**구조 (6):** `ratio_residential_zone`, `ratio_commercial_zone`, `ratio_agri_zone`, `ratio_land_danji`, `ratio_land_rice`, `ratio_land_forest`

**가격 (4):** `land_residential_mean`, `land_commercial_mean`, `land_industrial_mean`, `apartment_mean`

**필터:** `land_residential_count + apartment_count` ≥ 15, (선택) 인구 ±50%

### 2.2 후보 pool

- **읍·면·동** grain
- 앵커 **시도 + 육상 인접 시도** (`pipeline/sido_adjacency.py`)
- 자기 자신 제외

### 2.3 유사도

```
struct_sim = cosine(6개 composition ratio)
price_sim  = 1 - min(1, |mean(log means_A) - mean(log means_B)| / 2.5)
similarity = 0.65 × struct_sim + 0.35 × price_sim
```

Top-k(기본 5) 저장 → `twin_eupmyeondong_neighbor_mvp.detail_scores`에 `profile_version`, `as_of_month`, `window_years`, `struct_sim`, `price_sim` 기록.

### 2.4 Legacy Twin (algorithm_version=4) 와 비교

| | Legacy (`build_twin_eupmyeondong_mvp.py`) | Profile Twin (v5) |
|--|-------------------------------------------|-------------------|
| 입력 | 토지 원장 zone×지목 셀 집계 | `regional_profile` |
| 구조 | 셀 share cosine + Jaccard 보조 | 6개 ratio cosine |
| 가격 | 읍면동 median log | Profile mean log |
| 가중 | struct **72%** + price 28% | struct **65%** + price 35% |
| 인구 | ±**40%** | ±**50%** |

**가경동(43113113) 관찰 (2026-06-20):**

- Legacy Top5: 천안 신방동, 용인 성복·모현·고림, 김포 풍무동 (0.91~0.81)
- Profile Top3: 용인 고림·포곡, 화성 반월
- **교집합:** 고림동 — legacy 4위 / profile 1위. 순위·1위 후보는 **feature 해상도·가격 추정 차이**로 diverge.

**판단:** Profile-only v1은 feature가 **얇아** Twin 단독 엔진으로는 legacy 대비 설득력이 부족한 case 존재. Profile은 **회귀·AI·메타 SSOT**로 유지, Twin은 **하이브리드** 권장 (D-023).

---

## 3. D-023 — 하이브리드 Twin (v1.2 설계)

### 3.1 결정 요지

- **Profile-only Twin** 은 v1 검증·API 골격용.
- **제품 Twin** 은 세 블록 가중 결합:
  - **토지 legacy 50%** — 검증된 zone×지목 거래 패턴 MVP
  - **집합 market 30%** — apartment / rowhouse / officetel 시장 fingerprint
  - **Profile 20%** — 인구·density·land domain 요약 (composition과 legacy **중복 최소화**)

### 3.2 점수식 (hybrid_v2 — 구현 확정)

리뷰(2026-06-21) 반영. **역할 분리** = 토지(토지시장)·집합(집합시장)·Profile(지역특성).
모든 블록 점수 ∈ **[0, 1]**, **pairwise 로그차 유사도**(전역 min/max 비의존, 아웃라이어 강건).

```
# 토지 블록 (legacy 검증값 유지)
land_struct = cosine(zone×지목 거래 share)
land_price  = 1 - min(1, |log1p(median단가_A) - log1p(median단가_B)| / 2.5)
S_land      = 0.72 × land_struct + 0.28 × land_price

# 집합 블록 (구성비 + 가격수준; z-score·cosine 폐기)
coll_pattern = cosine([apt_count, 연립_count, 오피스텔_count])   # 구성비 방향, 결측=0(시장없음)
coll_price   = 1 - min(1, |log1p(apt_mean_A) - log1p(apt_mean_B)| / 2.5)
S_coll       = 0.70 × coll_pattern + 0.30 × coll_price           # apt_mean 결측 시 = coll_pattern

# Profile 블록 (가격 제거 → 지역 메타만)
S_prof = mean( pop_sim, density_sim )   # 각 1 - min(1, |log1p Δ| / 2.5)

# 적응형 가중치: 집합 신뢰도 = min(1, 집합거래수 / N0=20), 앵커·후보 min
conf  = min(conf_anchor, conf_cand)
(wl, wc, wp) = normalize( 0.50, 0.30 × conf, 0.20 )   # 남는 비중은 토지·Profile로 재분배
similarity = wl × S_land + wc × S_coll + wp × S_prof
```

**근거:**
- **스케일 통일** — 기존 `S_coll/S_prof`가 z-cosine으로 [−1,1]이라 집합이 감점 역할을 하던 버그 제거.
- **z-score+cosine 폐기** — "모든 항목 평균 이상 → cosine≈1" 병리 제거. 구성비 cosine + 가격 pairwise 로 대체.
- **가격 중복 제거** — 가격을 토지·집합 두 블록에만 둠(Profile에서 제거).
- **결측 = 시장 없음** — 평균 대체 금지. 구성비 0 + 적응형 가중치로 자연 처리.

### 3.3 `detail_scores` (설명 가능성)

문장은 DB 대신 **reason_codes + sub-signal(별점)** 로 저장 → 프론트에서 추천 이유 자동 생성(로케일·포맷 비종속).

```json
{
  "algorithm": "hybrid_v2",
  "profile_version": "v1.1-national",
  "window_years": 5,
  "s_land": 0.91, "s_collective": 0.90, "s_profile": 0.99,
  "similarity_final": 0.925,
  "land_struct_sim": 0.91, "land_price_sim": 0.83,
  "coll_pattern_sim": 0.90, "coll_price_sim": 0.61,
  "pop_sim": 0.99, "density_sim": null,
  "collective_confidence": 1.0,
  "weights_effective": {"land": 0.5, "collective": 0.3, "profile": 0.2},
  "stars": {"land_struct": 5, "land_price": 4, "coll_pattern": 5, "population": 5},
  "reason_codes": ["LAND_STRUCT_STRONG", "LAND_PRICE_STRONG", "COLL_PATTERN_STRONG", "POP_STRONG"]
}
```

### 3.4 중복 counting 방지

- **가격**: 토지(단가)·집합(아파트가)만. Profile은 인구·밀도만 → 3중 가격 counting 제거.
- **구조**: 토지=zone×지목, 집합=거래종류 구성비로 도메인 분리.
- 장기: legacy share·collective block을 **Profile feature로 흡수** → Twin은 Profile-only로 회귀 (D-017 SSOT).

### 3.5 검증 (충북 스모크, 2026-06-21)

- **anchor=충북, 후보풀=충북+인접 시도**(대전·세종·경기·강원·충남·경북)로 로드 → 스모크가 전국 결과를 대표.
- **가경동(43113113)** Top5: 용인 성복·고림, 남양주 호평, 용인 영덕, **천안 신방동** — legacy 1위였던 신방동을 포함하며 토지·집합·인구가 모두 강하게 일치.
- **서문동(아파트 시장 無)**: 집합 신뢰도 0 → 가중치 토지 0.714 / Profile 0.286 자동 재분배 확인.

### 3.6 구현 파일

| 파일 | 역할 |
|------|------|
| `pipeline/build_twin_hybrid.py` | hybrid_v2 — 3블록 [0,1] + 적응형 가중치 + reason_codes (**구현됨**) |
| `pipeline/rebuild_regional_profile_national.py` | `--twin-mode hybrid` (기본) |
| `backend/.../regional_profile/router.py` | `/twins` — v6 우선, v5 fallback |
| `algorithm_version` / `detail.algorithm` | **6** / `hybrid_v2` |

### 3.7 향후 (장기)

- **학습형 가중치**: 사용자 "추천 채택/거부" 피드백 로깅 → 가중치(0.5/0.3/0.2) 자동 최적화.
- **presence 플래그**: 전국 QA에서 구성비 cosine만으로 구분 안 되는 사례 확인 시 phase 2.

---

## 4. 내일 이어서 할 작업 (우선순위)

1. **Git 커밋** — profile 브랜치: UI v1.1, national pipeline, twin API, docs (built/기타 혼재 파일 제외)
2. **하이브리드 Twin v1.2** — `build_twin_hybrid.py` + 가경동 등 QA vs legacy
3. **백엔드 8000 정리** — zombie 프로세스 kill, proxy 기본 8000 복귀
4. **Profile 3y Twin** — `--window-years 3` (선택)
5. **Twin 빌드 성능** — 전국 O(n²) 벡터화/블록 인덱스
6. **복합 회귀 pooling** — Twin Top-k → AI 제안(1안) / 자동 pool(2안) 프로토타입

---

## 5. 로컬 재현 명령

```powershell
cd c:\ch2\ch2_Macro\pipeline

# 전국 Profile (land+profile만, collective 이미 있으면 skip)
python rebuild_regional_profile_national.py --skip-collective --windows 3,5

# Profile Twin
python build_twin_from_profile.py --profile-version v1.1-national --window-years 5

# 백엔드 (Twin API)
cd ..\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 프론트
cd ..\frontend
npm run dev
# → http://127.0.0.1:5173/land/ → 지역 프로필 → 읍면동 → 프로필 조회
```

---

## 6. 브랜치·커밋 상태 (2026-06-20 EOD)

- **브랜치:** `feature/regional-profile-chungbuk`
- **마지막 커밋:** `bad3f3d` (충북 파일럿)
- **미커밋:** UI v1.1, national orchestrator, twin builder/API, region UX, docs — **내일 커밋 권장**

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-20 | 초안 — Phase 1 전국 Profile/Twin, 가경동 legacy vs profile 비교, D-023 하이브리드 설계 |
