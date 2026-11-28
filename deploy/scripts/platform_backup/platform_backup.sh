#!/bin/bash
# PAY-003-A 매일 백업. 보관 세트는 지우지 않는다. 후보 목록만 남긴다.
set -euo pipefail
umask 077

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CONF=${PAY003_CONF:-$SCRIPT_DIR/platform_backup.conf}

# 설정 묶음 허용 목록. PLAN v3 §1. 이 두 이름만 tar에 넣는다.
CONFIG_BUNDLE_ENV=.env
CONFIG_BUNDLE_CRON=crontab.txt

BUCKET=""
REGION=""
FINGERPRINT=""
DATABASE=""
PG_DUMP=""
PG_RESTORE=""
PG_SUDO_USER=""
ENV_FILE=""
WORK_PARENT=""
LOCK_FILE=""
SERVER_SET_ROOT=""
GNUPGHOME=""
PUBKEY=""
LOG_FILE=""
HEARTBEAT=""
PLAINTEXT_CAP_BYTES=""
TIMEOUT_SEC=""
S3_PREFIX=""
TABLES_FILE=""

load_conf() {
  local line key val
  [ -f "$CONF" ] || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    case "$line" in
      ""|\#*) continue ;;
    esac
    key=${line%%=*}
    val=${line#*=}
    case "$key" in
      BUCKET) BUCKET=$val ;;
      REGION) REGION=$val ;;
      FINGERPRINT) FINGERPRINT=$val ;;
      DATABASE) DATABASE=$val ;;
      PG_DUMP) PG_DUMP=$val ;;
      PG_RESTORE) PG_RESTORE=$val ;;
      PG_SUDO_USER) PG_SUDO_USER=$val ;;
      ENV_FILE) ENV_FILE=$val ;;
      WORK_PARENT) WORK_PARENT=$val ;;
      LOCK_FILE) LOCK_FILE=$val ;;
      SERVER_SET_ROOT) SERVER_SET_ROOT=$val ;;
      GNUPGHOME) GNUPGHOME=$val ;;
      PUBKEY) PUBKEY=$val ;;
      LOG_FILE) LOG_FILE=$val ;;
      HEARTBEAT) HEARTBEAT=$val ;;
      PLAINTEXT_CAP_BYTES) PLAINTEXT_CAP_BYTES=$val ;;
      TIMEOUT_SEC) TIMEOUT_SEC=$val ;;
      S3_PREFIX) S3_PREFIX=$val ;;
      TABLES_FILE) TABLES_FILE=$val ;;
      *) return 1 ;;
    esac
  done < "$CONF"
}

apply_overrides() {
  if [ -n "${PAY003_BUCKET:-}" ]; then BUCKET=$PAY003_BUCKET; fi
  if [ -n "${PAY003_REGION:-}" ]; then REGION=$PAY003_REGION; fi
  if [ -n "${PAY003_FINGERPRINT:-}" ]; then FINGERPRINT=$PAY003_FINGERPRINT; fi
  if [ -n "${PAY003_DATABASE:-}" ]; then DATABASE=$PAY003_DATABASE; fi
  if [ -n "${PAY003_PG_DUMP:-}" ]; then PG_DUMP=$PAY003_PG_DUMP; fi
  if [ -n "${PAY003_PG_RESTORE:-}" ]; then PG_RESTORE=$PAY003_PG_RESTORE; fi
  if [ -n "${PAY003_PG_SUDO_USER+x}" ]; then PG_SUDO_USER=$PAY003_PG_SUDO_USER; fi
  if [ -n "${PAY003_ENV_FILE:-}" ]; then ENV_FILE=$PAY003_ENV_FILE; fi
  if [ -n "${PAY003_WORK_PARENT:-}" ]; then WORK_PARENT=$PAY003_WORK_PARENT; fi
  if [ -n "${PAY003_LOCK_FILE:-}" ]; then LOCK_FILE=$PAY003_LOCK_FILE; fi
  if [ -n "${PAY003_SERVER_SET_ROOT:-}" ]; then SERVER_SET_ROOT=$PAY003_SERVER_SET_ROOT; fi
  if [ -n "${PAY003_GNUPGHOME:-}" ]; then GNUPGHOME=$PAY003_GNUPGHOME; fi
  if [ -n "${PAY003_PUBKEY:-}" ]; then PUBKEY=$PAY003_PUBKEY; fi
  if [ -n "${PAY003_LOG:-}" ]; then LOG_FILE=$PAY003_LOG; fi
  if [ -n "${PAY003_HEARTBEAT:-}" ]; then HEARTBEAT=$PAY003_HEARTBEAT; fi
  if [ -n "${PAY003_CAP_BYTES:-}" ]; then PLAINTEXT_CAP_BYTES=$PAY003_CAP_BYTES; fi
  if [ -n "${PAY003_TIMEOUT_SEC:-}" ]; then TIMEOUT_SEC=$PAY003_TIMEOUT_SEC; fi
  if [ -n "${PAY003_S3_PREFIX:-}" ]; then S3_PREFIX=$PAY003_S3_PREFIX; fi
  if [ -n "${PAY003_TABLES:-}" ]; then TABLES_FILE=$PAY003_TABLES; fi
  return 0
}

MODE=manual
case "${1:-}" in
  "") MODE=${PAY003_MODE:-manual} ;;
  --manual) MODE=manual ;;
  --scheduled) MODE=scheduled ;;
  *) MODE=manual ;;
esac

SINK=${PAY003_SINK:-aws}
SINK_DIR=${PAY003_SINK_DIR:-}

RUN_DIR=""
RUN_CREATED=0
LOCK_PID=""
WATCHDOG_PID=""
CHILD_PID=""
TIMED_OUT=0

log_line() {
  local status="$1" rest="${2:-}"
  mkdir -p "$(dirname -- "$LOG_FILE")"
  printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status" "$rest" >> "$LOG_FILE"
}

fail() {
  log_line BACKUP_FAIL "reason=$1"
  exit 1
}

on_exit() {
  local ec=$?
  if [ -n "$WATCHDOG_PID" ]; then
    kill "$WATCHDOG_PID" 2>/dev/null || true
    wait "$WATCHDOG_PID" 2>/dev/null || true
  fi
  if [ "$RUN_CREATED" = 1 ] && [ -n "$RUN_DIR" ] && [ -d "$RUN_DIR" ]; then
    rm -rf -- "$RUN_DIR"
  fi
  if [ -n "$LOCK_PID" ]; then
    kill "$LOCK_PID" 2>/dev/null || true
    wait "$LOCK_PID" 2>/dev/null || true
  fi
  exit "$ec"
}
trap on_exit EXIT

on_term() {
  TIMED_OUT=1
  if [ -n "$CHILD_PID" ]; then
    kill -TERM "$CHILD_PID" 2>/dev/null || true
    local i=0
    while kill -0 "$CHILD_PID" 2>/dev/null && [ "$i" -lt 20 ]; do
      sleep 1
      i=$((i + 1))
    done
    if kill -0 "$CHILD_PID" 2>/dev/null; then
      kill -KILL "$CHILD_PID" 2>/dev/null || true
      wait "$CHILD_PID" 2>/dev/null || true
    fi
  fi
  log_line BACKUP_FAIL "reason=timeout"
  exit 124
}
trap on_term TERM

run_child() {
  "$@" &
  CHILD_PID=$!
  local ec=0
  wait "$CHILD_PID" || ec=$?
  CHILD_PID=""
  return "$ec"
}

start_watchdog() {
  (
    sleep "$TIMEOUT_SEC"
    kill -TERM $$ 2>/dev/null || true
  ) &
  WATCHDOG_PID=$!
}

sink_is_local() {
  [ "$SINK" = dir ]
}

acquire_lock() {
  mkdir -p "$(dirname -- "$LOCK_FILE")"
  if command -v flock >/dev/null 2>&1 && [ "${PAY003_LOCK_FALLBACK:-}" != perl ]; then
    exec 9>"$LOCK_FILE"
    if flock -n 9; then
      return 0
    fi
    return 1
  fi
  if [ "${PAY003_LOCK_FALLBACK:-}" != perl ] || ! sink_is_local; then
    log_line BACKUP_FAIL "reason=flock-missing"
    exit 1
  fi
  local reply
  coproc LOCKPROC {
    perl -e 'use Fcntl qw(:flock); open my $fh, ">>", $ARGV[0] or exit 2; if (!flock($fh, LOCK_EX|LOCK_NB)) { print "BUSY\n"; exit 1; } print "GOT\n"; STDOUT->autoflush(1); sleep 86400 while 1;' "$LOCK_FILE"
  }
  IFS= read -r reply <&"${LOCKPROC[0]}" || reply=BUSY
  if [ "$reply" != GOT ]; then
    kill "$LOCKPROC_PID" 2>/dev/null || true
    wait "$LOCKPROC_PID" 2>/dev/null || true
    return 1
  fi
  LOCK_PID=$LOCKPROC_PID
  return 0
}

remove_dead_run_dirs() {
  local d base pid
  [ -d "$WORK_PARENT" ] || return 0
  for d in "$WORK_PARENT"/run_*; do
    [ -d "$d" ] || continue
    base=$(basename -- "$d")
    pid=${base#run_}
    pid=${pid%%_*}
    case "$pid" in
      ''|*[!0-9]*) continue ;;
    esac
    if [ "$pid" = "$$" ]; then
      continue
    fi
    if kill -0 "$pid" 2>/dev/null; then
      continue
    fi
    rm -rf -- "$d"
  done
}

check_memory() {
  local avail fstype swaps
  if [ "${PAY003_FORCE_SWAP:-}" = 1 ]; then
    fail swap
  fi
  if [ "${PAY003_FORCE_LOW_SPACE:-}" = 1 ]; then
    fail space
  fi
  if [ "${PAY003_ASSUME_NO_SWAP:-}" = 1 ] && sink_is_local; then
    :
  elif [ -f /proc/swaps ]; then
    swaps=$(awk 'NR>1 { n++ } END { print n+0 }' /proc/swaps)
    if [ "$swaps" -gt 0 ]; then
      fail swap
    fi
  else
    fail swap-unknown
  fi
  fstype=$(df -T "$WORK_PARENT" | awk 'NR==2 { print $2 }')
  if [ "$fstype" != tmpfs ]; then
    if [ "${PAY003_ALLOW_NONTMPFS:-}" != 1 ] || ! sink_is_local; then
      fail not-tmpfs
    fi
  fi
  avail=$(df -B1 "$WORK_PARENT" | awk 'NR==2 { print $4 }')
  if [ "$avail" -lt "$PLAINTEXT_CAP_BYTES" ]; then
    fail space
  fi
  if [ -r /proc/meminfo ]; then
    avail=$(awk '/MemAvailable:/ { print $2 * 1024 }' /proc/meminfo)
    if [ -n "$avail" ] && [ "$avail" -lt "$PLAINTEXT_CAP_BYTES" ]; then
      fail memory
    fi
  elif [ "${PAY003_ALLOW_NONTMPFS:-}" != 1 ] || ! sink_is_local; then
    fail memory-unknown
  fi
}

normalize_fpr() {
  printf '%s' "$1" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]'
}

current_fpr() {
  gpg --batch --homedir "$GNUPGHOME" --with-colons --fingerprint 2>/dev/null \
    | awk -F: '/^fpr:/ { print $10; exit }'
}

ensure_key() {
  local want have
  want=$(normalize_fpr "$FINGERPRINT")
  mkdir -p "$GNUPGHOME"
  chmod 700 "$GNUPGHOME"
  have=$(normalize_fpr "$(current_fpr || true)")
  if [ "$have" != "$want" ] && [ -f "$PUBKEY" ]; then
    gpg --batch --homedir "$GNUPGHOME" --import "$PUBKEY" >/dev/null 2>&1 || true
    have=$(normalize_fpr "$(current_fpr || true)")
  fi
  [ "$have" = "$want" ] && [ -n "$want" ]
}

encrypt_to() {
  local src="$1" dest="$2" status="$RUN_DIR/gpg-status.txt" ec=0
  : > "$status"
  set +e
  gpg --batch --yes --homedir "$GNUPGHOME" --status-fd 1 \
    --trust-model always --recipient "$FINGERPRINT" \
    --output "$dest" --encrypt "$src" >"$status" 2>"$RUN_DIR/gpg.err"
  ec=$?
  set -e
  [ "$ec" -eq 0 ] || return 1
  grep -q "END_ENCRYPTION" "$status"
}

encrypt_config() {
  local env_dir status="$RUN_DIR/gpg-status.txt" tar_ec gpg_ec
  env_dir=$(dirname -- "$ENV_FILE")
  : > "$status"
  set +e
  tar -cf - -C "$env_dir" "$CONFIG_BUNDLE_ENV" -C "$RUN_DIR" "$CONFIG_BUNDLE_CRON" 2>"$RUN_DIR/tar.err" \
    | gpg --batch --yes --homedir "$GNUPGHOME" --status-fd 1 \
      --trust-model always --recipient "$FINGERPRINT" \
      --output "$RUN_DIR/config.gpg" --encrypt >"$status" 2>"$RUN_DIR/gpg.err"
  pipe_status=("${PIPESTATUS[@]}")
  tar_ec=${pipe_status[0]}
  gpg_ec=${pipe_status[1]}
  set -e
  [ "$tar_ec" -eq 0 ] && [ "$gpg_ec" -eq 0 ] || return 1
  grep -q "END_ENCRYPTION" "$status"
}

sha_file() {
  sha256sum -- "$1" | awk '{ print $1 }'
}

put_object() {
  local src="$1" key="$2" dest_dir
  if [ "${PAY003_UPLOAD_FAIL:-}" = 1 ]; then
    return 1
  fi
  if sink_is_local; then
    dest_dir=$SINK_DIR/$(dirname -- "$key")
    mkdir -p "$dest_dir"
    cp -- "$src" "$SINK_DIR/$key"
    return 0
  fi
  aws s3 cp --only-show-errors --region "$REGION" -- "$src" "s3://${BUCKET}/${key}"
}

remote_sha() {
  local key="$1" line ec1 ec2 size
  if [ "${PAY003_TRANSFER_FAIL:-}" = 1 ]; then
    return 1
  fi
  if sink_is_local; then
    [ -f "$SINK_DIR/$key" ] || return 1
    size=$(wc -c < "$SINK_DIR/$key" | tr -d ' ')
    if [ "$size" -gt "$PLAINTEXT_CAP_BYTES" ]; then
      return 1
    fi
    if [ "${PAY003_REMOTE_HASH_MISMATCH:-}" = 1 ]; then
      printf '%s\n' "0000000000000000000000000000000000000000000000000000000000000000"
      return 0
    fi
    sha_file "$SINK_DIR/$key"
    return 0
  fi
  size=$(aws s3api head-object --bucket "$BUCKET" --key "$key" --region "$REGION" --query ContentLength --output text)
  if [ "$size" -gt "$PLAINTEXT_CAP_BYTES" ]; then
    return 1
  fi
  set +e
  aws s3 cp --only-show-errors --region "$REGION" "s3://${BUCKET}/${key}" - 2>"$RUN_DIR/aws.err" \
    | sha256sum > "$RUN_DIR/remote.hashline"
  pipe_status=("${PIPESTATUS[@]}")
  ec1=${pipe_status[0]}
  ec2=${pipe_status[1]}
  set -e
  [ "$ec1" -eq 0 ] && [ "$ec2" -eq 0 ] || return 1
  line=$(awk '{ print $1 }' "$RUN_DIR/remote.hashline")
  [ -n "$line" ] || return 1
  printf '%s\n' "$line"
}

remote_text() {
  local key="$1"
  if [ "${PAY003_TRANSFER_FAIL:-}" = 1 ]; then
    return 1
  fi
  if sink_is_local; then
    [ -f "$SINK_DIR/$key" ] || return 1
    cat -- "$SINK_DIR/$key"
    return 0
  fi
  aws s3 cp --only-show-errors --region "$REGION" "s3://${BUCKET}/${key}" -
}

collect_tables() {
  local toc="$1" out="$2"
  awk '
    BEGIN { OFS=" " }
    /^;/ || /^$/ { next }
    {
      line=$0
      sub(/^[^;]*;/, "", line)
      sub(/^[ \t]+/, "", line)
      n=split(line, f, /[ \t]+/)
      if (n < 5) next
      rest=""
      for (i=3; i<=n; i++) rest=rest (i==3 ? "" : " ") f[i]
      if (index(rest, "TABLE DATA ") == 1) next
      if (index(rest, "TABLE ") == 1) {
        split(rest, t, /[ \t]+/)
        print t[2] "." t[3]
      }
    }
  ' "$toc" | sort > "$out"
}

dump_database() {
  if [ -n "$PG_SUDO_USER" ]; then
    run_child sudo -n -u "$PG_SUDO_USER" -- "$PG_DUMP" -Fc --no-owner --no-acl -f "$RUN_DIR/plain.dump" -d "$DATABASE"
  else
    run_child "$PG_DUMP" -Fc --no-owner --no-acl -f "$RUN_DIR/plain.dump" -d "$DATABASE"
  fi
}

write_crontab_text() {
  if [ -n "${PAY003_CRONTAB_FILE:-}" ]; then
    cp -- "$PAY003_CRONTAB_FILE" "$RUN_DIR/$CONFIG_BUNDLE_CRON"
  else
    crontab -l > "$RUN_DIR/$CONFIG_BUNDLE_CRON"
  fi
  chmod 600 "$RUN_DIR/$CONFIG_BUNDLE_CRON"
}

check_tables() {
  local found="$RUN_DIR/tables.found" expected="$RUN_DIR/tables.expected"
  "$PG_RESTORE" -l "$RUN_DIR/plain.dump" > "$RUN_DIR/toc.txt"
  collect_tables "$RUN_DIR/toc.txt" "$found"
  sort "$TABLES_FILE" > "$expected"
  cmp -s "$found" "$expected"
}

send_ping() {
  local perm
  if [ "$MODE" != scheduled ]; then
    return 0
  fi
  if [ ! -f "$HEARTBEAT" ]; then
    log_line PING_SKIPPED "reason=no-file"
    return 0
  fi
  perm=$(stat -c %a -- "$HEARTBEAT" 2>/dev/null || true)
  if [ "$perm" != 600 ]; then
    log_line PING_FAIL "reason=mode"
    return 1
  fi
  if curl --config "$HEARTBEAT" --silent --show-error --max-time 20; then
    return 0
  fi
  log_line PING_FAIL "reason=curl"
  return 1
}

print_candidates() {
  local d name
  log_line CLEANUP_CANDIDATE "action=none"
  {
    printf '%s\n' "server_sets:"
    if [ -d "$SERVER_SET_ROOT" ]; then
      for d in "$SERVER_SET_ROOT"/*; do
        [ -d "$d" ] || continue
        name=$(basename -- "$d")
        case "$name" in
          gnupg|run_*) continue ;;
        esac
        printf '%s\n' "$name"
      done | sort
    fi
    printf '%s\n' "bucket_sets:"
    if sink_is_local; then
      if [ -d "$SINK_DIR/$S3_PREFIX" ]; then
        for d in "$SINK_DIR/$S3_PREFIX"/*; do
          [ -d "$d" ] || continue
          basename -- "$d"
        done | sort
      fi
    else
      aws s3 ls "s3://${BUCKET}/${S3_PREFIX}/" --region "$REGION" || true
    fi
  } >> "$LOG_FILE"
}

load_conf || fail conf
apply_overrides
[ -n "$TABLES_FILE" ] || TABLES_FILE=$SCRIPT_DIR/expected_tables.txt
[ -n "$BUCKET" ] && [ -n "$REGION" ] && [ -n "$FINGERPRINT" ] || fail conf
[ -n "$DATABASE" ] && [ -n "$PG_DUMP" ] && [ -n "$PG_RESTORE" ] || fail conf
[ -n "$ENV_FILE" ] && [ -n "$WORK_PARENT" ] && [ -n "$LOCK_FILE" ] || fail conf
[ -n "$SERVER_SET_ROOT" ] && [ -n "$GNUPGHOME" ] && [ -n "$PUBKEY" ] || fail conf
[ -n "$LOG_FILE" ] && [ -n "$HEARTBEAT" ] && [ -n "$PLAINTEXT_CAP_BYTES" ] || fail conf
[ -n "$TIMEOUT_SEC" ] && [ -n "$S3_PREFIX" ] && [ -f "$TABLES_FILE" ] || fail conf
case "$MODE" in
  manual|scheduled) ;;
  *) fail mode ;;
esac
if [ "$SINK" = dir ] && [ -z "$SINK_DIR" ]; then
  fail sink
fi
case "$(basename -- "$ENV_FILE")" in
  "$CONFIG_BUNDLE_ENV") ;;
  *) fail env-name ;;
esac

RUN_TAG="$$_$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')"
RUN_DIR="${WORK_PARENT}/run_${RUN_TAG}"

if ! acquire_lock; then
  log_line OVERLAP "mode=$MODE"
  exit 0
fi

remove_dead_run_dirs
mkdir -p "$RUN_DIR"
chmod 700 "$RUN_DIR"
RUN_CREATED=1
start_watchdog

if [ -n "${PAY003_HOLD_SEC:-}" ]; then
  sleep "$PAY003_HOLD_SEC"
fi

check_memory

if [ -n "${PAY003_SLEEP_BEFORE_DUMP:-}" ]; then
  run_child sleep "$PAY003_SLEEP_BEFORE_DUMP"
fi

if ! ensure_key; then
  fail fingerprint
fi

[ -f "$ENV_FILE" ] || fail env-file
write_crontab_text
dump_database || fail dump
dump_bytes=$(wc -c < "$RUN_DIR/plain.dump" | tr -d ' ')
if [ "$dump_bytes" -gt "$PLAINTEXT_CAP_BYTES" ]; then
  fail too-large
fi
check_tables || fail tables

encrypt_to "$RUN_DIR/plain.dump" "$RUN_DIR/dump.gpg" || fail encrypt
encrypt_config || fail encrypt
rm -f -- "$RUN_DIR/plain.dump" "$RUN_DIR/$CONFIG_BUNDLE_CRON" "$RUN_DIR/toc.txt" "$RUN_DIR/tables.found" "$RUN_DIR/tables.expected"
if [ -e "$RUN_DIR/plain.dump" ] || [ -e "$RUN_DIR/$CONFIG_BUNDLE_CRON" ]; then
  fail plaintext
fi

dump_sha=$(sha_file "$RUN_DIR/dump.gpg")
config_sha=$(sha_file "$RUN_DIR/config.gpg")
dump_gpg_bytes=$(wc -c < "$RUN_DIR/dump.gpg" | tr -d ' ')
config_gpg_bytes=$(wc -c < "$RUN_DIR/config.gpg" | tr -d ' ')
created=$(date -u +%Y%m%dT%H%M%SZ)
rand=$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')
SET_ID="${created}_${rand}"

put_object "$RUN_DIR/dump.gpg" "${S3_PREFIX}/${SET_ID}/dump.gpg" || fail upload
put_object "$RUN_DIR/config.gpg" "${S3_PREFIX}/${SET_ID}/config.gpg" || fail upload
remote_dump=$(remote_sha "${S3_PREFIX}/${SET_ID}/dump.gpg") || fail transfer
remote_config=$(remote_sha "${S3_PREFIX}/${SET_ID}/config.gpg") || fail transfer
[ "$remote_dump" = "$dump_sha" ] || fail hash
[ "$remote_config" = "$config_sha" ] || fail hash

cat > "$RUN_DIR/COMPLETE" <<EOF
set_id=${SET_ID}
created_utc=${created}
dump.gpg ${dump_sha} ${dump_gpg_bytes}
config.gpg ${config_sha} ${config_gpg_bytes}
EOF
chmod 600 "$RUN_DIR/COMPLETE"
put_object "$RUN_DIR/COMPLETE" "${S3_PREFIX}/${SET_ID}/COMPLETE" || fail upload
remote_complete=$(remote_text "${S3_PREFIX}/${SET_ID}/COMPLETE") || fail transfer
if [ "$remote_complete" != "$(cat -- "$RUN_DIR/COMPLETE")" ]; then
  fail complete
fi

mkdir -p "${SERVER_SET_ROOT}/${SET_ID}"
chmod 700 "${SERVER_SET_ROOT}/${SET_ID}"
cp -- "$RUN_DIR/dump.gpg" "${SERVER_SET_ROOT}/${SET_ID}/dump.gpg"
cp -- "$RUN_DIR/config.gpg" "${SERVER_SET_ROOT}/${SET_ID}/config.gpg"
cp -- "$RUN_DIR/COMPLETE" "${SERVER_SET_ROOT}/${SET_ID}/COMPLETE"
chmod 600 "${SERVER_SET_ROOT}/${SET_ID}/dump.gpg" "${SERVER_SET_ROOT}/${SET_ID}/config.gpg" "${SERVER_SET_ROOT}/${SET_ID}/COMPLETE"

if [ "$MODE" = scheduled ]; then
  log_line SCHEDULED_OK "set=${SET_ID} bytes=${dump_gpg_bytes} sha256=${dump_sha}"
  send_ping || true
else
  log_line MANUAL_OK "set=${SET_ID} bytes=${dump_gpg_bytes} sha256=${dump_sha}"
fi
print_candidates
exit 0
