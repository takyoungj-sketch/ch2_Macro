# 월간 집합부동산(collective) 데이터 업데이트 SOP

> **목표:** 매월 초 **토지 cycle 완료 후** 아파트·연립·오피스텔 정제 xlsx → `collective_stats` 갱신.  
> **기준 루트:** `C:\ch2\ch2_Macro`

관련: [`MONTHLY_UPDATE_SOP.md`](MONTHLY_UPDATE_SOP.md), [`BUILT_MONTHLY_UPDATE_SOP.md`](BUILT_MONTHLY_UPDATE_SOP.md), [`COLLECTIVE_RESEARCH_MVP.md`](COLLECTIVE_RESEARCH_MVP.md)

> **⚠ CSV Selenium 수집:** historical·backfill 시 [`MOLIT_CSV_COLLECTOR_WARNINGS.md`](MOLIT_CSV_COLLECTOR_WARNINGS.md) — 검증 없는 rename 금지.

---

## 1. 실행 순서

```
1) 토지: run_monthly_cycle.py → Promote
2) (선택) 복합 built: run_built_monthly_cycle.py
3) 집합: run_collective_monthly_cycle.py → 검증 → Promote collective_stats
```

**토지를 먼저** — `region_codes` 동기화.

---

## 2. cycle_id=202607 (2026년 7월 초)

| 항목 | 값 |
|------|-----|
| cycle_id | `202607` |
| 수집 연월 (규칙) | `202508` ~ `202606` (직전 12개월, land/built와 동일) |

```powershell
py scripts\monthly\run_collective_monthly_cycle.py --cycle-id 202607 --require-land-cycle
```

전환기 (raw 미구축):

```powershell
py scripts\monthly\run_collective_monthly_cycle.py --cycle-id 202607 --use-legacy-defaults --require-land-cycle
```

---

## 3. raw 디렉터리 (권장)

```
raw\집합부동산\{cycle_id}\
  apartment\*.xlsx
  rowhouse\*.xlsx
  officetel\*.xlsx
```

또는 GUKTO legacy:

- `아파트_매매\아파트_매매_정제\`
- `연립다세대_매매\연립다세대_매매_정제\`
- `오피스텔_매매\오피스텔_매매_정제\`

---

## 4. 검증

```powershell
py scripts\monthly\snapshot_collective_tx_counts.py --cycle-id 202607
py scripts\monthly\compare_collective_count_snapshots.py --before ... --after ...
```

- [ ] asset_type별 건수·시도별 diff
- [ ] `GET /api/collective/buildings?addr1=...&addr2=...` smoke
- [ ] `backups/collective_stats_pre_promote_202607.dump` 보관

---

## 5. VPS Promote

로컬 dump → scp → VPS restore (PG 버전 주의, built와 동일 plain SQL 경로).

`BUILT_HANDOFF` §5 Promote 절차 참고 — **collective_stats** 대상.

---

## 6. 미구현 (스켈레ton)

- MOLIT Selenium 수집 (`참고/0.수집.ipynb`) 스크립트화 — 2차
- `contract_month` 정밀 12개월 창
