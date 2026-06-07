# 건축물대장(표제부) 연계 — 향후 작업 로드맵

> **작성:** 2026-06-06 · **상태:** 검토·문서화 완료, **구현 보류**  
> **원칙:** 지번을 100% 확정하기 위한 매칭이 아니라, **구조·층수·용도·승인일** 등 건물 특성을 **확률적으로** 보강한다.

---

## 1. 배경

CH2 Macro는 **국토부 실거래가** 기반이다. 원천 한계:

| 한계 | 영향 |
|------|------|
| **번지 마스킹** (`5**`, `7**` 등) | 복합부동산 거래 **100%** 마스킹 (로컬 `built_stats` 기준) |
| **구조 정보 부재** | 복합 회귀에 철근콘크리트·목구조 등 변수 불가 |
| **23년 이전 주소 품질** | 집합부동산 `addr4`(동) 공란 다수 — 단지·동 식별 약함 |
| **면적 정의 불일치** | 실거래 `연면적` ≠ 대장 `연면적`(건물 전체), `건축면적`·`대지면적`은 원천에 없거나 불완전 |

**보유 원본**

```
원본/국토교통부_건축물대장_표제부+(2026년+04월)/
  mart_djy_03.txt          # 약 3.5GB, 804만 행, 전국, 파이프(|) 77필드
  03. 표제부_*.xlsx        # 동일 스키마 샘플 (77컬럼)
```

**실측 요약 (2026-06 검토)**

- 전국 **804만** 행 (충북 **45.9만**)
- 대장 종류: 일반건축물 **739만** / 표제부(집합) **65.7만**
- 구조 종류: RC·벽돌·철골 등 **15종+** (상위 5~6종으로 축약 가능)
- 집합(공동주택류) 표제부 **57.7만** — 도로명 **99%**, 건물명 **78%**
- MOLIT `beopjungri_code`(10자리) ↔ 대장 필드 `[17]` 앞 10자리 **호환**

---

## 2. 전략 (판단 기준)

### 2.1 하는 것

- 대장을 **별도 마스터 테이블**로 적재 후, 거래 원장과 **LEFT JOIN enrichment**
- 매칭 결과에 **`match_tier`** · **`match_confidence`** · **`structure_name`** 등 부가
- 회귀·UI는 tier A/B(또는 단일 후보 fuzzy)만 “건물 특성 확정”으로 취급
- tier C/D는 “참고” 또는 구간 평균(生態学적) 변수로만 사용

### 2.2 하지 말 것

| 보류 | 이유 |
|------|------|
| **전 거래 지번 100% 복원** | 수 주~수 개월 투입 대비 ROI 매우 낮음. 마스킹 `5**`는 동일 법정리 내 **1:N** 후보 불가피 |
| **대지·건축·연면적 동시 exact match** | 실거래는 층·호·지분 거래, 대장은 건물 전체 기준 — **동시 일치 확률 극히 낮음** |
| **3.5GB txt 매번 on-the-fly 조인** | VPS·로컬 모두 비효율 → **DB 1회 적재** 전제 |

### 2.3 면적을 쓸 때의 원칙

- `gross_area`(실거래) vs 대장 `연면적`/`건축면적`: **hard filter 금지**, **후보 순위·신뢰도** 보조만
- 충북 복합 실측: `beopjungri + lot_prefix`만 → 후보 **88%**, 구조 1종 확정 **11%**
- 여기에 연면적 **0.1㎡ exact** 추가 → 후보 **2.8%**로 급감 (97% 탈락)
- **상대 오차(±5~10%) + 최근접 1건**은 scoring용으로 검토 가능하나, “확정” tier로 승격하려면 2등과 격차 검증 필요

---

## 3. 우선순위 (CH2 로드맵)

```
1순위  building_register_title 적재     ← 구축 무조건
2순위  structure 변수 (RC·철골·벽돌·목·기타)
3순위  지상층수 · 지하층수 · 사용승인일
4순위  집합 building_key 개선
```

각 단계는 **이전 단계 완료·검증 후** 착수. 2·3순위는 1순위 없이 진행하지 않음.

---

## 4. 1순위 — `building_register_title` 적재

### 4.1 목표

건축물대장 표제부를 **CH2 전용 DB**(또는 `built_stats` / `collective_stats` 공용 스키마)에 정규화 적재.

### 4.2 테이블 개요 (안)

| 컬럼군 | 예시 | 비고 |
|--------|------|------|
| PK | `mgmt_pk` | 대장 `[0]` 관리건축물대장PK |
| 대장 구분 | `ledger_kind` | 일반건축물 / 표제부 |
| 행정 코드 | `beopjungri_code`, `sigungu_code`, `bjdong_code`, `bun`, `ji` | 조인 핵심 |
| 주소 | `plat_addr`, `road_addr`, `addr1`~`addr4`, `lot_norm` | 파싱·정규화 |
| 건물 특성 | `structure_code`, `structure_name`, `main_purpose`, `total_area`, `arch_area`, `plat_area` | 2·3순위 입력 |
| 층·승인 | `grnd_flr_cnt`, `ugrnd_flr_cnt`, `use_apr_day` | 3순위 |
| 집합 | `building_name`, `ho_cnt`, `hhld_cnt` | 4순위 |
| 메타 | `source_month`, `crtn_day`, `loaded_at` | 2026-04 스냅샷 |

**인덱스 (안):**

- `(beopjungri_code, bun, ji)` — exact tier
- `(addr1, addr2, addr3, lot_norm)` — plat 파싱 조인
- `(road_addr_norm, building_name_norm)` — 집합·상가
- `(beopjungri_code, bun_prefix)` — 마스킹 prefix 후보 풀

### 4.3 파이프라인 (안, 미구현)

```
원본/mart_djy_03.txt
  → pipeline/br/ingest_title.py   # 청크 파싱, region_codes 정규화
  → building_register_title
  → pipeline/br/report_coverage.py  # 행정구·구조·용도 분포 리포트
```

### 4.4 완료 기준

- [ ] 전국 804만 행 적재 (중복 PK 정책 문서화)
- [ ] 충북·서울 등 표본 지역 **beop+bun+ji** exact self-join 100%
- [ ] 원본 txt 경로·`source_month` 메타 기록
- [ ] `.gitignore` — txt 원본은 Git 미포함 유지

---

## 5. 2순위 — 구조(`structure`) 변수

### 5.1 목표

**복합부동산** OLS 회귀에 `structure_dummy` 추가 (`backend/app/built/regression/engine.py`).

### 5.2 구조 축약 (5종, 안)

| 더미 | 대장 `structure_name` 매핑 예 |
|------|------------------------------|
| `RC` | 철근콘크리트구조, 철골철근콘크리트, (철근)콘크리트 |
| `steel` | 일반철골, 경량철골, steel 계열 |
| `masonry` | 벽돌구조, 블록구조, 석조 등 |
| `wood` | 목구조, 일반목구, 기와 등 |
| `other` | 기타·미매칭 |

### 5.3 매칭 tier (enrichment)

| Tier | 조건 | 회귀 사용 |
|------|------|-----------|
| **A exact** | `beopjungri + bun + ji` 일치 | ✅ 구조 확정 |
| **B single fuzzy** | `beop + lot_prefix` 후보 1종, 또는 면적·용도 score 1등·2등 격차 큼 | ✅ (confidence 표시) |
| **C multi** | 후보 2종+ | ❌ — 구간 평균 또는 제외 |
| **D none** | 후보 없음 | ❌ — `structure` 결측 |

### 5.4 기대 커버리지 (보수적)

| 대상 | tier A+B (추정) | 비고 |
|------|-----------------|------|
| 복합 `built_transactions` | **30~50%** | 지역·유형별 편차 |
| 연립·다세대 (지번 clear) | **50~70%** | addr 정규화 품질에 의존 |

### 5.5 완료 기준

- [ ] `built_transactions` 또는 enrichment view에 `structure_name`, `match_tier` 컬럼
- [ ] 회귀 UI·API에 `structure_dummy` 옵션 (tier A+B 필터 또는 전체+플래그)
- [ ] 충북·광주 등 **표본 지역** match rate 리포트

---

## 6. 3순위 — 층수·사용승인일

### 6.1 필드

| 필드 | 대장 | 활용 |
|------|------|------|
| `grnd_flr_cnt` | 지상층수 | 복합·집합 연식·규모 보조, 층 변수 검증 |
| `ugrnd_flr_cnt` | 지하층수 | 상가·지하 가격 패턴 |
| `use_apr_day` | 사용승인일 | `building_age` 교차 검증, 준공 불일치 탐지 |

### 6.2 주의

- 실거래 `building_age` / `building_year`와 승인일 **±1~2년** 차이 허용
- 증축·용도변경 건은 대장 시점(2026-04)과 과거 거래 불일치 가능 → UI “대장 기준” 명시

### 6.3 완료 기준

- [ ] enrichment에 3필드 추가
- [ ] 집합·복합 모달 또는 거래 목록에 “대장 층수/승인일 (tier)” 참고 컬럼 (선택)

---

## 7. 4순위 — 집합 `building_key` 개선

### 7.1 목표

[`COLLECTIVE_COMMERCIAL_DESIGN.md`](COLLECTIVE_COMMERCIAL_DESIGN.md) §4 **building_key_v2**와 연계.

- **아파트·연립:** 단지명 + 도로명 ↔ 표제부 **57.7만** 행
- **마스킹 상가:** tier C — 도로 cluster 유지, building_key는 High tier만
- [`pipeline/collective/building_keys.py`](../pipeline/collective/building_keys.py) — `building_key_v2` 분기 (표제부 PK 또는 normalized key)

### 7.2 기대 효과

- 23년 이전 **addr4 공란** — 표제부 `plat_addr`에서 동·리·번지 후보 복원 (**확률적**, tier 표시)
- **지번 exact 복원 아님** — 단지·건물 클러스터 해상도 향상이 목표

### 7.3 완료 기준

- [ ] `building_key_v2` + `resolution_mode` (`ledger` / `name_road` / `legacy`)
- [ ] collective UI tier 라벨 (“대장 매칭 · 높음/보통/미상”)
- [ ] 상가 2단계 착수 조건([`COLLECTIVE_COMMERCIAL_DESIGN.md`](COLLECTIVE_COMMERCIAL_DESIGN.md) §8) 재평가

---

## 8. 대상 DB·앱 매핑

| 앱 | DB | 1순위 | 2순위 | 3순위 | 4순위 |
|----|-----|-------|-------|-------|-------|
| 복합 `/built/` | `built_stats` | ✅ | ✅ **주력** | ✅ | — |
| 집합 `/collective/` | `collective_stats` | ✅ | △ (연립) | ✅ | ✅ **주력** |
| 집합상가 | `collective_stats` | ✅ | △ | △ | ✅ tier High만 |

**토지 `/land/`:** 범위 외 (건축물대장 미사용).

---

## 9. 의존·선행 작업

| 선행 | 내용 |
|------|------|
| `region_codes` | beopjungri ↔ 행정명 — [`pipeline/built/import_refined.py`](../pipeline/built/import_refined.py) 동기화 정책 유지 |
| 디스크 | txt 3.5GB + PG 인덱스 **~10GB+** 여유 (로컬·VPS) |
| 월간 배치 | 대장 **분기·반기** 갱신 빈도 검토 (실거래 월간과 분리) |

---

## 10. 리스크·미결정

| 항목 | 메모 |
|------|------|
| DB 위치 | `built_stats` 단독 vs 공용 `reference` DB — Promote·백업 정책 후 결정 |
| VPS | 4GB RAM — 804만 행 ingest 시 batch·인덱스 지연 생성 |
| 법적 | 공공데이터 이용약관·2차 가공 표시 — UI footer 한 줄 |
| 면적 scoring | ±5% vs ±10%, 2등 격차 threshold — 2순위 착수 시 파일럿 |

---

## 11. 관련 문서

| 문서 | 관계 |
|------|------|
| [`COLLECTIVE_COMMERCIAL_DESIGN.md`](COLLECTIVE_COMMERCIAL_DESIGN.md) | building_key 2단계, 마스킹 tier |
| [`BUILT_HANDOFF_AND_ROADMAP.md`](BUILT_HANDOFF_AND_ROADMAP.md) | 복합 MVP·월간 배치 |
| [`BUILT_RESEARCH_MVP.md`](BUILT_RESEARCH_MVP.md) | 복합 API·회귀 변수 |
| [`docs/DECISIONS.md`](DECISIONS.md) | 착수 시 D-xxx 결정 항목 추가 권장 |

---

## 12. 한 줄 요약

**`building_register_title` 적재 → 구조 5종 변수 → 층수·승인일 → 집합 building_key_v2.**  
지번 완전 복원·면적 exact match는 하지 않는다. **확률적 tier 매칭으로 건물 특성만 보강.**

---

*구현 착수 전 이 문서와 [`DECISIONS.md`](DECISIONS.md)에 스냅샷 월·DB 위치·tier 정의를 확정할 것.*
