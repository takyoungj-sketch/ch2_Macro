"""Stream pg_dump plain SQL, strip PG18-only GUC lines, gzip for VPS restore."""
from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile

PG_DUMP = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
SKIP_PREFIXES = (
    b"SET transaction_timeout =",
    b"\\restrict ",
    b"\\unrestrict ",
)


def dump_database(database: str, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        PG_DUMP, "-h", "localhost", "-U", "postgres", "-d", database,
        "-Fp", "--no-owner", "--no-acl",
    ]
    written = 0
    with NamedTemporaryFile(dir=output.parent, prefix=f".{output.name}.", delete=False) as temp_file:
        temporary = Path(temp_file.name)
    try:
        with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
            assert proc.stdout is not None
            with gzip.open(temporary, "wb", compresslevel=6) as gz:
                copying = False
                for line in proc.stdout:
                    if not copying and line.startswith(SKIP_PREFIXES):
                        continue
                    if copying:
                        copying = line.rstrip(b"\r\n") != b"\\."
                    elif line.startswith(b"COPY ") and line.rstrip(b"\r\n").endswith(b" FROM stdin;"):
                        copying = True
                    gz.write(line)
                    written += 1
                    if written % 500000 == 0:
                        print(f"{database} lines={written}", flush=True)
            status = proc.wait()
        if status == 0:
            temporary.replace(output)
        print(f"{database} exit={status} lines={written} out={output}")
        return status
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="VPS-compatible PostgreSQL plain SQL gzip dump")
    parser.add_argument("-d", "--database", required=True, help="Database name")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Output .sql.gz path")
    args = parser.parse_args()
    return dump_database(args.database, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
