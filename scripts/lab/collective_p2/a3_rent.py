import sys
import a3_rep_address as A
from _db import OUT, ROOT
sys.path.insert(0, str(ROOT / "pipeline")); sys.path.insert(0, str(ROOT / "pipeline" / "rent"))
from stats_pack import BUILDING_KEY_SQL
import pandas as pd
rc, na, nact, sa = A.c01.load_region_codes()
res = A.measure("rent", "rent_building_stats", "rent_transactions", BUILDING_KEY_SQL, "", "", "rent", (na, nact, sa))
pd.DataFrame(res).to_csv(OUT / "a3_rent_summary.csv", index=False)
print(pd.DataFrame(res).to_string())
