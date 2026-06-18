# 국토부 CSV 수집 — 치명적 주의사항

> **대상:** `deploy/molit_csv_collector`, `scripts/monthly/download_molit_*_csv.py`,  
> 월간·historical backfill 담당자

## 문제 요약

국토부 실거래 CSV는 Selenium으로 **브라우저 다운로드 폴더에 임시 파일**이 떨어진 뒤, 스크립트가 **rename** 하는 구조다.

다음 조건에서 **파일명과 내용이 어긋난 CSV**가 저장될 수 있다 (실제 발생):

| 증상 | 예 |
|------|-----|
| 연도 불일치 | 파일명 `…_2012.csv` 인데 메타데이터·데이터는 2011 |
| 시도 불일치 | `전북…` 파일명에 `전남` 데이터 |
| 연도 혼합 | 한 CSV에 여러 연도 거래 |

**원인:** 이전 다운로드가 끝나기 전 다음 요청 → `.crdownload`만 사라지면 “완료”로 오인 → **가장 최근 csv를 무조건 rename** (구버전 로직).

요청 간격 2초는 **경기·전국 대용량** 기준으로 **너무 짧다**.

## 필수 방어 (2026-06-12 이후)

수집 코어(`molit_csv_download_core.py`, `deploy/.../downloader.py`)는 아래를 **반드시** 수행한다:

1. **폴더 quiescent** — `.crdownload` 없음 + 파일 목록 2초 이상 안정
2. **신규 파일만 pickup** — 클릭 시점 `before` 스냅샷 diff + `mtime >= click`
3. **크기 안정 대기** — 3초간 byte 동일 후에만 확정
4. **CSV 메타 검증** — 상단 `시도`, `계약일자`, `실거래구분` 일치 후에만 `raw/` 이름으로 저장
5. **검증 실패** — 파일 **삭제하지 않음** → `{출력폴더}/failed/` 보관 + `.download_failures.jsonl`
6. **Chrome 다운로드** — `{출력폴더}/.downloads/` 격리 (다른 csv와 혼선 방지)
7. **시도 선택** — Selenium `Select` + UI 반영 확인 (3초 대기)
8. **기존 파일 재검증** — 스킵 전 검증; 오염 파일은 `failed/` 로 이동 후 재수집
9. **요청 간격 8초** (대용량 시 더 여유)
10. **진행 없음 조기중단** — `.crdownload`·신규 파일 없이 **180초** 경과 시 해당 건 보류
11. **작업 순서** — 연도별 시도 교차; 다운로드·저장 실패 시 **다른 시도 우선** → 마지막 일괄 재시도
12. **저장 재시도** — Windows 파일 잠금(WinError 32) 시 rename 12회 재시도 + copy fallback

**대용량 시도(경기·서울 등):** 국토부 서버 CSV 생성 + Chrome 다운로드에 **연도당 5~15분** 걸릴 수 있다.  
GUI 로그에 30초마다 `서버 CSV 생성 대기…` / `Chrome 다운로드 중…` 가 출력된다 — **멈춘 것이 아니다.**  
타임아웃: 경기 등 **900초(15분)**, 그 외 600초.

검증 실패 시 **최종 폴더에는 저장하지 않음**. 원본 csv는 `failed/` 에 보관하고, 실패는 `.download_failures.jsonl` + GUI 빨간 로그.

## 운영자가 할 일 (수동 전수 검증 불가)

1. **구버전으로 받은 CSV** — ingest 전 `pipeline/_inspect_bad_csv.py` 또는 재수집(GUI에서 해당 시도만 선택).
2. **실패 로그 확인** — 출력 폴더 `.download_failures.jsonl`, GUI 빨간 줄.
3. **재수집** — GUI에서 실패 시도만 체크 → 같은 연도·유형으로 재실행.
4. **월간 cycle** — `download_molit_*` 는 `molit_csv_download_core` 경유만 사용 (직접 sleep 2초 로직 추가 금지).

## ingest 전 spot check (자동)

```powershell
cd C:\ch2\ch2_Macro
py pipeline\_inspect_bad_csv.py raw\아파트_2010_2020\의심파일.csv
```

메타데이터 8~11행: `계약일자`, `시도`, `실거래구분` 이 파일명과 일치하는지 확인.

## 관련 문서

- `deploy/molit_csv_collector/README.md` — 사무실 배포
- `scripts/monthly/README.md` — CLI·월간
- `docs/MONTHLY_UPDATE_SOP.md` § CSV 수집
