# 집합부동산 MVP — 로컬 실행 가이드

아파트 · 연립(다세대) · 오피스텔을 `collective_stats` DB에 적재하고, **건물 단위** 단가 통계·상세 회귀를 제공합니다. 토지·복합(built)과 **DB·API·SPA 분리**.

## 데이터 유형

| asset_type | 설명 |
|------------|------|
| apartment | 아파트 (단지명) |
| rowhouse | 연립·다세대 (건물명·주택유형) |
| officetel | 오피스텔 (단지명) |

정제 규격: [`참고/1.아파트 통합 정제.ipynb`](../참고/1.아파트%20통합%20정제.ipynb), [`2.연립`](../참고/2.연립다세대%20통합%20정제.ipynb), [`4.오피스텔`](../참고/4.오피스텔%20통합%20정제.ipynb) → 통합 [`pipeline/collective/refine.py`](../pipeline/collective/refine.py)

## 1. DB

```powershell
cd c:\ch2\ch2_Macro\pipeline\collective
py setup_db.py
py import_refined.py --refresh-region-codes
```

환경: `pipeline/.env.collective` → `COLLECTIVE_DATABASE_URL`

## 2. 백엔드

`backend/.env`에 `COLLECTIVE_DATABASE_URL` 설정 시 `/api/collective/*` 활성.

```powershell
cd c:\ch2\ch2_Macro\backend
uvicorn app.main:app --reload --port 8000
```

### API

- `GET /api/collective/meta/filters`
- `GET /api/collective/buildings` — 건물별 n·평균·중앙·95% CI
- `GET /api/collective/buildings/{key}/transactions`
- `GET /api/collective/buildings/{key}/stats/by-year`
- `GET /api/collective/buildings/{key}/histogram`
- `POST /api/collective/buildings/{key}/regression/run`

## 3. 프론트

```powershell
cd c:\ch2\ch2_Macro\frontend-collective
npm install && npm run dev
```

http://localhost:5175/collective/

VPS: https://macro.ch2data.com/collective/

## building_key

- **건물명 있음:** `asset_type + addr1~3 + building_name` (동명 단지 방지)
- **건물명 없음:** `asset_type + addr1~4 + lot_number + road_name`

상세: [`docs/COLLECTIVE_HANDOFF.md`](COLLECTIVE_HANDOFF.md)

## 다음 확장

- 집합상가 · 집합공장 (`asset_type` 추가)
- AI 회귀 해석
- 월간: [`docs/COLLECTIVE_MONTHLY_UPDATE_SOP.md`](COLLECTIVE_MONTHLY_UPDATE_SOP.md)
