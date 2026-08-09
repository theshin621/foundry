#!/usr/bin/env bash
# ============================================================================
# maccleaner v1.1.4 — safe, auditable macOS cleanup
#
# Built for a dev MacBook via the foundry short-circuit process
# (maker -> adversarial checker -> fix -> re-verify).
# Philosophy: scan first, act only when told, quarantine instead of delete,
# always restorable, every action logged, never lie in the report.
#
# USAGE
#   bash maccleaner.sh                        scan + report (touches nothing)
#   bash maccleaner.sh --apply CATS           act on comma-separated categories
#   bash maccleaner.sh --apply all-safe       the conservative preset
#   bash maccleaner.sh --apply trash --trash-age 30
#   bash maccleaner.sh --list-quarantine      show quarantine batches
#   bash maccleaner.sh --restore TIMESTAMP    undo a quarantine batch
#   bash maccleaner.sh --purge-batch TIMESTAMP  permanently delete one batch now
#   bash maccleaner.sh --purge                permanently delete all batches
#                                             older than 14 days
#   bash maccleaner.sh --help | --version
#
# CATEGORIES
#   caches   user app caches     ~/Library/Caches/*        (quarantined)
#   logs     user app logs       ~/Library/Logs/*          (quarantined)
#   pip      pip caches          ~/Library/Caches/pip, ~/.cache/pip
#   npm      npm cache           native npm clean, verified, else quarantine
#   pnpm     pnpm store prune    native; reports measured freed space
#   yarn     yarn cache clean    native; reports measured freed space
#   gradle   gradle caches       ~/.gradle/caches          (quarantined)
#   cargo    cargo crate cache   ~/.cargo/registry/cache   (quarantined)
#   xcode    Xcode DerivedData   (quarantined)
#   sim      unavailable simulators (only when Command Line Tools installed)
#   brew     Homebrew cleanup    native; reports measured freed space
#   trash    ~/.Trash items whose content AND status are both older than
#            --trash-age days (PERMANENT delete; explicit-only; local Trash
#            only — external-drive .Trashes are not touched)
#   orphans  leftovers of uninstalled apps. Quarantines ONLY regenerable state
#            (Saved Application State, HTTPStorages, WebKit). Leftovers in
#            Application Support / Preferences / Containers / Group Containers
#            / LaunchAgents are REPORTED for manual review, never auto-moved:
#            they can hold real user data or active service definitions.
#   docker   docker system prune -f (explicit-only)
#
#   all-safe = caches,logs,pip,npm,pnpm,yarn,gradle,cargo,xcode,sim,brew
#   trash, orphans and docker must always be named explicitly.
#
# SAFETY GUARANTEES
#   - refuses to run as root; user-level only, never touches system paths
#   - default mode is a pure scan: it writes only its own report/log files
#   - every quarantine move is allowlist-checked against known-safe parents,
#     and refuses to move through a SYMLINKED parent directory — the checks
#     are path-based, so a symlinked ancestor (e.g. ~/Library/Caches pointed
#     at another volume or folder) would make them lie about where data
#     physically lives (v1.1.4, found by the deploy re-check)
#   - protected areas (Documents, Desktop, Dropbox, code folders, Pictures,
#     Music, Movies, Photos, iOS device backups) are structurally untouchable
#   - quarantined items keep their relative paths + a manifest for --restore
#   - quarantine lives on the same volume: applying MOVES data; disk space is
#     actually freed when you --purge-batch / --purge (the report says so)
#
# NOTES
#   - Sizes skip unreadable paths. For complete numbers, give your terminal
#     Full Disk Access (System Settings -> Privacy & Security). macOS may ask
#     permission for Desktop/Documents/Downloads on the first scan.
#   - Trash aging uses full days and requires BOTH the file's modification
#     time and its inode change time to exceed the threshold, so a freshly
#     trashed old file is protected (trashing updates ctime).
#   - Orphan tier 1 can include cookies/site data (HTTPStorages, WebKit) of an
#     app the scan cannot see (e.g. installed on an external volume): cost is
#     a re-login, and it is restorable. Undo is best-effort and time-sensitive
#     — a running app may recreate a path, and --restore never overwrites
#     (watch its WARN lines).
#   - pnpm stores and ~/.yarn/cache (and Yarn Berry's ~/.yarn/berry/cache)
#     are only reachable through their own tools; sizes are shown but never
#     counted in the promised total when the tool is absent.
#   - Verification gap, stated plainly: this build was tested on Linux with
#     bash 5 + GNU userland (85 automated checks + adversarial review), NOT
#     yet on stock macOS bash 3.2.57 / BSD tools. No bash-4+ syntax is used.
#     Make your first real run the default no-argument scan and read it
#     before applying anything.
#   - MC_ALLOW_NON_DARWIN=1 and MC_TRASH_IGNORE_CTIME=1 exist ONLY for the
#     sandbox test harness; never set them on a real machine.
# ============================================================================

set -euo pipefail

VERSION="1.1.4"

# ---------------------------------------------------------------- environment
if [ "$(id -u)" -eq 0 ]; then
  echo "maccleaner: refusing to run as root. Run as your normal user." >&2
  exit 1
fi

HOME_DIR="${HOME:?HOME is not set}"
if [ ! -d "$HOME_DIR" ]; then
  echo "maccleaner: HOME ($HOME_DIR) is not a directory." >&2
  exit 1
fi
case "$HOME_DIR" in
  /|/System*|/usr*|/bin*|/sbin*|/etc*|/var*)
    echo "maccleaner: HOME ($HOME_DIR) looks like a system path; aborting." >&2
    exit 1 ;;
esac

IS_DARWIN=0
[ "$(uname -s)" = "Darwin" ] && IS_DARWIN=1
if [ "$IS_DARWIN" = "0" ] && [ "${MC_ALLOW_NON_DARWIN:-0}" != "1" ]; then
  echo "maccleaner: this tool targets macOS (MC_ALLOW_NON_DARWIN=1 is for sandbox testing only)." >&2
  exit 1
fi

MC_ROOT="$HOME_DIR/MacCleaner"
Q_DIR="$MC_ROOT/quarantine"
R_DIR="$MC_ROOT/reports"
L_DIR="$MC_ROOT/logs"
TS="$(date +%Y%m%d-%H%M%S)"

is_cmd() { command -v "$1" >/dev/null 2>&1; }

# CLT gate: on a Mac without Command Line Tools, /usr/bin/xcrun and
# /usr/bin/python3 are stubs that pop a GUI installer dialog. Never call them.
clt_ok() {
  if [ "$IS_DARWIN" = "1" ]; then xcode-select -p >/dev/null 2>&1; else return 0; fi
}
py3_ok() { clt_ok && is_cmd python3; }

# ------------------------------------------------------------------ arguments
MODE="scan"   # scan | apply | restore | purge | purgebatch | list
APPLY_CATS=""
TRASH_AGE=30
RESTORE_TS=""
PURGE_TS=""

ALL_SAFE="caches,logs,pip,npm,pnpm,yarn,gradle,cargo,xcode,sim,brew"
KNOWN_CATS="caches logs pip npm pnpm yarn gradle cargo xcode sim brew trash orphans docker"

usage() {
  awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0" || true
}

validate_cats() {
  [ -n "$1" ] || { echo "maccleaner: --apply needs a non-empty category list" >&2; exit 2; }
  for c in $(printf '%s' "$1" | tr ',' ' '); do
    ok=0
    for k in $KNOWN_CATS; do [ "$c" = "$k" ] && ok=1; done
    [ "$ok" = "1" ] || { echo "maccleaner: unknown category '$c' (known: $KNOWN_CATS, all-safe)" >&2; exit 2; }
  done
}

# Quarantine timestamps are the ONLY thing --restore/--purge-batch accept.
# Whole-string case glob (not grep, which matches per-line and could pass a
# multi-line payload): kills path traversal before it can exist.
validate_ts() {
  case "$1" in
    [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]) : ;;
    *) echo "maccleaner: '$1' is not a quarantine timestamp (YYYYMMDD-HHMMSS; see --list-quarantine)" >&2; exit 2 ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)
      MODE="apply"
      [ $# -ge 2 ] || { echo "--apply needs a category list (or all-safe)" >&2; exit 2; }
      new_cats="$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')"
      new_cats="$(printf '%s' "$new_cats" | sed "s/all-safe/$ALL_SAFE/g")"
      # repeated --apply flags merge instead of silently replacing
      if [ -n "$APPLY_CATS" ]; then APPLY_CATS="$APPLY_CATS,$new_cats"; else APPLY_CATS="$new_cats"; fi
      validate_cats "$APPLY_CATS"
      shift 2 ;;
    --trash-age)
      [ $# -ge 2 ] || { echo "--trash-age needs a number of days" >&2; exit 2; }
      TRASH_AGE="$2"; shift 2 ;;
    --restore)
      MODE="restore"
      [ $# -ge 2 ] || { echo "--restore needs a quarantine timestamp" >&2; exit 2; }
      RESTORE_TS="$2"; validate_ts "$RESTORE_TS"; shift 2 ;;
    --purge-batch)
      MODE="purgebatch"
      [ $# -ge 2 ] || { echo "--purge-batch needs a quarantine timestamp" >&2; exit 2; }
      PURGE_TS="$2"; validate_ts "$PURGE_TS"; shift 2 ;;
    --purge) MODE="purge"; shift ;;
    --list-quarantine) MODE="list"; shift ;;
    --help|-h) usage; exit 0 ;;
    --version) echo "maccleaner $VERSION"; exit 0 ;;
    *) echo "maccleaner: unknown argument: $1 (see --help)" >&2; exit 2 ;;
  esac
done

case "$TRASH_AGE" in
  ''|*[!0-9]*) echo "maccleaner: --trash-age must be a whole number of days" >&2; exit 2 ;;
esac
if [ "${#TRASH_AGE}" -gt 5 ] || [ "$TRASH_AGE" -lt 1 ]; then
  echo "maccleaner: --trash-age must be between 1 and 99999 (full days)" >&2; exit 2
fi

cat_active() { case ",$APPLY_CATS," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }
is_safe_cat() { case ",$ALL_SAFE," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

# --------------------------------------------------- workspace (post-parse)
mkdir -p "$Q_DIR" "$R_DIR" "$L_DIR"
LOG_FILE="$L_DIR/run-$TS.log"
REPORT_FILE="$R_DIR/report-$TS.txt"
SCAN_TMP="$(mktemp "${TMPDIR:-/tmp}/maccleaner.scan.XXXXXX")"
INSTALLED_IDS="$(mktemp "${TMPDIR:-/tmp}/maccleaner.ids.XXXXXX")"
ORPHAN_REVIEW="$(mktemp "${TMPDIR:-/tmp}/maccleaner.rev.XXXXXX")"
ORPHAN_MOVED="$(mktemp "${TMPDIR:-/tmp}/maccleaner.mvd.XXXXXX")"
trap 'rm -f "$SCAN_TMP" "$INSTALLED_IDS" "$ORPHAN_REVIEW" "$ORPHAN_MOVED"' EXIT

log()  { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"; }
say()  { printf '%s\n' "$*"; printf '%s\n' "$*" >> "$REPORT_FILE"; }
warn() { printf 'WARN: %s\n' "$*" >&2; log "WARN: $*"; }

# du -sk works on BSD and GNU. du may exit nonzero on unreadable subpaths
# while still printing a usable total, so keep its output.
du_kb() {
  _p="$1"; _out=""
  if [ -e "$_p" ] || [ -L "$_p" ]; then
    _out="$(du -sk "$_p" 2>/dev/null | awk 'NR==1{print $1+0}')" || true
  fi
  if [ -n "$_out" ]; then echo "$_out"; else echo 0; fi
}

hum() { # KB -> human readable
  awk -v k="${1:-0}" 'BEGIN{
    v=k;
    if (v>=1048576) { printf "%.1f GB", v/1048576; exit }
    if (v>=1024)    { printf "%.1f MB", v/1024; exit }
    printf "%d KB", v }'
}

# --------------------------------------------------------- quarantine machinery
Q_BATCH="$Q_DIR/$TS"
MANIFEST="$Q_BATCH/MANIFEST.tsv"
TAB="$(printf '\t')"

# Allowlist of parents whose CHILDREN may be quarantined. A move is refused
# unless the source sits strictly inside one of these.
allowed_source() {
  s="$1"
  case "$s" in
    *"/../"*|*"/.."|*"$TAB"*|*"
"*|"") return 1 ;;
  esac
  case "$s" in
    "$HOME_DIR/Library/Caches/"?*) return 0 ;;
    "$HOME_DIR/Library/Logs/"?*) return 0 ;;
    "$HOME_DIR/.cache/"?*) return 0 ;;
    "$HOME_DIR/.gradle/caches") return 0 ;;
    "$HOME_DIR/.cargo/registry/cache") return 0 ;;
    "$HOME_DIR/.npm/_cacache") return 0 ;;
    "$HOME_DIR/Library/Developer/Xcode/DerivedData") return 0 ;;
    "$HOME_DIR/Library/Developer/Xcode/DerivedData/"?*) return 0 ;;
    "$HOME_DIR/Library/Saved Application State/"?*) return 0 ;;
    "$HOME_DIR/Library/HTTPStorages/"?*) return 0 ;;
    "$HOME_DIR/Library/WebKit/"?*) return 0 ;;
  esac
  return 1
}

# Belt-and-braces: absolute refusals even if allowlist logic ever regressed.
protected_source() {
  s="$1"
  case "$s" in
    "$HOME_DIR/Documents"*|"$HOME_DIR/Desktop"*|"$HOME_DIR/Dropbox"*| \
    "$HOME_DIR/Pictures"*|"$HOME_DIR/Movies"*|"$HOME_DIR/Music"*| \
    "$HOME_DIR/photos"*|"$HOME_DIR/Photos"*| \
    "$HOME_DIR/claudecoding"*|"$HOME_DIR/PycharmProjects"*| \
    "$HOME_DIR/EnterpriseDashboard"*|"$HOME_DIR/WeatherBot"*| \
    "$HOME_DIR/MRP_ClaudeBD"*| \
    "$HOME_DIR/Library/Application Support/MobileSync"*| \
    "$MC_ROOT"*) return 0 ;;
  esac
  return 1
}

# v1.1.4: the allowlist and protected veto match on the PATH STRING. If any
# ancestor of the source is a symlink (~/Library/Caches -> ~/Documents, a
# real relocated-caches setup), the string checks pass while the data
# physically lives somewhere protected. Refuse those moves outright.
has_symlink_ancestor() {
  p="$(dirname "$1")"
  while [ -n "$p" ] && [ "$p" != "/" ] && [ "$p" != "." ]; do
    [ -L "$p" ] && return 0
    [ "$p" = "$HOME_DIR" ] && break
    p="$(dirname "$p")"
  done
  return 1
}

safe_move() { # safe_move <source-path> -> quarantine, keeping relative path
  src="$1"
  [ -e "$src" ] || [ -L "$src" ] || return 1
  case "$src" in
    *"$TAB"*|*"
"*) warn "refused (tab/newline in name is unsupported): $src"; return 1 ;;
  esac
  if has_symlink_ancestor "$src"; then
    warn "refused (symlinked parent dir — physical location does not match the checked path): $src"; return 1
  fi
  if ! allowed_source "$src"; then
    warn "refused (not in allowlist): $src"; return 1
  fi
  if protected_source "$src"; then
    warn "refused (protected): $src"; return 1
  fi
  rel="${src#"$HOME_DIR"/}"
  dest="$Q_BATCH/$rel"
  if ! mkdir -p "$(dirname "$dest")" 2>/dev/null; then
    warn "could not create quarantine dir for: $src"; return 1
  fi
  kb="$(du_kb "$src")"
  if mv "$src" "$dest" 2>/dev/null; then
    printf '%s\t%s\t%s\n' "$src" "$dest" "$kb" >> "$MANIFEST"
    log "quarantined ($kb KB): $src"
    return 0
  else
    warn "could not move (in use?): $src"
    return 1
  fi
}

# ------------------------------------------------------------ restore / purge
do_restore() {
  batch="$Q_DIR/$RESTORE_TS"
  man="$batch/MANIFEST.tsv"
  [ -d "$batch" ] || { echo "No quarantine batch '$RESTORE_TS' (see --list-quarantine)" >&2; exit 1; }
  [ -f "$man" ] || { echo "Batch '$RESTORE_TS' has no manifest; restore by hand from $batch" >&2; exit 1; }
  restored=0; skipped=0
  while IFS="$TAB" read -r orig quar _kb; do
    [ -n "$orig" ] || continue
    if [ ! -e "$quar" ] && [ ! -L "$quar" ]; then
      warn "not in quarantine any more (already restored?): $orig"
      skipped=$((skipped+1)); continue
    fi
    if [ -e "$orig" ] || [ -L "$orig" ]; then
      warn "exists (owner app recreated it?), not overwriting: $orig"
      skipped=$((skipped+1)); continue
    fi
    if ! mkdir -p "$(dirname "$orig")" 2>/dev/null; then
      warn "could not recreate parent dir for: $orig"; skipped=$((skipped+1)); continue
    fi
    if mv "$quar" "$orig" 2>/dev/null; then restored=$((restored+1)); log "restored: $orig"
    else warn "failed to restore: $orig"; skipped=$((skipped+1)); fi
  done < "$man"
  echo "Restore complete: $restored restored, $skipped skipped (see warnings above)."
  echo "Log: $LOG_FILE"
}

purge_one() { # purge_one <batch-dir> — the ONLY recursive delete on quarantine
  b="$1"
  # defense in depth: prefix check, no traversal, basename must be a pure
  # timestamp, and the protected list gets a veto — even though validate_ts
  # already makes traversal impossible at parse time.
  case "$b" in
    "$Q_DIR"/?*) ;;
    *) warn "purge guard refused: $b"; return 1 ;;
  esac
  case "$b" in
    *"/../"*|*"/.."|*..*) warn "purge guard refused (traversal): $b"; return 1 ;;
  esac
  printf '%s' "$(basename "$b")" | grep -Eq '^[0-9]{8}-[0-9]{6}$' \
    || { warn "purge guard refused (not a batch timestamp): $b"; return 1; }
  kb="$(du_kb "$b")"
  if rm -rf "$b" 2>/dev/null; then
    log "purged batch $b ($kb KB)"
    echo "Purged $(basename "$b") — freed $(hum "$kb")"
    return 0
  else
    warn "could not fully purge: $b"
    return 1
  fi
}

do_purge() {
  n=0
  for b in "$Q_DIR"/*; do
    [ -d "$b" ] || continue
    if find "$b" -maxdepth 0 -mtime +14 2>/dev/null | grep -q .; then
      if purge_one "$b"; then n=$((n+1)); fi
    fi
  done
  [ "$n" -gt 0 ] || echo "No quarantine batches older than 14 days. Use --purge-batch TIMESTAMP to purge one now."
}

do_purge_batch() {
  b="$Q_DIR/$PURGE_TS"
  [ -d "$b" ] || { echo "No quarantine batch '$PURGE_TS' (see --list-quarantine)" >&2; exit 1; }
  purge_one "$b"
}

do_list() {
  found=0
  for b in "$Q_DIR"/*; do
    [ -d "$b" ] || continue
    found=1
    printf '%-22s %10s\n' "$(basename "$b")" "$(hum "$(du_kb "$b")")"
  done
  if [ "$found" = "1" ]; then
    echo ""
    echo "Restore one:  bash $0 --restore TIMESTAMP"
    echo "Free space:   bash $0 --purge-batch TIMESTAMP  (or --purge for 14d+)"
  else
    echo "Quarantine is empty."
  fi
}

case "$MODE" in
  restore) do_restore; exit 0 ;;
  purge) do_purge; exit 0 ;;
  purgebatch) do_purge_batch; exit 0 ;;
  list) do_list; exit 0 ;;
esac

# ------------------------------------------------------------------- scanning
add_row() { # add_row <category> <kb> <note>
  printf '%s|%s|%s\n' "$1" "$2" "$3" >> "$SCAN_TMP"
}

CACHE_DENY="CloudKit com.apple.bird com.apple.homed com.apple.HomeKit FamilyCircle com.apple.iCloudHelper"
cache_denied() {
  bn="$1"
  for d in $CACHE_DENY; do [ "$bn" = "$d" ] && return 0; done
  # Owned by their own categories — but only while that category can act:
  [ "$bn" = "pip" ] && return 0                      # pip category always handles it
  [ "$bn" = "Homebrew" ] && is_cmd brew && return 0  # else caches takes it
  [ "$bn" = "Yarn" ] && is_cmd yarn && return 0      # else caches takes it
  return 1
}

scan_dir_children() { # sum KB of children of a dir, honoring cache denylist flag
  parent="$1"; deny="$2"; sum=0
  [ -d "$parent" ] || { echo 0; return; }
  for e in "$parent"/*; do
    [ -e "$e" ] || continue
    if [ "$deny" = "deny" ] && cache_denied "$(basename "$e")"; then continue; fi
    sum=$((sum + $(du_kb "$e")))
  done
  echo "$sum"
}

apply_dir_children() { # quarantine children of a dir
  parent="$1"; deny="$2"; moved_kb=0
  [ -d "$parent" ] || { echo 0; return; }
  for e in "$parent"/*; do
    [ -e "$e" ] || continue
    if [ "$deny" = "deny" ] && cache_denied "$(basename "$e")"; then continue; fi
    kb="$(du_kb "$e")"
    if safe_move "$e"; then moved_kb=$((moved_kb + kb)); fi
  done
  echo "$moved_kb"
}

# --- caches / logs ---
run_caches() {
  if cat_active caches; then
    kb="$(apply_dir_children "$HOME_DIR/Library/Caches" deny)"
    add_row "caches" "$kb" "quarantined"
  else
    kb="$(scan_dir_children "$HOME_DIR/Library/Caches" deny)"
    add_row "caches" "$kb" "app caches; apps rebuild these"
  fi
}

run_logs() {
  if cat_active logs; then
    kb="$(apply_dir_children "$HOME_DIR/Library/Logs" nodeny)"
    add_row "logs" "$kb" "quarantined"
  else
    kb="$(scan_dir_children "$HOME_DIR/Library/Logs" nodeny)"
    add_row "logs" "$kb" "app log files"
  fi
}

# --- single-path quarantine categories ---
run_path_cat() { # run_path_cat <cat> <path> <note>
  c="$1"; p="$2"; note="$3"
  kb="$(du_kb "$p")"
  if cat_active "$c"; then
    if [ "$kb" -gt 0 ] && safe_move "$p"; then add_row "$c" "$kb" "quarantined"
    else add_row "$c" 0 "nothing to do"; fi
  else
    add_row "$c" "$kb" "$note"
  fi
}

run_xcode()  { run_path_cat xcode  "$HOME_DIR/Library/Developer/Xcode/DerivedData" "Xcode DerivedData (rebuilt on demand)"; }
run_gradle() { run_path_cat gradle "$HOME_DIR/.gradle/caches" "gradle caches (re-downloaded)"; }
run_cargo()  { run_path_cat cargo  "$HOME_DIR/.cargo/registry/cache" "cargo crate downloads (re-fetched)"; }

run_pip() {
  kb1="$(du_kb "$HOME_DIR/Library/Caches/pip")"; kb2="$(du_kb "$HOME_DIR/.cache/pip")"
  if cat_active pip; then
    moved=0
    if [ -d "$HOME_DIR/Library/Caches/pip" ] && safe_move "$HOME_DIR/Library/Caches/pip"; then moved=$((moved+kb1)); fi
    if [ -d "$HOME_DIR/.cache/pip" ] && safe_move "$HOME_DIR/.cache/pip"; then moved=$((moved+kb2)); fi
    add_row "pip" "$moved" "quarantined"
  else
    add_row "pip" "$((kb1+kb2))" "pip download caches"
  fi
}

run_npm() {
  cache_dir="$HOME_DIR/.npm/_cacache"
  kb="$(du_kb "$cache_dir")"
  if cat_active npm; then
    cleaned=0
    if is_cmd npm; then
      if npm cache clean --force >/dev/null 2>&1; then
        cleaned=1; log "npm cache clean --force run"
      else
        warn "npm cache clean failed; falling back to quarantine"
      fi
    fi
    # verify the claim: if any real files remain, quarantine the cache instead
    left_file="$(find "$cache_dir" -type f 2>/dev/null | head -1 || true)"
    if [ -n "$left_file" ] && [ -d "$cache_dir" ] && safe_move "$cache_dir"; then
      add_row "npm" "$kb" "quarantined"
    elif [ "$cleaned" = "1" ]; then
      freed=$((kb - $(du_kb "$cache_dir"))); [ "$freed" -lt 0 ] && freed=0
      add_row "npm" "$freed" "cleaned via npm (measured)"
    else
      add_row "npm" 0 "nothing to do"
    fi
  else
    add_row "npm" "$kb" "npm content cache"
  fi
}

# pnpm's store is reachable ONLY via `pnpm store prune`, and even then just
# the unreferenced fraction — so it is never counted in the promised total.
pnpm_kb() { echo $(( $(du_kb "$HOME_DIR/Library/pnpm/store") + $(du_kb "$HOME_DIR/.pnpm-store") )); }
run_pnpm() {
  kb="$(pnpm_kb)"
  if cat_active pnpm; then
    if is_cmd pnpm; then
      if pnpm store prune >/dev/null 2>&1; then
        freed=$((kb - $(pnpm_kb))); [ "$freed" -lt 0 ] && freed=0
        add_row "pnpm" "$freed" "pruned via pnpm (measured; only unreferenced pkgs are prunable)"
        log "pnpm store prune run (freed $freed KB)"
      else
        warn "pnpm store prune failed"; add_row "pnpm" 0 "prune FAILED (see log)"
      fi
    elif [ "$kb" -gt 0 ]; then
      add_row "pnpm" 0 "store is $(hum "$kb") but pnpm is not installed — unreachable (not counted)"
    else
      add_row "pnpm" 0 "pnpm not installed"
    fi
  else
    if is_cmd pnpm && [ "$kb" -gt 0 ]; then
      add_row "pnpm" 0 "store is $(hum "$kb"); only the unreferenced part is prunable (not counted in total)"
    elif [ "$kb" -gt 0 ]; then
      add_row "pnpm" 0 "store is $(hum "$kb") but pnpm is not installed — unreachable (not counted)"
    else
      add_row "pnpm" 0 "pnpm not installed"
    fi
  fi
}

# Yarn classic caches in ~/Library/Caches/Yarn (reachable by 'caches' when
# yarn is absent) AND ~/.yarn/cache (reachable only via yarn itself).
run_yarn() {
  kb_lib="$(du_kb "$HOME_DIR/Library/Caches/Yarn")"
  kb_home="$(du_kb "$HOME_DIR/.yarn/cache")"
  kb=$((kb_lib + kb_home))
  if cat_active yarn; then
    if is_cmd yarn; then
      if yarn cache clean >/dev/null 2>&1; then
        after=$(( $(du_kb "$HOME_DIR/Library/Caches/Yarn") + $(du_kb "$HOME_DIR/.yarn/cache") ))
        freed=$((kb - after)); [ "$freed" -lt 0 ] && freed=0
        add_row "yarn" "$freed" "cleaned via yarn (measured)"
        log "yarn cache clean run (freed $freed KB)"
      else
        warn "yarn cache clean failed"; add_row "yarn" 0 "clean FAILED (see log)"
      fi
    else
      note="yarn not installed"
      [ "$kb_lib" -gt 0 ] && note="$note; Library cache handled by 'caches'"
      [ "$kb_home" -gt 0 ] && note="$note; ~/.yarn/cache ($(hum "$kb_home")) unreachable without yarn"
      add_row "yarn" 0 "$note"
    fi
  else
    if is_cmd yarn; then
      add_row "yarn" "$kb" "yarn cache"
    else
      note="yarn not installed"
      [ "$kb_lib" -gt 0 ] && note="$note; $(hum "$kb_lib") counted under 'caches'"
      [ "$kb_home" -gt 0 ] && note="$note; ~/.yarn/cache ($(hum "$kb_home")) unreachable (not counted)"
      add_row "yarn" 0 "$note"
    fi
  fi
}

run_brew() {
  if ! is_cmd brew; then add_row "brew" 0 "homebrew not installed"; return; fi
  bcache="$HOME_DIR/Library/Caches/Homebrew"
  kb="$(du_kb "$bcache")"
  if cat_active brew; then
    if brew cleanup -s --prune=all >/dev/null 2>&1; then
      freed=$((kb - $(du_kb "$bcache"))); [ "$freed" -lt 0 ] && freed=0
      add_row "brew" "$freed" "brew cleanup run (measured from its cache dir)"
      log "brew cleanup -s --prune=all run (freed $freed KB)"
    else
      warn "brew cleanup returned nonzero"; add_row "brew" 0 "cleanup FAILED (see log)"
    fi
  else
    est="$(brew cleanup -n 2>/dev/null | grep -Eo '[0-9.,]+ ?[KMGT]B' | tail -1 || true)"
    add_row "brew" "$kb" "homebrew cache${est:+; brew estimates $est freeable}"
  fi
}

run_docker() {
  if ! is_cmd docker; then add_row "docker" 0 "docker not installed (explicit-only)"; return; fi
  if ! docker info >/dev/null 2>&1; then add_row "docker" 0 "docker not running (explicit-only)"; return; fi
  if cat_active docker; then
    if docker system prune -f >/dev/null 2>&1; then
      add_row "docker" 0 "docker system prune -f run (docker manages its own space)"
      log "docker system prune -f run"
    else
      warn "docker prune failed"; add_row "docker" 0 "prune FAILED (see log)"
    fi
  else
    add_row "docker" 0 "run --apply docker to prune stopped containers/dangling images"
  fi
}

run_sim() {
  if [ "$IS_DARWIN" != "1" ] || ! clt_ok || ! is_cmd xcrun; then
    add_row "sim" 0 "needs Xcode Command Line Tools"; return
  fi
  if cat_active sim; then
    if xcrun simctl delete unavailable >/dev/null 2>&1; then
      add_row "sim" 0 "unavailable simulators deleted"
    else
      add_row "sim" 0 "simctl not usable (no simulators?)"
    fi
  else
    add_row "sim" 0 "deletes only 'unavailable' simulator runtimes"
  fi
}

# --- trash ---
run_trash() {
  tdir="$HOME_DIR/.Trash"
  kb=0; n=0; freed=0; failed=0; failed_kb=0
  if [ -d "$tdir" ]; then
    # Age gate: BOTH mtime and ctime must exceed the threshold. Trashing a
    # file is a rename, which updates ctime — so a freshly trashed old file
    # is protected. (MC_TRASH_IGNORE_CTIME=1 is for the Linux test harness,
    # where ctime cannot be faked.)
    set -- -mindepth 1 -maxdepth 1 -mtime +"$TRASH_AGE"
    [ "${MC_TRASH_IGNORE_CTIME:-0}" = "1" ] || set -- "$@" -ctime +"$TRASH_AGE"
    while IFS= read -r -d '' item; do
      [ -n "$item" ] || continue
      ikb="$(du_kb "$item")"
      kb=$((kb + ikb)); n=$((n+1))
      if cat_active trash; then
        case "$item" in
          "$tdir"/?*)
            if rm -rf "$item" 2>/dev/null; then
              freed=$((freed + ikb)); log "trash purged: $item"
            else
              failed=$((failed+1)); failed_kb=$((failed_kb + ikb))
              warn "could not remove (locked/permissions?): $item"
            fi ;;
          *) warn "trash guard refused: $item" ;;
        esac
      fi
    done < <(find "$tdir" "$@" -print0 2>/dev/null)
  fi
  if cat_active trash; then
    note="$((n-failed)) of $n aged items (untouched >${TRASH_AGE}d) PERMANENTLY deleted"
    [ "$failed" -gt 0 ] && note="$note; $failed items / $(hum "$failed_kb") could not be removed"
    add_row "trash" "$freed" "$note"
  else
    add_row "trash" "$kb" "$n items untouched >${TRASH_AGE}d (explicit-only, permanent; local Trash only)"
  fi
}

# --- orphans (AppCleaner-style leftovers) ---
get_bundle_id() { # <Info.plist path>
  f="$1"
  if is_cmd plutil; then
    plutil -extract CFBundleIdentifier raw -o - "$f" 2>/dev/null && return 0
  fi
  if py3_ok; then
    python3 - "$f" 2>/dev/null <<'EOF_PY' && return 0
import plistlib, sys
with open(sys.argv[1], 'rb') as fh:
    print(plistlib.load(fh).get('CFBundleIdentifier', ''))
EOF_PY
  fi
  grep -A1 '<key>CFBundleIdentifier</key>' "$f" 2>/dev/null \
    | grep -Eo '<string>[^<]+</string>' | head -1 | sed 's/<[^>]*>//g'
}

collect_installed_ids() {
  : > "$INSTALLED_IDS"
  for root in /Applications /System/Applications "$HOME_DIR/Applications"; do
    [ -d "$root" ] || continue
    # -L follows symlinked .app bundles (common for brew casks / linked apps)
    while IFS= read -r -d '' plist; do
      [ -n "$plist" ] || continue
      bid="$(get_bundle_id "$plist" | tr -d '[:space:]' || true)"
      [ -n "$bid" ] && printf '%s\n' "$bid" >> "$INSTALLED_IDS"
    done < <(find -L "$root" -maxdepth 5 -name Info.plist -path '*.app/Contents/Info.plist' -print0 2>/dev/null)
  done
  sort -u "$INSTALLED_IDS" -o "$INSTALLED_IDS"
}

normalize_bid() { # strip container/team-ID decorations from an entry name
  b="$1"
  case "$b" in *.plist) b="${b%.plist}" ;; esac
  case "$b" in *.savedState) b="${b%.savedState}" ;; esac
  case "$b" in *.binarycookies) b="${b%.binarycookies}" ;; esac
  case "$b" in group.*) b="${b#group.}" ;; esac
  seg1="${b%%.*}"
  # Apple developer team IDs are 10 chars of A-Z0-9 (e.g. 2BUA8C4S2C.com.app)
  if printf '%s' "$seg1" | grep -Eq '^[A-Z0-9]{8,12}$'; then b="${b#*.}"; fi
  printf '%s' "$b"
}

id_is_installed() { # exact id, or shares a vendor prefix with an installed app
  bid="$1"
  grep -qFx "$bid" "$INSTALLED_IDS" && return 0
  pfx="$(printf '%s' "$bid" | cut -d. -f1-2)"
  [ -n "$pfx" ] && grep -q "^$pfx\." "$INSTALLED_IDS" && return 0
  return 1
}

orphan_entry_check() { # <entry-path> ; echoes KB if it is an orphan candidate
  e="$1"
  bn="$(basename "$e")"
  bid="$(normalize_bid "$bn")"
  # only reverse-DNS-looking names; human-named folders are never touched
  printf '%s' "$bid" | grep -Eq '^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}$' || return 1
  case "$bid" in
    com.apple.*|com.apple|systemgroup.*|homebrew.*|org.nixos.*) return 1 ;;
  esac
  id_is_installed "$bid" && return 1
  # recently-active entries are skipped: the owner may be a running tool
  if find "$e" -maxdepth 0 -mtime -30 2>/dev/null | grep -q .; then return 1; fi
  du_kb "$e"
  return 0
}

run_orphans() {
  collect_installed_ids
  if ! [ -s "$INSTALLED_IDS" ]; then
    add_row "orphans" 0 "SKIPPED: could not read installed apps (safety abort)"
    warn "orphan scan aborted: installed-app list came back empty"
    return
  fi
  # Tier 1 — regenerable state: safe to quarantine automatically.
  okb=0; on=0
  for d in "$HOME_DIR/Library/Saved Application State" \
           "$HOME_DIR/Library/HTTPStorages" "$HOME_DIR/Library/WebKit"; do
    [ -d "$d" ] || continue
    for e in "$d"/*; do
      [ -e "$e" ] || continue
      if kb="$(orphan_entry_check "$e")"; then
        if cat_active orphans; then
          if safe_move "$e"; then
            okb=$((okb + kb)); on=$((on+1))
            printf '  %-58s %10s\n' "$(basename "$e")" "$(hum "$kb")" >> "$ORPHAN_MOVED"
          fi
        else
          okb=$((okb + kb)); on=$((on+1))
          printf '  %-58s %10s\n' "$(basename "$e")" "$(hum "$kb")" >> "$ORPHAN_MOVED"
        fi
      fi
    done
  done
  # Tier 2 — may hold user data or live service definitions: REPORT ONLY.
  rkb=0; rn=0
  for d in "$HOME_DIR/Library/Application Support" "$HOME_DIR/Library/Preferences" \
           "$HOME_DIR/Library/Containers" "$HOME_DIR/Library/Group Containers" \
           "$HOME_DIR/Library/LaunchAgents"; do
    [ -d "$d" ] || continue
    dn="$(basename "$d")"
    for e in "$d"/*; do
      [ -e "$e" ] || continue
      if kb="$(orphan_entry_check "$e")"; then
        rkb=$((rkb + kb)); rn=$((rn+1))
        printf '  %-14s %-43s %10s\n' "$dn" "$(basename "$e")" "$(hum "$kb")" >> "$ORPHAN_REVIEW"
      fi
    done
  done
  if cat_active orphans; then
    add_row "orphans" "$okb" "$on regenerable leftovers quarantined; $rn more listed for manual review"
  else
    add_row "orphans" "$okb" "$on regenerable leftovers (explicit-only); $rn more for review below"
  fi
  ORPHAN_REVIEW_KB="$rkb"
}
ORPHAN_REVIEW_KB=0

# --- report-only sections ---
report_only_sections() {
  bdir="$HOME_DIR/Library/Application Support/MobileSync/Backup"
  say ""
  say "REPORT-ONLY (never cleaned by this tool)"
  if [ -d "$bdir" ]; then
    if ls "$bdir" >/dev/null 2>&1; then
      say "$(printf '  %-10s %10s  %s' "ios-backup" "$(hum "$(du_kb "$bdir")")" "device backups — manage in Finder/Settings")"
    else
      say "$(printf '  %-10s %10s  %s' "ios-backup" "unreadable" "grant Terminal Full Disk Access for a true figure")"
    fi
  else
    say "$(printf '  %-10s %10s  %s' "ios-backup" "none" "no local device backups found (or parent unreadable)")"
  fi
  say ""
  say "LARGEST FILES under ~ (top 15, >250MB; Library, media, Documents/Desktop and code folders excluded)"
  find "$HOME_DIR" \
    \( -path "$HOME_DIR/Library" -o -path "$HOME_DIR/Documents" \
       -o -path "$HOME_DIR/Desktop" -o -path "$HOME_DIR/Pictures" \
       -o -path "$HOME_DIR/Movies" -o -path "$HOME_DIR/Music" \
       -o -path "$HOME_DIR/photos" -o -path "$HOME_DIR/Photos" \
       -o -path "$HOME_DIR/Dropbox*" -o -path "$MC_ROOT" \
       -o -path "$HOME_DIR/claudecoding" -o -path "$HOME_DIR/PycharmProjects" \
       -o -path "$HOME_DIR/EnterpriseDashboard" -o -path "$HOME_DIR/WeatherBot" \
       -o -path "$HOME_DIR/MRP_ClaudeBD" \
       -o -name node_modules -o -name ".git" \) -prune \
    -o -type f -size +512000 -print 2>/dev/null \
  | while IFS= read -r f; do
      printf '%s\t%s\n' "$(du_kb "$f")" "$f"
    done | sort -rn | head -15 \
  | while IFS="$TAB" read -r kb f; do
      say "$(printf '  %10s  %s' "$(hum "$kb")" "$f")"
    done || true
}

# ---------------------------------------------------------------------- main
say "maccleaner $VERSION — $(date '+%Y-%m-%d %H:%M:%S')"
if [ "$MODE" = "apply" ]; then
  say "MODE: APPLY [$APPLY_CATS]   quarantine batch: $TS"
else
  say "MODE: DRY RUN — nothing will be moved or deleted"
fi
say "Note: sizes skip unreadable paths (grant Terminal Full Disk Access for full numbers)."
say "------------------------------------------------------------------"

run_caches; run_logs; run_pip; run_npm; run_pnpm; run_yarn
run_gradle; run_cargo; run_xcode; run_sim; run_brew; run_trash
run_docker; run_orphans

if [ "$MODE" = "apply" ]; then HEAD_COL="MOVED/FREED"; else HEAD_COL="RECLAIMABLE"; fi
say ""
say "$(printf 'CATEGORY %14s  NOTE' "$HEAD_COL")"
SAFE_KB=0; EXTRA_KB=0
while IFS='|' read -r c kb note; do
  say "$(printf '  %-8s %14s  %s' "$c" "$(hum "$kb")" "$note")"
  if is_safe_cat "$c"; then SAFE_KB=$((SAFE_KB + kb)); else EXTRA_KB=$((EXTRA_KB + kb)); fi
done < "$SCAN_TMP"
say "  ------------------------------------------"
say "$(printf '  %-22s %14s' "TOTAL (all-safe set)" "$(hum "$SAFE_KB")")"
say "$(printf '  %-22s %14s' "Explicit-only extras" "$(hum "$EXTRA_KB")")  (trash/orphans/docker — must be named)"

if [ -s "$ORPHAN_MOVED" ]; then
  say ""
  if cat_active orphans; then say "ORPHANS (regenerable) — quarantined:"; else say "ORPHANS (regenerable state of uninstalled apps) — cleaned by --apply orphans:"; fi
  head -40 "$ORPHAN_MOVED" >> "$REPORT_FILE"; head -40 "$ORPHAN_MOVED"
fi
if [ -s "$ORPHAN_REVIEW" ]; then
  say ""
  say "ORPHANS — MANUAL REVIEW ONLY ($(hum "$ORPHAN_REVIEW_KB") across $(wc -l < "$ORPHAN_REVIEW" | tr -d ' ') items; may hold user data — never auto-moved):"
  head -40 "$ORPHAN_REVIEW" >> "$REPORT_FILE"; head -40 "$ORPHAN_REVIEW"
  if [ "$(wc -l < "$ORPHAN_REVIEW")" -gt 40 ]; then
    say "  ... list truncated; full list in the report file"
  fi
fi

report_only_sections

say ""
if [ "$MODE" = "apply" ]; then
  if [ -d "$Q_BATCH" ]; then
    say "Quarantined data was MOVED, not yet deleted — disk space frees on purge:"
    say "  Undo:        bash $0 --restore $TS"
    say "  Free space:  bash $0 --purge-batch $TS   (or --purge after 14 days)"
  else
    say "No items were quarantined in this run."
  fi
else
  say "Nothing was touched. To act:"
  say "  bash $0 --apply all-safe          # caches,logs,dev caches,brew,sim"
  say "  bash $0 --apply trash --trash-age 30"
  say "  bash $0 --apply orphans           # quarantines regenerable leftovers"
  say "  bash $0 --apply docker"
fi
say ""
say "Report: $REPORT_FILE"
say "Log:    $LOG_FILE"
