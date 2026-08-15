# 주거 전월세(A)

> **상태:** 원장·건물 마트·목록 UI · **전환율 연구 종료 · `mean_simple` 확정 (D-040)** · **B 상권 병기(하위시장)** · **매매 조인=차후(3안)**  
> **실험 SSOT:** [`RENT_CONVERSION_EXPERIMENT.md`](./RENT_CONVERSION_EXPERIMENT.md)  
> **원천:** `임대시장/A.주거용/{유형}_전월세_*/*.csv` (레포 미포함)  
> **DB:** `rent_stats.rent_transactions` · 14,466,608행 (2019–2026)  
> 아파트 7,462,935 · 단독 3,565,386 · 연립 1,801,938 · 오피스텔 1,636,349.

## 규칙

- 신고 보증금·월세를 덮어쓰지 않는다. 환산 컬럼을 원장·마트에 두지 않는다.
- 단가: `deposit_per_m2`, `monthly_per_m2`. 면적=전용(아파트·연립·오피), 단독=계약면적.
- 목록은 **건물 1행**. 전세 / 반전세 / 월세를 한 단가로 합치지 않는다.
  - 전세: 보증금/㎡ (월세=0)
  - 반전세: 보증금/㎡ **와** 월세/㎡ (둘 다 >0)
  - 월세: 월세/㎡만 (보증금=0)
- 목록 칸은 n + P50. 평균·95% CI·롤링은 상세. n&lt;15 표시.
- 임대 헤더에 토지/복합/집합 탭을 넣지 않는다. 홈(`/`)만 매매·임대 분기.

## 3층

1. 원장 — ingest  
2. 표준화 — `jeonse` / `monthly` / `mixed` 뷰  
3. 분석 — `rent_conversion_rates` (지역×유형×창 r) · 목록 환산은 API 분석층

## 전환율 (CH2 자체 산출)

- **외부 공표(한국부동산원)를 매칭·고정값(5%)으로 쓰지 않는다.** REB r은 채택 후 교차검증만.
- **원장·건물 마트에 환산 컬럼을 두지 않는다.** r과 환산 대표값은 분석층.
- **grain:** 시군구(`addr1`+`addr2`) × 주택유형(`apartment`/`rowhouse`/`officetel`/`detached`) × 롤링 3·5·7년. `as_of`는 건물 마트와 동일(직전 월말).
- **식별:** 창 안 **같은 건물**에 전세·반전세가 모두 있을 때만. 전세 P50=\(J\), 반전세 보증금·월세 P50=\(D,M\)(㎡당). 순수월세는 r 식별에 쓰지 않음. 1차 식별 유형: 아파트·연립·오피(단독 `building_key` 약함).
- **경제식:** \(r = 12M/(J-D)\) (%). 건물별 \(r_b\) 후 지역 집계.
- **4후보 (마트에 모두 유지. 적용만 교체):**

| 후보 | 내용 | 역할 |
|------|------|------|
| `mean_simple` | 건물 \(r_b\) 단순평균 | **확정 기본 (`r_selected`)** |
| `mean_weighted` | \(r_b\)에 \(\min(n_{전세},n_{반전세})\) 가중 | 보관 |
| `ols_origin` | \(Y=12M\), \(X=J-D\), 절편 0 | 경제식 후보·실험 화면 |
| `ols_weighted` | 원점회귀 + 식별 n 가중 | 보관. 적용 비추천 |

- **채택 기준 (2026-08 서울 검증 후, 연구 종료):** “경제적 관계 추정”이 아니라 **반전세→전세환산이 실제 전세 P50에 가까운가**(hold-out MAPE). 시군구·동 × 3·5·7 여섯 조건 모두 `mean_simple` 1위. 4방법 재실험·연립 전용 산식은 하지 않음. 상세: [`RENT_CONVERSION_EXPERIMENT.md`](./RENT_CONVERSION_EXPERIMENT.md).
- **게이트:** (1) 식별 가능 건물 수 ≥ 임계 (2) 해당 건물들의 전세·반전세 건수 각 ≥ 임계. 미달 시 r 없음 → 상위 grain fallback. 임계: [`pipeline/rent/conversion.py`](../pipeline/rent/conversion.py).
- **적용:** 3↔3, 5↔5, 7↔7. 읍면동 `mean_simple` → 게이트 실패 시 시군구 `mean_simple`. 사용자 화면은 `적용 전환율 5년 5.1%`만. 방법명·4방안은 실험/관리 화면.
- **모달:** 건물 \(r_b\) · 지역 r · 선택 건물 풀 r + 원 3유형. 풀도 \(r_b\) 단순평균. 정의 문구: “지역·주택유형·N년 거래자료를 이용해 산출한 전환율”.
- **검증 리포트:** [`pipeline/rent/_seoul_conversion_validate.json`](../pipeline/rent/_seoul_conversion_validate.json) · UI「검증 결과」. 상시 재계산 아님.

### 서울 5년 커버리지 (2026-07 as_of)

| 유형 | 시군구 | 게이트 통과 | 식별 건물 P50 | 전세 n P50 | 반전세 n P50 |
|------|--------|------------|--------------|-----------|-------------|
| apartment | 25 | 25/25 | 180 | 24,024 | 16,372 |
| rowhouse | 25 | 25/25 | 561 | 4,908 | 4,479 |
| officetel | 25 | 25/25 | 90 | 3,027 | 7,169 |

임계 `MIN_REGION_BUILDINGS=5`, `MIN_REGION_JEONSE/MIXED=30`, 건물별 각 3건 — 서울 기준 충분. 상세 JSON: `pipeline/rent/_seoul_5y_coverage.json`.

### 전환율 연구 — 종료 (2026-08-15)

방법론은 닫았다. 기록·`?`·AI 답변 SSOT: [`RENT_CONVERSION_EXPERIMENT.md`](./RENT_CONVERSION_EXPERIMENT.md).

| 항목 | 상태 |
|------|------|
| `mean_simple` 확정 | 완료 |
| 전국 3·5·7 마트 | 완료 (batch `5d3801b7eb08`). 세종은 `__FLAT_SIDO__`(시 전체=`addr2` 공백) |
| 읍면동 → 시군구 fallback | 완료 |
| 전세/월세 환산 API·목록·상세 | 완료 |
| `?` 팝업 · AI 채택 이유 | 제품 반영 |
| 사람 몇 지역 확인 | 실험 문서 §7 체크리스트 |

산식·게이트·4열을 더 바꾸지 않는다. \(r_b\) 분포는 품질 확인용이다.

## 적재

```powershell
py pipeline/rent/import_molit.py
py pipeline/rent/build_building_stats.py
py pipeline/rent/build_conversion_rates.py --method mean_simple
py pipeline/rent/import_sangkwon.py
# 서울 r_b 분포: py pipeline/rent/report_rb_distribution.py
# 검증(완료, 재실행 불필요): pipeline/rent/_seoul_conversion_validate.json
```

DDL: [`db/055_rent_transactions.sql`](../db/055_rent_transactions.sql) · [`db/056_rent_building_stats.sql`](../db/056_rent_building_stats.sql) · [`db/057_rent_conversion_rates.sql`](../db/057_rent_conversion_rates.sql)  
로컬 UI: http://localhost:5178/rent/

## 차후: 매매 창 조인 (3안, 2026-08 확정)

매매와 임대를 **원장·마트·진입에서 합치지 않는다.** 홈(`/`) 매매/임대 분기와 임대 전용 화면을 유지한다. 사용자가 한 건물에서 매매·전월세를 같이 보는 것은 **분석층 조인 뷰**로 나중에 붙인다.

하지 않는 것:

- 매매 목록이 임대의 SSOT가 되게 합치기 (매매 없는 건물의 임대가 사라짐)
- 매매 원장·마트에 환산·수익률 컬럼 저장
- 시군구 r로 환산한 전세를 그 건물 고유 수익률처럼 단정
- 단독다가구 강제 매칭 (주소 마스킹, `building_key` 약함)

조인 범위:

| 대상 | 조인 | 비고 |
|------|------|------|
| 아파트·연립·오피 | 주소/`building_key` 매칭 가능 시 | 1차 |
| 단독다가구 | 안 함 | 임대 화면에만 |
| 임대만 있는 건물 | 매매 목록에 끼워 넣지 않음 | 임대 화면에 남김 |
| 매칭 실패 | “조인 없음” 명시 | 없는 것처럼 숨기지 않음 |

매매 상세(같은 창)에 붙일 임대 패널: 전세/반전세/월세 원값 + 적용 r + 환산 P50 + n. 창 정합은 임대와 동일(3↔3, 5↔5, 7↔7). 임대 상세에 매매 패널을 다는 것은 같은 조인의 반대 방향이며 필수는 아님.

구현 순서:

1. 유형별 매칭률·매매만/임대만 비율 커버리지 리포트 (게이트와 같은 한계 노출)
2. 매칭 가능한 유형부터 매매 건물 상세에 임대 패널
3. 수익성(환산전세/매매 등)은 커버리지 통과 후에만 회귀 **후보 변수**. 기본 통계의 대표값이 되지 않게 함

### 상업용 B (임대 화면 병기)

B는 CH2 원장 조인이 아니다. 한국부동산원 상업용부동산 임대동향조사 **하위시장(상권)** 공표를 주거 임대 화면에 병기한다. 거래 원장·전환율·회귀와 섞지 않는다. 공표 정의·표본·산출식: [`REB_COMMERCIAL_RENT_SURVEY.md`](./REB_COMMERCIAL_RENT_SURVEY.md).

- 원천: `임대시장/B.상업용/` 공식 xlsx + `상권구획도2024.shp` (커스텀 통합 엑셀 없음)
- 마트: `rent_sangkwon` · `rent_sangkwon_quarterly` (`db/059_rent_sangkwon.sql`)
- 적재: `py pipeline/rent/import_sangkwon.py`
- 화면: 주거 목록과 섞지 않음. 「통계분석」 아래 **상권분석** 모달. 범위는 선택한 동의 시군구(구)와 교차하는 상권. 본문 지도에는 상권 없음. 모달 지도에 시군구 경계+상권 윤곽.
- 본문 = 최신 연도 연간값. 임대료·층별임대료는 **월단가 평균×12**(만원/㎡·년). 순영업소득 금액은 **4분기 합**(만원/㎡·년). 소득·자본·투자수익률은 **4분기 복리**. 구성비·공실·전환율·지수는 분기 평균. 동수·층수·면적은 그 해 마지막 분기. 4분기 없으면 금액·수익률은 빈칸.
- 모달: 2019년~ 연간 꺾은선. 주거 3/5/7 창과 묶지 않음.
- 오피스 규모별 서울광역(`104`·`106`) 제외. 층별 10층↓/11층↑(`109`–`112`)는 저장만.
