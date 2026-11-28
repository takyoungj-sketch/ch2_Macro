#!/bin/bash
# PAY-003-A 매일 백업. 보관 세트는 지우지 않는다. 후보 목록만 남긴다.
set -euo pipefail
umask 077

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CONF=${PAY003_CONF:-$SCRIPT_DIR/platform_backup.conf}

# 설정 묶음 허용 목록. PLAN v3 §1. 이 두 이름만 tar에 넣는다.
CONFIG_BUNDLE_ENV=.env
CONFIG_BUNDLE_CRON=crontab.txt
# 평문 상한과 같은 크기의 암호문, 그리고 설정 묶음 여유까지 더해 공간을 본다.
CONFIG_BUNDLE_CAP_BYTES=1048576
ALLOWED_WORK_PARENT=/dev/shm/ch2pay003

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
CHILD_PGID=""
CHILDREN_REAPED=1
CHILDREN_LIVE=0
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

reap_children() {
  local i=0 pgid
  if [ "$CHILDREN_REAPED" = 1 ] || [ -z "$CHILD_PGID" ]; then
    CHILDREN_REAPED=1
    return 0
  fi
  pgid=$CHILD_PGID
  kill -TERM -"$pgid" 2>/dev/null || kill -TERM "$pgid" 2>/dev/null || true
  while kill -0 "$pgid" 2>/dev/null && [ "$i" -lt 20 ]; do
    sleep 1
    i=$((i + 1))
  done
  if kill -0 "$pgid" 2>/dev/null; then
    kill -KILL -"$pgid" 2>/dev/null || kill -KILL "$pgid" 2>/dev/null || true
    wait "$pgid" 2>/dev/null || true
  else
    wait "$pgid" 2>/dev/null || true
  fi
  if kill -0 "$pgid" 2>/dev/null; then
    CHILDREN_LIVE=1
  fi
  CHILD_PID=""
  CHILD_PGID=""
  CHILDREN_REAPED=1
}

on_exit() {
  local ec=$?
  reap_children
  if [ -n "$WATCHDOG_PID" ]; then
    kill "$WATCHDOG_PID" 2>/dev/null || true
    wait "$WATCHDOG_PID" 2>/dev/null || true
    WATCHDOG_PID=""
  fi
  if [ "$CHILDREN_LIVE" != 1 ] && [ "$RUN_CREATED" = 1 ]; then
    safe_rm_run_dir "$RUN_DIR" || true
  fi
  if [ -n "$LOCK_PID" ]; then
    kill "$LOCK_PID" 2>/dev/null || true
    wait "$LOCK_PID" 2>/dev/null || true
    LOCK_PID=""
  fi
  exit "$ec"
}
trap on_exit EXIT

on_term() {
  TIMED_OUT=1
  reap_children
  log_line BACKUP_FAIL "reason=timeout"
  exit 124
}
trap on_term TERM

run_group() {
  local ec=0
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" &
  else
    set -m
    "$@" &
  fi
  CHILD_PID=$!
  CHILD_PGID=$CHILD_PID
  CHILDREN_REAPED=0
  set +e
  wait "$CHILD_PID"
  ec=$?
  set -e
  CHILD_PID=""
  CHILD_PGID=""
  CHILDREN_REAPED=1
  return "$ec"
}

run_child() {
  run_group "$@"
}

hang_stage() {
  local stage="$1"
  [ -n "${PAY003_HANG_PIDFILE:-}" ] || return 1
  run_group bash -c 'printf "%s\n" "$$" > "$1"; exec sleep 300' _ "$PAY003_HANG_PIDFILE"
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
    exec 9>>"$LOCK_FILE"
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

run_name_ok() {
  printf '%s' "$1" | grep -Eq '^run_[0-9]+_[0-9a-fA-F]+$'
}

phys_dir() {
  (CDPATH= cd -P -- "$1" && pwd)
}

safe_rm_run_dir() {
  local target="$1" base parent_phys target_phys
  [ -n "${target:-}" ] || return 1
  [ -d "$target" ] || return 0
  [ ! -L "$target" ] || return 1
  base=$(basename -- "$target")
  run_name_ok "$base" || return 1
  parent_phys=$(phys_dir "$WORK_PARENT") || return 1
  target_phys=$(phys_dir "$target") || return 1
  [ "$(dirname -- "$target_phys")" = "$parent_phys" ] || return 1
  rm -rf -- "$target_phys"
}

test_work_allowed() {
  sink_is_local && [ "${PAY003_ALLOW_NONTMPFS:-}" = 1 ]
}

validate_work_parent() {
  local logical physical
  if test_work_allowed; then
    [ -d "$WORK_PARENT" ] || fail work-parent
    [ ! -L "$WORK_PARENT" ] || fail work-parent
    logical=$(CDPATH= cd -- "$WORK_PARENT" && pwd) || fail work-parent
    physical=$(phys_dir "$WORK_PARENT") || fail work-parent
    [ "$logical" = "$physical" ] || fail work-parent
    case "$physical" in
      /|/tmp|/dev|/dev/shm|/opt|/home|/var) fail work-parent ;;
    esac
    WORK_PARENT=$physical
    return 0
  fi
  [ "$WORK_PARENT" = "$ALLOWED_WORK_PARENT" ] || fail work-parent
  [ -d /dev/shm ] || fail work-parent
  [ ! -L /dev/shm ] || fail work-parent
  if [ ! -d "$ALLOWED_WORK_PARENT" ]; then
    mkdir -- "$ALLOWED_WORK_PARENT" || fail work-parent
  fi
  [ ! -L "$ALLOWED_WORK_PARENT" ] || fail work-parent
  physical=$(phys_dir "$ALLOWED_WORK_PARENT") || fail work-parent
  [ "$physical" = "$ALLOWED_WORK_PARENT" ] || fail work-parent
  WORK_PARENT=$physical
}

remove_dead_run_dirs() {
  local d base pid
  [ -d "$WORK_PARENT" ] || return 0
  [ ! -L "$WORK_PARENT" ] || return 0
  for d in "$WORK_PARENT"/run_*; do
    [ -e "$d" ] || continue
    [ -L "$d" ] && continue
    [ -d "$d" ] || continue
    base=$(basename -- "$d")
    run_name_ok "$base" || continue
    pid=${base#run_}
    pid=${pid%%_*}
    if [ "$pid" = "$$" ]; then
      continue
    fi
    if kill -0 "$pid" 2>/dev/null; then
      continue
    fi
    safe_rm_run_dir "$d" || true
  done
}

peak_need() {
  local env_bytes=0 extra="${1:-0}"
  if [ -f "$ENV_FILE" ]; then
    env_bytes=$(wc -c < "$ENV_FILE" | tr -d ' ')
  fi
  echo $((PLAINTEXT_CAP_BYTES + PLAINTEXT_CAP_BYTES + env_bytes + CONFIG_BUNDLE_CAP_BYTES + extra))
}

space_ok() {
  local need="$1" avail
  avail=$(df -B1 "$WORK_PARENT" | awk 'NR==2 { print $4 }')
  case "$avail" in
    ''|*[!0-9]*) return 1 ;;
  esac
  [ "$avail" -ge "$need" ]
}

check_memory() {
  local avail fstype swaps need
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
    if ! test_work_allowed; then
      fail not-tmpfs
    fi
  fi
  need=$(peak_need 0)
  if ! space_ok "$need"; then
    fail space
  fi
  if [ -r /proc/meminfo ]; then
    avail=$(awk '/MemAvailable:/ { print $2 * 1024 }' /proc/meminfo)
    if [ -n "$avail" ] && [ "$avail" -lt "$need" ]; then
      fail memory
    fi
  elif ! test_work_allowed; then
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

keyring_ok() {
  local want="$1"
  gpg --batch --homedir "$GNUPGHOME" --with-colons --list-keys 2>/dev/null \
    | awk -F: -v want="$want" '
      BEGIN { pubs=0; enc=0; fpr="" }
      $1=="pub" {
        pubs++
        if (index($12, "e") > 0 || index($12, "E") > 0) enc=1
      }
      $1=="sub" {
        if (index($12, "e") > 0 || index($12, "E") > 0) enc=1
      }
      $1=="fpr" && fpr=="" { fpr=$10 }
      END { exit !(pubs==1 && enc==1 && fpr==want && want!="") }
    '
}

ensure_key() {
  local want
  want=$(normalize_fpr "$FINGERPRINT")
  [ -n "$want" ] || return 1
  mkdir -p "$GNUPGHOME"
  chmod 700 "$GNUPGHOME"
  if ! keyring_ok "$want" && [ -f "$PUBKEY" ]; then
    gpg --batch --homedir "$GNUPGHOME" --import "$PUBKEY" >/dev/null 2>&1 || true
  fi
  keyring_ok "$want"
}

encrypt_to() {
  local src="$1" dest="$2"
  if [ "${PAY003_HANG:-}" = gpg ]; then
    hang_stage gpg
    return $?
  fi
  : > "$RUN_DIR/gpg-status.txt"
  run_group bash -c '
    gpg --batch --yes --homedir "$1" --status-fd 1 \
      --trust-model always --recipient "$2" \
      --output "$3" --encrypt "$4" >"$5" 2>"$6"
  ' _ "$GNUPGHOME" "$FINGERPRINT" "$dest" "$src" "$RUN_DIR/gpg-status.txt" "$RUN_DIR/gpg.err" \
    || return 1
  grep -q "END_ENCRYPTION" "$RUN_DIR/gpg-status.txt"
}

encrypt_config() {
  local env_dir tar_ec gpg_ec
  env_dir=$(dirname -- "$ENV_FILE")
  if [ "${PAY003_HANG:-}" = tar ]; then
    hang_stage tar
    return $?
  fi
  : > "$RUN_DIR/gpg-status.txt"
  run_group bash -c '
    tar -cf - -C "$1" "$2" -C "$3" "$4" 2>"$3/tar.err" \
      | gpg --batch --yes --homedir "$5" --status-fd 1 \
          --trust-model always --recipient "$6" \
          --output "$3/config.gpg" --encrypt >"$3/gpg-status.txt" 2>"$3/gpg.err"
    printf "%s %s\n" "${PIPESTATUS[0]}" "${PIPESTATUS[1]}" > "$3/pipe.status"
  ' _ "$env_dir" "$CONFIG_BUNDLE_ENV" "$RUN_DIR" "$CONFIG_BUNDLE_CRON" "$GNUPGHOME" "$FINGERPRINT" \
    || return 1
  read -r tar_ec gpg_ec < "$RUN_DIR/pipe.status"
  [ "$tar_ec" -eq 0 ] && [ "$gpg_ec" -eq 0 ] || return 1
  grep -q "END_ENCRYPTION" "$RUN_DIR/gpg-status.txt"
}

sha_file() {
  sha256sum -- "$1" | awk '{ print $1 }'
}

put_object() {
  local src="$1" key="$2" dest_dir dest uncertain=0
  if [ "${PAY003_HANG:-}" = aws ]; then
    hang_stage aws
    return $?
  fi
  if [ "${PAY003_UPLOAD_FAIL:-}" = 1 ]; then
    return 1
  fi
  case "$key" in
    */COMPLETE)
      if [ "${PAY003_COMPLETE_UNCERTAIN:-}" = 1 ]; then
        uncertain=1
      fi
      ;;
  esac
  if sink_is_local; then
    dest=$SINK_DIR/$key
    if [ -e "$dest" ]; then
      return 1
    fi
    dest_dir=$(dirname -- "$dest")
    mkdir -p "$dest_dir"
    cp -- "$src" "$dest"
    if [ "$uncertain" -eq 1 ]; then
      return 1
    fi
    return 0
  fi
  if run_group aws s3api head-object --bucket "$BUCKET" --key "$key" --region "$REGION" >/dev/null 2>&1; then
    return 1
  fi
  run_group aws s3 cp --only-show-errors --region "$REGION" -- "$src" "s3://${BUCKET}/${key}" || return 1
  if [ "$uncertain" -eq 1 ]; then
    return 1
  fi
  return 0
}

complete_read_blocked() {
  [ "${PAY003_COMPLETE_READ_FAIL:-}" = 1 ] || return 1
  case "$1" in
    */COMPLETE) return 0 ;;
  esac
  return 1
}

remote_sha() {
  local key="$1" line ec1 ec2 size
  if [ "${PAY003_TRANSFER_FAIL:-}" = 1 ] || complete_read_blocked "$key"; then
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
  size=$(run_group aws s3api head-object --bucket "$BUCKET" --key "$key" --region "$REGION" --query ContentLength --output text) || return 1
  if [ "$size" -gt "$PLAINTEXT_CAP_BYTES" ]; then
    return 1
  fi
  run_group bash -c '
    aws s3 cp --only-show-errors --region "$1" "s3://$2/$3" - 2>"$4/aws.err" \
      | sha256sum > "$4/remote.hashline"
    printf "%s %s\n" "${PIPESTATUS[0]}" "${PIPESTATUS[1]}" > "$4/aws.status"
  ' _ "$REGION" "$BUCKET" "$key" "$RUN_DIR" || return 1
  read -r ec1 ec2 < "$RUN_DIR/aws.status"
  [ "$ec1" -eq 0 ] && [ "$ec2" -eq 0 ] || return 1
  line=$(awk '{ print $1 }' "$RUN_DIR/remote.hashline")
  [ -n "$line" ] || return 1
  printf '%s\n' "$line"
}

remote_text() {
  local key="$1"
  if [ "${PAY003_TRANSFER_FAIL:-}" = 1 ] || complete_read_blocked "$key"; then
    return 1
  fi
  if sink_is_local; then
    [ -f "$SINK_DIR/$key" ] || return 1
    cat -- "$SINK_DIR/$key"
    return 0
  fi
  run_group aws s3 cp --only-show-errors --region "$REGION" "s3://${BUCKET}/${key}" -
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
  local ping_out="$RUN_DIR/ping.out" code=0
  : > "$ping_out"
  chmod 600 "$ping_out"
  set +e
  run_group bash -c 'curl --config "$1" --silent --max-time 20 >"$2" 2>&1' _ "$HEARTBEAT" "$ping_out"
  code=$?
  set -e
  rm -f -- "$ping_out"
  if [ "$code" -eq 0 ]; then
    return 0
  fi
  log_line PING_FAIL "reason=curl code=${code}"
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

validate_work_parent
check_memory

if ! acquire_lock; then
  log_line OVERLAP "mode=$MODE"
  exit 0
fi

remove_dead_run_dirs
RUN_TAG="$$_$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')"
RUN_DIR="${WORK_PARENT}/run_${RUN_TAG}"
run_name_ok "$(basename -- "$RUN_DIR")" || fail work-parent
mkdir -p "$RUN_DIR"
chmod 700 "$RUN_DIR"
RUN_CREATED=1
start_watchdog

if [ -n "${PAY003_HOLD_SEC:-}" ]; then
  sleep "$PAY003_HOLD_SEC"
fi

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
env_bytes=$(wc -c < "$ENV_FILE" | tr -d ' ')
cron_bytes=$(wc -c < "$RUN_DIR/$CONFIG_BUNDLE_CRON" | tr -d ' ')
rm -f -- "$RUN_DIR/plain.dump" "$RUN_DIR/$CONFIG_BUNDLE_CRON" "$RUN_DIR/toc.txt" "$RUN_DIR/tables.found" "$RUN_DIR/tables.expected"
if [ -e "$RUN_DIR/plain.dump" ] || [ -e "$RUN_DIR/$CONFIG_BUNDLE_CRON" ]; then
  fail plaintext
fi

dump_sha=$(sha_file "$RUN_DIR/dump.gpg")
config_sha=$(sha_file "$RUN_DIR/config.gpg")
dump_gpg_bytes=$(wc -c < "$RUN_DIR/dump.gpg" | tr -d ' ')
config_gpg_bytes=$(wc -c < "$RUN_DIR/config.gpg" | tr -d ' ')
if ! space_ok $((dump_bytes + dump_gpg_bytes + env_bytes + cron_bytes)); then
  fail memory
fi

make_set_id() {
  local created rand
  created=$(date -u +%Y%m%dT%H%M%SZ)
  rand=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
  printf '%s_%s\n' "$created" "$rand"
}

set_id_taken() {
  local id="$1"
  [ -e "${SERVER_SET_ROOT}/${id}" ] && return 0
  if sink_is_local; then
    [ -e "$SINK_DIR/$S3_PREFIX/$id" ] && return 0
    return 1
  fi
  set +e
  run_group aws s3 ls "s3://${BUCKET}/${S3_PREFIX}/${id}/" --region "$REGION" > "$RUN_DIR/s3.ls" 2>"$RUN_DIR/s3.err"
  set -e
  if [ -s "$RUN_DIR/s3.ls" ]; then
    return 0
  fi
  return 1
}

choose_set_id() {
  local id="" i=0
  if [ -n "${PAY003_FORCE_SET_ID:-}" ]; then
    id=$PAY003_FORCE_SET_ID
  fi
  while [ "$i" -lt 5 ]; do
    if [ -z "$id" ]; then
      id=$(make_set_id)
    fi
    if set_id_taken "$id"; then
      id=""
      i=$((i + 1))
      continue
    fi
    SET_ID=$id
    return 0
  done
  return 1
}

choose_set_id || fail collision
created=${SET_ID%%_*}

put_object "$RUN_DIR/dump.gpg" "${S3_PREFIX}/${SET_ID}/dump.gpg" || fail upload
put_object "$RUN_DIR/config.gpg" "${S3_PREFIX}/${SET_ID}/config.gpg" || fail upload
remote_dump=$(remote_sha "${S3_PREFIX}/${SET_ID}/dump.gpg") || fail transfer
remote_config=$(remote_sha "${S3_PREFIX}/${SET_ID}/config.gpg") || fail transfer
[ "$remote_dump" = "$dump_sha" ] || fail hash
[ "$remote_config" = "$config_sha" ] || fail hash

if [ "${PAY003_SERVER_COPY_FAIL:-}" = 1 ]; then
  fail server-copy
fi
[ -e "${SERVER_SET_ROOT}/${SET_ID}" ] && fail collision
mkdir -p "${SERVER_SET_ROOT}/${SET_ID}"
chmod 700 "${SERVER_SET_ROOT}/${SET_ID}"
cp -- "$RUN_DIR/dump.gpg" "${SERVER_SET_ROOT}/${SET_ID}/dump.gpg"
cp -- "$RUN_DIR/config.gpg" "${SERVER_SET_ROOT}/${SET_ID}/config.gpg"

cat > "$RUN_DIR/COMPLETE" <<EOF
set_id=${SET_ID}
created_utc=${created}
dump.gpg ${dump_sha} ${dump_gpg_bytes}
config.gpg ${config_sha} ${config_gpg_bytes}
EOF
chmod 600 "$RUN_DIR/COMPLETE"
cp -- "$RUN_DIR/COMPLETE" "${SERVER_SET_ROOT}/${SET_ID}/COMPLETE"
chmod 600 "${SERVER_SET_ROOT}/${SET_ID}/dump.gpg" "${SERVER_SET_ROOT}/${SET_ID}/config.gpg" "${SERVER_SET_ROOT}/${SET_ID}/COMPLETE"
[ "$(stat -c %a "${SERVER_SET_ROOT}/${SET_ID}")" = 700 ] || fail server-copy
[ "$(stat -c %a "${SERVER_SET_ROOT}/${SET_ID}/dump.gpg")" = 600 ] || fail server-copy
[ "$(stat -c %a "${SERVER_SET_ROOT}/${SET_ID}/config.gpg")" = 600 ] || fail server-copy
[ "$(stat -c %a "${SERVER_SET_ROOT}/${SET_ID}/COMPLETE")" = 600 ] || fail server-copy
[ "$(sha_file "${SERVER_SET_ROOT}/${SET_ID}/dump.gpg")" = "$dump_sha" ] || fail server-copy
[ "$(sha_file "${SERVER_SET_ROOT}/${SET_ID}/config.gpg")" = "$config_sha" ] || fail server-copy
cmp -s "$RUN_DIR/COMPLETE" "${SERVER_SET_ROOT}/${SET_ID}/COMPLETE" || fail server-copy

complete_sha=$(sha_file "$RUN_DIR/COMPLETE")
put_object "$RUN_DIR/COMPLETE" "${S3_PREFIX}/${SET_ID}/COMPLETE" || true
remote_complete=$(remote_sha "${S3_PREFIX}/${SET_ID}/COMPLETE") || fail complete
[ "$remote_complete" = "$complete_sha" ] || fail complete

if [ "$MODE" = scheduled ]; then
  log_line SCHEDULED_OK "set=${SET_ID} bytes=${dump_gpg_bytes} sha256=${dump_sha}"
  send_ping || true
else
  log_line MANUAL_OK "set=${SET_ID} bytes=${dump_gpg_bytes} sha256=${dump_sha}"
fi
print_candidates
exit 0
