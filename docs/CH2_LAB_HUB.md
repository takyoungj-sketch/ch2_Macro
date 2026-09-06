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
| 쌍둥이 지역 실험 | `twin` | V2 거리(D-044, 기본) · V1 풀 CV-MAPE (`?pane=mape`) |
| 전월세 전환율 | `rent` | 4방법 r · 서울 검증 (D-040) |
| AI 사용량 | `ai` | 월 LLM 호출·추정 원 장부. 질문 문장 없음 |
| 대장DB | `parcel` | 로컬 `parcel_master` 필지·동·용도지역 조회. 읽기 전용. 운영 DB 없음. 설계 [`PARCEL_MASTER_DESIGN.md`](./PARCEL_MASTER_DESIGN.md) · 월간 [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md) |
| 시장 규모의 관계 | `size` | 같은 체급 log 거래액·건수 r + 인구 보정, ① n붕괴 · ② 시군구 내부 규모 · ③ ㎡당 P50(인구보정 없음) · ④ 시군구 내부 단가 (D-058, 장기). 프로필 8×8 없음. G3 시계열 없음 |
| 유동성·금리 시계열 | `g3` | 전국 연도 M2·CD·기준금리·국고3년 변화 × 8유형 건수·액 YoY (D-055). Insight 아님 |

공개 게이트웨이 **Macro Insight**(6번째 문)는 구상만. 랩 실험 전부를 올리지 않고, 선별 배포. 계획 [`MACRO_INSIGHT_PLAN.md`](./MACRO_INSIGHT_PLAN.md). 구현·결정 카드 없음.

G3 시계열 랩: [`lab/G3_TIMESERIES_LAB.md`](./lab/G3_TIMESERIES_LAB.md) · `?tool=g3`.

계획일지 표 규칙:

- 열은 제품 축과 같다. 집합을 주거/비주거로 쪼개지 않는다.
- 빈 날짜 행은 만들지 않는다.
- 행은 과거(있는 날만) · 오늘 · 다음 · 공통.
- 「왜」는 결정 카드만 연다. 화면에서 표를 편집하지 않는다.
- 하루를 끝낼 때 「계획일지 정리」라고 하면 Cursor가 `plan.json`·일지를 갱신한다. **정리 ≠ 커밋.**
- 칸에 커밋 상태(`committed` / `needed` / `none`)를 적는다. 축별로 어디서 멈췄는지 본다.

일지 원본 `docs/lab/journal/` · 결정 원장 [DECISIONS.md](./DECISIONS.md).

운영 주소는 주소창에 `https://macro.ch2data.com/lab/` 을 직접 치거나 북마크합니다. 브라우저가 비밀번호를 묻습니다. 배포: `deploy-from-windows.ps1 -Scope lab`. 비밀번호 재발급: VPS `sudo bash /opt/ch2_Macro/deploy/scripts/setup-ch2-lab-auth.sh` 에 `CH2_LAB_AUTH_PASS`를 넣어 실행.
