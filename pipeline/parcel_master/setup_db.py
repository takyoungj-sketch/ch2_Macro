"""Create local parcel_master database if missing."""

from __future__ import annotations

import psycopg2

from parcel_master.db_utils import admin_url


def main() -> None:
    conn = psycopg2.connect(admin_url())
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'parcel_master'")
    if cur.fetchone():
        print("parcel_master already exists")
    else:
        cur.execute("CREATE DATABASE parcel_master")
        print("created parcel_master")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
