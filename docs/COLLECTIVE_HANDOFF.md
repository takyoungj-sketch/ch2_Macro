# 집합부동산 — 인수·기술 메모

## 아키텍처

```
collective_stats
  collective_transactions  (거래 원장, building_key)
land_stats.region_codes  → sync → collective_stats.region_codes
/api/collective/*  →  frontend-collective (/collective/)
```

## 통일 정제 (canonical)

| 필드 | 설명 |
|------|------|
| building_name | 단지명(아파트·오피스텔) 또는 건물명(연립) |
| exclusive_area, price, unit_price | 전용면적, 만원, 만원/㎡ |
| floor, dong | 층·동 (아파트 dong은 raw col10) |
| area_bucket, age_bucket | round(면적/30)*30, round(연식/10)*10 |

## building_key / display_name

구현: [`pipeline/collective/building_keys.py`](../pipeline/collective/building_keys.py)

## 통계

토지와 동일 95% t-CI: [`backend/app/stats_utils.py`](../backend/app/stats_utils.py), `MIN_RELIABLE_COUNT=15`

## 월간

[`COLLECTIVE_MONTHLY_UPDATE_SOP.md`](COLLECTIVE_MONTHLY_UPDATE_SOP.md) · `run_collective_monthly_cycle.py`

## 202607 업데이트

1. 토지 `run_monthly_cycle.py --cycle-id 202607` → Promote
2. GUKTO 정제 xlsx 갱신
3. `run_collective_monthly_cycle.py --cycle-id 202607 --require-land-cycle`
4. snapshot/compare → VPS Promote (built와 독립)
