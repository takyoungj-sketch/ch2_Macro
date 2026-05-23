# 토지 엑셀: 참고 노트북 통합·정제 (템플릿 호환용)

운영 DB 적재 파이프라인(`pipeline/collect.py` → `clean.py` → 통계 빌드)과 **별도** 로,
[`참고/7.토지 통합 정제.ipynb`](../참고/7.토지 통합 정제.ipynb) 과 같은 산출 구조를 자동 생성한다.

## 설계 선택 (순서)

- **DB**: 국토부 **원본** xlsx 가 정본. `토지_매매/` 또는 `flatten` 후 `collect` 로 `land_transactions` 적재 및 이후 사전통계 빌드.
- **통합·정제 엑셀**: 사용자 **시세분석 템플릿**(정제 결과 시트 규격) 용이다. 같은 원본 폴더에서 독립 실행하며 DB와 충돌하지 않도록 별 디렉터리에 출력한다.

## 출력 구조 (`raw/토지/<cycle_id>/`)

| 단계 | 폴더 | 내용 |
|------|------|------|
| 다운로드 | `토지_매매/` | Selenium 받은 원본 |
| 통합 | `토지_매매_통합/` | `{시도}_토지_매매_통합.xlsx` (헤더 없음) |
| 정제 | `토지_매매_정제/` | `{시도}_토지_매매_정제.xlsx` |

## 명령

```powershell
cd C:\ch2\ch2_Macro
py scripts\monthly\run_land_notebook_excel_prep.py --cycle-id 202605
```

단계별:

```powershell
py scripts\monthly\notebook_land_merge.py --cycle-id 202605
py scripts\monthly\notebook_land_refine.py --cycle-id 202605
```

## 다음 단계 (사전통계 DB)

`run_monthly_cycle.py`(또는 `run_pipeline --with-v2`)는 **`flatten`(원본 디렉터리)** 또는 DB 경로 로 동작하고, 노트북 정제 결과를 직접 넣지는 않는다.  
통계 재생성은 DB 선행 적재 후 `build_stats` / `build_stats_v2` 가 맞다.

## 분석 템플릿 엑셀 붙넣기 (노트북 마지막 셀)

노트북의 「시세분석_토지_매매_템플릿.xlsx」 에 시트 채워 넣기는 시간이 길어,
템플릿 경로·시트 이름이 환경마다 다르다면 **수동 또는 별도 자동화**로 두었다.
