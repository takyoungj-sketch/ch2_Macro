"""Stream pg_dump plain SQL, strip PG18-only GUC lines, gzip for VPS restore."""
import gzip
import os
import subprocess
import sys

OUT = "E:/ch2/ch2_Macro/backups/land_stats_promote_202608.sql.gz"
PG_DUMP = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
SKIP_SUBSTRINGS = (
    b"transaction_timeout",
    b"\\restrict",
    b"\\unrestrict",
)

env = os.environ.copy()
# PGPASSWORD set by caller

proc = subprocess.Popen(
    [PG_DUMP, "-h", "localhost", "-U", "postgres", "-d", "land_stats", "-Fp", "--no-owner", "--no-acl"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
assert proc.stdout is not None
written = 0
with gzip.open(OUT, "wb", compresslevel=6) as gz:
    for line in proc.stdout:
        if any(s in line for s in SKIP_SUBSTRINGS):
            continue
        gz.write(line)
        written += 1
        if written % 500000 == 0:
            print(f"lines={written}", flush=True)
err = proc.stderr.read() if proc.stderr else b""
rc = proc.wait()
print(f"exit={rc} lines={written} out={OUT}")
if rc != 0:
    print(err.decode("utf-8", errors="replace")[:2000], file=sys.stderr)
    sys.exit(rc)
