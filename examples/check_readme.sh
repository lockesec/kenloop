#!/bin/sh
# Checks the README's quick-start block against a captured run of examples/demo.sh:
#
#   sh examples/demo.sh > demo.out && sh examples/check_readme.sh demo.out
#
# Every line of the first ```console block must appear, verbatim, as a whole
# line of the demo output (colour codes stripped). CI runs this, so the README
# transcript cannot drift from the tool. Exits 1 and names the first line that
# is missing; exits 2 if it could not look (no output file, no block found).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-}
[ -r "$OUT" ] || { echo "check_readme: NOT EVALUABLE: cannot read demo output '$OUT'" >&2; exit 2; }
CLEAN=$(mktemp); BLOCK=$(mktemp)
trap 'rm -f "$CLEAN" "$BLOCK"' EXIT
sed 's/\x1b\[[0-9;]*m//g' "$OUT" > "$CLEAN"
awk '/^```console/{f=1;next} /^```/{if(f)exit} f' "$HERE/../README.md" > "$BLOCK"
[ -s "$BLOCK" ] || { echo "check_readme: NOT EVALUABLE: no console block in README.md" >&2; exit 2; }
n=0
while IFS= read -r line; do
    n=$((n + 1))
    grep -Fxq -- "$line" "$CLEAN" || { echo "check_readme: README line not in demo output: $line" >&2; exit 1; }
done < "$BLOCK"
echo "check_readme: $n README line(s) match the demo output"
