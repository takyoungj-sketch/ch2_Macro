"""Create collective_stats database if missing."""

from __future__ import annotations

import os

import psycopg2
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env.collective")
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

URL = os.environ.get("COLLECTIVE_ADMIN_URL", "postgresql://postgres:8972@localhost:5432/postgres")


def main() -> None:
    conn = psycopg2.connect(URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'collective_stats'")
    if cur.fetchone():
        print("collective_stats already exists")
    else:
        cur.execute("CREATE DATABASE collective_stats")
        print("created collective_stats")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
