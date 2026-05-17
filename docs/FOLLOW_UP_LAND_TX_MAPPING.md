# 법정동 매핑·통계 후속 작업 메모

작성 목적: **괄호 한자 병기 정규화 등 매핑 로직 개선**을 반영한 뒤, **통계 재생성 전에** 백엔드·프론트 검증을 하고, 추가 수정이 있으면 **한 번에** 묶어 처리하기 위함.

---

## 1. 이미 반영된 것 (참고)

- `pipeline/clean.py`: 강한 키만 사용, 약한 키·임의 fallback 제거, `--reprocess-all` 시 `land_transactions` 전체 삭제 후 재적재(해시 변경 시 중복 방지), 배치 UPSERT, 읍면동·법정리명 **괄호 병기 제거** 정규화(`_normalize_admin_label`).
- `db/009_land_transactions_mapping_review.sql`: `needs_review`, `mapping_notes`.
- ORM `LandTransaction`에 동일 컬럼.

---

## 2. 당장 할 일 (우선순위)

| 순서 | 작업 | 비고 |
|------|------|------|
| P1 | **매핑만 재반영** | `cd pipeline` 후 `Python 3.13`(또는 pandas 설치된 인터프리터)으로 `python clean.py --reprocess-all` |
| P2 | DB 확인 | `needs_review` 건수·`mapping_notes` 분포, 샘플(괄호 병기) 매칭 여부 |
| P3 | **백엔드·프론트 수동/스모크 검증** | 아래 §4 참고 |
| P4 | QA 중 발견 이슈 수정 | API·UI·설정 |

---

## 3. 후속으로 미룬 일 (통계와 완전 일치)

| 순서 | 작업 | 비고 |
|------|------|------|
| S1 | `python build_stats.py` | `land_basic_stats` 전체 재계산 |
| S2 | `python build_stats_v2.py --as-of YYYY-MM-01 --windows 3,5` | 운영 스냅샷 일자 합의 후. [V2_OPERATOR_CHECKLIST.md](./V2_OPERATOR_CHECKLIST.md) |
| S3 | 백엔드 재시작 | `.env`의 `STATS_V2_*` 변경 시 |
| S4 | 프론트 재시작 | Vite env 변경 시 |

**주의:** 매핑만 고치고 집계를 안 돌리면, **원장(`land_transactions`) 기반 API**와 **`land_basic_stats` / `land_basic_stats_v2` 기반 무료 API**가 어긋날 수 있음. 검증 시 어떤 엔드포인트가 어떤 테이블을 쓰는지 구분할 것.

---

## 4. 검증 시 체크 포인트

- **원장 직접 조회**: 유료 필터·일부 무료 연도/원장 쿼리 — `is_valid = TRUE` 등으로 매핑 결과가 반영되는지.
- **사전 집계 무료 V1/V2**: 집계 **재생성 전**에는 이전 배치와 섞여 보일 수 있음.
- **`needs_review`**: 현재 API 스키마에 노출하지 않을 수 있음. 내부용으로만 DB 확인.

---

## 5. 한 번에 묶을 때 권장 순서 (통계까지)

1. 코드·설정 최종 확정  
2. `clean.py --reprocess-all`  
3. `build_stats.py` → `build_stats_v2.py` (스냅샷·windows 합의)  
4. 백엔드·프론트 재기동 및 샘플 검증  

---

## 6. 로컬 서버 (개발)

- 백엔드: 저장소 `backend` 디렉터리에서  
  `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
- 프론트: 저장소 `frontend` 디렉터리에서  
  `npm run dev` (기본 `http://localhost:5173`, `/api` 는 Vite가 `8000` 으로 프록시).  
  포트가 이미 쓰 중이면 Vite가 **5174** 등 다음 포트를 쓸 수 있음 — 백엔드 `CORS` 설정에 해당 origin 이 포함돼 있는지 확인.
