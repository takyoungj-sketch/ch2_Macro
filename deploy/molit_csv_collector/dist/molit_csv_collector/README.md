# 국토부 실거래 CSV 수집기 (사무실 배포용)

ch2_Macro 전체 없이 **CSV만** 수집. 파일명은 본 프로젝트 `raw/` 와 동일.

```
{시도}_{유형}_매매_{연도}.csv
```

## ⚠ 필독 — 데이터 오염 방지

구버전(2026-06-12 이전)은 **요청 간격 2초 + 무검증 rename** 으로 시도·연도가 뒤바뀐 CSV가 저장될 수 있습니다.

**현재 버전 방어:**
- 다운로드 완료·파일 크기 안정 대기
- CSV 상단 메타(`시도`, `계약일자`, `실거래구분`) 검증 후에만 저장
- 기존 파일도 스킵 전 재검증 (오염 시 자동 재수집)
- 실패: `.download_failures.jsonl` + GUI **빨간 로그**

상세: [`docs/MOLIT_CSV_COLLECTOR_WARNINGS.md`](../../docs/MOLIT_CSV_COLLECTOR_WARNINGS.md)

## 실행

| 방법 | 설명 |
|------|------|
| **`MolitCsvCollector.exe`** | Python 없이 GUI (dist zip 포함) |
| `run_gui.bat` | Python + Chrome 필요 |
| `py run_collector.py` | 터미널 (권장 — 오류 확인 쉬움) |

## GUI

- **유형·연도·신규 상한(100)**
- **시도 체크박스** — 기본 전국, 실패 시 해당 시도만 선택 후 재실행
- **실패 로그** — 빨간색 강조

## 배포 zip / EXE 빌드 (집 PC)

```powershell
cd C:\ch2\ch2_Macro
powershell -File deploy\molit_csv_collector\build_dist.ps1 -WithExe
```

→ **`deploy/molit_csv_collector/dist/molit_csv_collector.zip`** 만 유지 (EXE·소스·run_gui.bat 포함).  
사무실: zip 압축 해제 → **`MolitCsvCollector.exe`** 실행 (Chrome 필요)

## 집 PC로 복사

```
사무실 MolitCSV\아파트_2010_2020\*.csv
  → C:\ch2\ch2_Macro\raw\아파트_2010_2020\
```

## CLI

```powershell
py -m molit_csv_collector --cli --property-type apartment --start-year 2010 --end-year 2020 --output-dir D:\out --max-new-downloads 100 --regions "경기도,서울특별시"
```
