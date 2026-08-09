"""Stream pg_dump plain SQL, strip PG18-only GUC lines, gzip for VPS restore."""
from __future__ import annotations

import argparse
import gzip
import subprocess
import sys

PG_DUMP = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
SKIP_SUBSTRINGS = (
    b"transaction_timeout",
    b"\\restrict",
    b"\\unrestrict",
)


def main() -> None:
    p = argparse.ArgumentParser(description="VPS-compatible PostgreSQL plain SQL gzip dump")
    p.add_argument("-d", "--database", required=True, help="Database name")
    p.add_argument("-o", "--output", required=True, help="Output .sql.gz path")
    args = p.parse_args()

    proc = subprocess.Popen(
        [PG_DUMP, "-h", "localhost", "-U", "postgres", "-d", args.database, "-Fp", "--no-owner", "--no-acl"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    written = 0
    with gzip.open(args.output, "wb", compresslevel=6) as gz:
        for line in proc.stdout:
            if any(s in line for s in SKIP_SUBSTRINGS):
                continue
            gz.write(line)
            written += 1
            if written % 500000 == 0:
                print(f"{args.database} lines={written}", flush=True)
    err = proc.stderr.read() if proc.stderr else b""
    rc = proc.wait()
    print(f"{args.database} exit={rc} lines={written} out={args.output}")
    if rc != 0:
        print(err.decode("utf-8", errors="replace")[:2000], file=sys.stderr)
        sys.exit(rc)


if __name__ == "__main__":
    main()
