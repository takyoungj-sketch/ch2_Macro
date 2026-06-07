from sqlalchemy import text

from app.collective.db import get_collective_engine

e = get_collective_engine()
with e.connect() as c:
    shop = c.execute(
        text("SELECT COUNT(*) FROM collective_commercial_transactions WHERE asset_type='collective_shop'")
    ).scalar()
    fac = c.execute(
        text("SELECT COUNT(*) FROM collective_commercial_transactions WHERE asset_type='collective_factory'")
    ).scalar()
    cl = c.execute(text("SELECT COUNT(*) FROM commercial_clusters")).scalar()
    sample = c.execute(
        text(
            "SELECT display_label, n_total FROM commercial_clusters "
            "WHERE addr2 = :a2 ORDER BY n_total DESC LIMIT 3"
        ),
        {"a2": "강남구"},
    ).fetchall()
print("shop", shop, "factory", fac, "clusters", cl)
for row in sample:
    print(row)
