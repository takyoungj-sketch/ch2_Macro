"""Trace why Jeonbuk 2010 raw rows don't appear in land_transactions."""
from sqlalchemy import text

from clean import clean_dataframe, fetch_unprocessed_raw
from db_utils import get_engine


def main() -> None:
    e = get_engine()
    with e.connect() as c:
        rows = c.execute(
            text(
                """
                SELECT r.id, r.source_year, r.raw_data
                FROM land_transactions_raw r
                WHERE r.source_year = 2010 AND r.source_month = 6
                  AND r.raw_data->>'deal_ymd' LIKE '2010%'
                LIMIT 5000
                """
            )
        ).fetchall()
        print(f"sample raw 2010 jeonbuk-like: {len(rows)}")
        if not rows:
            return
        import pandas as pd

        recs = [{"_raw_id": r[0], "_source_year": r[1], **r[2]} for r in rows]
        df = pd.DataFrame(recs)
        cleaned = clean_dataframe(df)
        print("contract_year null:", cleaned["contract_year"].isna().sum(), "/", len(cleaned))
        print("year vc:", cleaned["contract_year"].value_counts().head())
        print("is_valid true:", (cleaned["is_valid"] == True).sum())
        print("beop empty:", cleaned["beopjungri_code"].fillna("").astype(str).str.strip().eq("").sum())

    unproc = fetch_unprocessed_raw()
    print("total unprocessed raw:", len(unproc))
    if len(unproc):
        y2010 = unproc[unproc.get("deal_ymd", pd.Series()).astype(str).str.startswith("2010")]
        print("unprocessed deal_ymd 2010:", len(y2010))


if __name__ == "__main__":
    main()
