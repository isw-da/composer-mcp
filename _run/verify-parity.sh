#!/usr/bin/env bash
# Parity gate. For each absorbed capability: the target file must carry the marker
# that defines it, and the source in Peter's bundle that justified it must exist.
#
# The marker check is deliberately content-level, not file-level: a file that exists
# but had its section deleted must go red, otherwise `touch` satisfies the gate.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
FAILS=0; CHECKS=0
fail(){ echo "  FAIL: $1"; FAILS=$((FAILS+1)); }

while IFS=$'\t' read -r cap target marker source; do
  case "$cap" in ''|'#'*) continue;; esac
  CHECKS=$((CHECKS+1))
  if [ ! -f "$ROOT/$target" ]; then
    fail "$cap: $target does not exist"; continue
  fi
  if ! grep -qi -- "$marker" "$ROOT/$target"; then
    fail "$cap: $target exists but has no '$marker'"
  fi
  CHECKS=$((CHECKS+1))
  [ -f "$source" ] || fail "$cap: source citation does not resolve: $source"
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
if [ "$FAILS" -gt 0 ]; then echo "PARITY FAILED: $FAILS of $CHECKS checks"; exit 1; fi
echo "PARITY OK: $CHECKS checks, every capability absorbed and every citation resolves"; exit 0
