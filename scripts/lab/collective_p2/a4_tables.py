from _db import engine, q, settings
from sqlalchemy import create_engine
urls = {"land": settings.database_url, "built": settings.built_database_url, "collective": settings.collective_database_url,
        "rent": settings.rent_database_url or settings.database_url.replace("/land_stats", "/rent_stats")}
for nm in ("macro_ts_database_url", "platform_database_url", "ai_database_url", "auth_database_url"):
    u = getattr(settings, nm, None)
    if u: urls[nm] = u
seen=set()
for db, u in urls.items():
    if not u or u in seen: continue
    seen.add(u)
    e = create_engine(u, connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=600000"})
    try:
        with e.connect() as c:
            dbn = q(c, "select current_database()")[0][0]
            rows = q(c, """select table_name, string_agg(column_name, ',') from information_schema.columns
                           where table_schema='public' and (column_name ilike '%building_key%' or column_name ilike '%complex_key%' or column_name in ('sale_building_key','cluster_key'))
                           group by 1 order by 1""")
            for t, cols in rows:
                n = q(c, f'select count(*) from "{t}"')[0][0]
                print(db, dbn, t, cols, n)
    except Exception as ex:
        print(db, "ERR", type(ex).__name__)
