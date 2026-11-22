# 월간 집합부동산(collective) 데이터 업데이트 SOP

> **목표:** 매월 초 **토지 cycle 완료 후** 아파트·연립·오피스텔 → `collective_stats` 갱신.  
> **기준 루트:** 저장소 루트. 예: `C:\ch2\ch2_Macro` · `E:\ch2\ch2_Macro`.
>
> **SSOT:** `scripts/monthly/run_collective_cycle_csv.py`. 1페이지: [`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md).  
> 축약·K-apt·공시지가 달력: [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md) §4. 실거래 러너 주거 신규 키 공시지가 공급 기본.
> xlsx 경로는 복구·레거시. git deploy ≠ 월갱신.

관련: [`MONTHLY_UPDATE_SOP.md`](MONTHLY_UPDATE_SOP.md), [`BUILT_MONTHLY_UPDATE_SOP.md`](BUILT_MONTHLY_UPDATE_SOP.md), [`COLLECTIVE_RESEARCH_MVP.md`](COLLECTIVE_RESEARCH_MVP.md), [`COLLECTIVE_PRESALE_BUILDING_KEY.md`](COLLECTIVE_PRESALE_BUILDING_KEY.md)

> **⚠ CSV Selenium 수집:** historical·backfill 시 [`MOLIT_CSV_COLLECTOR_WARNINGS.md`](MOLIT_CSV_COLLECTOR_WARNINGS.md) — 검증 없는 rename 금지.

> **분양·입주권 키:** 월간 적재 시 `pipeline/collective/building_keys.py` 의 분양권 단지명 정규화가 **반드시** 적용돼야 한다. 규칙·재키·미스매칭 안내 → [`COLLECTIVE_PRESALE_BUILDING_KEY.md`](COLLECTIVE_PRESALE_BUILDING_KEY.md).

---

## 1. 실행 순서

```
1) 토지: run_land_cycle_csv.py → Promote
2) 복합: run_built_cycle_csv.py
3) 집합: run_collective_cycle_csv.py → 검증 → Promote collective_stats
```

xlsx `run_collective_monthly_cycle.py` 는 **복구**. 토지를 먼저 — `region_codes` 동기화.

체크리스트 **0.7** CSV 수(유형당 16개)를 통과하기 전에는 시작하지 않는다. 빠진 지역이 있으면 사용자에게 먼저 알린다.

---

## 2. cycle_id (토지·복합과 동일 YYYYMM)

```powershell
py scripts\monthly\run_collective_cycle_csv.py --cycle-id YYYYMM --attr-snapshot-ym 202607 --kapt-file "K-apt 단지 기본정보.xlsx"
```

수집 연월은 `collection_yyyymm_range_from_cycle_id` (직전 12개월). 끝 월이 다르면 러너/`--v2-as-of` 규칙을 토지와 맞춘다.

속성 판은 `--attr-snapshot-ym`만 쓴다. 지금 판은 `202607`이다. cycle-id나 K-apt 파일 이름에 있는 달을 속성 판으로 쓰지 않는다. 그 판에 기존 행이 있을 때만, 속성 행이 없는 아파트·연립·오피스텔 키만 K-apt와 title_fill로 넣는다. 판 전체를 다시 쓰지 않는다. 실거래만 다시 돌릴 때는 `--skip-attributes`. `vps_sync_collective_building_attributes.sh`의 `--replace`는 이 단계가 아니다.

xlsx 복구:

```powershell
py scripts\monthly\run_collective_monthly_cycle.py --cycle-id YYYYMM --require-land-cycle
```

---

## 3. raw 디렉터리

**현행 CSV:** `molit_csv_collector` 출력. 러너가 `cycle_utils.resolve_csv_subdir` 로 아파트·연립·오피스텔·분양·집합상가·집합공장을 찾는다.

xlsx 복구:

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
- [ ] **자동 등록 C-2 조각 검토(T):** 월간 integrity(`integrity_p2`)의 「C-2 월간 적재 자동 등록 조각 N개(source=auto_ingest) — 판정 검토 대상」 경고가 있으면, 판정 표 `collective_building_key_c2_units` 의 `source='auto_ingest'` 행을 T 가 검토한다(같은 단지면 `part` 를 기존 조각으로 고치거나 행 삭제 후 재적재 판단). 집합 2단계 런북 [`docs/ops/COLLECTIVE_P2_RUNBOOK.md`](ops/COLLECTIVE_P2_RUNBOOK.md) 5.1 C-2 메모
- [ ] **분양권:** 정규화 코드로 적재됐는지 · 대표 분열 단지(IPARK/공백)가 한 키인지 ([`COLLECTIVE_PRESALE_BUILDING_KEY.md`](COLLECTIVE_PRESALE_BUILDING_KEY.md))

### 4.1 분양권 building_key (매 cycle)

| 할 일 | 비고 |
|------|------|
| `building_keys.py` 최신본으로 ingest | 옛 로직만 쓰면 신규월이 다시 키 분열 |
| alias/규칙 변경 시 | `rekey_presale_building_keys.py --purge-presale-marts` 후 mart 재구축 + **long-term annual 분양권 재ingest** |
| 목록 통계 | 분양권 기본 = **3/5년 rolling** (타유형과 동일). `lifetime`은 보조 API |
| 장기 annual | `ingest_collective_long_term_annual.py --asset-type=presale` (필요 시) |
| 준공유형 연결 | 키 병합 금지 · 모달 `presale-catalog` 검색(아파트·연립·오피스텔) / sibling. 이름 유사도 자동 추천 없음 |
| mart 빌드 | `build_collective_presale_lifetime_stats.py` — 보조 mart 유지 · DDL `db/040_….sql` |

---

## 5. VPS Promote
로컬 dump → scp → VPS restore (PG 버전 주의, built와 동일 plain SQL 경로).

`BUILT_HANDOFF` §5 Promote 절차 참고 — **collective_stats** 대상.

---

## 6. 레거시·축약 달력 (1페이지 밖)

- xlsx Selenium 수집 — 복구만. 월간은 CSV 수집기.
- `contract_month` 정밀 12개월 창 — 잔여.
- 축약 enrich · K-apt 월 갱신 · 공시지가 재파생 — [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md) §4·§7. **체크리스트 완주 범위에 칸을 넣지 않음** (빼는 결정).
