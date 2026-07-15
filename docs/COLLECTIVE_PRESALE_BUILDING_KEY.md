# 분양·입주권 `building_key` 정규화

> **목적:** 동일 분양권 단지가 원본 단지명 표기 차이로 키가 갈라지지 않게 한다.  
> **범위:** `asset_type = presale` 의 **키 생성만**. 아파트·연립·오피스텔 키 규칙 불변.  
> **비범위:** 분양권 ↔ 준공 아파트 **키 병합**. 비교는 sibling/장기추세 오버레이로 한다.

구현 SSOT: [`pipeline/collective/building_keys.py`](../pipeline/collective/building_keys.py)  
재키 스크립트: [`pipeline/collective/rekey_presale_building_keys.py`](../pipeline/collective/rekey_presale_building_keys.py)

---

## 1. 규칙 (보수적)

`normalize_building_name_for_key(..., asset_type="presale")`:

1. 유니코드 NFC  
2. **모든 공백 제거**  
3. 브랜드 alias (현재): `I-PARK` / `IPARK` / `I PARK`(대소문자 무시) → `아이파크`  
4. `제N단지` → `N단지`

- 원본 `building_name` / 거래별 `display_name` 은 **수정하지 않음**.  
- 키 원재료: `presale|addr1|addr2|addr3|name:{정규화단지명}` (단지명 있으면 **번지 미포함**).

아파트 등 타 유형은 기존처럼 공백만 축소(`normalize_name`) — alias·공백 제거 없음.

---

## 2. 2026-07 일회 재키 결과 (로컬 `collective_stats`)

| 항목 | 값 |
|------|-----|
| 분양권 거래 | 372,130 |
| 구 키 → 신 키 | 4,743 → 4,061 |
| **동일물건 병합(구키≥2→신키1)** | **682** (전부 구키 2개 쌍) |
| 그중 공백만 차이 | **677** |
| 그중 alias(IPARK 등) | **5** |
| 병합 단지 소속 거래 | ~11.5만 |
| 키 문자열만 변경(단일 키 포함) | ~26.7만 |

미스매칭 위험은 **낮음**. 682건 전수 검토는 불필요.  
권장: alias 5건·이상 의심 샘플만 스팟 체크. (번지가 달라도 이름 키에는 원래 번지가 안 들어감 — 다번지≠오병합.)

---

## 3. 통계 mart · UI 원칙

| mart | 역할 |
|------|------|
| `collective_building_stats` (3·5년, 분양권 포함) | **목록 기본** — 타유형과 동일 롤링 |
| `collective_presale_lifetime_stats` | **보조** — `presale_stats_mode=lifetime` (기본 UI 비사용) |
| `collective_building_annual_stats` | 연도별·장기추세 (2010–2020 long-term ingest 포함) |
| `collective_building_rolling_stats` | 모달 롤링 버킷 |

빌드: `py pipeline/build_collective_presale_lifetime_stats.py --as-of YYYY-MM-01 --replace`  
월 cycle에 lifetime 빌드 포함 가능(보조 mart 유지).

API:

- `GET /buildings?presale_stats_mode=rolling|lifetime` — **기본 `rolling`**
- `GET /buildings/{key}/related-presale` — 장기추세용 분양권 annual 후보(이름·동 유사, **키 병합 없음**)

### 장기(2010–2020) 분양권 annual

- 적재: `py pipeline/ingest_collective_long_term_annual.py --asset-type presale`
- 원본: `raw/raw long term/분양입주권_2010_2020/`
- 원장(ledger) 전체 백필 없이 annual만 보강해도 **준공유형 장기추세 + 분양권 시리즈** 비교 가능.

### 아파트·연립·오피스텔 ↔ 분양권 비교

- **동일 키로 합치지 않는다.**
- 기본 목록은 유형별 3/5년.
- 과거 분양 시세 대비는 모달 **장기 추세 → 과거 분양권 추세 추가** (오피스텔 포함).

---

## 4. 월간 업데이트에서 반드시 지킬 것

1. **적재는 항상 최신 `attach_building_identity`를 타게 한다.**  
   `import_refined.py` / long-term ingest 가 `building_keys.py` 를 import — **월 cycle 전에 해당 코드가 배포·사용 경로에 있어야** 한다.  
   옛 키 로직으로만 적재하면 신규월이 다시 키 분열한다.
2. **alias·정규화 규칙을 바꾸면** 과거 원장도  
   `py pipeline/collective/rekey_presale_building_keys.py --purge-presale-marts`  
   후 분양권 mart 재구축(또는 당분간 live 목록).  
   purge 후 **반드시** long-term annual 분양권 재ingest (`ingest_collective_long_term_annual.py --asset-type presale`).
3. **분양권 목록 통계:** 연도 미지정 시 타유형과 같이 **3/5년 rolling**.  
   보조로만 `presale_stats_mode=lifetime`.
4. **준공유형(아파트·연립·오피스텔)과 같은 키로 합치지 않는다.** 연속 분석은 related-presale / cohort.

체크 (cycle 후 스모크 예):

- [ ] 알려진 분열 단지(예: 청주 가경 IPARK / 아이파크)가 **분양권 1키**로 보이는지 (3/5년 창)
- [ ] 동일 단지 **아파트** 행이 분양권과 **키가 다른지**
- [ ] 장기 옵션에서 관련 분양권 annual(예: 청주 테크노폴리스 우미린 2017)이 후보로 뜨는지

---

## 5. 관련 SOP

- [`COLLECTIVE_MONTHLY_UPDATE_SOP.md`](COLLECTIVE_MONTHLY_UPDATE_SOP.md) § 분양권 building_key  
- [`scripts/monthly/README.md`](../scripts/monthly/README.md) 집합 절
