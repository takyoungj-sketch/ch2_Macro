#!/bin/bash
# 운영 서버, 운영 키, 운영 데이터베이스는 쓰지 않는다.
set -euo pipefail
umask 077

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

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
INITDB=$(dirname -- "$PSQL")/initdb.exe
PG_CTL=$(dirname -- "$PSQL")/pg_ctl.exe
PG_ISREADY=$(dirname -- "$PSQL")/pg_isready.exe

safe_rm_tree() {
  local target="$1" prefix="$2" base canon logical
  [ -n "${target:-}" ] || return 0
  [ -d "$target" ] || return 0
  [ ! -L "$target" ] || return 0
  base=$(basename -- "$target")
  case "$base" in
    ${prefix}.*) ;;
    *) return 0 ;;
  esac
  logical=$(CDPATH= cd -- "$target" && pwd)
  canon=$(CDPATH= cd -P -- "$target" && pwd)
  [ "$logical" = "$canon" ] || return 0
  case "$canon" in
    /|/tmp|/dev|/dev/shm) return 0 ;;
  esac
  case "$canon" in
    /tmp/${prefix}.*) ;;
    *) return 0 ;;
  esac
  rm -rf -- "$canon"
}

ROOT=$(mktemp -d /tmp/pay003a-local.XXXXXX)
chmod 700 "$ROOT"
printf 'pay003a-local-temp\n' > "$ROOT/pay003a-temp-root"
ROOT_CANON=$(CDPATH= cd -P -- "$ROOT" && pwd)
case "$(basename -- "$ROOT")" in
  pay003a-local.*) ;;
  *) echo "FAIL test-root" >&2; exit 2 ;;
esac
[ ! -L "$ROOT" ]
[ "$ROOT_CANON" = "$(CDPATH= cd -- "$ROOT" && pwd)" ]

SENTINEL=$(mktemp -d /tmp/pay003a-sentinel.XXXXXX)
printf 'keep\n' > "$SENTINEL/keep"
export PAY003_TEST_ROOT=$SENTINEL

DB_NAME=pay003a_dummy
PGDATA=$ROOT/pgdata
PORT=55432
while [ "$PORT" -le 55532 ]; do
  set +e
  "$PG_ISREADY" -h 127.0.0.1 -p "$PORT" >/dev/null 2>&1
  ready=$?
  set -e
  [ "$ready" -eq 2 ] && break
  PORT=$((PORT + 1))
done
[ "$PORT" -ne 5432 ]
[ "$PORT" -le 55532 ]

GNUPGHOME=$ROOT/gnupg
export GNUPGHOME
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

CLUSTER_STARTED=0
cleanup() {
  if [ -n "${LIVE_PID:-}" ]; then
    kill "$LIVE_PID" 2>/dev/null || true
    wait "$LIVE_PID" 2>/dev/null || true
  fi
  if [ "$CLUSTER_STARTED" = 1 ]; then
    python "$SCRIPT_DIR/local_db.py" drop "$PSQL" "$DB_NAME" "$(cygpath -w "$PGDATA")" "$PORT" >/dev/null 2>&1 || true
    "$PG_CTL" -D "$(cygpath -w "$PGDATA")" -m fast -w stop >/dev/null 2>&1 || true
  fi
  safe_rm_tree "$ROOT" pay003a-local
  safe_rm_tree "${SENTINEL:-}" pay003a-sentinel
}
trap cleanup EXIT

WINDATA=$(cygpath -w "$PGDATA")
"$INITDB" -D "$WINDATA" -U postgres -A trust --encoding=UTF8 --no-locale --auth-local=trust --auth-host=trust > "$ROOT/initdb.log"
printf '%s\n' "host all all 127.0.0.1/32 trust" "host all all ::1/128 trust" >> "$PGDATA/pg_hba.conf"
"$PG_CTL" -D "$WINDATA" -l "$ROOT/pg.log" -w start -o "-p $PORT -h 127.0.0.1" > "$ROOT/pgctl.log"
CLUSTER_STARTED=1

export PGHOST=127.0.0.1
export PGPORT=$PORT
export PGUSER=postgres
export PGCONNECT_TIMEOUT=15
unset PGPASSWORD || true
unset PGPASSFILE || true

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

WINDATA=$(cygpath -w "$PGDATA")
set +e
python "$SCRIPT_DIR/local_db.py" drop "$PSQL" ch2_platform "$WINDATA" "$PORT" >/dev/null 2>&1
name_ec=$?
python "$SCRIPT_DIR/local_db.py" drop "$PSQL" "$DB_NAME" "$WINDATA" 5432 >/dev/null 2>&1
port_ec=$?
set -e
if [ "$name_ec" -eq 0 ] || [ "$port_ec" -eq 0 ]; then
  note "FAIL db-refuse"
  FAILS=$((FAILS + 1))
else
  note "PASS db-refuse"
  PASS=$((PASS + 1))
fi
mkdir -p "$SENTINEL/pgdata"
set +e
python "$SCRIPT_DIR/local_db.py" create "$PSQL" "$DB_NAME" "$(cygpath -w "$SENTINEL/pgdata")" "$PORT" >/dev/null 2>&1
marker_ec=$?
set -e
if [ "$marker_ec" -eq 0 ]; then
  note "FAIL db-marker"
  FAILS=$((FAILS + 1))
else
  note "PASS db-marker"
  PASS=$((PASS + 1))
fi
"$PSQL" -h 127.0.0.1 -p "$PORT" -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE pay003a_dummy" >/dev/null
"$PSQL" -h 127.0.0.1 -p "$PORT" -U postgres -d pay003a_dummy -v ON_ERROR_STOP=1 -c "CREATE TABLE marker (id integer); INSERT INTO marker VALUES (1);" >/dev/null
set +e
python "$SCRIPT_DIR/local_db.py" create "$PSQL" "$DB_NAME" "$WINDATA" "$PORT" >/dev/null 2>&1
exists_ec=$?
set -e
marker=$("$PSQL" -h 127.0.0.1 -p "$PORT" -U postgres -d pay003a_dummy -tAc "SELECT count(*) FROM marker")
if [ "$exists_ec" -eq 0 ] || [ "$marker" != 1 ]; then
  note "FAIL db-protect"
  FAILS=$((FAILS + 1))
else
  note "PASS db-protect"
  PASS=$((PASS + 1))
fi
python "$SCRIPT_DIR/local_db.py" drop "$PSQL" "$DB_NAME" "$WINDATA" "$PORT" >/dev/null
python "$SCRIPT_DIR/local_db.py" create "$PSQL" "$DB_NAME" "$WINDATA" "$PORT" >/dev/null

run_backup() {
  env \
    PAY003_CONF="$SCRIPT_DIR/platform_backup.conf" \
    PAY003_SINK="${CASE_SINK_MODE:-dir}" \
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
    PAY003_HANG="${CASE_HANG:-}" \
    PAY003_HANG_PIDFILE="${CASE_HANG_PID:-}" \
    PAY003_FORCE_SET_ID="${CASE_SET_ID:-}" \
    PAY003_SERVER_COPY_FAIL="${CASE_SERVER_COPY_FAIL:-}" \
    PAY003_COMPLETE_READ_FAIL="${CASE_COMPLETE_READ_FAIL:-}" \
    PAY003_HANG_CHILDFILE="${CASE_HANG_CHILD:-}" \
    PAY003_AWS_STUB="${CASE_AWS_STUB:-}" \
    PAY003_SAME_GROUP="${CASE_SAME_GROUP:-}" \
    PATH="$ROOT/bin:${PATH}" \
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
  if [ -n "$(find "$CASE_WORK" \( -name 'plain.dump' -o -name 'crontab.txt' \) -print 2>/dev/null)" ]; then
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
mkdir -p "$CASE_WORK/run_${LIVE_PID}_ab12" "$CASE_WORK/run_999999_dead"
printf 'x\n' > "$CASE_WORK/run_999999_dead/plain.dump"
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
  elif [ ! -d "$CASE_WORK/run_${LIVE_PID}_ab12" ]; then note "FAIL ok-manual live-dir"; FAILS=$((FAILS + 1));
  elif [ -d "$CASE_WORK/run_999999_dead" ]; then note "FAIL ok-manual stale"; FAILS=$((FAILS + 1));
  elif [ -n "$(find "$CASE_WORK" -name 'plain.dump' -print)" ]; then note "FAIL ok-manual plaintext"; FAILS=$((FAILS + 1));
  elif [ "$(find "$CASE_SINK" -name COMPLETE | wc -l | tr -d ' ')" != 1 ]; then note "FAIL ok-manual complete"; FAILS=$((FAILS + 1));
  else
    SET_DIR=$(find "$CASE_SERVER" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    gpg --batch --pinentry-mode loopback --passphrase '' --homedir "$GNUPGHOME" --decrypt "$SET_DIR/dump.gpg" > "$CASE_DIR/dump.bin"
    "$PG_RESTORE" -l "$CASE_DIR/dump.bin" > "$CASE_DIR/toc.txt"
    missing=0
    while IFS= read -r table; do
      table=${table%$'\r'}
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
  bash "$SCRIPT_DIR/platform_backup.sh" --manual > "$CASE_DIR/first.out" 2> "$CASE_DIR/first.err" &
first_pid=$!
sleep 1
mkdir -p "$CASE_WORK/run_999998_deadbeef"
printf 'x\n' > "$CASE_WORK/run_999998_deadbeef/plain.dump"
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
  bash "$SCRIPT_DIR/platform_backup.sh" --manual
second_ec=$?
wait "$first_pid"
first_ec=$?
set -e
if [ "$second_ec" -ne 0 ] || ! grep -q "OVERLAP " "$SECOND_LOG"; then
  note "FAIL overlap"
  FAILS=$((FAILS + 1))
elif [ ! -d "$CASE_WORK/run_999998_deadbeef" ]; then
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

hang_case() {
  local stage="$1" ec=0 pid=""
  new_case "hang-$stage"
  CASE_TIMEOUT=3
  CASE_HANG=$stage
  CASE_HANG_PID=$CASE_DIR/hang.pid
  set +e
  run_backup
  ec=$?
  set -e
  unset CASE_HANG CASE_HANG_PID
  CASE_TIMEOUT=
  if [ -s "$CASE_DIR/hang.pid" ]; then
    pid=$(cat "$CASE_DIR/hang.pid")
  fi
  if [ "$ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=timeout" "$CASE_LOG"; then
    note "FAIL hang-$stage exit=$ec"
    sed -n '1,20p' "$CASE_LOG" "$CASE_DIR/stderr" >&2 || true
    FAILS=$((FAILS + 1))
  elif [ -n "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
    note "FAIL hang-$stage complete"
    FAILS=$((FAILS + 1))
  elif [ -n "$(find "$CASE_WORK" \( -name 'plain.dump' -o -name 'crontab.txt' \) -print 2>/dev/null)" ]; then
    note "FAIL hang-$stage plaintext"
    FAILS=$((FAILS + 1))
  elif [ -z "$pid" ] || kill -0 "$pid" 2>/dev/null; then
    note "FAIL hang-$stage alive"
    [ -n "$pid" ] && kill -KILL "$pid" 2>/dev/null || true
    FAILS=$((FAILS + 1))
  else
    note "PASS hang-$stage"
    PASS=$((PASS + 1))
  fi
}

hang_case gpg
hang_case tar
hang_case aws

new_case server-copy
CASE_SERVER_COPY_FAIL=1
set +e
run_backup
ec=$?
set -e
unset CASE_SERVER_COPY_FAIL
if [ "$ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=server-copy" "$CASE_LOG"; then
  note "FAIL server-copy"
  FAILS=$((FAILS + 1))
elif [ -n "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
  note "FAIL server-copy complete"
  FAILS=$((FAILS + 1))
elif [ -z "$(find "$CASE_SINK" -name 'dump.gpg' -print 2>/dev/null)" ]; then
  note "FAIL server-copy deleted"
  FAILS=$((FAILS + 1))
else
  note "PASS server-copy"
  PASS=$((PASS + 1))
fi

new_case complete-read
CASE_COMPLETE_READ_FAIL=1
set +e
run_backup
ec=$?
set -e
unset CASE_COMPLETE_READ_FAIL
if [ "$ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=complete" "$CASE_LOG"; then
  note "FAIL complete-read"
  FAILS=$((FAILS + 1))
elif [ -z "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
  note "FAIL complete-read missing"
  FAILS=$((FAILS + 1))
elif grep -q "MANUAL_OK\|SCHEDULED_OK" "$CASE_LOG"; then
  note "FAIL complete-read success"
  FAILS=$((FAILS + 1))
else
  note "PASS complete-read"
  PASS=$((PASS + 1))
fi

new_case collision
COLLIDE=20260101T000000Z_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
mkdir -p "$CASE_SERVER/$COLLIDE" "$CASE_SINK/platform/$COLLIDE"
printf 'KEEP\n' > "$CASE_SERVER/$COLLIDE/marker"
printf 'KEEP\n' > "$CASE_SINK/platform/$COLLIDE/marker"
CASE_SET_ID=$COLLIDE
set +e
run_backup
ec=$?
set -e
unset CASE_SET_ID
got=$(sed -n 's/.*MANUAL_OK set=\([^ ]*\).*/\1/p' "$CASE_LOG" | head -n 1)
if [ "$ec" -ne 0 ] || [ -z "$got" ] || [ "$got" = "$COLLIDE" ]; then
  note "FAIL collision id"
  FAILS=$((FAILS + 1))
elif [ "$(cat "$CASE_SERVER/$COLLIDE/marker")" != "KEEP" ]; then
  note "FAIL collision marker"
  FAILS=$((FAILS + 1))
elif [ "$(cat "$CASE_SINK/platform/$COLLIDE/marker")" != "KEEP" ]; then
  note "FAIL collision bucket"
  FAILS=$((FAILS + 1))
else
  note "PASS collision"
  PASS=$((PASS + 1))
fi

new_case ping-leak
CASE_ARG=--scheduled
CASE_HEART=$CASE_DIR/heartbeat.curl
PAY003_CURL_TRACE=$CASE_DIR/curl.trace
export PAY003_CURL_TRACE
cat > "$CASE_HEART" <<'EOF'
silent
url = "http://127.0.0.1/pay003a-heartbeat-test"
EOF
chmod 600 "$CASE_HEART"
cat > "$ROOT/bin/curl" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "${PAY003_CURL_TRACE:?}"
printf '%s\n' "http://127.0.0.1/pay003a-heartbeat-test"
printf '%s\n' "BODY-SECRET-MARKER" >&2
exit 7
EOF
chmod 700 "$ROOT/bin/curl"
set +e
run_backup
ec=$?
set -e
cat > "$ROOT/bin/curl" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "${PAY003_CURL_TRACE:?}"
exit 0
EOF
chmod 700 "$ROOT/bin/curl"
unset CASE_ARG PAY003_CURL_TRACE
if ! grep -q "PING_FAIL reason=curl code=7" "$CASE_LOG"; then
  note "FAIL ping-leak log"
  sed -n '1,20p' "$CASE_LOG" >&2 || true
  FAILS=$((FAILS + 1))
elif grep -q "pay003a-heartbeat-test\|BODY-SECRET-MARKER" "$CASE_LOG" "$CASE_DIR/stdout" "$CASE_DIR/stderr"; then
  note "FAIL ping-leak exposed"
  FAILS=$((FAILS + 1))
else
  note "PASS ping-leak"
  PASS=$((PASS + 1))
fi

new_case bad-parent
mkdir -p "$CASE_DIR/outside/run_1_aa"
printf 'keep\n' > "$CASE_DIR/outside/run_1_aa/plain.dump"
set +e
env \
  PAY003_CONF="$SCRIPT_DIR/platform_backup.conf" \
  PAY003_SINK=dir \
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
  PAY003_WORK_PARENT="$CASE_DIR/outside" \
  PAY003_SINK_DIR="$CASE_SINK" \
  PAY003_SERVER_SET_ROOT="$CASE_SERVER" \
  PAY003_LOCK_FILE="$CASE_LOCK" \
  PAY003_LOG="$CASE_LOG" \
  PAY003_HEARTBEAT="$CASE_HEART" \
  bash "$SCRIPT_DIR/platform_backup.sh" --manual >"$CASE_DIR/stdout" 2>"$CASE_DIR/stderr"
ec=$?
set -e
if [ "$ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=work-parent" "$CASE_LOG"; then
  note "FAIL bad-parent"
  FAILS=$((FAILS + 1))
elif [ ! -f "$CASE_DIR/outside/run_1_aa/plain.dump" ]; then
  note "FAIL bad-parent deleted"
  FAILS=$((FAILS + 1))
else
  note "PASS bad-parent"
  PASS=$((PASS + 1))
fi

new_case bad-symlink
mkdir -p "$CASE_DIR/real"
printf 'keep\n' > "$CASE_DIR/real/keep"
ln -s "$CASE_DIR/real" "$CASE_DIR/link" 2>/dev/null || true
if [ ! -L "$CASE_DIR/link" ]; then
  if grep -F -q '[ ! -L "$WORK_PARENT" ] || fail work-parent' "$SCRIPT_DIR/platform_backup.sh" \
    && grep -F -q '[ ! -L /dev/shm ] || fail work-parent' "$SCRIPT_DIR/platform_backup.sh"; then
    note "SKIP bad-symlink no-privilege"
  else
    note "FAIL bad-symlink check-missing"
    FAILS=$((FAILS + 1))
  fi
else
  set +e
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
    PAY003_WORK_PARENT="$CASE_DIR/link" \
    PAY003_SINK_DIR="$CASE_SINK" \
    PAY003_SERVER_SET_ROOT="$CASE_SERVER" \
    PAY003_LOCK_FILE="$CASE_LOCK" \
    PAY003_LOG="$CASE_LOG" \
    PAY003_HEARTBEAT="$CASE_HEART" \
    bash "$SCRIPT_DIR/platform_backup.sh" --manual >"$CASE_DIR/stdout" 2>"$CASE_DIR/stderr"
  ec=$?
  set -e
  if [ "$ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=work-parent" "$CASE_LOG"; then
    note "FAIL bad-symlink"
    FAILS=$((FAILS + 1))
  elif [ ! -f "$CASE_DIR/real/keep" ]; then
    note "FAIL bad-symlink deleted"
    FAILS=$((FAILS + 1))
  else
    note "PASS bad-symlink"
    PASS=$((PASS + 1))
  fi
fi

new_case hang-group
CASE_TIMEOUT=3
CASE_HANG=group
CASE_HANG_PID=$CASE_DIR/hang.pid
CASE_HANG_CHILD=$CASE_DIR/child.pid
set +e
run_backup
group_ec=$?
set -e
unset CASE_HANG CASE_HANG_PID CASE_HANG_CHILD
CASE_TIMEOUT=
group_child=""
if [ -s "$CASE_DIR/child.pid" ]; then
  group_child=$(cat "$CASE_DIR/child.pid")
fi
if [ "$group_ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=timeout" "$CASE_LOG"; then
  note "FAIL hang-group exit=$group_ec"
  sed -n '1,20p' "$CASE_LOG" >&2 || true
  FAILS=$((FAILS + 1))
elif [ -z "$group_child" ] || kill -0 "$group_child" 2>/dev/null; then
  note "FAIL hang-group child"
  [ -n "$group_child" ] && kill -KILL "$group_child" 2>/dev/null || true
  FAILS=$((FAILS + 1))
elif grep -q "children-alive" "$CASE_LOG"; then
  note "FAIL hang-group lock"
  FAILS=$((FAILS + 1))
else
  note "PASS hang-group"
  PASS=$((PASS + 1))
fi

new_case own-group
CASE_TIMEOUT=3
CASE_HANG=same
CASE_HANG_PID=$CASE_DIR/hang.pid
set +e
run_backup
own_ec=$?
set -e
unset CASE_HANG CASE_HANG_PID
CASE_TIMEOUT=
own_pid=""
if [ -s "$CASE_DIR/hang.pid" ]; then
  own_pid=$(cat "$CASE_DIR/hang.pid")
fi
if [ "$own_ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=own-group" "$CASE_LOG"; then
  note "FAIL own-group exit=$own_ec"
  sed -n '1,20p' "$CASE_LOG" >&2 || true
  FAILS=$((FAILS + 1))
elif [ -z "$own_pid" ] || ! kill -0 "$own_pid" 2>/dev/null; then
  note "FAIL own-group signaled"
  FAILS=$((FAILS + 1))
else
  note "PASS own-group"
  PASS=$((PASS + 1))
fi
if [ -n "$own_pid" ]; then
  kill -KILL "$own_pid" 2>/dev/null || true
fi

new_case bad-set-id
printf 'keep\n' > "$CASE_DIR/keep-outside"
CASE_SET_ID='../outside'
set +e
run_backup
id_ec=$?
set -e
unset CASE_SET_ID
if [ "$id_ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=set-id" "$CASE_LOG"; then
  note "FAIL bad-set-id"
  FAILS=$((FAILS + 1))
elif [ "$(cat "$CASE_DIR/keep-outside")" != "keep" ]; then
  note "FAIL bad-set-id escaped"
  FAILS=$((FAILS + 1))
elif [ -n "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
  note "FAIL bad-set-id complete"
  FAILS=$((FAILS + 1))
else
  note "PASS bad-set-id"
  PASS=$((PASS + 1))
fi

new_case s3-error
CASE_SINK_MODE=aws
CASE_AWS_STUB=1
cat > "$ROOT/bin/aws" <<'EOF'
#!/bin/bash
echo "An error occurred (AccessDenied) when calling the ListObjectsV2 operation: Access Denied" >&2
exit 1
EOF
chmod 700 "$ROOT/bin/aws"
set +e
run_backup
s3_ec=$?
set -e
rm -f -- "$ROOT/bin/aws"
unset CASE_SINK_MODE CASE_AWS_STUB
if [ "$s3_ec" -eq 0 ] || ! grep -q "BACKUP_FAIL reason=s3" "$CASE_LOG"; then
  note "FAIL s3-error"
  sed -n '1,20p' "$CASE_LOG" >&2 || true
  FAILS=$((FAILS + 1))
elif [ -n "$(find "$CASE_SINK" -name COMPLETE -print 2>/dev/null)" ]; then
  note "FAIL s3-error complete"
  FAILS=$((FAILS + 1))
else
  note "PASS s3-error"
  PASS=$((PASS + 1))
fi

if [ ! -f "$SENTINEL/keep" ] || [ "$ROOT" = "$SENTINEL" ]; then
  note "FAIL test-root"
  FAILS=$((FAILS + 1))
else
  note "PASS test-root"
  PASS=$((PASS + 1))
fi

note "RESULT pass=$PASS fail=$FAILS"
[ "$FAILS" -eq 0 ]
