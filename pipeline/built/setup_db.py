"""Create built_stats database if missing."""

from __future__ import annotations

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

URL = "postgresql://postgres:8972@localhost:5432/postgres"


def main() -> None:
    conn = psycopg2.connect(URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'built_stats'")
    if cur.fetchone():
        print("built_stats already exists")
    else:
        cur.execute("CREATE DATABASE built_stats")
        print("created built_stats")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
