# CH2 Macro 관리자

> **작성:** 2026-08-16  
> **성격:** 관리자·개발 전용. **공개 게이트웨이 카드에 없음.**  
> **로컬:** http://localhost:5179/lab/  
> **운영:** https://macro.ch2data.com/lab/ — 게이트웨이 카드 없음. Nginx Basic Auth (D-061).

홈은 출입문만 둡니다.

| 문 | `?tool=` | 하는 일 |
|----|----------|---------|
| 계획일지 | `plan` | 토지·복합·집합·임대·지역프로필·관리 표. SSOT `docs/lab/plan.json` |
| 검증로봇 | `qa` | 집합 L1–L3 (D-042) · 복합 보강 `built_enriched` (D-047) |
| 쌍둥이 지역 실험 | `twin` | V2 거리(D-044, 기본) · V1 풀 CV-MAPE (`?pane=mape`) · 읍면동 권역 확장 기록 (`?pane=scope`, 카드 범위는 권역 유지) · Fingerprint 재순위 `fingerprint-twin-chungbuk12`·`fingerprint-twin-gyeonggi12`(다음=붙임 실험, [`lab/FINGERPRINT_TWIN_LAB.md`](./lab/FINGERPRINT_TWIN_LAB.md)) |
| 전월세 전환율 | `rent` | 4방법 r · 서울 검증 (D-040) |
| AI 사용량 | `ai` | 월 LLM 호출·추정 원 장부. 질문 문장 없음 |
| 대장DB | `parcel` | 로컬 `parcel_master` 필지·동·용도지역 조회. 읽기 전용. 운영 DB 없음. 설계 [`PARCEL_MASTER_DESIGN.md`](./PARCEL_MASTER_DESIGN.md) · 월간 [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md) |
| 시장 규모의 관계 | `size` | 같은 체급 log 거래액·건수 r + 인구 보정, ① n붕괴 · ② 시군구 내부 규모 · ③ ㎡당 P50(인구보정 없음) · ④ 시군구 내부 단가 (D-058, 장기). 프로필 8×8 없음. G3 시계열 없음 |
| 유동성·금리 시계열 | `g3` | 월·연 모두 국토부 CSV 전국 합 마트(2026-09-16). 연은 월 합, 미완결연 제외. M2·CD·기준금리·국고3년 전년(동월) × 8유형 건수·액 YoY, 월 시차 0/1/3/6 (D-055). Insight #1은 월 |
| 신규아파트 실험 | `newapt` | 대전 M2 잠정 · 충북 전이 · 학습/검증/오차. 집합 기본통계 버튼 없음. 상품화는 실험 후 (D-045) |
| 시공사 효과 | `builder` | 공시지가 vs 시군구 FE · within-gu. **다음=브랜드 vs 시공사.** 제품 식 미변경 (D-063·D-065) |
| 연식=0 잔차 | `age0` | 재고 식 연식=0 vs 실제 신축. **다음=서울·경기 분리.** 전국 공통 프리미엄 미가산 (D-064) |
| 모형추천 Twin 벤치 | `recommend-twin` | Local / Twin1 / Twin2 × 지역더미 전후. 실험 Twin은 1위만. 제품 식은 Twin1=1위+더미, Twin2=확인용 재탐색. [`lab/RECOMMEND_TWIN_BENCH_LAB.md`](./lab/RECOMMEND_TWIN_BENCH_LAB.md) |
| 토지 면적 탄성 | `area-elasticity` | 1–3차 정리(교차표). **차후=용도지역 분할.** Insight 4번 본문. 제품 식 미변경 |
| 연립·다세대 층·승강기 | `rowhouse-floor` | 3차 기록. **최상×승강기 가산 합의.** 제품 층 식 미변경 |
| 연 거래액 규모·구성 | `macro-scale` | GDP·M2·주식 대비 연 거래액 비율 + 8유형 구성. G3와 별문. Insight 5번 본문 |
| 도로 지목 상대가격 | `road-jimok` | 읍면동×용도에서 도로/대·전·답 중앙단가 비. 공개는 Insight 6번. 도시 전체 %는 본문에 없음 |
| 층 효용 기록 | `floor-utility` | 아파트(종료, Insight 8)·오피스텔(저층=100, 차이 2포인트 안, 8번 맨 끝)·집합상가(종료, Insight 10). 숫자는 서로 더하지 않음. 제품 층 식 미변경 |
| 수익률 비교 | `yield-compare` | 전국 2021–2025 표. 상업 오피스·상가 공표, 주거 월세환산, 국고 3년, KODEX KOSPI TR. 공개는 #11 |
| 상권과 아파트 | `sangkwon-apt` | 2021–2025 상권 수익률과 경계가 겹치는 읍면동 아파트. 공개 `/insight/?q=12` |

공개 게이트웨이 **Macro Insight**(6번째 문)는 `/insight/`. 1번(금리·시중 돈과 거래) [`MACRO_INSIGHT_01.md`](./MACRO_INSIGHT_01.md) · 2번(유형 규모·단가 상관) [`MACRO_INSIGHT_02.md`](./MACRO_INSIGHT_02.md) · 3번(연립·다세대 층×승강기) [`MACRO_INSIGHT_03.md`](./MACRO_INSIGHT_03.md) · 4번(토지 면적×㎡당 가격) [`MACRO_INSIGHT_04.md`](./MACRO_INSIGHT_04.md) · 5번(연 거래액/GDP·M2·주식·유형 구성) [`MACRO_INSIGHT_05.md`](./MACRO_INSIGHT_05.md) · 6번(도로 지목 상대가격) [`MACRO_INSIGHT_06.md`](./MACRO_INSIGHT_06.md) · 7번(쌍둥이 지역을 고르는 방법) [`MACRO_INSIGHT_07.md`](./MACRO_INSIGHT_07.md) · 8번(아파트 윗층과 지역·높이) [`MACRO_INSIGHT_08.md`](./MACRO_INSIGHT_08.md) · 10번(집합상가 도로의 1층과 2층) [`MACRO_INSIGHT_10.md`](./MACRO_INSIGHT_10.md). 결정 카드 없음. 랩 `?tool=size`는 실험실로 남긴다.

G3 시계열 랩: [`lab/G3_TIMESERIES_LAB.md`](./lab/G3_TIMESERIES_LAB.md) · `?tool=g3`.  
G3·Insight 월 합 출처 수정: [`lab/MACRO_TS_RAW_MONTH_MART.md`](./lab/MACRO_TS_RAW_MONTH_MART.md) (원장 대신 raw CSV 전국 월 마트).
신규아파트 실험: [`NEW_APARTMENT_REGRESSION_DESIGN.md`](./NEW_APARTMENT_REGRESSION_DESIGN.md) · `?tool=newapt`.
시공사 효과: [`lab/BUILDER_IDENT_LAB.md`](./lab/BUILDER_IDENT_LAB.md) · `?tool=builder`.
연식=0 잔차: [`lab/AGE0_RESIDUAL_LAB.md`](./lab/AGE0_RESIDUAL_LAB.md) · `?tool=age0`.
모형추천 Twin 벤치: [`lab/RECOMMEND_TWIN_BENCH_LAB.md`](./lab/RECOMMEND_TWIN_BENCH_LAB.md) · `?tool=recommend-twin`.
토지 면적 탄성(광평수): [`lab/LAND_AREA_ELASTICITY_LAB.md`](./lab/LAND_AREA_ELASTICITY_LAB.md) · `?tool=area-elasticity` — 1–3차 정리. 차후=용도지역 분할. 공개 기록은 Insight #4. 제품 식 미변경.
연립·다세대 층·승강기: [`lab/ROWHOUSE_FLOOR_ELEVATOR_LAB.md`](./lab/ROWHOUSE_FLOOR_ELEVATOR_LAB.md) · `?tool=rowhouse-floor` — 3차 최상×승강기 가산 합의. 공개 기록은 Insight #3. 제품 층 식 미변경.
연 거래액 규모(GDP·M2·주식·유형 구성): [`lab/MACRO_ANNUAL_SCALE_LAB.md`](./lab/MACRO_ANNUAL_SCALE_LAB.md) · `?tool=macro-scale`. 공개 기록은 Insight #5. G3와 문을 섞지 않음.
도로 지목 상대가격: [`lab/LAND_ROAD_JIMOK_RATIO_LAB.md`](./lab/LAND_ROAD_JIMOK_RATIO_LAB.md). 랩 `?tool=road-jimok`. 공개는 [`MACRO_INSIGHT_06.md`](./MACRO_INSIGHT_06.md) `/insight/?q=6`. 제품 토지 식 미변경.
아파트·오피스텔·집합상가 층 효용 기록 창: `?tool=floor-utility`. 아파트는 [`lab/APT_FLOOR_UTILITY_LAB.md`](./lab/APT_FLOOR_UTILITY_LAB.md), 공개 [`MACRO_INSIGHT_08.md`](./MACRO_INSIGHT_08.md) `/insight/?q=8`. 오피스텔은 [`lab/OFFICETEL_FLOOR_UTILITY_LAB.md`](./lab/OFFICETEL_FLOOR_UTILITY_LAB.md). 저층=100, 차이는 2포인트 안, 공개는 #8 맨 끝. 집합상가는 [`lab/SHOP_FLOOR_UTILITY_LAB.md`](./lab/SHOP_FLOOR_UTILITY_LAB.md), 공개 [`MACRO_INSIGHT_10.md`](./MACRO_INSIGHT_10.md) `/insight/?q=10`. 세 숫자는 더하지 않음. 제품 층 식 미변경.
수익률 비교: [`lab/YIELD_COMPARE_LAB.md`](./lab/YIELD_COMPARE_LAB.md) · `?tool=yield-compare`. 스냅샷 [`lab/yield_compare_national.json`](./lab/yield_compare_national.json). 공개 [`MACRO_INSIGHT_11.md`](./MACRO_INSIGHT_11.md) `/insight/?q=11`. #1·#5와 문을 섞지 않음.
계획일지 표 규칙:

- 열은 제품 축과 같다. 집합을 주거/비주거로 쪼개지 않는다.
- 빈 날짜 행은 만들지 않는다.
- 행은 과거(있는 날만) · 오늘 · 다음 · 공통.
- 「왜」는 결정 카드만 연다. 화면에서 표를 편집하지 않는다.
- 하루를 끝낼 때 「계획일지 정리」라고 하면 Cursor가 `plan.json`·일지를 갱신한다. **정리 ≠ 커밋.**
- 칸에 커밋 상태(`committed` / `needed` / `none`)를 적는다. 축별로 어디서 멈췄는지 본다.

일지 원본 `docs/lab/journal/` · 결정 원장 [DECISIONS.md](./DECISIONS.md).

운영 주소는 주소창에 `https://macro.ch2data.com/lab/` 을 직접 치거나 북마크합니다. 브라우저가 비밀번호를 묻습니다. 배포: `deploy-from-windows.ps1 -Scope lab`. 비밀번호 재발급: VPS `sudo bash /opt/ch2_Macro/deploy/scripts/setup-ch2-lab-auth.sh` 에 `CH2_LAB_AUTH_PASS`를 넣어 실행.
