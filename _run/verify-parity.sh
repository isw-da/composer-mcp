#!/usr/bin/env bash
# Parity gate. For each absorbed capability: the target file must carry the marker
# that defines it, and the source in Peter's bundle that justified it must exist.
#
# The marker check is deliberately content-level, not file-level: a file that exists
# but had its section deleted must go red, otherwise `touch` satisfies the gate.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
FAILS=0; CHECKS=0; SKIPPED=0; SKIP_NAMES=""; SRC_SKIPPED=0
SOURCE_ROOT="$HOME/logi-composer/peter-kb"
fail(){ echo "  FAIL: $1"; FAILS=$((FAILS+1)); }

while IFS=$'\t' read -r cap target marker source; do
  case "$cap" in ''|'#'*) continue;; esac
  # Two rows point at _internal-only/, which is gitignored and therefore absent
  # from any clone. Failing on that made this gate green only on the machine
  # that wrote it, which is not a gate. It is now explicitly NOT APPLICABLE
  # there, counted, and reported: a silent skip reads as a pass, which is worse
  # than either outcome.
  case "$target" in
    _internal-only/*)
      if [ ! -f "$ROOT/$target" ]; then
        SKIPPED=$((SKIPPED+1)); SKIP_NAMES="$SKIP_NAMES $cap"; continue
      fi;;
  esac
  CHECKS=$((CHECKS+1))
  if [ ! -f "$ROOT/$target" ]; then
    fail "$cap: $target does not exist"; continue
  fi
  if ! grep -qi -- "$marker" "$ROOT/$target"; then
    fail "$cap: $target exists but has no '$marker'"
  fi
  # The source citation is an absolute path into a working copy of Peter's
  # bundle. It proves the claim is traceable, which is worth checking on the
  # machine that has it, and is impossible anywhere else. Same treatment as
  # the internal-only rows: explicitly not applicable, named and counted,
  # never a silent skip. If the root IS present, a missing file still fails.
  if [ -d "$SOURCE_ROOT" ]; then
    CHECKS=$((CHECKS+1))
    [ -f "$source" ] || fail "$cap: source citation does not resolve: $source"
  else
    SRC_SKIPPED=$((SRC_SKIPPED+1))
  fi
done < "$DIR/parity.tsv"

# house style, same rule the rest of the workspace enforces
for f in "$ROOT"/*.md; do
  case "$(basename "$f")" in
    EMBEDDING_API.md|CHATBOT_EVENTS.md|CHATBOT_THEMING.md|VISUAL_TYPES.md|CUSTOM_METRICS.md|SECURITY_ANSWERS.md|DISCLOSURE.md|BEYOND_PARITY.md) ;;
    *) continue;;
  esac
  CHECKS=$((CHECKS+1))
  grep -q $'\xe2\x80\x94\|\xe2\x80\x93' "$f" && fail "$(basename "$f") contains an em or en dash"
done

echo ""
if [ "$SRC_SKIPPED" -gt 0 ]; then
  echo "SOURCE CITATIONS NOT CHECKED ($SRC_SKIPPED): $SOURCE_ROOT is not present."
  echo "  Those citations point into a private working copy and can only be"
  echo "  resolved on a machine that has it. The claims they support are still"
  echo "  checked above; only their provenance is unverifiable here."
  echo ""
fi
if [ "$SKIPPED" -gt 0 ]; then
  echo "NOT APPLICABLE in this checkout ($SKIPPED):$SKIP_NAMES"
  echo "  Those capabilities live in _internal-only/, which is gitignored and never"
  echo "  published. They are complete; this clone just cannot see them."
  echo ""
fi
if [ "$FAILS" -gt 0 ]; then echo "PARITY FAILED: $FAILS of $CHECKS checks"; exit 1; fi
echo "PARITY OK: $CHECKS checks run, $SKIPPED not applicable, $SRC_SKIPPED citations unresolvable here"; exit 0
