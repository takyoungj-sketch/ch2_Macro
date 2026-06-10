import pandas as pd
from sqlalchemy import text

from clean import build_region_lookup, map_beopjungri_codes
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    rows = c.execute(
        text(
            """
            SELECT sido_name, sigungu_name, eupmyeondong_name, beopjungri_code
            FROM region_codes
            WHERE sigungu_name = '군산시' AND eupmyeondong_name LIKE '나운%'
            LIMIT 5
            """
        )
    ).fetchall()
    print("gunsan naun:", rows)

lookup = build_region_lookup(e)
tests = [
    "전북특별자치도 전주시 완산구 효자동",
    "전주광역시 완산구 효자동",
    "군산시 나운동",
    "익산시 모현동",
]
for a in tests:
    m = map_beopjungri_codes(pd.DataFrame({"sigungu_name": [a]}), lookup)
    print(a, "->", m["beopjungri_code"].iloc[0], m["mapping_notes"].iloc[0])
