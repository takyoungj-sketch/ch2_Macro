"""조건 4 — 프로필·market_stats 가 이번 변경으로 바뀌는지(읽기 전용, 데이터 확인)."""
from _db import engine, q, md_table
with engine().connect() as c:
    # 프로필이 읽는 as_of·창
    prof = q(c, "select as_of_month, window_years, count(*) from regional_profile group by 1,2 order by 1 desc,2")
    # 옛 시도명 행이 3·5년 창(최신 as_of 기준)에 들어오는지
    rows = q(c, """select ms.window_years, min(ms.period_start), max(ms.period_end),
                   (select count(*) from collective_transactions t where t.addr1 = any(array['광주광역시','전라남도'])
                      and t.contract_date between min(ms.period_start) and max(ms.period_end)) as legacy_rows_in_window
                   from market_stats ms where ms.as_of_month = (select max(as_of_month) from market_stats) group by 1 order by 1""")
    # 프로필이 쓰는 연간 표의 연도 범위 vs 옛 이름 연도
    yrs = q(c, "select min(calendar_year), max(calendar_year) from market_annual_stats")
    leg = q(c, "select min(contract_year), max(contract_year) from collective_transactions where addr1 = any(array['광주광역시','전라남도'])")
print(md_table(prof[:8], ["profile as_of", "window", "rows"]))
print(md_table(rows, ["market window", "period_start", "period_end", "옛 시도명 거래(창 안)"]))
print("market_annual_stats 연도", yrs, "옛 시도명 계약연도", leg)
