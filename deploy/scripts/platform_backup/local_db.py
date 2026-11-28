"""시험용 빈 데이터베이스를 임시 클러스터에만 만든다. 이미 있으면 지우지 않는다."""

import os
import re
import subprocess
import sys

ALLOWED_DB = "pay003a_dummy"
SYSTEM_DATA = os.path.normcase(os.path.abspath(r"D:\PostgreSQL\18\data")).replace("\\", "/").rstrip("/")


def norm_path(path):
    return os.path.normcase(os.path.abspath(path)).replace("\\", "/").rstrip("/")


def quote_ident(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise SystemExit("bad-ident")
    return '"' + name.replace('"', '""') + '"'


def table_names(script_dir):
    path = os.path.join(script_dir, "expected_tables.txt")
    names = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not line.startswith("public."):
                raise SystemExit("bad-table")
            name = line[len("public."):]
            quote_ident(name)
            names.append(name)
    if not names:
        raise SystemExit("bad-table")
    return names


def psql(psql_bin, port, database, sql):
    env = os.environ.copy()
    env.pop("PGPASSWORD", None)
    env["PGCLIENTENCODING"] = "UTF8"
    result = subprocess.run(
        [psql_bin, "-h", "127.0.0.1", "-p", str(port), "-U", "postgres", "-d", database,
         "-v", "ON_ERROR_STOP=1", "-tAc", sql],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit("psql-failed")
    return result.stdout.strip()


def check_cluster(psql_bin, pgdata, port):
    if not re.fullmatch(r"[0-9]+", str(port)):
        raise SystemExit("refused-port")
    port_n = int(port)
    if port_n == 5432 or port_n < 1024 or port_n > 65535:
        raise SystemExit("refused-port")
    if not os.path.isdir(pgdata) or os.path.islink(pgdata):
        raise SystemExit("refused-cluster")
    if not os.path.isfile(os.path.join(pgdata, "PG_VERSION")):
        raise SystemExit("refused-cluster")
    data = norm_path(pgdata)
    if data == SYSTEM_DATA or data.endswith("/postgresql/18/data"):
        raise SystemExit("refused-cluster")
    shown = norm_path(psql(psql_bin, port_n, "postgres", "SHOW data_directory"))
    shown_port = psql(psql_bin, port_n, "postgres", "SHOW port")
    if shown != data or shown_port != str(port_n):
        raise SystemExit("refused-cluster")
    return port_n


def main():
    if len(sys.argv) != 6:
        raise SystemExit("usage")
    action, psql_bin, dbname, pgdata, port = sys.argv[1:6]
    if dbname != ALLOWED_DB:
        raise SystemExit("refused-name")
    port_n = check_cluster(psql_bin, pgdata, port)
    ident = quote_ident(ALLOWED_DB)
    exists = psql(
        psql_bin, port_n, "postgres",
        "SELECT 1 FROM pg_database WHERE datname = '%s'" % ALLOWED_DB,
    )
    if action == "create":
        if exists == "1":
            print("exists")
            raise SystemExit(3)
        psql(psql_bin, port_n, "postgres", "CREATE DATABASE %s" % ident)
        ddl = "; ".join("CREATE TABLE %s (id integer)" % quote_ident(name) for name in table_names(os.path.dirname(__file__)))
        psql(psql_bin, port_n, ALLOWED_DB, ddl)
        print("created")
    elif action == "drop":
        psql(psql_bin, port_n, "postgres", "DROP DATABASE IF EXISTS %s WITH (FORCE)" % ident)
        print("dropped")
    else:
        raise SystemExit("usage")


if __name__ == "__main__":
    main()
