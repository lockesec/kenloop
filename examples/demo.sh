#!/bin/sh
# The whole loop, once, offline, on invented data (see demo/SYNTHETIC-DATA).
# Runs in a temporary copy; reads nothing outside it; needs no network.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(mktemp -d)
trap 'rm -r "$WORK"' EXIT
cp -R "$HERE/demo/." "$WORK/"
export CAREERLOOP_HOME="$WORK" CAREERLOOP_TODAY=2030-03-20
say() { printf '\n\033[1m$ careerloop %s\033[0m\n' "$*"; }
cl() { say "$@"; careerloop "$@"; }
clx() { say "$@"; careerloop "$@" || echo "(exit $?)"; }   # a non-zero exit is part of the story

cl jobs discover --board fixture --company example-folio --intake --exclude-senior
cl jobs score example-folio-web-developer --fit 4.5
cl jobs score example-folio-api-engineer --fit 3.5
cl jobs score example-folio-integration-engineer --fit 4.2
cl jobs status example-folio-support-engineer closed --reason filled
for r in "$WORK"/roles/*/; do cl jobs check "$(basename "$r")"; done
cl jobs upskill
cl learn gaps
cl learn plan web-security --from-gap "Web security"
say learn quiz http-fundamentals --interactive --n 4 "  (answers scripted)"
printf 'c\nh\n2\n?\n?\nAccept\nm\no\nthe same headers repeat\nm\no\nHttpOnly\nh\no\n' \
  | careerloop learn quiz http-fundamentals --interactive --n 4
cl learn graduate http-fundamentals
clx jobs check-claims resumes/draft-example-folio.md
cl next
cl jobs status example-folio-integration-engineer applied
cl next
say "learn graduate http-fundamentals --emit >> facts.md" "  (you paste it under ## Held; nothing writes facts.md for you)"
careerloop learn graduate http-fundamentals --emit | tee -a "$WORK/facts.md"
cl next --all
cp "$WORK/fixtures/example-folio-later.json" "$WORK/fixtures/example-folio.json"
cl jobs reconcile
cl jobs board
careerloop jobs upskill > /dev/null   # demand is derived from the roles and coverage: re-derive it so doctor sees it fresh
clx doctor
say "jobs check <every role>" "  (the pasted facts changed what you hold, so coverage is re-measured)"
for r in "$WORK"/roles/*/; do careerloop jobs check "$(basename "$r")" > /dev/null; done
careerloop jobs upskill > /dev/null   # coverage was just re-measured
cl doctor
