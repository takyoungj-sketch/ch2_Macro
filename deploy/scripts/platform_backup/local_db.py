"""로컬 가짜 회원 DB를 만들고 지운다. localhost 가 아니면 거절한다."""

import os
import subprocess
import sys
from urllib.parse import unquote, urlparse

TABLES = [
    "ai_allowance_accounts",
    "ai_allowance_adjustments",
    "ai_allowance_requests",
    "ai_allowance_results",
    "ai_allowances",
    "ai_provider_calls",
    "comments",
    "device_ai_usage",
    "entitlements",
    "ops_events",
    "posts",
    "subscriptions",
    "users",
]


def load_local_url(path):
    url = ""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("DATABASE_URL_PLATFORM="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not url:
        raise SystemExit("missing-url")
    parsed = urlparse(url)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        raise SystemExit("refused-host")
    if not parsed.username:
        raise SystemExit("missing-user")
    return parsed


def pgpass_escape(value):
    return value.replace("\\", "\\\\").replace(":", "\\:")


def write_pgpass(path, parsed):
    port = str(parsed.port or 5432)
    user = unquote(parsed.username)
    password = unquote(parsed.password or "")
    line = "localhost:%s:*:%s:%s\n" % (port, pgpass_escape(user), pgpass_escape(password))
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
    return port, user


def psql(psql_bin, port, user, pgpass, database, sql):
    env = os.environ.copy()
    env["PGPASSFILE"] = pgpass
    env.pop("PGPASSWORD", None)
    result = subprocess.run(
        [psql_bin, "-h", "localhost", "-p", port, "-U", user, "-d", database, "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit("psql-failed")
    return result


def main():
    if len(sys.argv) != 6:
        raise SystemExit("usage")
    action, envfile, psql_bin, dbname, pgpass = sys.argv[1:6]
    parsed = load_local_url(envfile)
    port, user = write_pgpass(pgpass, parsed)
    if action == "create":
        psql(psql_bin, port, user, pgpass, "postgres", 'DROP DATABASE IF EXISTS "%s" WITH (FORCE)' % dbname)
        psql(psql_bin, port, user, pgpass, "postgres", 'CREATE DATABASE "%s"' % dbname)
        ddl = "; ".join("CREATE TABLE %s (id integer)" % name for name in TABLES)
        psql(psql_bin, port, user, pgpass, dbname, ddl)
        print("created")
    elif action == "drop":
        psql(psql_bin, port, user, pgpass, "postgres", 'DROP DATABASE IF EXISTS "%s" WITH (FORCE)' % dbname)
        try:
            os.remove(pgpass)
        except OSError:
            pass
        print("dropped")
    else:
        raise SystemExit("usage")


if __name__ == "__main__":
    main()
