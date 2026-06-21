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

### 3.2 점수식 (초안)

동일 후보 pool (인접 시도 + min_tx + 인구 허들)에서:

```
S_land   = legacy MVP 점수 (struct×0.72 + price×0.28, algorithm_version=4)
S_coll   = cosine( z-score( apartment/rowhouse/officetel mean, count, volatility ) )
S_prof   = cosine( population, density, land_R/C/I mean )   // ratio_* 제외 권장

similarity_hybrid = 0.50 × S_land + 0.30 × S_coll + 0.20 × S_prof
```

각 `S_*` ∈ [0, 1] 정규화. 가중치는 **튜닝 가능 파라미터** (파일럿 10~20 앵커 QA).

### 3.3 `detail_scores` (설명 가능성)

```json
{
  "algorithm": "hybrid_v1",
  "profile_version": "v1.1-national",
  "as_of_month": "2026-05-01",
  "window_years": 5,
  "s_land": 0.46,
  "s_collective": 0.28,
  "s_profile": 0.18,
  "similarity_final": 0.42
}
```

UI: legacy 화면처럼 블록별 기여도 표시.

### 3.4 중복 counting 방지

- Profile **composition ratio** ≈ legacy zone×지목 share의 **축약** → hybrid에서 Profile 블록은 **비구조 feature** 위주.
- 장기: legacy share·collective block을 **Profile v1.2 feature로 흡수** → Twin은 Profile-only로 회귀 (D-017 SSOT).

### 3.5 구현 파일

| 파일 | 역할 |
|------|------|
| `pipeline/build_twin_hybrid.py` | 3블록 점수 + Top-k (**구현됨**) |
| `pipeline/rebuild_regional_profile_national.py` | `--twin-mode hybrid` (기본) |
| `backend/.../regional_profile/router.py` | `/twins` — v6 우선, v5 fallback |
| `algorithm_version` | **6** (hybrid) |

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
