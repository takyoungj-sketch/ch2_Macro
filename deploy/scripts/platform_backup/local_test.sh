#!/bin/bash
# 운영 서버, 운영 키, 운영 데이터베이스는 쓰지 않는다.
set -euo pipefail
umask 077

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -z "${PAY003_TEST_ENV:-}" ]; then
  echo "FAIL missing PAY003_TEST_ENV" >&2
  exit 2
fi

PG_DUMP=${PAY003_TEST_PG_DUMP:-/c/Program\ Files/PostgreSQL/18/bin/pg_dump.exe}
PG_RESTORE=${PAY003_TEST_PG_RESTORE:-/c/Program\ Files/PostgreSQL/18/bin/pg_restore.exe}
PSQL=${PAY003_TEST_PSQL:-/c/Program\ Files/PostgreSQL/18/bin/psql.exe}
# The default above is not a real path when the space is escaped inside the variable.
# Callers may override. This file also accepts the Windows layout below.
if [ ! -x "$PG_DUMP" ] && [ -x "/c/Program Files/PostgreSQL/18/bin/pg_dump.exe" ]; then
  PG_DUMP="/c/Program Files/PostgreSQL/18/bin/pg_dump.exe"
  PG_RESTORE="/c/Program Files/PostgreSQL/18/bin/pg_restore.exe"
  PSQL="/c/Program Files/PostgreSQL/18/bin/psql.exe"
fi

ROOT=${PAY003_TEST_ROOT:-/tmp/pay003a-local-$$}
DB_NAME=pay003a_dummy
mkdir -p "$ROOT"
chmod 700 "$ROOT"
PASSFILE=$ROOT/pgpass
GNUPGHOME=$ROOT/gnupg
export GNUPGHOME
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

cleanup() {
  if [ -n "${LIVE_PID:-}" ]; then
    kill "$LIVE_PID" 2>/dev/null || true
    wait "$LIVE_PID" 2>/dev/null || true
  fi
  python "$SCRIPT_DIR/local_db.py" drop "$PAY003_TEST_ENV" "$PSQL" "$DB_NAME" "$PASSFILE" >/dev/null 2>&1 || true
  rm -rf -- "$ROOT"
}
trap cleanup EXIT

python "$SCRIPT_DIR/local_db.py" create "$PAY003_TEST_ENV" "$PSQL" "$DB_NAME" "$PASSFILE"
PASSFILE_WIN=$(cygpath -w "$PASSFILE")
export PGPASSFILE=$PASSFILE_WIN
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGCONNECT_TIMEOUT=15
unset PGPASSWORD || true

gpg --batch --pinentry-mode loopback --passphrase '' \
  --quick-gen-key "PAY003A local test <pay003a-test@invalid>" rsa4096 encr 2d >/dev/null
FPR=$(gpg --batch --homedir "$GNUPGHOME" --with-colons --fingerprint | awk -F: '/^fpr:/ { print $10; exit }')
gpg --batch --homedir "$GNUPGHOME" --armor --export "$FPR" > "$ROOT/pub.asc"
mkdir -p "$ROOT/backend"
printf 'EXAMPLE=local-test\n' > "$ROOT/backend/.env"
chmod 600 "$ROOT/backend/.env"
printf '0 5 * * * echo local-test\n' > "$ROOT/crontab.txt"
chmod 600 "$ROOT/crontab.txt"

mkdir -p "$ROOT/bin"
cat > "$ROOT/bin/curl" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "${PAY003_CURL_TRACE:?}"
exit 0
EOF
chmod 700 "$ROOT/bin/curl"

PASS=0
FAILS=0

note() { printf '%s\n' "$1"; }

run_backup() {
  env \
    PAY003_CONF="$SCRIPT_DIR/platform_backup.conf" \
    PAY003_SINK=dir \
    PAY003_ALLOW_NONTMPFS=1 \
    PAY003_ASSUME_NO_SWAP=1 \
    PAY003_LOCK_FALLBACK="${CASE_LOCK_FALLBACK-perl}" \
    PAY003_PG_DUMP="$PG_DUMP" \
    PAY003_PG_RESTORE="$PG_RESTORE" \
    PAY003_PG_SUDO_USER= \
    PAY003_DATABASE="$DB_NAME" \
    PAY003_ENV_FILE="$ROOT/backend/.env" \
    PAY003_CRONTAB_FILE="$ROOT/crontab.txt" \
    PAY003_GNUPGHOME="$GNUPGHOME" \
    PAY003_PUBKEY="$ROOT/pub.asc" \
    PAY003_FINGERPRINT="${CASE_FPR:-$FPR}" \
    PAY003_WORK_PARENT="$CASE_WORK" \
    PAY003_SINK_DIR="$CASE_SINK" \
    PAY003_SERVER_SET_ROOT="$CASE_SERVER" \
    PAY003_LOCK_FILE="$CASE_LOCK" \
    PAY003_LOG="$CASE_LOG" \
    PAY003_HEARTBEAT="$CASE_HEART" \
    PAY003_TIMEOUT_SEC="${CASE_TIMEOUT:-120}" \
    PATH="$ROOT/bin:${PATH}" \
    PGPASSFILE="$PASSFILE_WIN" \
    GNUPGHOME="$GNUPGHOME" \
    bash "$SCRIPT_DIR/platform_backup.sh" ${CASE_ARG:-} >"${CASE_DIR}/stdout" 2>"${CASE_DIR}/stderr"
}

new_case() {
  local name="$1"
  CASE_DIR=$ROOT/cases/$name
  CASE_WORK=$CASE_DIR/work
  CASE_SINK=$CASE_DIR/sink
  CASE_SERVER=$CASE_DIR/server
  CASE_LOCK=$CASE_DIR/backup.lock
  CASE_LOG=$CASE_DIR/backup.log
  CASE_HEART=$CASE_DIR/missing-heartbeat
  mkdir -p "$CASE_WORK" "$CASE_SINK" "$CASE_SERVER"
  : > "$CASE_LOG"
}

expect_fail() {
  local name="$1" reason="$2"
  new_case "$name"
  set +e
  run_backup
  local ec=$?
  set -e
  if [ "$ec" -eq 0 ]; then
    note "FAIL $name exit=0"
    FAILS=$((FAILS + 1))
    return
  fi
  if [ -n "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
    note "FAIL $name complete-exists"
    FAILS=$((FAILS + 1))
    return
  fi
  if grep -q "MANUAL_OK\|SCHEDULED_OK" "$CASE_LOG"; then
    note "FAIL $name success-log"
    FAILS=$((FAILS + 1))
    return
  fi
  if ! grep -q "BACKUP_FAIL reason=${reason}" "$CASE_LOG"; then
    note "FAIL $name reason"
    FAILS=$((FAILS + 1))
    return
  fi
  if [ -n "$(find "$CASE_WORK" -name 'plain.dump' -o -name 'crontab.txt' -print 2>/dev/null)" ]; then
    note "FAIL $name plaintext"
    FAILS=$((FAILS + 1))
    return
  fi
  note "PASS $name"
  PASS=$((PASS + 1))
}

if grep -E -n 's3 rm|delete-object|s3api delete' "$SCRIPT_DIR/platform_backup.sh"; then
  note "FAIL no-delete-command"
  FAILS=$((FAILS + 1))
else
  note "PASS no-delete-command"
  PASS=$((PASS + 1))
fi

# 수동 성공
new_case ok-manual
sleep 120 &
LIVE_PID=$!
mkdir -p "$CASE_WORK/run_${LIVE_PID}_keep" "$CASE_WORK/run_999999_stale"
printf 'x\n' > "$CASE_WORK/run_999999_stale/plain.dump"
set +e
run_backup --manual
ok_ec=$?
set -e
if [ "$ok_ec" -ne 0 ]; then
  note "FAIL ok-manual exit=$ok_ec"
  sed -n '1,20p' "$CASE_LOG" "$CASE_DIR/stderr"
  FAILS=$((FAILS + 1))
elif ! grep -q "MANUAL_OK " "$CASE_LOG"; then note "FAIL ok-manual log"; FAILS=$((FAILS + 1)); else
  if grep -q "SCHEDULED_OK\|PING_" "$CASE_LOG"; then note "FAIL ok-manual ping"; FAILS=$((FAILS + 1));
  elif [ ! -d "$CASE_WORK/run_${LIVE_PID}_keep" ]; then note "FAIL ok-manual live-dir"; FAILS=$((FAILS + 1));
  elif [ -d "$CASE_WORK/run_999999_stale" ]; then note "FAIL ok-manual stale"; FAILS=$((FAILS + 1));
  elif [ -n "$(find "$CASE_WORK" -name 'plain.dump' -print)" ]; then note "FAIL ok-manual plaintext"; FAILS=$((FAILS + 1));
  elif [ "$(find "$CASE_SINK" -name COMPLETE | wc -l | tr -d ' ')" != 1 ]; then note "FAIL ok-manual complete"; FAILS=$((FAILS + 1));
  else
    SET_DIR=$(find "$CASE_SERVER" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    gpg --batch --pinentry-mode loopback --passphrase '' --homedir "$GNUPGHOME" --decrypt "$SET_DIR/dump.gpg" > "$CASE_DIR/dump.bin"
    "$PG_RESTORE" -l "$CASE_DIR/dump.bin" > "$CASE_DIR/toc.txt"
    missing=0
    while IFS= read -r table; do
      schema=${table%%.*}
      name=${table#*.}
      if ! grep -E "[[:space:]]TABLE[[:space:]]+${schema}[[:space:]]+${name}[[:space:]]" "$CASE_DIR/toc.txt" >/dev/null; then
        missing=1
      fi
    done < "$SCRIPT_DIR/expected_tables.txt"
    gpg --batch --pinentry-mode loopback --passphrase '' --homedir "$GNUPGHOME" --decrypt "$SET_DIR/config.gpg" > "$CASE_DIR/config.tar"
    tar -tf "$CASE_DIR/config.tar" | sort > "$CASE_DIR/members.txt"
    printf '%s\n' ".env" "crontab.txt" | sort > "$CASE_DIR/members.expected"
    if [ "$missing" -ne 0 ]; then note "FAIL ok-manual tables"; FAILS=$((FAILS + 1));
    elif ! cmp -s "$CASE_DIR/members.txt" "$CASE_DIR/members.expected"; then note "FAIL ok-manual bundle"; FAILS=$((FAILS + 1));
    elif ! grep -q "CLEANUP_CANDIDATE action=none" "$CASE_LOG"; then note "FAIL ok-manual candidate"; FAILS=$((FAILS + 1));
    else note "PASS ok-manual"; PASS=$((PASS + 1)); fi
  fi
fi
kill "$LIVE_PID" 2>/dev/null || true
wait "$LIVE_PID" 2>/dev/null || true

# 예약 실행은 핑을 보내고, 주소는 인자에 없다
new_case ok-scheduled
CASE_ARG=--scheduled
CASE_HEART=$CASE_DIR/heartbeat.curl
PAY003_CURL_TRACE=$CASE_DIR/curl.trace
export PAY003_CURL_TRACE
cat > "$CASE_HEART" <<'EOF'
silent
output = "/dev/null"
url = "http://127.0.0.1/pay003a-heartbeat-test"
EOF
chmod 600 "$CASE_HEART"
run_backup
if ! grep -q "SCHEDULED_OK " "$CASE_LOG"; then note "FAIL ok-scheduled log"; FAILS=$((FAILS + 1));
elif ! grep -q -- "--config" "$PAY003_CURL_TRACE"; then note "FAIL ok-scheduled curl"; FAILS=$((FAILS + 1));
elif grep -q "http" "$PAY003_CURL_TRACE"; then note "FAIL ok-scheduled url-in-argv"; FAILS=$((FAILS + 1));
else note "PASS ok-scheduled"; PASS=$((PASS + 1)); fi
unset CASE_ARG PAY003_CURL_TRACE

# 하트비트 파일이 없으면 기록만
new_case ping-missing
CASE_ARG=--scheduled
run_backup
if ! grep -q "SCHEDULED_OK " "$CASE_LOG"; then note "FAIL ping-missing ok"; FAILS=$((FAILS + 1));
elif ! grep -q "PING_SKIPPED reason=no-file" "$CASE_LOG"; then note "FAIL ping-missing skip"; FAILS=$((FAILS + 1));
else note "PASS ping-missing"; PASS=$((PASS + 1)); fi
unset CASE_ARG

CASE_FPR=0000000000000000000000000000000000000000
expect_fail fingerprint fingerprint
unset CASE_FPR

new_case no-key
EMPTY_GNUPG=$CASE_DIR/empty-gnupg
mkdir -p "$EMPTY_GNUPG"
chmod 700 "$EMPTY_GNUPG"
PAY003_GNUPGHOME_SAVE=$GNUPGHOME
GNUPGHOME=$EMPTY_GNUPG
CASE_FPR=$FPR
# 공개키 파일을 치우고 빈 키링만 둔다.
PUB_SAVE=$ROOT/pub.asc
mv "$ROOT/pub.asc" "$ROOT/pub.asc.hide"
set +e
run_backup
ec=$?
set -e
mv "$ROOT/pub.asc.hide" "$ROOT/pub.asc"
GNUPGHOME=$PAY003_GNUPGHOME_SAVE
unset CASE_FPR
if [ "$ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=fingerprint" "$CASE_LOG"; then
  note "FAIL no-key"
  FAILS=$((FAILS + 1))
else
  note "PASS no-key"
  PASS=$((PASS + 1))
fi

force_fail() {
  local name="$1" var="$2" reason="$3" ec=0
  new_case "$name"
  export "${var}=1"
  set +e
  run_backup
  ec=$?
  set -e
  unset "$var"
  if [ "$ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=${reason}" "$CASE_LOG"; then
    note "FAIL $name"
    FAILS=$((FAILS + 1))
  elif [ -n "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
    note "FAIL $name complete"
    FAILS=$((FAILS + 1))
  elif grep -q "MANUAL_OK\|SCHEDULED_OK" "$CASE_LOG"; then
    note "FAIL $name success"
    FAILS=$((FAILS + 1))
  else
    note "PASS $name"
    PASS=$((PASS + 1))
  fi
}

# fingerprint already used expect_fail. low-space needs the variable.
# Remove the mistaken expect_fail low-space by not calling it. It was called above.
# That call did not set FORCE, so it may have succeeded and been marked FAIL for missing reason=space.
# Re-count is messy. Do not call expect_fail for space. I already did. The result will show FAIL low-space
# and then PASS from force_fail if I name it differently.

force_fail swap PAY003_FORCE_SWAP swap
force_fail upload PAY003_UPLOAD_FAIL upload
force_fail transfer PAY003_TRANSFER_FAIL transfer
force_fail hash PAY003_REMOTE_HASH_MISMATCH hash
force_fail space PAY003_FORCE_LOW_SPACE space

# 동시 실행
new_case overlap
CASE_TIMEOUT=30
set +e
env PAY003_HOLD_SEC=6 bash -c 'exec "$@"' _ \
  env \
  PAY003_HOLD_SEC=6 \
  PAY003_CONF="$SCRIPT_DIR/platform_backup.conf" \
  PAY003_SINK=dir \
  PAY003_ALLOW_NONTMPFS=1 \
  PAY003_ASSUME_NO_SWAP=1 \
  PAY003_LOCK_FALLBACK=perl \
  PAY003_PG_DUMP="$PG_DUMP" \
  PAY003_PG_RESTORE="$PG_RESTORE" \
  PAY003_PG_SUDO_USER= \
  PAY003_DATABASE="$DB_NAME" \
  PAY003_ENV_FILE="$ROOT/backend/.env" \
  PAY003_CRONTAB_FILE="$ROOT/crontab.txt" \
  PAY003_GNUPGHOME="$GNUPGHOME" \
  PAY003_PUBKEY="$ROOT/pub.asc" \
  PAY003_FINGERPRINT="$FPR" \
  PAY003_WORK_PARENT="$CASE_WORK" \
  PAY003_SINK_DIR="$CASE_SINK" \
  PAY003_SERVER_SET_ROOT="$CASE_SERVER" \
  PAY003_LOCK_FILE="$CASE_LOCK" \
  PAY003_LOG="$CASE_LOG" \
  PAY003_HEARTBEAT="$CASE_HEART" \
  PAY003_TIMEOUT_SEC=30 \
  PGPASSFILE="$PASSFILE_WIN" \
  bash "$SCRIPT_DIR/platform_backup.sh" --manual > "$CASE_DIR/first.out" 2> "$CASE_DIR/first.err" &
first_pid=$!
sleep 1
mkdir -p "$CASE_WORK/run_999998_stale"
printf 'x\n' > "$CASE_WORK/run_999998_stale/plain.dump"
SECOND_LOG=$CASE_DIR/second.log
: > "$SECOND_LOG"
env \
  PAY003_CONF="$SCRIPT_DIR/platform_backup.conf" \
  PAY003_SINK=dir \
  PAY003_ALLOW_NONTMPFS=1 \
  PAY003_ASSUME_NO_SWAP=1 \
  PAY003_LOCK_FALLBACK=perl \
  PAY003_PG_DUMP="$PG_DUMP" \
  PAY003_PG_RESTORE="$PG_RESTORE" \
  PAY003_PG_SUDO_USER= \
  PAY003_DATABASE="$DB_NAME" \
  PAY003_ENV_FILE="$ROOT/backend/.env" \
  PAY003_CRONTAB_FILE="$ROOT/crontab.txt" \
  PAY003_GNUPGHOME="$GNUPGHOME" \
  PAY003_PUBKEY="$ROOT/pub.asc" \
  PAY003_FINGERPRINT="$FPR" \
  PAY003_WORK_PARENT="$CASE_WORK" \
  PAY003_SINK_DIR="$CASE_SINK" \
  PAY003_SERVER_SET_ROOT="$CASE_SERVER" \
  PAY003_LOCK_FILE="$CASE_LOCK" \
  PAY003_LOG="$SECOND_LOG" \
  PAY003_HEARTBEAT="$CASE_HEART" \
  PGPASSFILE="$PASSFILE_WIN" \
  bash "$SCRIPT_DIR/platform_backup.sh" --manual
second_ec=$?
wait "$first_pid"
first_ec=$?
set -e
if [ "$second_ec" -ne 0 ] || ! grep -q "OVERLAP " "$SECOND_LOG"; then
  note "FAIL overlap"
  FAILS=$((FAILS + 1))
elif [ ! -d "$CASE_WORK/run_999998_stale" ]; then
  note "FAIL overlap stale-removed"
  FAILS=$((FAILS + 1))
elif grep -q "MANUAL_OK\|SCHEDULED_OK" "$SECOND_LOG"; then
  note "FAIL overlap success"
  FAILS=$((FAILS + 1))
else
  note "PASS overlap"
  PASS=$((PASS + 1))
fi
unset CASE_TIMEOUT

# Git bash에는 flock이 없다. 실패만 돌려주는 명령으로 OVERLAP 경로를 확인한다.
new_case flock-busy
CASE_LOCK_FALLBACK=
cat > "$ROOT/bin/flock" <<'EOF'
#!/bin/bash
exit 1
EOF
chmod 700 "$ROOT/bin/flock"
set +e
run_backup --manual
flock_ec=$?
set -e
rm -f -- "$ROOT/bin/flock"
unset CASE_LOCK_FALLBACK
if [ "$flock_ec" -ne 0 ] || ! grep -q "OVERLAP " "$CASE_LOG"; then
  note "FAIL flock-busy"
  FAILS=$((FAILS + 1))
elif grep -q "MANUAL_OK\|SCHEDULED_OK" "$CASE_LOG"; then
  note "FAIL flock-busy success"
  FAILS=$((FAILS + 1))
elif [ -n "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
  note "FAIL flock-busy complete"
  FAILS=$((FAILS + 1))
else
  note "PASS flock-busy"
  PASS=$((PASS + 1))
fi

# 제한 시간
new_case timeout
CASE_TIMEOUT=1
set +e
env PAY003_SLEEP_BEFORE_DUMP=20 PAY003_TIMEOUT_SEC=1 bash -c 'exec "$@"' _ \
  env \
  PAY003_SLEEP_BEFORE_DUMP=20 \
  PAY003_TIMEOUT_SEC=1 \
  PAY003_CONF="$SCRIPT_DIR/platform_backup.conf" \
  PAY003_SINK=dir \
  PAY003_ALLOW_NONTMPFS=1 \
  PAY003_ASSUME_NO_SWAP=1 \
  PAY003_LOCK_FALLBACK=perl \
  PAY003_PG_DUMP="$PG_DUMP" \
  PAY003_PG_RESTORE="$PG_RESTORE" \
  PAY003_PG_SUDO_USER= \
  PAY003_DATABASE="$DB_NAME" \
  PAY003_ENV_FILE="$ROOT/backend/.env" \
  PAY003_CRONTAB_FILE="$ROOT/crontab.txt" \
  PAY003_GNUPGHOME="$GNUPGHOME" \
  PAY003_PUBKEY="$ROOT/pub.asc" \
  PAY003_FINGERPRINT="$FPR" \
  PAY003_WORK_PARENT="$CASE_WORK" \
  PAY003_SINK_DIR="$CASE_SINK" \
  PAY003_SERVER_SET_ROOT="$CASE_SERVER" \
  PAY003_LOCK_FILE="$CASE_LOCK" \
  PAY003_LOG="$CASE_LOG" \
  PAY003_HEARTBEAT="$CASE_HEART" \
  PGPASSFILE="$PASSFILE_WIN" \
  bash "$SCRIPT_DIR/platform_backup.sh" --manual
ec=$?
set -e
if [ "$ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=timeout" "$CASE_LOG"; then
  note "FAIL timeout"
  FAILS=$((FAILS + 1))
elif [ -n "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
  note "FAIL timeout complete"
  FAILS=$((FAILS + 1))
elif [ -n "$(find "$CASE_WORK" -name 'plain.dump' -print 2>/dev/null)" ]; then
  note "FAIL timeout plaintext"
  FAILS=$((FAILS + 1))
else
  note "PASS timeout"
  PASS=$((PASS + 1))
fi

note "RESULT pass=$PASS fail=$FAILS"
[ "$FAILS" -eq 0 ]
