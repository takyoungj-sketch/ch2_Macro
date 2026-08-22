# 집합(주거) 단지 속성 보강 — 실험 트랙 작업 기록

> **브랜치:** `experiment/collective-danji-attributes`  
> **기준일:** 2026-08-09  
> **상태:** P1~P2.5 완료 · **다음 = P3(1단계 품질지수)**  
> **설계 SSOT:** [`COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md`](COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md)  
> **검토 문서:** [`COLLECTIVE_RESIDENTIAL_VALUATION_EXPANSION_REVIEW.md`](COLLECTIVE_RESIDENTIAL_VALUATION_EXPANSION_REVIEW.md)

---

## 1. 이번 세션에서 끝난 것

| 단계 | 내용 | 핵심 산출 |
|---|---|---|
| P1 | K-apt → `builder_master` + `collective_building_attributes` 매칭 적재 | `db/049_…sql` · `pipeline/build_collective_building_attributes.py` |
| P2 | 시공사 정규화·기업집단·브랜드 사전 + 품질 플래그 | `pipeline/collective/danji_brand_dictionary.py` · `apply_danji_dictionary.py` · `db/052_…sql` |
| P2.5 | 단지 정보 API + 상세 모달 「단지 정보」탭(실험 모드) | `backend/app/collective/danji_attributes.py` · `BuildingDetailModal` |

**제품 원칙:** CH2 Macro는 AVM이 아니다. 값만 내지 않고 출처·매칭 tier·회귀 제외 사유·원본 이상값 사유를 함께 노출한다.

**비범위 준수:** 기존 `regression/engine.py`·기존 mart·기존 엔드포인트 무수정. 비주거 모달은 K-apt 대응 데이터 없어 미수정(parity 예외).

---

## 2. 로컬 DB 실측 요약 (snapshot_ym=202607)

| 항목 | 값 |
|---|---|
| `builder_master` | 21,651 |
| `collective_building_attributes` | 41,832 |
| tier A / B / C / E | 5,149 / 218 / 12,574 / 833 |
| 거래가중 A+B+C | 82.6% (A+B+C+E 85.4%) |
| year_diff 완전일치 | A 98.3% · C 96.1% · E 75.6% |
| `builder_group` 채움 | 18,263단지 · 거래가중 83.7% |
| brand 검출 | 5,109단지 · 거래가중 23.7% |
| 품질 플래그 | 742건 (1.77%) — floor_implausible 541 · scale_inconsistent 150 · parking_implausible 50 · hh_zero 15 |
| 2단계 후보(A·B·C, hh>0, n_tx≥10) | 17,361단지 / 거래 274만건 |

재적재:

```powershell
python pipeline/build_collective_building_attributes.py --snapshot-ym 202607 --apply-ddl --replace
python backend/_tmp_apply_ddl.py db/052_collective_attributes_dictionary_columns.sql   # psql 없을 때
python pipeline/collective/apply_danji_dictionary.py --snapshot-ym 202607
```

확인 UI: http://localhost:5175/collective/ → 아파트 건물 → **단지 정보** 탭  
API: `GET /api/collective/buildings/{building_key}/danji-attributes`

---

## 3. 다음에 이어서 할 일 (P3)

**목표:** 시군구별 단지 FE → 「단지 품질지수」 mart (`db/050` + 빌드).  
기존 건물/코호트 회귀 엔진은 읽기 전용 참조만. 상세 스펙은 설계 문서 §2·§4·§5·§7.

P3 이후 순서: **P4** 2단계 특성회귀(브랜드·규모) → **P5** API·UI 노출.

착수 전 확인 권고:

1. 「단지 정보」탭 UI를 사용자가 한 번 더 보고 문구·배치 다듬을지
2. 설계 §9 미결정 중 `danji_code` 1:N(257건) 처리 방식 — 클러스터 SE vs 대표키

---

## 4. 커밋에 포함하지 않은 것

- `_tmp_*` 프로브·검증 스크립트·JSON (로컬 탐색용)
- `deploy/`·`logs/`·molit collector dist 등 무관 변경
- DB 데이터 자체(로컬 `collective_stats`에만 적재됨 — VPS 미반영)

---

## 5. 알려진 한계 (이어서 작업 시 참고)

- 브랜드 표시 범위 > 브랜드 회귀 표본(미매칭에도 브랜드 가능 — 설계 §3.1.2)
- `builder_group`에 시공사가 아닌 법인이 남는 경우(예: 금호고속) — 단지 30개 미만은 「기타」로 묶임
- `brand.detected_from`은 현재 고정값「실거래 단지명」(원장 결측 0건)
- `households_rent`는 NULL이 아니라 0으로 오는 원본 관행
- **D·F 다중후보 목록 채움은 보류** — 202607 아파트 D 249 + F 126 = 375단지. 앵커는 청주 분평주공3(지번 1200에 3-1/3-2). 백로그 [`docs/lab/collective_danji_unmatched_backlog.md`](lab/collective_danji_unmatched_backlog.md). 축약대장 이후에도 자동으로 안 메워짐. 대응 시 세대수 합산·모달 전 행, 첫째 행 금지, 회귀는 계속 제외
