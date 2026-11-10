#!/bin/sh
# The whole loop, once, offline, on invented data (see demo/SYNTHETIC-DATA).
# Runs in a temporary copy; reads nothing outside it; needs no network.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(mktemp -d)
trap 'rm -r "$WORK"' EXIT
cp -R "$HERE/demo/." "$WORK/"
export KENLOOP_HOME="$WORK" KENLOOP_TODAY=2030-03-20
say() {   # print the command as typed: quote an argument with a space; an argument starting "  " is a note
  out=""
  for a in "$@"; do
    case "$a" in "  "*) out="$out$a" ;; *" "*|*"?"*) out="$out \"$a\"" ;; *) out="$out $a" ;; esac
  done
  printf '\n\033[1m$ ken%s\033[0m\n' "$out"
}
cl() { say "$@"; ken "$@"; }
clx() { say "$@"; ken "$@" || echo "(exit $?)"; }   # a non-zero exit is part of the story

# Study first: a topic studied for its own sake, a graded dialogue, a question.
cl board
say quiz http-fundamentals --interactive --n 4 "  (answers scripted)"
printf 'c\nh\n2\n?\n?\nAccept\nm\no\nthe same headers repeat\nm\no\nHttpOnly\nh\no\n' \
  | ken quiz http-fundamentals --interactive --n 4
cl talk http-fundamentals semantics:cookies
cl record http-fundamentals semantics:cookies partial --mode dialogue --rubric chain=2,predict=1,limits=1 \
  --grader demo-tutor --before "a cookie is sent to every site" --confidence high \
  --after "a cookie goes back only to the site that set it" --after-confidence med \
  --held "the server sets it with a response header" --broke "so every later request carries it" \
  --next "the Domain and SameSite attributes" --open "how does SameSite stop a cross-site request?"
cl beliefs http-fundamentals
cl ask "why does a browser send cookies back to the server?"
cl rung q1 http-fundamentals --existing semantics:cookies
cl next
# The job-search sidecar: roles, coverage, demand, the claim check.
cl jobs discover --board fixture --company example-folio --intake --exclude-senior
cl jobs score example-folio-web-developer --fit 4.5
cl jobs score example-folio-api-engineer --fit 3.5
cl jobs score example-folio-integration-engineer --fit 4.2
cl jobs status example-folio-support-engineer closed --reason filled
for r in "$WORK"/roles/*/; do cl jobs check "$(basename "$r")"; done
cl jobs upskill
cl jobs gaps
cl plan web-security --from-gap "Web security"
cl jobs graduate http-fundamentals
clx jobs check-claims resumes/draft-example-folio.md
cl next
cl jobs status example-folio-integration-engineer applied
cl next
say jobs graduate http-fundamentals --emit ">>" facts.md "  (you paste it under ## Held; nothing writes facts.md for you)"
ken jobs graduate http-fundamentals --emit | tee -a "$WORK/facts.md"
cl next --all
cp "$WORK/fixtures/example-folio-later.json" "$WORK/fixtures/example-folio.json"
cl jobs reconcile
cl jobs board
ken jobs upskill > /dev/null   # demand is derived from the roles and coverage: re-derive it so doctor sees it fresh
clx doctor
say jobs check "<role>" "  (for every role: the pasted facts changed what you hold, so coverage is re-measured)"
for r in "$WORK"/roles/*/; do ken jobs check "$(basename "$r")" > /dev/null; done
ken jobs upskill > /dev/null   # coverage was just re-measured
cl doctor
